"""Least-privilege projections for the voice performer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from bot.director.errors import ProjectionError
from bot.director.models import Campaign, NpcDefinition


@dataclass(frozen=True)
class ProjectionContext:
    scene_id: str
    revealed_fact_ids: frozenset[str] = field(default_factory=frozenset)
    present_npc_ids: tuple[str, ...] | None = None
    npc_relationships: Mapping[str, Mapping[str, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class CampaignStartBrief:
    campaign_id: str
    title: str
    tagline: str
    target_minutes: int
    recommended_level: int
    player_count: int
    tone: tuple[str, ...]
    content_notes: tuple[str, ...]
    opening_description: str
    opening_prompt: str
    style: tuple[str, ...]
    turn_pattern: tuple[str, ...]
    roll_policy: str
    fail_forward_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "title": self.title,
            "tagline": self.tagline,
            "target_minutes": self.target_minutes,
            "recommended_level": self.recommended_level,
            "player_count": self.player_count,
            "tone": list(self.tone),
            "content_notes": list(self.content_notes),
            "opening": {
                "description": self.opening_description,
                "prompt": self.opening_prompt,
            },
            "performance_contract": {
                "style": list(self.style),
                "turn_pattern": list(self.turn_pattern),
                "roll_policy": self.roll_policy,
                "fail_forward_policy": self.fail_forward_policy,
            },
        }


@dataclass(frozen=True)
class NpcPerformerBrief:
    npc_id: str
    name: str
    role: str
    public_description: str
    voice_direction: str
    behavior_cues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "role": self.role,
            "public_description": self.public_description,
            "voice_direction": self.voice_direction,
            "behavior_cues": list(self.behavior_cues),
        }


@dataclass(frozen=True)
class PublicFactBrief:
    fact_id: str
    public_statement: str

    def to_dict(self) -> dict[str, str]:
        # Internal fact and motive identifiers are not performer-facing, even
        # after the statement itself becomes public.
        return {"public_statement": self.public_statement}


@dataclass(frozen=True)
class DecisionOptionBrief:
    description: str
    cost: str

    def to_dict(self) -> dict[str, str]:
        # End-state prose stays server-side; the performer receives only the
        # choice and its immediate, player-facing cost.
        return {"description": self.description, "cost": self.cost}


@dataclass(frozen=True)
class PerformerBrief:
    campaign_id: str
    campaign_title: str
    scene_id: str
    scene_title: str
    public_goal: str
    entry_description: str
    npcs: tuple[NpcPerformerBrief, ...]
    revealed_facts: tuple[PublicFactBrief, ...]
    decision_options: tuple[DecisionOptionBrief, ...]
    agency_rule: str | None
    style: tuple[str, ...]
    turn_pattern: tuple[str, ...]
    roll_policy: str
    fail_forward_policy: str

    def to_dict(self) -> dict[str, Any]:
        current_scene: dict[str, Any] = {
            "id": self.scene_id,
            "title": self.scene_title,
            "public_goal": self.public_goal,
            "entry_description": self.entry_description,
        }
        if self.decision_options:
            current_scene["decision_options"] = [
                option.to_dict() for option in self.decision_options
            ]
        if self.agency_rule:
            current_scene["agency_rule"] = self.agency_rule

        return {
            "campaign": {
                "id": self.campaign_id,
                "title": self.campaign_title,
            },
            "current_scene": current_scene,
            "npcs": [npc.to_dict() for npc in self.npcs],
            "revealed_facts": [fact.to_dict() for fact in self.revealed_facts],
            "performance_contract": {
                "style": list(self.style),
                "turn_pattern": list(self.turn_pattern),
                "roll_policy": self.roll_policy,
                "fail_forward_policy": self.fail_forward_policy,
            },
        }


def _relationship_cues(npc: NpcDefinition, relationship: Mapping[str, int]) -> list[str]:
    values = dict(npc.initial_relationship)
    values.update({key: int(value) for key, value in relationship.items()})
    cues: list[str] = []
    trust = values.get("trust", 0)
    suspicion = values.get("suspicion", 0)
    fear = values.get("fear", 0)
    respect = values.get("respect", 0)

    if trust >= 2:
        cues.append("Open and cooperative; volunteer useful details that are already public.")
    elif trust < 0:
        cues.append("Cool and reluctant; require reassurance before cooperating.")
    if suspicion >= 2:
        cues.append("Guarded and watchful; ask what the adventurers intend before answering.")
    if fear >= 2:
        cues.append("Let visible anxiety shorten sentences without making the character helpless.")
    if respect >= 2:
        cues.append("Treat the adventurers as capable peers and take their plan seriously.")
    return cues


def _npc_brief(
    campaign: Campaign,
    npc: NpcDefinition,
    relationship: Mapping[str, int],
) -> NpcPerformerBrief:
    cues = _relationship_cues(npc, relationship)
    for fact_id in npc.knows_fact_ids:
        safe_cue = campaign.facts[fact_id].safe_performance_cue
        if safe_cue and safe_cue not in cues:
            cues.append(safe_cue)
    return NpcPerformerBrief(
        npc_id=npc.npc_id,
        name=npc.name,
        role=npc.role,
        public_description=npc.public_description,
        voice_direction=npc.voice_direction,
        behavior_cues=tuple(cues),
    )


def build_safe_campaign_start_brief(campaign: Campaign) -> CampaignStartBrief:
    """Return the campaign setup with no scenes, checks, motives, or facts."""

    return CampaignStartBrief(
        campaign_id=campaign.campaign_id,
        title=campaign.title,
        tagline=campaign.tagline,
        target_minutes=campaign.target_minutes,
        recommended_level=campaign.recommended_level,
        player_count=campaign.player_count,
        tone=campaign.tone,
        content_notes=campaign.content_notes,
        opening_description=campaign.opening.public,
        opening_prompt=campaign.opening.prompt,
        style=campaign.dm_contract.style,
        turn_pattern=campaign.dm_contract.turn_pattern,
        roll_policy=campaign.dm_contract.roll_policy,
        fail_forward_policy=campaign.dm_contract.fail_forward_policy,
    )


def build_performer_brief(campaign: Campaign, context: ProjectionContext) -> PerformerBrief:
    """Project only the scene-local information a voice performer may know."""

    scene = campaign.scenes.get(context.scene_id)
    if scene is None:
        raise ProjectionError(f"unknown current scene '{context.scene_id}'")

    unknown_facts = set(context.revealed_fact_ids) - set(campaign.facts)
    if unknown_facts:
        raise ProjectionError(f"projection references unknown revealed facts: {sorted(unknown_facts)}")

    available_npc_ids = set(scene.available_npc_ids)
    present_npc_ids = (
        scene.available_npc_ids
        if context.present_npc_ids is None
        else context.present_npc_ids
    )
    disallowed_npcs = set(present_npc_ids) - available_npc_ids
    if disallowed_npcs:
        raise ProjectionError(
            f"NPCs are not available in scene '{scene.scene_id}': {sorted(disallowed_npcs)}"
        )

    revealed_ids = set(context.revealed_fact_ids)
    # Reaching a scene is itself the committed gate for its automatic reveals.
    revealed_ids.update(scene.automatic_reveals)
    revealed_facts = tuple(
        PublicFactBrief(fact_id=fact_id, public_statement=campaign.facts[fact_id].private_truth)
        for fact_id in campaign.facts
        if fact_id in revealed_ids
    )

    npc_briefs = tuple(
        _npc_brief(
            campaign,
            campaign.npcs[npc_id],
            context.npc_relationships.get(npc_id, {}),
        )
        for npc_id in present_npc_ids
    )

    return PerformerBrief(
        campaign_id=campaign.campaign_id,
        campaign_title=campaign.title,
        scene_id=scene.scene_id,
        scene_title=scene.title,
        public_goal=scene.public_goal,
        entry_description=scene.entry_description,
        npcs=npc_briefs,
        revealed_facts=revealed_facts,
        decision_options=tuple(
            DecisionOptionBrief(description=choice.description, cost=choice.cost)
            for choice in scene.final_choices
        ),
        agency_rule=scene.agency_rule,
        style=campaign.dm_contract.style,
        turn_pattern=campaign.dm_contract.turn_pattern,
        roll_policy=campaign.dm_contract.roll_policy,
        fail_forward_policy=campaign.dm_contract.fail_forward_policy,
    )
