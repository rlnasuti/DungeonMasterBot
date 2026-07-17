"""Flask routes for short-lived OpenAI Realtime browser credentials.

Register ``realtime_bp`` on the application to expose
``POST /api/realtime/client-secret``.  The long-lived server API key never
leaves this module; callers receive only the short-lived client secret that is
intended for a browser WebRTC connection.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, jsonify, make_response

from bot.game.models import CURRENCY_AWARD_MAXIMUM, CURRENCY_DENOMINATIONS


REALTIME_PROVIDER_ID = "openai-realtime"
DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_REALTIME_VOICE = "marin"
DEFAULT_CLIENT_SECRET_TTL_SECONDS = 600
OPENAI_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"

_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2}$")
_SAFETY_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SUPPORTED_VOICES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "sage",
        "shimmer",
        "verse",
        "marin",
        "cedar",
    }
)
_SUPPORTED_TRANSCRIPTION_MODELS = frozenset(
    {
        "whisper-1",
        "gpt-4o-mini-transcribe",
        "gpt-4o-mini-transcribe-2025-12-15",
        "gpt-4o-transcribe",
        "gpt-4o-transcribe-diarize",
        "gpt-realtime-whisper",
    }
)
_SUPPORTED_REASONING_EFFORTS = frozenset(
    {"minimal", "low", "medium", "high", "xhigh"}
)
_SUPPORTED_NOISE_REDUCTION = frozenset({"near_field", "far_field", "off"})

DEFAULT_REALTIME_INSTRUCTIONS = (
    "You are the spoken interface for a collaborative tabletop role-playing "
    "game. Speak naturally and concisely, preserve player agency, and ask the "
    "players to roll before resolving actions that require physical dice."
)

# These schemas deliberately contain only player-visible intent. The trusted
# application executor supplies state versions, idempotency keys, roll DCs,
# and engine-calculated modifiers before it reaches authoritative game state.
GAMEPLAY_FUNCTION_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "name": "read_public_game_state",
        "description": (
            "Read the current player-visible game and character state. Use this "
            "instead of guessing hit points, resources, pending rolls, or public facts."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "request_physical_roll",
        "description": (
            "Commit one physical d20 check before asking the player to roll. "
            "Choose a standard difficulty tier and whether its DC is public or "
            "private. An authored campaign check may override both. The application "
            "determines the exact authoritative DC and modifier. If the returned "
            "dc_visibility is public, announce its target_total; if private, never "
            "state or imply the DC."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {
                    "type": "string",
                    "description": "The player who should make the roll.",
                    "minLength": 1,
                    "maxLength": 128,
                },
                "roll_kind": {
                    "type": "string",
                    "enum": [
                        "ability",
                        "saving_throw",
                        "skill",
                        "initiative",
                        "death_save",
                    ],
                },
                "check_key": {
                    "type": "string",
                    "description": (
                        "Ability or skill key when the roll kind needs one, such "
                        "as wisdom, perception, or stealth."
                    ),
                    "minLength": 1,
                    "maxLength": 128,
                },
                "difficulty": {
                    "type": "string",
                    "enum": [
                        "very_easy",
                        "easy",
                        "medium",
                        "hard",
                        "very_hard",
                        "nearly_impossible",
                    ],
                    "description": (
                        "Standard SRD difficulty tier for an improvised check. "
                        "Always provide it; an authored campaign check overrides it."
                    ),
                },
                "dc_visibility": {
                    "type": "string",
                    "enum": ["public", "private"],
                    "description": (
                        "Use public when the character can know the target before "
                        "rolling. Use private when knowing whether the check succeeded "
                        "is itself uncertain, such as searching for a hidden trap, "
                        "reading a lie, or sneaking past an unseen observer."
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": (
                        "A brief player-facing explanation of what to roll. Never put "
                        "a DC, target number, threshold, or required die result in this "
                        "text; only the tool result may expose an authorized target_total."
                    ),
                    "minLength": 1,
                    "maxLength": 500,
                },
            },
            "required": [
                "player_id",
                "roll_kind",
                "difficulty",
                "dc_visibility",
                "prompt",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "apply_damage",
        "description": "Apply resolved damage to a player character.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "amount": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "required": ["player_id", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "apply_healing",
        "description": "Apply resolved healing to a player character.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "amount": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "required": ["player_id", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "award_character_currency",
        "description": (
            "Commit a public monetary award to one confirmed player character. "
            "Call this before saying that money changed hands, and narrate only "
            "the amount and balance returned by the authoritative ledger."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "amount": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": CURRENCY_AWARD_MAXIMUM,
                },
                "denomination": {
                    "type": "string",
                    "enum": list(CURRENCY_DENOMINATIONS),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "A concise player-visible reason grounded in the "
                        "interaction or discovery that earned the award."
                    ),
                    "minLength": 1,
                    "maxLength": 500,
                },
            },
            "required": ["player_id", "amount", "denomination", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "use_character_resource",
        "description": (
            "Spend a spell slot, class resource, or hit die. For a level 1+ "
            "spell, call this with the slot level before narrating the spell as cast."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "resource_type": {
                    "type": "string",
                    "enum": ["spell_slot", "class_resource", "hit_die"],
                },
                "resource_key": {"type": "string", "minLength": 1, "maxLength": 128},
                "amount": {"type": "integer", "minimum": 1, "maximum": 99},
            },
            "required": ["player_id", "resource_type", "resource_key", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "restore_character_resource",
        "description": "Restore a spell slot, class resource, or hit die.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "resource_type": {
                    "type": "string",
                    "enum": ["spell_slot", "class_resource", "hit_die"],
                },
                "resource_key": {"type": "string", "minLength": 1, "maxLength": 128},
                "amount": {"type": "integer", "minimum": 1, "maximum": 99},
            },
            "required": ["player_id", "resource_type", "resource_key", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_performer_context",
        "description": (
            "Read trusted behind-the-screen context for portraying the current "
            "scene and its NPCs. Treat non-public details as secret and never "
            "quote or reveal them to players."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "advance_campaign_scene",
        "description": (
            "Commit an explicit player decision to leave the current scene. Call this "
            "before narrating arrival, describing the destination, or requesting a "
            "destination-specific check. The trusted campaign director chooses the "
            "next eligible scene."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": (
                        "A concise reason grounded only in events the players have "
                        "already experienced."
                    ),
                    "minLength": 1,
                    "maxLength": 500,
                },
            },
            "required": ["reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "record_npc_reaction",
        "description": (
            "Record how a currently encountered NPC reacts to a player-visible "
            "interaction. The trusted campaign director applies the authoritative change."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "npc_id": {
                    "type": "string",
                    "description": "The identifier of the NPC currently reacting.",
                    "minLength": 1,
                    "maxLength": 128,
                },
                "reaction": {
                    "type": "string",
                    "enum": [
                        "trusts_more",
                        "trusts_less",
                        "more_suspicious",
                        "less_suspicious",
                        "more_fearful",
                        "less_fearful",
                        "more_respectful",
                        "less_respectful",
                    ],
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "A concise reason grounded only in the interaction the "
                        "players just witnessed."
                    ),
                    "minLength": 1,
                    "maxLength": 500,
                },
            },
            "required": ["npc_id", "reaction", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "record_scene_discovery",
        "description": (
            "Record a generic discovery the players visibly completed in the "
            "current scene. The trusted campaign director resolves any progression."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "discovery": {
                    "type": "string",
                    "enum": [
                        "careful_observation",
                        "thorough_search",
                        "npc_trust_earned",
                        "evidence_pair_completed",
                        "echo_questioned",
                    ],
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "A concise reason grounded only in what the players have "
                        "already discovered."
                    ),
                    "minLength": 1,
                    "maxLength": 500,
                },
            },
            "required": ["discovery", "reason"],
            "additionalProperties": False,
        },
    },
)

realtime_bp = Blueprint(
    "realtime",
    __name__,
    url_prefix="/api/realtime",
)


class RealtimeConfigurationError(ValueError):
    """Raised for invalid or missing trusted server configuration."""


class RealtimeUpstreamError(RuntimeError):
    """A deliberately sanitized representation of an upstream failure."""

    def __init__(self, status: int | None = None, reason: str = "upstream_error"):
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class RealtimeSettings:
    api_key: str
    model: str
    voice: str
    transcription_model: str
    language: str | None
    reasoning_effort: str
    noise_reduction: str
    instructions: str
    ttl_seconds: int
    safety_identifier: str | None


def _configured_value(name: str, default: Any = None) -> Any:
    """Read a non-secret setting from Flask config, then the environment."""

    configured = current_app.config.get(name)
    if configured is not None:
        return configured
    return os.getenv(name, default)


def _validated_choice(name: str, value: Any, choices: frozenset[str]) -> str:
    normalized = str(value).strip()
    if normalized not in choices:
        raise RealtimeConfigurationError(f"Invalid {name} configuration")
    return normalized


def _load_settings() -> RealtimeSettings:
    # OPENAI_API_KEY intentionally comes only from the trusted process
    # environment.  It must never be accepted from a browser request.
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or len(api_key) > 4096 or any(char.isspace() for char in api_key):
        raise RealtimeConfigurationError("OPENAI_API_KEY is not configured")

    model = str(
        _configured_value("OPENAI_REALTIME_MODEL", DEFAULT_REALTIME_MODEL)
    ).strip()
    if not _MODEL_PATTERN.fullmatch(model):
        raise RealtimeConfigurationError("Invalid realtime model configuration")

    voice = _validated_choice(
        "realtime voice",
        _configured_value("OPENAI_REALTIME_VOICE", DEFAULT_REALTIME_VOICE),
        _SUPPORTED_VOICES,
    )
    transcription_model = _validated_choice(
        "transcription model",
        _configured_value(
            "OPENAI_REALTIME_TRANSCRIPTION_MODEL",
            DEFAULT_TRANSCRIPTION_MODEL,
        ),
        _SUPPORTED_TRANSCRIPTION_MODELS,
    )
    reasoning_effort = _validated_choice(
        "realtime reasoning effort",
        _configured_value("OPENAI_REALTIME_REASONING_EFFORT", "low"),
        _SUPPORTED_REASONING_EFFORTS,
    )
    noise_reduction = _validated_choice(
        "noise reduction",
        _configured_value("OPENAI_REALTIME_NOISE_REDUCTION", "far_field"),
        _SUPPORTED_NOISE_REDUCTION,
    )

    language_value = str(
        _configured_value("OPENAI_REALTIME_LANGUAGE", "en")
    ).strip()
    language = language_value or None
    if language and not _LANGUAGE_PATTERN.fullmatch(language):
        raise RealtimeConfigurationError("Invalid realtime language configuration")

    instructions = str(
        _configured_value(
            "OPENAI_REALTIME_INSTRUCTIONS",
            DEFAULT_REALTIME_INSTRUCTIONS,
        )
    ).strip()
    if not instructions or len(instructions) > 32_000:
        raise RealtimeConfigurationError("Invalid realtime instructions configuration")

    try:
        ttl_seconds = int(
            _configured_value(
                "OPENAI_REALTIME_TOKEN_TTL_SECONDS",
                DEFAULT_CLIENT_SECRET_TTL_SECONDS,
            )
        )
    except (TypeError, ValueError) as error:
        raise RealtimeConfigurationError("Invalid client secret TTL") from error
    if not 10 <= ttl_seconds <= 7200:
        raise RealtimeConfigurationError("Client secret TTL is outside the supported range")

    safety_value = str(
        _configured_value("OPENAI_SAFETY_IDENTIFIER", "")
    ).strip()
    safety_identifier = safety_value or None
    if safety_identifier and not _SAFETY_IDENTIFIER_PATTERN.fullmatch(
        safety_identifier
    ):
        raise RealtimeConfigurationError("Invalid safety identifier configuration")

    return RealtimeSettings(
        api_key=api_key,
        model=model,
        voice=voice,
        transcription_model=transcription_model,
        language=language,
        reasoning_effort=reasoning_effort,
        noise_reduction=noise_reduction,
        instructions=instructions,
        ttl_seconds=ttl_seconds,
        safety_identifier=safety_identifier,
    )


def _session_payload(settings: RealtimeSettings) -> dict[str, Any]:
    transcription: dict[str, str] = {"model": settings.transcription_model}
    if settings.language:
        transcription["language"] = settings.language

    audio_input: dict[str, Any] = {
        "transcription": transcription,
        "turn_detection": {
            "type": "semantic_vad",
            "eagerness": "auto",
            # The browser attaches the selected player identity immediately
            # after the committed audio item, then explicitly creates the
            # response. Automatic inference can otherwise race that tag.
            "create_response": False,
            "interrupt_response": True,
        },
    }
    if settings.noise_reduction != "off":
        audio_input["noise_reduction"] = {"type": settings.noise_reduction}

    session: dict[str, Any] = {
        "type": "realtime",
        "model": settings.model,
        "output_modalities": ["audio"],
        "instructions": settings.instructions,
        "tools": list(GAMEPLAY_FUNCTION_TOOLS),
        "tool_choice": "auto",
        "audio": {
            "input": audio_input,
            "output": {
                "voice": settings.voice,
            },
        },
    }
    if settings.model.startswith("gpt-realtime-2"):
        session["reasoning"] = {"effort": settings.reasoning_effort}

    return {
        "expires_after": {
            "anchor": "created_at",
            "seconds": settings.ttl_seconds,
        },
        "session": session,
    }


def _request_client_secret(settings: RealtimeSettings) -> tuple[str, int | None]:
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "DungeonMasterBot/realtime-credential-broker",
    }
    if settings.safety_identifier:
        headers["OpenAI-Safety-Identifier"] = settings.safety_identifier

    request = Request(
        OPENAI_CLIENT_SECRETS_URL,
        data=json.dumps(_session_payload(settings)).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw_response = response.read(1_000_000)
    except HTTPError as error:
        # Consume a small bounded amount so the connection can be reused, but
        # never relay or log the upstream body because it may contain details
        # that are inappropriate for the browser.
        try:
            error.read(16_384)
        except Exception:
            pass
        raise RealtimeUpstreamError(error.code, "upstream_http_error") from None
    except (URLError, TimeoutError, OSError):
        raise RealtimeUpstreamError(None, "upstream_unreachable") from None

    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RealtimeUpstreamError(None, "invalid_upstream_response") from None

    if not isinstance(payload, dict):
        raise RealtimeUpstreamError(None, "invalid_upstream_response")

    secret = payload.get("value")
    if not isinstance(secret, str) or not secret or len(secret) > 4096:
        raise RealtimeUpstreamError(None, "invalid_upstream_response")

    expires_at = payload.get("expires_at")
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
        expires_at = None
    elif expires_at < 0:
        expires_at = None
    else:
        expires_at = int(expires_at)

    return secret, expires_at


def _json_response(payload: dict[str, Any], status: int = 200):
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _error_response(code: str, message: str, status: int):
    return _json_response(
        {
            "error": {
                "code": code,
                "message": message,
            }
        },
        status,
    )


@realtime_bp.post("/client-secret")
def create_realtime_client_secret():
    """Mint and return a browser-safe, short-lived Realtime credential."""

    try:
        settings = _load_settings()
        client_secret, expires_at = _request_client_secret(settings)
    except RealtimeConfigurationError:
        current_app.logger.warning("Realtime client-secret configuration is invalid")
        return _error_response(
            "realtime_not_configured",
            "Voice service is not configured.",
            503,
        )
    except RealtimeUpstreamError as error:
        current_app.logger.warning(
            "Realtime client-secret request failed (upstream_status=%s, reason=%s)",
            error.status,
            error.reason,
        )
        if error.status == 429:
            return _error_response(
                "realtime_rate_limited",
                "Voice service is temporarily busy. Please try again shortly.",
                503,
            )
        return _error_response(
            "realtime_unavailable",
            "Voice service is temporarily unavailable.",
            502,
        )
    except Exception:
        # Keep the browser response generic and avoid interpolating exception
        # text, which can occasionally contain request metadata.
        current_app.logger.exception("Unexpected Realtime client-secret failure")
        return _error_response(
            "realtime_unavailable",
            "Voice service is temporarily unavailable.",
            500,
        )

    return _json_response(
        {
            "provider": REALTIME_PROVIDER_ID,
            "model": settings.model,
            "client_secret": client_secret,
            "expires_at": expires_at,
        }
    )


__all__ = [
    "DEFAULT_REALTIME_MODEL",
    "GAMEPLAY_FUNCTION_TOOLS",
    "REALTIME_PROVIDER_ID",
    "create_realtime_client_secret",
    "realtime_bp",
]
