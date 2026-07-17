"""SQLite-backed authoritative state engine for a two-player one-shot."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from bot.game.errors import ConflictError, NotFoundError, StaleVersionError, ValidationError
from bot.game.models import (
    CURRENCY_AWARD_MAXIMUM,
    CURRENCY_BALANCE_MAXIMUM,
    CURRENCY_DENOMINATIONS,
    CharacterState,
    ResourcePool,
    normalize_key,
    require_int,
    require_text,
)


PRIVATE_PUBLIC_KEYS = {
    "private",
    "private_state",
    "secret",
    "secrets",
    "hidden",
    "hidden_facts",
    "gm_notes",
    "dm_notes",
    "motives",
    "ulterior_motives",
    "attitude_by_player",
    "dc",
    "modifier",
}

CONVERSATION_MESSAGE_ROLES = frozenset({"user", "assistant"})
CONVERSATION_MESSAGE_ID_MAXIMUM = 200
CONVERSATION_MESSAGE_TEXT_MAXIMUM = 50_000
ROLL_DC_VISIBILITIES = frozenset({"public", "private"})
BINARY_ROLL_KINDS = frozenset(
    {"ability", "skill", "saving_throw", "save", "death_save", "attack"}
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _json_object(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field_name} must be an object.")
    try:
        return json.loads(_json(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must contain only JSON-compatible values.") from exc


def _validate_public_boundary(value: Any, path: str = "public_world") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = normalize_key(str(raw_key))
            if key in PRIVATE_PUBLIC_KEYS:
                raise ValidationError(f"Private field '{raw_key}' cannot be stored under {path}.")
            _validate_public_boundary(child, f"{path}.{raw_key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_public_boundary(child, f"{path}[{index}]")


def _deep_merge(original: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    merged = json.loads(_json(original))
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is None:
            merged.pop(key, None)
        else:
            merged[key] = json.loads(_json(value))
    return merged


@dataclass
class _Mutation:
    response: dict[str, Any]
    event_type: str
    public_event: dict[str, Any]
    private_event: dict[str, Any]


class GameStore:
    """Owns validated game transitions; clients only submit observations such as a d20 face."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            if self.database_path != ":memory:":
                connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state_version INTEGER NOT NULL DEFAULT 0,
                    public_world_json TEXT NOT NULL,
                    private_world_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS players (
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    player_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    seat INTEGER NOT NULL CHECK (seat IN (1, 2)),
                    character_status TEXT NOT NULL DEFAULT 'empty'
                        CHECK (character_status IN ('empty', 'draft', 'confirmed')),
                    character_source TEXT,
                    character_json TEXT,
                    PRIMARY KEY (session_id, player_id),
                    UNIQUE (session_id, seat)
                );

                CREATE TABLE IF NOT EXISTS pending_rolls (
                    roll_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    player_id TEXT NOT NULL,
                    roll_kind TEXT NOT NULL,
                    check_key TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    modifier INTEGER NOT NULL,
                    dc INTEGER,
                    dc_visibility TEXT NOT NULL DEFAULT 'private',
                    raw_d20 INTEGER,
                    total INTEGER,
                    success INTEGER,
                    requested_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (session_id, player_id) REFERENCES players(session_id, player_id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    state_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    public_payload_json TEXT NOT NULL,
                    private_payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS events_by_session_version
                    ON events(session_id, state_version, event_id);

                CREATE TABLE IF NOT EXISTS idempotency (
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    idempotency_key TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS creation_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_messages (
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    message_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK (sequence >= 1),
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, message_id),
                    UNIQUE (session_id, sequence)
                );

                CREATE INDEX IF NOT EXISTS conversation_messages_chronological
                    ON conversation_messages(session_id, sequence);
                """
            )
            # Additive migration for sessions created before roll visibility was
            # persisted. Existing rolls retain the historical hidden-DC behavior.
            roll_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(pending_rolls)")
            }
            if "dc_visibility" not in roll_columns:
                connection.execute(
                    "ALTER TABLE pending_rolls ADD COLUMN "
                    "dc_visibility TEXT NOT NULL DEFAULT 'private'"
                )

    @staticmethod
    def _validate_idempotency_key(value: Any) -> str:
        return require_text(value, "idempotency_key", maximum=200)

    @staticmethod
    def _validate_expected_version(value: Any) -> int:
        return require_int(value, "expected_state_version", minimum=0)

    @staticmethod
    def _validate_players(players: Any) -> list[dict[str, Any]]:
        if not isinstance(players, list) or len(players) != 2:
            raise ValidationError("A session requires exactly two player identities.")
        validated: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for index, player in enumerate(players):
            if not isinstance(player, Mapping):
                raise ValidationError(f"players[{index}] must be an object.")
            unknown = set(player) - {"player_id", "display_name"}
            if unknown:
                raise ValidationError(f"players[{index}] has unknown fields: {sorted(unknown)}")
            player_id = require_text(player.get("player_id", str(uuid4())), f"players[{index}].player_id")
            if player_id in seen_ids:
                raise ValidationError("Player IDs must be unique within a session.")
            seen_ids.add(player_id)
            validated.append(
                {
                    "player_id": player_id,
                    "display_name": require_text(player.get("display_name"), f"players[{index}].display_name"),
                    "seat": index + 1,
                }
            )
        return validated

    def create_session(
        self,
        *,
        players: Sequence[Mapping[str, Any]],
        idempotency_key: str,
        session_id: str | None = None,
        public_world: Mapping[str, Any] | None = None,
        private_world: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = self._validate_idempotency_key(idempotency_key)
        public = _json_object(public_world, "public_world")
        private = _json_object(private_world, "private_world")
        _validate_public_boundary(public)
        request_players = json.loads(_json(players))
        request_payload = {
            "session_id": session_id,
            "players": request_players,
            "public_world": public,
            "private_world": private,
        }
        request_hash = _json_hash(request_payload)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT request_hash, response_json FROM creation_idempotency WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise ConflictError("The creation idempotency key was already used with a different request.")
                connection.commit()
                return json.loads(existing["response_json"])

            validated_players = self._validate_players(request_players)
            resolved_session_id = require_text(session_id or str(uuid4()), "session_id")
            timestamp = _now()
            try:
                connection.execute(
                    """
                    INSERT INTO sessions (
                        session_id, state_version, public_world_json, private_world_json, created_at, updated_at
                    ) VALUES (?, 0, ?, ?, ?, ?)
                    """,
                    (resolved_session_id, _json(public), _json(private), timestamp, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Session '{resolved_session_id}' already exists.") from exc
            for player in validated_players:
                connection.execute(
                    """
                    INSERT INTO players (session_id, player_id, display_name, seat)
                    VALUES (?, ?, ?, ?)
                    """,
                    (resolved_session_id, player["player_id"], player["display_name"], player["seat"]),
                )

            connection.execute(
                """
                INSERT INTO events (
                    session_id, state_version, event_type, public_payload_json, private_payload_json, created_at
                ) VALUES (?, 0, 'session_created', ?, ?, ?)
                """,
                (
                    resolved_session_id,
                    _json({"players": validated_players, "world": public}),
                    _json({"world": private}),
                    timestamp,
                ),
            )
            response = self._public_snapshot(connection, resolved_session_id)
            connection.execute(
                """
                INSERT INTO creation_idempotency (idempotency_key, request_hash, response_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, request_hash, _json(response), timestamp),
            )
            connection.commit()
            return response
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _mutate(
        self,
        *,
        session_id: str,
        expected_version: int,
        idempotency_key: str,
        operation: str,
        request_payload: Mapping[str, Any],
        change: Callable[[sqlite3.Connection], _Mutation],
    ) -> dict[str, Any]:
        expected = self._validate_expected_version(expected_version)
        key = self._validate_idempotency_key(idempotency_key)
        request_hash = _json_hash({"expected_version": expected, "payload": request_payload})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                """
                SELECT operation, request_hash, response_json
                FROM idempotency WHERE session_id = ? AND idempotency_key = ?
                """,
                (session_id, key),
            ).fetchone()
            if replay:
                if replay["operation"] != operation or replay["request_hash"] != request_hash:
                    raise ConflictError("The idempotency key was already used with a different mutation.")
                connection.commit()
                return json.loads(replay["response_json"])

            session = connection.execute(
                "SELECT state_version FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not session:
                raise NotFoundError(f"Session '{session_id}' was not found.")
            current_version = int(session["state_version"])
            if current_version != expected:
                raise StaleVersionError(expected, current_version)

            mutation = change(connection)
            next_version = current_version + 1
            timestamp = _now()
            connection.execute(
                "UPDATE sessions SET state_version = ?, updated_at = ? WHERE session_id = ?",
                (next_version, timestamp, session_id),
            )
            connection.execute(
                """
                INSERT INTO events (
                    session_id, state_version, event_type, public_payload_json, private_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    next_version,
                    mutation.event_type,
                    _json(mutation.public_event),
                    _json(mutation.private_event),
                    timestamp,
                ),
            )
            response = dict(mutation.response)
            response.setdefault("session_id", session_id)
            response["state_version"] = next_version
            connection.execute(
                """
                INSERT INTO idempotency (
                    session_id, idempotency_key, operation, request_hash, response_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, key, operation, request_hash, _json(response), timestamp),
            )
            connection.commit()
            return response
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _public_snapshot(self, connection: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        session = connection.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not session:
            raise NotFoundError(f"Session '{session_id}' was not found.")
        players = []
        for row in connection.execute(
            "SELECT * FROM players WHERE session_id = ? ORDER BY seat", (session_id,)
        ):
            player: dict[str, Any] = {
                "player_id": row["player_id"],
                "display_name": row["display_name"],
                "seat": row["seat"],
                "character_status": row["character_status"],
                "character_source": row["character_source"],
            }
            if row["character_status"] == "confirmed" and row["character_json"]:
                # Normalize persisted sheets through the current public schema.
                # This keeps additive fields (such as the coin purse) visible for
                # campaigns created before that field existed, without a risky
                # destructive database migration.
                player["character"] = CharacterState.from_dict(
                    json.loads(row["character_json"])
                ).to_dict()
            players.append(player)

        pending_rolls = []
        for row in connection.execute(
            """
            SELECT roll_id, player_id, roll_kind, check_key, prompt, dc,
                   dc_visibility, requested_at
            FROM pending_rolls
            WHERE session_id = ? AND resolved_at IS NULL
            ORDER BY requested_at, roll_id
            """,
            (session_id,),
        ):
            pending_roll = {
                "roll_id": row["roll_id"],
                "player_id": row["player_id"],
                "roll_kind": row["roll_kind"],
                "check_key": row["check_key"],
                "prompt": row["prompt"],
                "dc_visibility": row["dc_visibility"],
                "requested_at": row["requested_at"],
            }
            if row["dc_visibility"] == "public" and row["dc"] is not None:
                pending_roll["target_total"] = row["dc"]
            pending_rolls.append(pending_roll)

        return {
            "session_id": session["session_id"],
            "state_version": session["state_version"],
            "world": json.loads(session["public_world_json"]),
            "players": players,
            "pending_rolls": pending_rolls,
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        }

    def get_public_session(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            return self._public_snapshot(connection, session_id)

    def get_latest_public_session(self) -> dict[str, Any]:
        """Return one latest public snapshot without exposing a session collection."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session_id
                FROM sessions
                ORDER BY updated_at DESC, created_at DESC, session_id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                raise NotFoundError("No game sessions were found.")
            return self._public_snapshot(connection, row["session_id"])

    def get_engine_session(self, session_id: str) -> dict[str, Any]:
        """Returns private context for the trusted DM engine; this is intentionally not an HTTP GET."""
        with self._connect() as connection:
            snapshot = self._public_snapshot(connection, session_id)
            session = connection.execute(
                "SELECT private_world_json FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            private_rolls = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT roll_id, player_id, modifier, dc, dc_visibility
                    FROM pending_rolls WHERE session_id = ? AND resolved_at IS NULL
                    """,
                    (session_id,),
                )
            ]
            snapshot["private_world"] = json.loads(session["private_world_json"])
            snapshot["engine_roll_state"] = private_rolls
            return snapshot

    def get_public_events(self, session_id: str, *, after_version: int = -1) -> list[dict[str, Any]]:
        if isinstance(after_version, bool) or not isinstance(after_version, int) or after_version < -1:
            raise ValidationError("after_version must be an integer of -1 or greater.")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not exists:
                raise NotFoundError(f"Session '{session_id}' was not found.")
            return [
                {
                    "event_id": row["event_id"],
                    "state_version": row["state_version"],
                    "event_type": row["event_type"],
                    "payload": json.loads(row["public_payload_json"]),
                    "created_at": row["created_at"],
                }
                for row in connection.execute(
                    """
                    SELECT event_id, state_version, event_type, public_payload_json, created_at
                    FROM events
                    WHERE session_id = ? AND state_version > ?
                    ORDER BY state_version, event_id
                    """,
                    (session_id, after_version),
                )
            ]

    @staticmethod
    def _validate_conversation_identifier(value: Any, field_name: str) -> str:
        identifier = require_text(
            value,
            field_name,
            maximum=CONVERSATION_MESSAGE_ID_MAXIMUM,
        )
        if identifier != value:
            raise ValidationError(f"{field_name} cannot have leading or trailing whitespace.")
        if any(ord(character) < 32 or ord(character) == 127 for character in identifier):
            raise ValidationError(f"{field_name} cannot contain control characters.")
        return identifier

    @staticmethod
    def _validate_conversation_role(value: Any) -> str:
        if not isinstance(value, str) or value not in CONVERSATION_MESSAGE_ROLES:
            allowed = sorted(CONVERSATION_MESSAGE_ROLES)
            raise ValidationError(f"role must be one of {allowed}.")
        return value

    @staticmethod
    def _validate_conversation_text(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("text must be a non-empty string.")
        if len(value) > CONVERSATION_MESSAGE_TEXT_MAXIMUM:
            raise ValidationError(
                f"text must be no more than {CONVERSATION_MESSAGE_TEXT_MAXIMUM} characters."
            )
        return value

    @staticmethod
    def _conversation_message_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "message_id": row["message_id"],
            "sequence": row["sequence"],
            "role": row["role"],
            "text": row["text"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_conversation_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Return finalized, player-visible transcript messages in insertion order."""
        resolved_session_id = self._validate_conversation_identifier(session_id, "session_id")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (resolved_session_id,)
            ).fetchone()
            if not exists:
                raise NotFoundError(f"Session '{resolved_session_id}' was not found.")
            return [
                self._conversation_message_from_row(row)
                for row in connection.execute(
                    """
                    SELECT message_id, sequence, role, text, created_at, updated_at
                    FROM conversation_messages
                    WHERE session_id = ?
                    ORDER BY sequence
                    """,
                    (resolved_session_id,),
                )
            ]

    def put_conversation_message(
        self,
        session_id: str,
        message_id: str,
        *,
        role: str,
        text: str,
    ) -> dict[str, Any]:
        """Insert one finalized public message, or replay its exact persisted value.

        This ledger is deliberately independent of authoritative game mutations:
        writes do not increment ``sessions.state_version``, update the session, or
        create public/private game events.
        """
        resolved_session_id = self._validate_conversation_identifier(session_id, "session_id")
        resolved_message_id = self._validate_conversation_identifier(message_id, "message_id")
        resolved_role = self._validate_conversation_role(role)
        resolved_text = self._validate_conversation_text(text)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (resolved_session_id,)
            ).fetchone()
            if not exists:
                raise NotFoundError(f"Session '{resolved_session_id}' was not found.")

            existing = connection.execute(
                """
                SELECT message_id, sequence, role, text, created_at, updated_at
                FROM conversation_messages
                WHERE session_id = ? AND message_id = ?
                """,
                (resolved_session_id, resolved_message_id),
            ).fetchone()
            if existing:
                if existing["role"] != resolved_role or existing["text"] != resolved_text:
                    raise ConflictError(
                        "The conversation message ID was already used with different content."
                    )
                connection.commit()
                return self._conversation_message_from_row(existing)

            next_sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM conversation_messages
                WHERE session_id = ?
                """,
                (resolved_session_id,),
            ).fetchone()[0]
            timestamp = _now()
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    session_id, message_id, sequence, role, text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_session_id,
                    resolved_message_id,
                    next_sequence,
                    resolved_role,
                    resolved_text,
                    timestamp,
                    timestamp,
                ),
            )
            inserted = connection.execute(
                """
                SELECT message_id, sequence, role, text, created_at, updated_at
                FROM conversation_messages
                WHERE session_id = ? AND message_id = ?
                """,
                (resolved_session_id, resolved_message_id),
            ).fetchone()
            connection.commit()
            return self._conversation_message_from_row(inserted)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def clear_conversation_messages(self, session_id: str) -> int:
        """Clear only the public transcript ledger and return the deleted row count."""
        resolved_session_id = self._validate_conversation_identifier(session_id, "session_id")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (resolved_session_id,)
            ).fetchone()
            if not exists:
                raise NotFoundError(f"Session '{resolved_session_id}' was not found.")
            cursor = connection.execute(
                "DELETE FROM conversation_messages WHERE session_id = ?",
                (resolved_session_id,),
            )
            deleted_count = cursor.rowcount
            connection.commit()
            return deleted_count
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def update_world_state(
        self,
        session_id: str,
        *,
        public_patch: Mapping[str, Any] | None,
        private_patch: Mapping[str, Any] | None,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        public_delta = _json_object(public_patch, "public_patch")
        private_delta = _json_object(private_patch, "private_patch")
        _validate_public_boundary(public_delta, "public_patch")

        def change(connection: sqlite3.Connection) -> _Mutation:
            row = connection.execute(
                "SELECT public_world_json, private_world_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            public = _deep_merge(json.loads(row["public_world_json"]), public_delta)
            private = _deep_merge(json.loads(row["private_world_json"]), private_delta)
            connection.execute(
                "UPDATE sessions SET public_world_json = ?, private_world_json = ? WHERE session_id = ?",
                (_json(public), _json(private), session_id),
            )
            return _Mutation(
                response={"world": public},
                event_type="world_state_updated",
                public_event={"patch": public_delta},
                private_event={"patch": private_delta},
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation="update_world_state",
            request_payload={"public_patch": public_delta, "private_patch": private_delta},
            change=change,
        )

    @staticmethod
    def _player_row(connection: sqlite3.Connection, session_id: str, player_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM players WHERE session_id = ? AND player_id = ?", (session_id, player_id)
        ).fetchone()
        if not row:
            raise NotFoundError(f"Player '{player_id}' was not found in session '{session_id}'.")
        return row

    @classmethod
    def _confirmed_character(
        cls, connection: sqlite3.Connection, session_id: str, player_id: str
    ) -> CharacterState:
        row = cls._player_row(connection, session_id, player_id)
        if row["character_status"] != "confirmed" or not row["character_json"]:
            raise ConflictError(f"Player '{player_id}' does not have a confirmed character.")
        return CharacterState.from_dict(json.loads(row["character_json"]))

    @staticmethod
    def _save_character(
        connection: sqlite3.Connection, session_id: str, player_id: str, character: CharacterState
    ) -> None:
        connection.execute(
            "UPDATE players SET character_json = ? WHERE session_id = ? AND player_id = ?",
            (_json(character.to_dict()), session_id, player_id),
        )

    def update_player_identity(
        self,
        session_id: str,
        player_id: str,
        *,
        display_name: str | None = None,
        character_name: str | None = None,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Update public player-facing names without replacing character state.

        Character renames deliberately preserve the confirmed character, its
        resources, and all other sheet fields. This is narrower than a respec.
        """
        if display_name is None and character_name is None:
            raise ValidationError("At least one of display_name or character_name is required.")
        normalized_display_name = (
            require_text(display_name, "display_name") if display_name is not None else None
        )
        normalized_character_name = (
            require_text(character_name, "character_name") if character_name is not None else None
        )

        def change(connection: sqlite3.Connection) -> _Mutation:
            row = self._player_row(connection, session_id, player_id)
            resolved_display_name = normalized_display_name or row["display_name"]
            character = None
            if normalized_character_name is not None:
                if not row["character_json"]:
                    raise ConflictError(
                        f"Player '{player_id}' does not have a character to rename."
                    )
                character = CharacterState.from_dict(json.loads(row["character_json"]))
                character.name = normalized_character_name

            if normalized_display_name is not None:
                connection.execute(
                    "UPDATE players SET display_name = ? WHERE session_id = ? AND player_id = ?",
                    (normalized_display_name, session_id, player_id),
                )
            if character is not None:
                self._save_character(connection, session_id, player_id, character)

            public = {
                "player_id": player_id,
                "display_name": resolved_display_name,
                "character_status": row["character_status"],
            }
            if character is not None:
                public["character_name"] = character.name
            elif row["character_json"]:
                public["character_name"] = CharacterState.from_dict(
                    json.loads(row["character_json"])
                ).name
            return _Mutation(
                response=public,
                event_type="player_identity_updated",
                public_event=public,
                private_event={},
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"update_player_identity:{player_id}",
            request_payload={
                "player_id": player_id,
                "display_name": normalized_display_name,
                "character_name": normalized_character_name,
            },
            change=change,
        )

    def stage_character(
        self,
        session_id: str,
        player_id: str,
        *,
        character: Mapping[str, Any],
        source: str,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        source_key = normalize_key(source)
        if source_key not in {"created", "imported"}:
            raise ValidationError("character source must be 'created' or 'imported'.")
        character_state = CharacterState.from_dict(character)

        def change(connection: sqlite3.Connection) -> _Mutation:
            row = self._player_row(connection, session_id, player_id)
            if row["character_status"] == "confirmed":
                raise ConflictError("A confirmed character cannot be replaced without a dedicated respec flow.")
            connection.execute(
                """
                UPDATE players
                SET character_status = 'draft', character_source = ?, character_json = ?
                WHERE session_id = ? AND player_id = ?
                """,
                (source_key, _json(character_state.to_dict()), session_id, player_id),
            )
            public = {
                "player_id": player_id,
                "character_status": "draft",
                "character_source": source_key,
                "character": character_state.to_dict(),
            }
            return _Mutation(
                response=public,
                event_type="character_staged",
                public_event={
                    "player_id": player_id,
                    "character_status": "draft",
                    "character_source": source_key,
                    "character_name": character_state.name,
                },
                private_event={},
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"stage_character:{player_id}",
            request_payload={"player_id": player_id, "source": source_key, "character": character},
            change=change,
        )

    def confirm_character(
        self,
        session_id: str,
        player_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        def change(connection: sqlite3.Connection) -> _Mutation:
            row = self._player_row(connection, session_id, player_id)
            if row["character_status"] != "draft" or not row["character_json"]:
                raise ConflictError("Only a staged character can be confirmed.")
            character = CharacterState.from_dict(json.loads(row["character_json"]))
            connection.execute(
                """
                UPDATE players SET character_status = 'confirmed'
                WHERE session_id = ? AND player_id = ?
                """,
                (session_id, player_id),
            )
            public = {
                "player_id": player_id,
                "character_status": "confirmed",
                "character_source": row["character_source"],
                "character": character.to_dict(),
            }
            return _Mutation(
                response=public,
                event_type="character_confirmed",
                public_event=public,
                private_event={},
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"confirm_character:{player_id}",
            request_payload={"player_id": player_id},
            change=change,
        )

    @staticmethod
    def _carry_resource_usage(
        current: Mapping[str, ResourcePool],
        replacement: Mapping[str, ResourcePool],
    ) -> None:
        """Carry expended uses into a corrected rules profile.

        Profiles own each pool's new maximum. Existing play owns how many uses
        have already been spent. This lets a 2024 correction such as Second
        Wind 1 -> 2 become 2/2 when the old pool was full, or 1/2 when its one
        old use had already been spent.
        """

        for key, replacement_pool in replacement.items():
            current_pool = current.get(key)
            if current_pool is None:
                continue
            expended = current_pool.maximum - current_pool.current
            replacement_pool.current = max(0, replacement_pool.maximum - expended)

    def apply_character_rules_profile(
        self,
        session_id: str,
        player_id: str,
        *,
        profile: Mapping[str, Any],
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Enrich a confirmed sheet without turning the operation into a respec.

        The supplied profile may add rules-derived armor, attacks, features,
        spells, proficiencies, and inventory metadata. Class, level, ability
        scores, maximum HP, and Proficiency Bonus must match the confirmed
        character. Mutable play state is carried forward transactionally.
        """

        replacement = CharacterState.from_dict(profile)
        if replacement.ruleset_id == "manual":
            raise ValidationError("A rules profile must declare a versioned ruleset_id.")

        def change(connection: sqlite3.Connection) -> _Mutation:
            current = self._confirmed_character(connection, session_id, player_id)
            mismatches: list[str] = []
            if current.class_name.casefold() != replacement.class_name.casefold():
                mismatches.append("class_name")
            if current.level != replacement.level:
                mismatches.append("level")
            if current.abilities != replacement.abilities:
                mismatches.append("abilities")
            if current.max_hp != replacement.max_hp:
                mismatches.append("max_hp")
            if current.proficiency_bonus != replacement.proficiency_bonus:
                mismatches.append("proficiency_bonus")
            if current.ruleset_id not in {"manual", replacement.ruleset_id}:
                mismatches.append("ruleset_id")
            if mismatches:
                raise ConflictError(
                    "A rules profile cannot change core character choices; use a dedicated respec flow.",
                    mismatched_fields=mismatches,
                )

            replacement.character_id = current.character_id
            replacement.name = current.name
            replacement.hp = current.hp
            replacement.temp_hp = current.temp_hp
            replacement.heroic_inspiration = current.heroic_inspiration
            replacement.death_saves = current.death_saves
            replacement.conditions = list(current.conditions)
            replacement.currency = dict(current.currency)

            self._carry_resource_usage(current.hit_dice, replacement.hit_dice)
            self._carry_resource_usage(current.spell_slots, replacement.spell_slots)
            self._carry_resource_usage(current.class_resources, replacement.class_resources)

            current_items = {item.item_id: item for item in current.inventory}
            replacement_ids = {item.item_id for item in replacement.inventory}
            for item in replacement.inventory:
                prior = current_items.get(item.item_id)
                if prior is None:
                    continue
                item.quantity = prior.quantity
                item.equipped = prior.equipped
                item.notes = prior.notes
            replacement.inventory.extend(
                item for item in current.inventory if item.item_id not in replacement_ids
            )

            self._save_character(connection, session_id, player_id, replacement)
            public = {
                "player_id": player_id,
                "character_name": replacement.name,
                "ruleset_id": replacement.ruleset_id,
                "class_name": replacement.class_name,
                "subclass_name": replacement.subclass_name,
                "level": replacement.level,
                "armor_class": replacement.armor_class,
                "has_spellcasting": replacement.spellcasting is not None,
            }
            return _Mutation(
                response={**public, "character": replacement.to_dict()},
                event_type="character_rules_profile_applied",
                public_event=public,
                private_event={},
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"apply_character_rules_profile:{player_id}",
            request_payload={"player_id": player_id, "profile": profile},
            change=change,
        )

    def apply_damage(
        self,
        session_id: str,
        player_id: str,
        *,
        amount: int,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        damage = require_int(amount, "amount", minimum=1, maximum=9999)

        def change(connection: sqlite3.Connection) -> _Mutation:
            character = self._confirmed_character(connection, session_id, player_id)
            absorbed = min(character.temp_hp, damage)
            character.temp_hp -= absorbed
            hp_lost = min(character.hp, damage - absorbed)
            character.hp -= hp_lost
            self._save_character(connection, session_id, player_id, character)
            public = {
                "player_id": player_id,
                "amount": damage,
                "absorbed_by_temp_hp": absorbed,
                "hp_lost": hp_lost,
                "hp": character.hp,
                "max_hp": character.max_hp,
                "temp_hp": character.temp_hp,
            }
            return _Mutation(public, "damage_applied", public, {})

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"damage:{player_id}",
            request_payload={"player_id": player_id, "amount": damage},
            change=change,
        )

    def apply_healing(
        self,
        session_id: str,
        player_id: str,
        *,
        amount: int,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        healing = require_int(amount, "amount", minimum=1, maximum=9999)

        def change(connection: sqlite3.Connection) -> _Mutation:
            character = self._confirmed_character(connection, session_id, player_id)
            restored = min(healing, character.max_hp - character.hp)
            character.hp += restored
            self._save_character(connection, session_id, player_id, character)
            public = {
                "player_id": player_id,
                "amount": healing,
                "hp_restored": restored,
                "hp": character.hp,
                "max_hp": character.max_hp,
                "temp_hp": character.temp_hp,
            }
            return _Mutation(public, "healing_applied", public, {})

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"healing:{player_id}",
            request_payload={"player_id": player_id, "amount": healing},
            change=change,
        )

    def award_currency(
        self,
        session_id: str,
        player_id: str,
        *,
        amount: int,
        denomination: str,
        reason: str,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Commit a public monetary award to one confirmed character."""

        quantity = require_int(
            amount,
            "amount",
            minimum=1,
            maximum=CURRENCY_AWARD_MAXIMUM,
        )
        denomination_key = normalize_key(
            require_text(denomination, "denomination", maximum=10)
        )
        if denomination_key not in CURRENCY_DENOMINATIONS:
            raise ValidationError(
                f"denomination must be one of {sorted(CURRENCY_DENOMINATIONS)}."
            )
        public_reason = require_text(reason, "reason", maximum=500)

        def change(connection: sqlite3.Connection) -> _Mutation:
            character = self._confirmed_character(connection, session_id, player_id)
            previous_balance = character.currency[denomination_key]
            if previous_balance > CURRENCY_BALANCE_MAXIMUM - quantity:
                raise ConflictError(
                    f"The {denomination_key} balance cannot exceed "
                    f"{CURRENCY_BALANCE_MAXIMUM}."
                )
            balance = previous_balance + quantity
            character.currency[denomination_key] = balance
            self._save_character(connection, session_id, player_id, character)
            public = {
                "player_id": player_id,
                "character_name": character.name,
                "amount": quantity,
                "denomination": denomination_key,
                "balance": balance,
                "currency": dict(character.currency),
                "reason": public_reason,
            }
            return _Mutation(public, "currency_awarded", public, {})

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"award_currency:{player_id}",
            request_payload={
                "player_id": player_id,
                "amount": quantity,
                "denomination": denomination_key,
                "reason": public_reason,
            },
            change=change,
        )

    @staticmethod
    def _resource_pool(
        character: CharacterState, resource_type: str, resource_key: str
    ) -> tuple[dict[str, ResourcePool], str, str]:
        type_key = normalize_key(resource_type)
        if type_key == "spell_slot":
            try:
                slot_level = int(resource_key)
            except (TypeError, ValueError) as exc:
                raise ValidationError("A spell-slot resource key must be a level from 1 through 9.") from exc
            if slot_level < 1 or slot_level > 9:
                raise ValidationError("A spell-slot resource key must be a level from 1 through 9.")
            key = str(slot_level)
            pools = character.spell_slots
        elif type_key == "class_resource":
            key = normalize_key(resource_key)
            pools = character.class_resources
        elif type_key == "hit_die":
            key = normalize_key(resource_key)
            pools = character.hit_dice
        else:
            raise ValidationError("resource_type must be spell_slot, class_resource, or hit_die.")
        if key not in pools:
            raise NotFoundError(f"Character does not have {type_key} resource '{key}'.")
        return pools, type_key, key

    def change_resource(
        self,
        session_id: str,
        player_id: str,
        *,
        resource_type: str,
        resource_key: str,
        amount: int,
        restore: bool,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        quantity = require_int(amount, "amount", minimum=1, maximum=999)

        def change(connection: sqlite3.Connection) -> _Mutation:
            character = self._confirmed_character(connection, session_id, player_id)
            pools, type_key, key = self._resource_pool(character, resource_type, resource_key)
            pool = pools[key]
            if restore:
                changed = min(quantity, pool.maximum - pool.current)
                pool.current += changed
            else:
                if pool.current < quantity:
                    raise ConflictError(
                        f"Insufficient {type_key} '{key}'.",
                        available=pool.current,
                        requested=quantity,
                    )
                changed = quantity
                pool.current -= changed
            self._save_character(connection, session_id, player_id, character)
            public = {
                "player_id": player_id,
                "resource_type": type_key,
                "resource_key": key,
                "requested_amount": quantity,
                "changed_amount": changed,
                "current": pool.current,
                "maximum": pool.maximum,
            }
            event_type = "resource_restored" if restore else "resource_used"
            return _Mutation(public, event_type, public, {})

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"resource:{'restore' if restore else 'use'}:{player_id}",
            request_payload={
                "player_id": player_id,
                "resource_type": resource_type,
                "resource_key": resource_key,
                "amount": quantity,
            },
            change=change,
        )

    def request_roll(
        self,
        session_id: str,
        player_id: str,
        *,
        roll_kind: str,
        check_key: str | None,
        prompt: str,
        dc: int | None,
        engine_modifier: int | None,
        dc_visibility: str = "private",
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        kind = normalize_key(roll_kind)
        normalized_check = normalize_key(check_key) if check_key else kind
        prompt_text = require_text(prompt, "prompt", maximum=500)
        resolved_dc = None if dc is None else require_int(dc, "dc", minimum=1, maximum=50)
        if kind in BINARY_ROLL_KINDS and resolved_dc is None:
            raise ValidationError(
                f"A {kind} roll requires a difficulty class before dice are rolled."
            )
        supplied_modifier = (
            None
            if engine_modifier is None
            else require_int(engine_modifier, "engine_modifier", minimum=-30, maximum=30)
        )
        resolved_dc_visibility = normalize_key(
            require_text(dc_visibility, "dc_visibility", maximum=20)
        )
        if resolved_dc_visibility not in ROLL_DC_VISIBILITIES:
            raise ValidationError("dc_visibility must be public or private.")
        if resolved_dc_visibility == "public" and resolved_dc is None:
            raise ValidationError("A public roll target requires a difficulty class.")

        def change(connection: sqlite3.Connection) -> _Mutation:
            character = self._confirmed_character(connection, session_id, player_id)
            modifier = supplied_modifier
            if modifier is None:
                modifier = character.roll_modifier(kind, normalized_check)
            roll_id = str(uuid4())
            requested_at = _now()
            connection.execute(
                """
                INSERT INTO pending_rolls (
                    roll_id, session_id, player_id, roll_kind, check_key, prompt,
                    modifier, dc, dc_visibility, requested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    roll_id,
                    session_id,
                    player_id,
                    kind,
                    normalized_check,
                    prompt_text,
                    modifier,
                    resolved_dc,
                    resolved_dc_visibility,
                    requested_at,
                ),
            )
            public = {
                "roll_id": roll_id,
                "player_id": player_id,
                "roll_kind": kind,
                "check_key": normalized_check,
                "prompt": prompt_text,
                "dc_visibility": resolved_dc_visibility,
                "requested_at": requested_at,
            }
            if resolved_dc_visibility == "public":
                public["target_total"] = resolved_dc
            return _Mutation(
                response={"pending_roll": public},
                event_type="physical_roll_requested",
                public_event=public,
                private_event={
                    "roll_id": roll_id,
                    "modifier": modifier,
                    "dc": resolved_dc,
                    "dc_visibility": resolved_dc_visibility,
                },
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"request_roll:{player_id}",
            request_payload={
                "player_id": player_id,
                "roll_kind": kind,
                "check_key": normalized_check,
                "prompt": prompt_text,
                "dc": resolved_dc,
                "engine_modifier": supplied_modifier,
                "dc_visibility": resolved_dc_visibility,
            },
            change=change,
        )

    def submit_roll(
        self,
        session_id: str,
        roll_id: str,
        player_id: str,
        *,
        raw_d20: int,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        natural_roll = require_int(raw_d20, "natural_roll", minimum=1, maximum=20)

        def change(connection: sqlite3.Connection) -> _Mutation:
            row = connection.execute(
                "SELECT * FROM pending_rolls WHERE session_id = ? AND roll_id = ?",
                (session_id, roll_id),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Roll '{roll_id}' was not found in session '{session_id}'.")
            if row["resolved_at"] is not None:
                raise ConflictError(f"Roll '{roll_id}' was already resolved.")
            if row["player_id"] != player_id:
                raise ConflictError("Only the requested player can submit this physical roll.")
            total = natural_roll + int(row["modifier"])
            success = None if row["dc"] is None else total >= int(row["dc"])
            resolved_at = _now()
            connection.execute(
                """
                UPDATE pending_rolls
                SET raw_d20 = ?, total = ?, success = ?, resolved_at = ?
                WHERE roll_id = ?
                """,
                (
                    natural_roll,
                    total,
                    None if success is None else int(success),
                    resolved_at,
                    roll_id,
                ),
            )
            public = {
                "roll_id": roll_id,
                "player_id": player_id,
                "roll_kind": row["roll_kind"],
                "check_key": row["check_key"],
                "natural_roll": natural_roll,
                "total": total,
                "success": success,
                "dc_visibility": row["dc_visibility"],
                "natural_20": natural_roll == 20,
                "natural_1": natural_roll == 1,
                "resolved_at": resolved_at,
            }
            if row["dc_visibility"] == "public" and row["dc"] is not None:
                public["target_total"] = row["dc"]
            return _Mutation(
                response={"roll_result": public},
                event_type="physical_roll_submitted",
                public_event=public,
                private_event={
                    "roll_id": roll_id,
                    "modifier": row["modifier"],
                    "dc": row["dc"],
                    "success": success,
                    "dc_visibility": row["dc_visibility"],
                },
            )

        return self._mutate(
            session_id=session_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            operation=f"submit_roll:{roll_id}",
            request_payload={"roll_id": roll_id, "player_id": player_id, "natural_roll": natural_roll},
            change=change,
        )
