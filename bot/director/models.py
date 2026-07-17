"""Private, immutable campaign definitions used by the server-side Director."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CampaignOpening:
    public: str
    prompt: str


@dataclass(frozen=True)
class CampaignClock:
    clock_id: str
    label: str
    current: int
    maximum: int
    visibility: str
    advance_on: tuple[str, ...]
    at_maximum: str


@dataclass(frozen=True)
class CampaignFact:
    """Canonical fact. ``private_truth`` must never be projected before reveal."""

    fact_id: str
    visibility: str
    private_truth: str
    reveal_conditions: tuple[str, ...]
    safe_performance_cue: str | None = None


@dataclass(frozen=True)
class RelationshipTrigger:
    event: str
    deltas: Mapping[str, int]


@dataclass(frozen=True)
class NpcDefinition:
    npc_id: str
    name: str
    role: str
    public_description: str
    initial_relationship: Mapping[str, int]
    goals: tuple[str, ...]
    private_motive_ids: tuple[str, ...]
    knows_fact_ids: tuple[str, ...]
    knowledge_limits: tuple[str, ...]
    relationship_triggers: tuple[RelationshipTrigger, ...]
    voice_direction: str


@dataclass(frozen=True)
class CheckDefinition:
    check_id: str
    ability: str
    skill: str
    private_dc: int
    dc_visibility: str
    success: str
    fail_forward: str


@dataclass(frozen=True)
class ClueDefinition:
    clue_id: str
    find_when: str
    counts_toward: str | None = None


@dataclass(frozen=True)
class FinalChoiceDefinition:
    choice_id: str
    description: str
    cost: str
    ending: str


@dataclass(frozen=True)
class SceneDefinition:
    scene_id: str
    title: str
    public_goal: str
    entry_description: str
    available_npc_ids: tuple[str, ...]
    player_approaches: tuple[str, ...]
    checks: Mapping[str, CheckDefinition]
    clues: Mapping[str, ClueDefinition]
    exit_conditions: tuple[str, ...]
    next_scene_ids: tuple[str, ...]
    automatic_reveals: tuple[str, ...]
    final_choices: tuple[FinalChoiceDefinition, ...]
    agency_rule: str | None = None


@dataclass(frozen=True)
class DmContract:
    style: tuple[str, ...]
    turn_pattern: tuple[str, ...]
    never: tuple[str, ...]
    roll_policy: str
    fail_forward_policy: str


@dataclass(frozen=True)
class Campaign:
    """The complete canonical campaign, including private server-only material."""

    schema_version: int
    campaign_id: str
    title: str
    tagline: str
    target_minutes: int
    recommended_level: int
    player_count: int
    rules_baseline: str
    tone: tuple[str, ...]
    content_notes: tuple[str, ...]
    opening: CampaignOpening
    clocks: Mapping[str, CampaignClock]
    facts: Mapping[str, CampaignFact]
    npcs: Mapping[str, NpcDefinition]
    scenes: Mapping[str, SceneDefinition]
    scene_order: tuple[str, ...]
    dm_contract: DmContract

    @property
    def start_scene_id(self) -> str:
        return self.scene_order[0]

    def get_scene(self, scene_id: str) -> SceneDefinition:
        return self.scenes[scene_id]

    def get_fact(self, fact_id: str) -> CampaignFact:
        return self.facts[fact_id]

    def get_npc(self, npc_id: str) -> NpcDefinition:
        return self.npcs[npc_id]


JsonObject = Mapping[str, Any]
