"""Pure reveal-gate evaluation over committed event and clue identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bot.director.models import Campaign


@dataclass(frozen=True)
class RevealEvaluation:
    satisfied_gate_ids: frozenset[str]
    revealable_fact_ids: frozenset[str]


def evaluate_reveal_gates(
    campaign: Campaign,
    *,
    committed_event_ids: Iterable[str] = (),
    committed_clue_ids: Iterable[str] = (),
    current_scene_id: str | None = None,
    already_revealed_fact_ids: Iterable[str] = (),
) -> RevealEvaluation:
    """Return gates and facts made eligible by already-committed state.

    Direct gates are satisfied by a matching committed event or clue ID. A
    composite clue gate is satisfied only after every clue explicitly marked
    ``counts_toward`` that gate has been committed. This function never records
    the reveal; the caller must persist a ``RecordRevealCommand`` separately.
    """

    events = frozenset(str(event_id) for event_id in committed_event_ids)
    clues = frozenset(str(clue_id) for clue_id in committed_clue_ids)
    satisfied = set(events | clues)

    clue_groups: dict[str, set[str]] = {}
    for scene in campaign.scenes.values():
        for clue in scene.clues.values():
            if clue.counts_toward:
                clue_groups.setdefault(clue.counts_toward, set()).add(clue.clue_id)
    for gate_id, required_clues in clue_groups.items():
        if required_clues and required_clues.issubset(clues):
            satisfied.add(gate_id)

    revealable = {
        fact_id
        for fact_id in already_revealed_fact_ids
        if fact_id in campaign.facts
    }
    revealable.update(
        fact.fact_id for fact in campaign.facts.values() if fact.visibility == "public"
    )
    for fact in campaign.facts.values():
        if any(condition in satisfied for condition in fact.reveal_conditions):
            revealable.add(fact.fact_id)

    if current_scene_id is not None:
        scene = campaign.scenes.get(current_scene_id)
        if scene is not None:
            revealable.update(scene.automatic_reveals)

    return RevealEvaluation(
        satisfied_gate_ids=frozenset(satisfied),
        revealable_fact_ids=frozenset(revealable),
    )
