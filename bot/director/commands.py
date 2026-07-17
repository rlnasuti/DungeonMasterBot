"""Side-effect-free command values proposed by the Director."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

from bot.director.errors import DirectorError
from bot.director.models import Campaign


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DirectorError(f"{field_name} must be a non-empty string")
    return value.strip()


def _version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DirectorError("expected_state_version must be a non-negative integer")
    return value


@dataclass(frozen=True, kw_only=True)
class TransitionSceneCommand:
    session_id: str
    expected_state_version: int
    idempotency_key: str
    from_scene_id: str
    to_scene_id: str
    reason_event_id: str


@dataclass(frozen=True, kw_only=True)
class AdjustNpcRelationshipCommand:
    session_id: str
    expected_state_version: int
    idempotency_key: str
    npc_id: str
    deltas: Mapping[str, int]
    reason_event_id: str


@dataclass(frozen=True, kw_only=True)
class RecordClueCommand:
    session_id: str
    expected_state_version: int
    idempotency_key: str
    clue_id: str
    source_event_id: str


@dataclass(frozen=True, kw_only=True)
class RecordRevealCommand:
    session_id: str
    expected_state_version: int
    idempotency_key: str
    fact_id: str
    satisfied_gate_id: str


@dataclass(frozen=True, kw_only=True)
class RequestRollCommand:
    """A public roll request; the canonical check DC intentionally stays absent."""

    session_id: str
    expected_state_version: int
    idempotency_key: str
    roll_id: str
    player_id: str
    scene_id: str
    check_id: str
    ability: str
    skill: str
    public_reason: str
    die: str = "d20"


DirectorCommand: TypeAlias = (
    TransitionSceneCommand
    | AdjustNpcRelationshipCommand
    | RecordClueCommand
    | RecordRevealCommand
    | RequestRollCommand
)


class CommandFactory:
    """Validate proposals against campaign identity without changing game state."""

    def __init__(self, campaign: Campaign) -> None:
        self._campaign = campaign

    @staticmethod
    def _common(session_id: str, expected_state_version: int, idempotency_key: str) -> dict[str, object]:
        return {
            "session_id": _required_text(session_id, "session_id"),
            "expected_state_version": _version(expected_state_version),
            "idempotency_key": _required_text(idempotency_key, "idempotency_key"),
        }

    def transition_scene(
        self,
        *,
        session_id: str,
        expected_state_version: int,
        idempotency_key: str,
        from_scene_id: str,
        to_scene_id: str,
        reason_event_id: str,
    ) -> TransitionSceneCommand:
        source = self._campaign.scenes.get(from_scene_id)
        if source is None or to_scene_id not in self._campaign.scenes:
            raise DirectorError("scene transition references an unknown scene")
        if to_scene_id not in source.next_scene_ids:
            raise DirectorError(f"scene '{to_scene_id}' is not an allowed transition from '{from_scene_id}'")
        return TransitionSceneCommand(
            **self._common(session_id, expected_state_version, idempotency_key),
            from_scene_id=from_scene_id,
            to_scene_id=to_scene_id,
            reason_event_id=_required_text(reason_event_id, "reason_event_id"),
        )

    def adjust_npc_relationship(
        self,
        *,
        session_id: str,
        expected_state_version: int,
        idempotency_key: str,
        npc_id: str,
        deltas: Mapping[str, int],
        reason_event_id: str,
    ) -> AdjustNpcRelationshipCommand:
        npc = self._campaign.npcs.get(npc_id)
        if npc is None:
            raise DirectorError(f"unknown NPC '{npc_id}'")
        if not isinstance(deltas, Mapping) or not deltas:
            raise DirectorError("relationship deltas must be a non-empty mapping")
        normalized: dict[str, int] = {}
        for axis, delta in deltas.items():
            if axis not in npc.initial_relationship:
                raise DirectorError(f"unknown relationship axis '{axis}' for NPC '{npc_id}'")
            if isinstance(delta, bool) or not isinstance(delta, int) or delta == 0:
                raise DirectorError(f"relationship delta '{axis}' must be a non-zero integer")
            normalized[axis] = delta
        return AdjustNpcRelationshipCommand(
            **self._common(session_id, expected_state_version, idempotency_key),
            npc_id=npc_id,
            deltas=MappingProxyType(normalized),
            reason_event_id=_required_text(reason_event_id, "reason_event_id"),
        )

    def record_clue(
        self,
        *,
        session_id: str,
        expected_state_version: int,
        idempotency_key: str,
        clue_id: str,
        source_event_id: str,
    ) -> RecordClueCommand:
        return RecordClueCommand(
            **self._common(session_id, expected_state_version, idempotency_key),
            clue_id=_required_text(clue_id, "clue_id"),
            source_event_id=_required_text(source_event_id, "source_event_id"),
        )

    def record_reveal(
        self,
        *,
        session_id: str,
        expected_state_version: int,
        idempotency_key: str,
        fact_id: str,
        satisfied_gate_id: str,
    ) -> RecordRevealCommand:
        fact = self._campaign.facts.get(fact_id)
        if fact is None:
            raise DirectorError(f"unknown fact '{fact_id}'")
        gate_id = _required_text(satisfied_gate_id, "satisfied_gate_id")
        automatic_scene = self._campaign.scenes.get(gate_id.removeprefix("scene:")) \
            if gate_id.startswith("scene:") else None
        automatic_gate = bool(automatic_scene and fact_id in automatic_scene.automatic_reveals)
        if fact.visibility != "public" and gate_id not in fact.reveal_conditions and not automatic_gate:
            raise DirectorError(f"gate '{gate_id}' cannot reveal fact '{fact_id}'")
        return RecordRevealCommand(
            **self._common(session_id, expected_state_version, idempotency_key),
            fact_id=fact_id,
            satisfied_gate_id=gate_id,
        )

    def request_roll(
        self,
        *,
        session_id: str,
        expected_state_version: int,
        idempotency_key: str,
        roll_id: str,
        player_id: str,
        scene_id: str,
        check_id: str,
        public_reason: str,
    ) -> RequestRollCommand:
        scene = self._campaign.scenes.get(scene_id)
        check = scene.checks.get(check_id) if scene else None
        if check is None:
            raise DirectorError(f"unknown check '{check_id}' in scene '{scene_id}'")
        return RequestRollCommand(
            **self._common(session_id, expected_state_version, idempotency_key),
            roll_id=_required_text(roll_id, "roll_id"),
            player_id=_required_text(player_id, "player_id"),
            scene_id=scene_id,
            check_id=check_id,
            ability=check.ability,
            skill=check.skill,
            public_reason=_required_text(public_reason, "public_reason"),
        )
