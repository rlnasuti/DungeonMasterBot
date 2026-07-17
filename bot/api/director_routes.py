"""Campaign-runtime bridge between immutable Director data and persisted game state.

Every response is rebuilt from an allowlisted performer projection. Canonical
checks, future scenes, motives, unrevealed facts, and numeric relationships stay
inside the server process and SQLite private state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from bot.api.game_routes import _store as get_game_store
from bot.director import CampaignDirector, DirectorError, ProjectionContext
from bot.game.errors import (
    ConflictError,
    GameStateError,
    StaleVersionError,
    ValidationError,
)
from bot.game.models import normalize_key, require_int, require_text
from bot.game.store import GameStore


director_blueprint = Blueprint("director_api", __name__, url_prefix="/api")

REACTIONS: dict[str, tuple[str, int]] = {
    "trusts_more": ("trust", 1),
    "trusts_less": ("trust", -1),
    "more_suspicious": ("suspicion", 1),
    "less_suspicious": ("suspicion", -1),
    "more_fearful": ("fear", 1),
    "less_fearful": ("fear", -1),
    "more_respectful": ("respect", 1),
    "less_respectful": ("respect", -1),
}
RELATIONSHIP_MIN = -3
RELATIONSHIP_MAX = 3

DIFFICULTY_CLASS_BY_TIER: dict[str, int] = {
    "very_easy": 5,
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "very_hard": 25,
    "nearly_impossible": 30,
}
BINARY_CHECK_KINDS = frozenset({"ability", "skill", "saving_throw", "death_save"})

# These canonical IDs are deliberately server-only. HTTP accepts only the
# generic keys on the left and never returns a mapped identifier.
DISCOVERY_MAP: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {
    "careful_observation": {
        "rainy-square": {"events": ("find-finn-tracks",)},
        "ruined-chapel": {"events": ("inspect-chapel-mural",)},
        "bell-vault": {"events": ("reach-bell-vault",)},
    },
    "thorough_search": {
        "rainy-square": {"events": ("find-finn-tracks",)},
        "ruined-chapel": {"events": ("inspect-chapel-mural",)},
        "bell-vault": {"events": ("reach-bell-vault",)},
    },
    "npc_trust_earned": {
        "rainy-square": {"events": ("earn-mara-trust",)},
        "bell-vault": {"events": ("earn-mara-trust",)},
    },
    "evidence_pair_completed": {
        "ruined-chapel": {
            "clues": ("grain-sack-thread", "magistrate-seal-wax"),
        },
    },
    "echo_questioned": {
        "ruined-chapel": {"events": ("ask-the-echo",)},
    },
}


def _director() -> CampaignDirector:
    director = current_app.extensions.get("campaign_director")
    if not isinstance(director, CampaignDirector):
        raise ConflictError("Campaign Director is not initialized for this application.")
    return director


def _body(*, allowed: set[str], required: set[str]) -> dict[str, Any]:
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValidationError("Request body must be a JSON object.")
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"Request has unknown fields: {sorted(unknown)}")
    missing = required - set(value)
    if missing:
        raise ValidationError(f"Request is missing required fields: {sorted(missing)}")
    return dict(value)


def _mutation_fields(body: Mapping[str, Any]) -> tuple[int, str]:
    expected = require_int(
        body.get("expected_state_version"),
        "expected_state_version",
        minimum=0,
    )
    key = require_text(body.get("idempotency_key"), "idempotency_key", maximum=200)
    return expected, key


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_ids(value: Any, *, known: set[str], field_name: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConflictError(f"Stored {field_name} state is invalid.")
    identifiers = set(value)
    if not identifiers.issubset(known):
        raise ConflictError(f"Stored {field_name} state references unknown campaign data.")
    return identifiers


def _runtime_parts(
    store: GameStore,
    director: CampaignDirector,
    session_id: str,
) -> tuple[dict[str, Any], str, set[str], dict[str, dict[str, int]], tuple[str, ...]]:
    engine = store.get_engine_session(session_id)
    campaign = director.canonical_campaign
    public_world = _mapping(engine.get("world"))
    public_campaign = _mapping(public_world.get("campaign"))
    scene_id = public_campaign.get("current_scene")
    if not isinstance(scene_id, str) or scene_id not in campaign.scenes:
        raise ConflictError("Session does not reference a valid current campaign scene.")
    stored_campaign_id = public_campaign.get("campaign_id")
    if stored_campaign_id is not None and stored_campaign_id != campaign.campaign_id:
        raise ConflictError("Session campaign does not match the active Campaign Director.")

    private_world = _mapping(engine.get("private_world"))
    private_campaign = _mapping(private_world.get("campaign"))
    revealed_ids = _string_ids(
        private_campaign.get("revealed_fact_ids", []),
        known=set(campaign.facts),
        field_name="revealed facts",
    )

    private_npcs = _mapping(private_world.get("npcs"))
    relationships: dict[str, dict[str, int]] = {}
    for npc_id, npc in campaign.npcs.items():
        raw_relationship = _mapping(_mapping(private_npcs.get(npc_id)).get("relationship"))
        relationship = dict(npc.initial_relationship)
        for axis, raw_score in raw_relationship.items():
            if axis not in npc.initial_relationship:
                raise ConflictError("Stored NPC relationship state is invalid.")
            if isinstance(raw_score, bool) or not isinstance(raw_score, int):
                raise ConflictError("Stored NPC relationship state is invalid.")
            relationship[axis] = max(RELATIONSHIP_MIN, min(RELATIONSHIP_MAX, raw_score))
        relationships[npc_id] = relationship

    scene = campaign.scenes[scene_id]
    public_npcs = _mapping(public_world.get("npcs"))
    if public_npcs:
        present_ids = tuple(
            npc_id
            for npc_id in scene.available_npc_ids
            if _mapping(public_npcs.get(npc_id)).get("present") is True
        )
    else:
        present_ids = scene.available_npc_ids
    return engine, scene_id, revealed_ids, relationships, present_ids


def _safe_response(
    store: GameStore,
    director: CampaignDirector,
    session_id: str,
) -> dict[str, Any]:
    engine, scene_id, revealed_ids, relationships, present_ids = _runtime_parts(
        store, director, session_id
    )
    campaign = director.canonical_campaign
    brief = director.performer_brief(
        ProjectionContext(
            scene_id=scene_id,
            revealed_fact_ids=frozenset(revealed_ids),
            present_npc_ids=present_ids,
            npc_relationships=relationships,
        )
    ).to_dict()

    public_world = _mapping(engine.get("world"))
    public_npcs = _mapping(public_world.get("npcs"))
    safe_npcs: dict[str, dict[str, Any]] = {}
    for npc_brief in brief["npcs"]:
        npc_id = npc_brief["npc_id"]
        stored_npc = _mapping(public_npcs.get(npc_id))
        safe_npcs[npc_id] = {
            "name": npc_brief["name"],
            "public_description": npc_brief["public_description"],
            "visible_attitude": stored_npc.get("visible_attitude", "Present and attentive"),
            "present": True,
        }

    safe_public_state = {
        "campaign": {
            "campaign_id": campaign.campaign_id,
            "title": campaign.title,
            "current_scene": scene_id,
            "scene_title": campaign.scenes[scene_id].title,
            "revealed_facts": list(brief["revealed_facts"]),
        },
        "npcs": safe_npcs,
    }
    return {
        "session_id": session_id,
        "state_version": engine["state_version"],
        "performer_context": brief,
        "public_state": safe_public_state,
    }


def _public_fact_statements(director: CampaignDirector, fact_ids: set[str]) -> list[dict[str, str]]:
    campaign = director.canonical_campaign
    return [
        {"public_statement": fact.private_truth}
        for fact in campaign.facts.values()
        if fact.fact_id in fact_ids
    ]


def _last_world_patch(store: GameStore, session_id: str, expected_version: int) -> dict[str, Any] | None:
    events = store.get_public_events(session_id, after_version=expected_version)
    matching = [
        event
        for event in events
        if event["state_version"] == expected_version + 1
        and event["event_type"] == "world_state_updated"
    ]
    if len(matching) != 1:
        return None
    patch = _mapping(_mapping(matching[0].get("payload")).get("patch"))
    return dict(patch)


def _campaign_action(patch: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(_mapping(patch.get("campaign")).get("last_director_action"))


def _npc_action(patch: Mapping[str, Any], npc_id: str) -> Mapping[str, Any]:
    return _mapping(_mapping(_mapping(patch.get("npcs")).get(npc_id)).get("last_reaction"))


def _matching_retry_patch(
    store: GameStore,
    session_id: str,
    *,
    expected_version: int,
    current_version: int,
    expected_action: Mapping[str, Any],
    npc_id: str | None = None,
) -> dict[str, Any] | None:
    if current_version == expected_version:
        return None
    if current_version != expected_version + 1:
        raise StaleVersionError(expected_version, current_version)
    patch = _last_world_patch(store, session_id, expected_version)
    if patch is None:
        raise StaleVersionError(expected_version, current_version)
    actual_action = _npc_action(patch, npc_id) if npc_id else _campaign_action(patch)
    if dict(actual_action) != dict(expected_action):
        raise StaleVersionError(expected_version, current_version)
    return patch


def _validate_linear_campaign(director: CampaignDirector) -> None:
    campaign = director.canonical_campaign
    for index, scene_id in enumerate(campaign.scene_order):
        expected_next = (
            (campaign.scene_order[index + 1],)
            if index + 1 < len(campaign.scene_order)
            else ()
        )
        if tuple(campaign.scenes[scene_id].next_scene_ids) != expected_next:
            raise ConflictError("Campaign runtime requires a linear scene sequence.")


def _coarse_attitude(relationship: Mapping[str, int]) -> str:
    if relationship.get("suspicion", 0) >= 2:
        return "Guarded and watchful"
    if relationship.get("trust", 0) >= 2:
        return "Open and cooperative"
    if relationship.get("trust", 0) <= -2:
        return "Cold and reluctant"
    if relationship.get("fear", 0) >= 2:
        return "Uneasy but engaged"
    if relationship.get("respect", 0) >= 2:
        return "Respectful and attentive"
    return "Reserved but attentive"


def _check_tokens(value: str) -> set[str]:
    return {
        normalize_key(token.replace("'", ""))
        for token in re.split(r"\s+or\s+|,\s*(?:or\s+)?", value.lower())
        if token.strip()
    }


@dataclass(frozen=True)
class _RollAdjudication:
    dc: int | None
    dc_visibility: str


def _canonical_adjudication(
    director: CampaignDirector,
    scene_id: str,
    roll_kind: str,
    check_key: str | None,
) -> _RollAdjudication | None:
    if not check_key:
        return None
    normalized_key = normalize_key(check_key.replace("'", ""))
    kind = normalize_key(roll_kind)
    matching: set[tuple[int, str]] = set()
    for check in director.canonical_campaign.scenes[scene_id].checks.values():
        source = check.skill if kind == "skill" else check.ability if kind == "ability" else ""
        if normalized_key in _check_tokens(source):
            matching.add((check.private_dc, check.dc_visibility))
    if len(matching) != 1:
        return None
    dc, visibility = next(iter(matching))
    return _RollAdjudication(
        dc=dc,
        dc_visibility=visibility,
    )


def _improvised_adjudication(
    *,
    roll_kind: str,
    difficulty: Any,
    dc_visibility: Any,
) -> _RollAdjudication:
    kind = normalize_key(roll_kind)
    if kind == "initiative":
        return _RollAdjudication(
            dc=None,
            dc_visibility="private",
        )
    if kind == "death_save":
        return _RollAdjudication(
            dc=10,
            dc_visibility="public",
        )
    if kind not in BINARY_CHECK_KINDS:
        raise ValidationError(
            "Director rolls must be an ability check, skill check, saving throw, "
            "death save, or initiative roll."
        )
    if difficulty is None:
        raise ValidationError(
            "An improvised ability check, skill check, or saving throw requires difficulty."
        )
    tier = normalize_key(require_text(difficulty, "difficulty", maximum=40))
    if tier not in DIFFICULTY_CLASS_BY_TIER:
        raise ValidationError(
            "difficulty must be very_easy, easy, medium, hard, very_hard, "
            "or nearly_impossible."
        )
    resolved_visibility = normalize_key(
        require_text(dc_visibility or "private", "dc_visibility", maximum=20)
    )
    if resolved_visibility not in {"public", "private"}:
        raise ValidationError("dc_visibility must be public or private.")
    return _RollAdjudication(
        dc=DIFFICULTY_CLASS_BY_TIER[tier],
        dc_visibility=resolved_visibility,
    )


@director_blueprint.errorhandler(GameStateError)
def _handle_game_error(error: GameStateError):
    return jsonify(error.to_dict()), error.status_code


@director_blueprint.errorhandler(DirectorError)
def _handle_director_error(_error: DirectorError):
    return (
        jsonify(
            {
                "error": "director_projection_error",
                "message": "Campaign state could not be projected safely.",
            }
        ),
        409,
    )


@director_blueprint.get("/sessions/<session_id>/director")
def performer_context(session_id: str):
    return jsonify(_safe_response(get_game_store(), _director(), session_id))


@director_blueprint.post("/sessions/<session_id>/director/roll")
def request_campaign_roll(session_id: str):
    """Commit authoritative DC and visibility before requesting a physical roll."""

    body = _body(
        allowed={
            "player_id",
            "roll_kind",
            "check_key",
            "difficulty",
            "dc_visibility",
            "prompt",
            "expected_state_version",
            "idempotency_key",
        },
        required={
            "player_id",
            "roll_kind",
            "prompt",
            "expected_state_version",
            "idempotency_key",
        },
    )
    expected_version, idempotency_key = _mutation_fields(body)
    player_id = require_text(body["player_id"], "player_id")
    roll_kind = require_text(body["roll_kind"], "roll_kind")
    check_key_value = body.get("check_key")
    check_key = (
        require_text(check_key_value, "check_key")
        if check_key_value is not None
        else None
    )
    prompt = require_text(body["prompt"], "prompt", maximum=500)

    store = get_game_store()
    director = _director()
    _engine, scene_id, _revealed, _relationships, _present = _runtime_parts(
        store, director, session_id
    )
    adjudication = _canonical_adjudication(
        director,
        scene_id,
        roll_kind,
        check_key,
    ) or _improvised_adjudication(
        roll_kind=roll_kind,
        difficulty=body.get("difficulty"),
        dc_visibility=body.get("dc_visibility"),
    )
    result = store.request_roll(
        session_id,
        player_id,
        roll_kind=roll_kind,
        check_key=check_key,
        prompt=prompt,
        dc=adjudication.dc,
        engine_modifier=None,
        dc_visibility=adjudication.dc_visibility,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
    )
    return jsonify(result), 201


@director_blueprint.post("/sessions/<session_id>/director/advance")
def advance_scene(session_id: str):
    body = _body(
        allowed={"reason", "expected_state_version", "idempotency_key"},
        required={"reason", "expected_state_version", "idempotency_key"},
    )
    expected_version, idempotency_key = _mutation_fields(body)
    reason = require_text(body["reason"], "reason", maximum=500)
    store = get_game_store()
    director = _director()
    _validate_linear_campaign(director)
    engine, current_scene_id, revealed_ids, _relationships, _present = _runtime_parts(
        store, director, session_id
    )
    action = {"type": "advance", "reason": reason}
    retry_patch = _matching_retry_patch(
        store,
        session_id,
        expected_version=expected_version,
        current_version=engine["state_version"],
        expected_action=action,
    )

    campaign = director.canonical_campaign
    if retry_patch is not None:
        target_scene_id = _mapping(retry_patch.get("campaign")).get("current_scene")
        if target_scene_id != current_scene_id:
            raise StaleVersionError(expected_version, engine["state_version"])
        public_patch = retry_patch
    else:
        scene_index = campaign.scene_order.index(current_scene_id)
        if scene_index + 1 >= len(campaign.scene_order):
            raise ConflictError("The campaign is already at its final scene.")
        target_scene_id = campaign.scene_order[scene_index + 1]
        if target_scene_id not in campaign.scenes[current_scene_id].next_scene_ids:
            raise ConflictError("The next campaign scene is not an allowed transition.")
        target_scene = campaign.scenes[target_scene_id]
        revealed_ids.update(target_scene.automatic_reveals)
        revealed_ids.update(
            fact.fact_id for fact in campaign.facts.values() if fact.visibility == "public"
        )
        public_patch = {
            "campaign": {
                "current_scene": target_scene_id,
                "scene_title": target_scene.title,
                "revealed_facts": _public_fact_statements(director, revealed_ids),
                "last_director_action": action,
            }
        }

    # On an idempotent retry, current private state is the exact state written by
    # the first call. Reusing it reconstructs the original GameStore request hash.
    private_patch = {"campaign": {"revealed_fact_ids": sorted(revealed_ids)}}
    store.update_world_state(
        session_id,
        public_patch=public_patch,
        private_patch=private_patch,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
    )
    return jsonify(_safe_response(store, director, session_id))


@director_blueprint.post("/sessions/<session_id>/director/npc-reaction")
def npc_reaction(session_id: str):
    body = _body(
        allowed={
            "npc_id",
            "reaction",
            "public_reason",
            "expected_state_version",
            "idempotency_key",
        },
        required={
            "npc_id",
            "reaction",
            "public_reason",
            "expected_state_version",
            "idempotency_key",
        },
    )
    expected_version, idempotency_key = _mutation_fields(body)
    npc_id = require_text(body["npc_id"], "npc_id")
    reaction = require_text(body["reaction"], "reaction")
    if reaction not in REACTIONS:
        raise ValidationError(f"reaction must be one of {sorted(REACTIONS)}")
    public_reason = require_text(body["public_reason"], "public_reason", maximum=500)

    store = get_game_store()
    director = _director()
    engine, scene_id, _revealed, relationships, present_ids = _runtime_parts(
        store, director, session_id
    )
    campaign = director.canonical_campaign
    public_npc = _mapping(_mapping(engine.get("world")).get("npcs")).get(npc_id)
    if (
        npc_id not in campaign.npcs
        or npc_id not in campaign.scenes[scene_id].available_npc_ids
        or npc_id not in present_ids
        or _mapping(public_npc).get("present") is not True
    ):
        raise ConflictError("The requested NPC is not present in the current scene.")

    action = {
        "type": "npc_reaction",
        "npc_id": npc_id,
        "reaction": reaction,
        "reason": public_reason,
    }
    retry_patch = _matching_retry_patch(
        store,
        session_id,
        expected_version=expected_version,
        current_version=engine["state_version"],
        expected_action=action,
        npc_id=npc_id,
    )
    relationship = dict(relationships[npc_id])
    if retry_patch is None:
        axis, delta = REACTIONS[reaction]
        relationship[axis] = max(
            RELATIONSHIP_MIN,
            min(RELATIONSHIP_MAX, relationship.get(axis, 0) + delta),
        )
        public_patch = {
            "npcs": {
                npc_id: {
                    "visible_attitude": _coarse_attitude(relationship),
                    "last_reaction": action,
                }
            }
        }
    else:
        public_patch = retry_patch

    store.update_world_state(
        session_id,
        public_patch=public_patch,
        private_patch={"npcs": {npc_id: {"relationship": relationship}}},
        expected_version=expected_version,
        idempotency_key=idempotency_key,
    )
    return jsonify(_safe_response(store, director, session_id))


@director_blueprint.post("/sessions/<session_id>/director/discovery")
def record_discovery(session_id: str):
    body = _body(
        allowed={
            "discovery",
            "public_reason",
            "expected_state_version",
            "idempotency_key",
        },
        required={
            "discovery",
            "public_reason",
            "expected_state_version",
            "idempotency_key",
        },
    )
    expected_version, idempotency_key = _mutation_fields(body)
    discovery = require_text(body["discovery"], "discovery")
    if discovery not in DISCOVERY_MAP:
        raise ValidationError(f"discovery must be one of {sorted(DISCOVERY_MAP)}")
    public_reason = require_text(body["public_reason"], "public_reason", maximum=500)

    store = get_game_store()
    director = _director()
    engine, scene_id, revealed_ids, _relationships, _present_ids = _runtime_parts(
        store, director, session_id
    )
    canonical = DISCOVERY_MAP[discovery].get(scene_id)
    if canonical is None:
        raise ConflictError("That discovery is not available in the current scene.")

    action = {"type": "discovery", "discovery": discovery, "reason": public_reason}
    retry_patch = _matching_retry_patch(
        store,
        session_id,
        expected_version=expected_version,
        current_version=engine["state_version"],
        expected_action=action,
    )
    private_campaign = _mapping(_mapping(engine.get("private_world")).get("campaign"))
    campaign = director.canonical_campaign
    committed_events = _string_ids(
        private_campaign.get("committed_event_ids", []),
        known={condition for fact in campaign.facts.values() for condition in fact.reveal_conditions}
        | {event for scene in campaign.scenes.values() for event in scene.exit_conditions}
        | {"find-finn-tracks", "inspect-chapel-mural", "earn-mara-trust", "ask-the-echo", "reach-bell-vault"},
        field_name="committed events",
    )
    committed_clues = _string_ids(
        private_campaign.get("committed_clue_ids", []),
        known={clue_id for scene in campaign.scenes.values() for clue_id in scene.clues},
        field_name="committed clues",
    )
    committed_events.update(canonical.get("events", ()))
    committed_clues.update(canonical.get("clues", ()))

    evaluation = director.evaluate_reveals(
        committed_event_ids=committed_events,
        committed_clue_ids=committed_clues,
        current_scene_id=scene_id,
        already_revealed_fact_ids=revealed_ids,
    )
    revealed_ids.update(evaluation.revealable_fact_ids)
    if retry_patch is None:
        public_patch = {
            "campaign": {
                "revealed_facts": _public_fact_statements(director, revealed_ids),
                "last_director_action": action,
            }
        }
    else:
        public_patch = retry_patch

    store.update_world_state(
        session_id,
        public_patch=public_patch,
        private_patch={
            "campaign": {
                "revealed_fact_ids": sorted(revealed_ids),
                "committed_event_ids": sorted(committed_events),
                "committed_clue_ids": sorted(committed_clues),
            }
        },
        expected_version=expected_version,
        idempotency_key=idempotency_key,
    )
    return jsonify(_safe_response(store, director, session_id))
