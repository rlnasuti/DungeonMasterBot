"""Flask blueprint for the authoritative game-state service.

Register ``game_blueprint`` on an application. The SQLite store is created lazily
from ``GAME_DATABASE_PATH`` or can be injected into
``app.extensions['dungeonmaster_game_store']`` for tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from bot.game.demo import DEMO_SESSION_ID, bootstrap_demo_session
from bot.game.errors import GameStateError, ValidationError
from bot.game.models import require_int
from bot.game.store import GameStore


STORE_EXTENSION_KEY = "dungeonmaster_game_store"
_STORE_INITIALIZATION_LOCK = Lock()
game_blueprint = Blueprint("game_api", __name__, url_prefix="/api")


def _store() -> GameStore:
    existing = current_app.extensions.get(STORE_EXTENSION_KEY)
    if existing is not None:
        return existing
    # The React development runtime deliberately mounts effects twice. Two
    # simultaneous first requests must not both negotiate SQLite WAL mode.
    with _STORE_INITIALIZATION_LOCK:
        existing = current_app.extensions.get(STORE_EXTENSION_KEY)
        if existing is not None:
            return existing
        configured_path = current_app.config.get("GAME_DATABASE_PATH")
        database_path = configured_path or str(Path(current_app.instance_path) / "game_state.sqlite3")
        store = GameStore(database_path)
        current_app.extensions[STORE_EXTENSION_KEY] = store
        return store


def _body() -> dict[str, Any]:
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValidationError("Request body must be a JSON object.")
    return dict(value)


def _validate_fields(
    body: dict[str, Any], *, allowed: set[str], required: set[str] = frozenset()
) -> None:
    unknown = set(body) - allowed
    if unknown:
        raise ValidationError(f"Request has unknown fields: {sorted(unknown)}")
    missing = required - set(body)
    if missing:
        raise ValidationError(f"Request is missing required fields: {sorted(missing)}")


def _idempotency_key(body: dict[str, Any], *, fallback: str | None = None) -> str:
    body_key = body.pop("idempotency_key", None)
    header_key = request.headers.get("Idempotency-Key")
    if body_key and header_key and body_key != header_key:
        raise ValidationError("Body and header idempotency keys do not match.")
    key = header_key or body_key or fallback
    if not key:
        raise ValidationError("An Idempotency-Key header or idempotency_key field is required.")
    return key


def _expected_version(body: dict[str, Any]) -> int:
    if "expected_state_version" not in body:
        raise ValidationError("expected_state_version is required.")
    return require_int(body.pop("expected_state_version"), "expected_state_version", minimum=0)


def _derived_roll_key(
    session_id: str, roll_id: str, player_id: Any, natural_roll: Any, expected_version: Any
) -> str:
    canonical = json.dumps(
        [session_id, roll_id, player_id, natural_roll, expected_version],
        separators=(",", ":"),
    )
    return "roll-submit:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@game_blueprint.errorhandler(GameStateError)
def _handle_game_error(error: GameStateError):
    return jsonify(error.to_dict()), error.status_code


@game_blueprint.post("/sessions")
def create_session():
    body = _body()
    _validate_fields(
        body,
        allowed={
            "session_id",
            "players",
            "public_world",
            "private_world",
            "idempotency_key",
        },
        required={"players"},
    )
    key = _idempotency_key(body)
    result = _store().create_session(
        session_id=body.get("session_id"),
        players=body["players"],
        public_world=body.get("public_world"),
        private_world=body.get("private_world"),
        idempotency_key=key,
    )
    return jsonify(result), 201


@game_blueprint.post("/demo-sessions")
def create_demo_session():
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")
    _validate_fields(body, allowed={"session_id"})
    result = bootstrap_demo_session(_store(), session_id=body.get("session_id", DEMO_SESSION_ID))
    return jsonify(result), 201


@game_blueprint.get("/sessions/latest")
def read_latest_session():
    if request.content_length not in (None, 0):
        raise ValidationError("Latest-session lookup does not accept a request body.")
    if request.args:
        raise ValidationError("Latest-session lookup does not accept query parameters.")
    return jsonify(_store().get_latest_public_session())


@game_blueprint.get("/sessions/<session_id>")
def read_session(session_id: str):
    return jsonify(_store().get_public_session(session_id))


@game_blueprint.get("/sessions/<session_id>/view")
def read_session_view(session_id: str):
    raw_since = request.args.get("since_version", "-1")
    try:
        since_version = int(raw_since)
    except ValueError as exc:
        raise ValidationError("since_version must be an integer.") from exc
    snapshot = _store().get_public_session(session_id)
    snapshot["events"] = _store().get_public_events(session_id, after_version=since_version)
    return jsonify(snapshot)


@game_blueprint.get("/sessions/<session_id>/events")
def read_events(session_id: str):
    raw_after = request.args.get("after_version", "-1")
    try:
        after_version = int(raw_after)
    except ValueError as exc:
        raise ValidationError("after_version must be an integer.") from exc
    return jsonify(
        {
            "session_id": session_id,
            "events": _store().get_public_events(session_id, after_version=after_version),
        }
    )


@game_blueprint.get("/sessions/<session_id>/conversation")
def read_conversation(session_id: str):
    if request.content_length not in (None, 0):
        raise ValidationError("Conversation listing does not accept a request body.")
    if request.args:
        raise ValidationError("Conversation listing does not accept query parameters.")
    return jsonify(
        {
            "session_id": session_id,
            "messages": _store().get_conversation_messages(session_id),
        }
    )


@game_blueprint.put("/sessions/<session_id>/conversation/messages/<message_id>")
def put_conversation_message(session_id: str, message_id: str):
    if request.args:
        raise ValidationError("Conversation message insertion does not accept query parameters.")
    body = _body()
    _validate_fields(body, allowed={"role", "text"}, required={"role", "text"})
    return jsonify(
        _store().put_conversation_message(
            session_id,
            message_id,
            role=body["role"],
            text=body["text"],
        )
    )


@game_blueprint.delete("/sessions/<session_id>/conversation")
def clear_conversation(session_id: str):
    if request.content_length not in (None, 0):
        raise ValidationError("Conversation clearing does not accept a request body.")
    if request.args:
        raise ValidationError("Conversation clearing does not accept query parameters.")
    return jsonify(
        {
            "session_id": session_id,
            "deleted_count": _store().clear_conversation_messages(session_id),
        }
    )


@game_blueprint.patch("/sessions/<session_id>/world")
def update_world(session_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={"public_patch", "private_patch", "expected_state_version", "idempotency_key"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    result = _store().update_world_state(
        session_id,
        public_patch=body.get("public_patch"),
        private_patch=body.get("private_patch"),
        expected_version=expected,
        idempotency_key=key,
    )
    return jsonify(result)


@game_blueprint.patch("/sessions/<session_id>/players/<player_id>")
def update_player_identity(session_id: str, player_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={
            "display_name",
            "character_name",
            "expected_state_version",
            "idempotency_key",
        },
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    return jsonify(
        _store().update_player_identity(
            session_id,
            player_id,
            display_name=body.get("display_name"),
            character_name=body.get("character_name"),
            expected_version=expected,
            idempotency_key=key,
        )
    )


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/character")
def stage_character(session_id: str, player_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={"character", "source", "expected_state_version", "idempotency_key"},
        required={"character", "source"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    result = _store().stage_character(
        session_id,
        player_id,
        character=body["character"],
        source=body["source"],
        expected_version=expected,
        idempotency_key=key,
    )
    return jsonify(result), 201


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/character/confirm")
def confirm_character(session_id: str, player_id: str):
    body = _body()
    _validate_fields(body, allowed={"expected_state_version", "idempotency_key"})
    key = _idempotency_key(body)
    expected = _expected_version(body)
    return jsonify(
        _store().confirm_character(
            session_id,
            player_id,
            expected_version=expected,
            idempotency_key=key,
        )
    )


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/damage")
def apply_damage(session_id: str, player_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={"amount", "expected_state_version", "idempotency_key"},
        required={"amount"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    return jsonify(
        _store().apply_damage(
            session_id,
            player_id,
            amount=body["amount"],
            expected_version=expected,
            idempotency_key=key,
        )
    )


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/healing")
def apply_healing(session_id: str, player_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={"amount", "expected_state_version", "idempotency_key"},
        required={"amount"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    return jsonify(
        _store().apply_healing(
            session_id,
            player_id,
            amount=body["amount"],
            expected_version=expected,
            idempotency_key=key,
        )
    )


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/currency/award")
def award_currency(session_id: str, player_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={
            "amount",
            "denomination",
            "reason",
            "expected_state_version",
            "idempotency_key",
        },
        required={"amount", "denomination", "reason"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    return jsonify(
        _store().award_currency(
            session_id,
            player_id,
            amount=body["amount"],
            denomination=body["denomination"],
            reason=body["reason"],
            expected_version=expected,
            idempotency_key=key,
        )
    )


def _resource_change(session_id: str, player_id: str, *, restore: bool):
    body = _body()
    _validate_fields(
        body,
        allowed={
            "resource_type",
            "resource_key",
            "amount",
            "expected_state_version",
            "idempotency_key",
        },
        required={"resource_type", "resource_key", "amount"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    return jsonify(
        _store().change_resource(
            session_id,
            player_id,
            resource_type=body["resource_type"],
            resource_key=body["resource_key"],
            amount=body["amount"],
            restore=restore,
            expected_version=expected,
            idempotency_key=key,
        )
    )


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/resources/use")
def use_resource(session_id: str, player_id: str):
    return _resource_change(session_id, player_id, restore=False)


@game_blueprint.post("/sessions/<session_id>/players/<player_id>/resources/restore")
def restore_resource(session_id: str, player_id: str):
    return _resource_change(session_id, player_id, restore=True)


@game_blueprint.post("/sessions/<session_id>/rolls")
def request_physical_roll(session_id: str):
    body = _body()
    _validate_fields(
        body,
        allowed={
            "player_id",
            "roll_kind",
            "check_key",
            "prompt",
            "dc",
            "engine_modifier",
            "expected_state_version",
            "idempotency_key",
        },
        required={"player_id", "roll_kind", "prompt"},
    )
    key = _idempotency_key(body)
    expected = _expected_version(body)
    result = _store().request_roll(
        session_id,
        body["player_id"],
        roll_kind=body["roll_kind"],
        check_key=body.get("check_key"),
        prompt=body["prompt"],
        dc=body.get("dc"),
        engine_modifier=body.get("engine_modifier"),
        expected_version=expected,
        idempotency_key=key,
    )
    return jsonify(result), 201


@game_blueprint.post("/sessions/<session_id>/rolls/<roll_id>")
def submit_physical_roll(session_id: str, roll_id: str):
    """Frontend contract: the caller may report only the physical d20 face."""
    body = _body()
    _validate_fields(
        body,
        allowed={"player_id", "natural_roll", "expected_state_version", "idempotency_key"},
        required={"player_id", "natural_roll", "expected_state_version"},
    )
    fallback_key = _derived_roll_key(
        session_id,
        roll_id,
        body.get("player_id"),
        body.get("natural_roll"),
        body.get("expected_state_version"),
    )
    key = _idempotency_key(body, fallback=fallback_key)
    expected = _expected_version(body)
    return jsonify(
        _store().submit_roll(
            session_id,
            roll_id,
            body["player_id"],
            raw_d20=body["natural_roll"],
            expected_version=expected,
            idempotency_key=key,
        )
    )
