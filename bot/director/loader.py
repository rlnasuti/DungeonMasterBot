"""Load and validate immutable campaign definitions from JSON."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from bot.director.errors import CampaignValidationError
from bot.director.models import (
    Campaign,
    CampaignClock,
    CampaignFact,
    CampaignOpening,
    CheckDefinition,
    ClueDefinition,
    DmContract,
    FinalChoiceDefinition,
    NpcDefinition,
    RelationshipTrigger,
    SceneDefinition,
)


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CampaignValidationError(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise CampaignValidationError(f"{path} must be an array")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CampaignValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CampaignValidationError(f"{path} must be an integer of at least {minimum}")
    return value


def _strings(value: Any, path: str, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    return tuple(_text(item, f"{path}[{index}]") for index, item in enumerate(_array(value, path)))


def _unique_id(value: Any, path: str, seen: set[str]) -> str:
    identifier = _text(value, path)
    if identifier in seen:
        raise CampaignValidationError(f"{path} duplicates id '{identifier}'")
    seen.add(identifier)
    return identifier


def _freeze(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(values))


def _load_clocks(raw: Any) -> Mapping[str, CampaignClock]:
    clocks: dict[str, CampaignClock] = {}
    seen: set[str] = set()
    for index, item in enumerate(_array(raw, "clocks")):
        path = f"clocks[{index}]"
        value = _object(item, path)
        clock_id = _unique_id(value.get("id"), f"{path}.id", seen)
        maximum = _integer(value.get("maximum"), f"{path}.maximum", minimum=1)
        current = _integer(value.get("current"), f"{path}.current")
        if current > maximum:
            raise CampaignValidationError(f"{path}.current cannot exceed maximum")
        clocks[clock_id] = CampaignClock(
            clock_id=clock_id,
            label=_text(value.get("label"), f"{path}.label"),
            current=current,
            maximum=maximum,
            visibility=_text(value.get("visibility"), f"{path}.visibility"),
            advance_on=_strings(value.get("advance_on"), f"{path}.advance_on"),
            at_maximum=_text(value.get("at_maximum"), f"{path}.at_maximum"),
        )
    return _freeze(clocks)


def _load_facts(raw: Any) -> Mapping[str, CampaignFact]:
    facts: dict[str, CampaignFact] = {}
    seen: set[str] = set()
    for index, item in enumerate(_array(raw, "facts")):
        path = f"facts[{index}]"
        value = _object(item, path)
        fact_id = _unique_id(value.get("id"), f"{path}.id", seen)
        visibility = _text(value.get("visibility"), f"{path}.visibility")
        if visibility not in {"private", "public"}:
            raise CampaignValidationError(f"{path}.visibility must be private or public")
        reveal_conditions = _strings(value.get("reveal_conditions"), f"{path}.reveal_conditions")
        if visibility == "private" and not reveal_conditions:
            raise CampaignValidationError(f"{path} requires at least one reveal condition")
        safe_cue = value.get("safe_performance_cue")
        if safe_cue is not None:
            safe_cue = _text(safe_cue, f"{path}.safe_performance_cue")
        facts[fact_id] = CampaignFact(
            fact_id=fact_id,
            visibility=visibility,
            private_truth=_text(value.get("truth"), f"{path}.truth"),
            reveal_conditions=reveal_conditions,
            safe_performance_cue=safe_cue,
        )
    return _freeze(facts)


def _load_npcs(raw: Any) -> Mapping[str, NpcDefinition]:
    npcs: dict[str, NpcDefinition] = {}
    seen: set[str] = set()
    for index, item in enumerate(_array(raw, "npcs")):
        path = f"npcs[{index}]"
        value = _object(item, path)
        npc_id = _unique_id(value.get("id"), f"{path}.id", seen)

        relationship_raw = _object(value.get("initial_relationship"), f"{path}.initial_relationship")
        relationship: dict[str, int] = {}
        for key, raw_score in relationship_raw.items():
            relationship[_text(key, f"{path}.initial_relationship key")] = _integer(
                raw_score,
                f"{path}.initial_relationship.{key}",
            )

        triggers: list[RelationshipTrigger] = []
        for trigger_index, trigger_item in enumerate(_array(value.get("relationship_triggers", []), f"{path}.relationship_triggers")):
            trigger_path = f"{path}.relationship_triggers[{trigger_index}]"
            trigger = _object(trigger_item, trigger_path)
            deltas: dict[str, int] = {}
            for raw_key, raw_delta in trigger.items():
                if raw_key == "event":
                    continue
                if not raw_key.endswith("_delta"):
                    raise CampaignValidationError(f"{trigger_path}.{raw_key} must be a *_delta field")
                if isinstance(raw_delta, bool) or not isinstance(raw_delta, int):
                    raise CampaignValidationError(f"{trigger_path}.{raw_key} must be an integer")
                deltas[raw_key.removesuffix("_delta")] = raw_delta
            triggers.append(RelationshipTrigger(
                event=_text(trigger.get("event"), f"{trigger_path}.event"),
                deltas=_freeze(deltas),
            ))

        npcs[npc_id] = NpcDefinition(
            npc_id=npc_id,
            name=_text(value.get("name"), f"{path}.name"),
            role=_text(value.get("role"), f"{path}.role"),
            public_description=_text(value.get("public_description"), f"{path}.public_description"),
            initial_relationship=_freeze(relationship),
            goals=_strings(value.get("goals"), f"{path}.goals"),
            private_motive_ids=_strings(value.get("private_motive_ids"), f"{path}.private_motive_ids"),
            knows_fact_ids=_strings(value.get("knows_fact_ids"), f"{path}.knows_fact_ids"),
            knowledge_limits=_strings(value.get("knowledge_limits"), f"{path}.knowledge_limits"),
            relationship_triggers=tuple(triggers),
            voice_direction=_text(value.get("voice_direction"), f"{path}.voice_direction"),
        )
    return _freeze(npcs)


def _load_scenes(raw: Any) -> tuple[Mapping[str, SceneDefinition], tuple[str, ...]]:
    scenes: dict[str, SceneDefinition] = {}
    scene_order: list[str] = []
    seen_scene_ids: set[str] = set()
    seen_check_ids: set[str] = set()
    seen_clue_ids: set[str] = set()

    for index, item in enumerate(_array(raw, "scenes")):
        path = f"scenes[{index}]"
        value = _object(item, path)
        scene_id = _unique_id(value.get("id"), f"{path}.id", seen_scene_ids)
        scene_order.append(scene_id)

        checks: dict[str, CheckDefinition] = {}
        for check_index, check_item in enumerate(_array(value.get("checks", []), f"{path}.checks")):
            check_path = f"{path}.checks[{check_index}]"
            check = _object(check_item, check_path)
            check_id = _unique_id(check.get("id"), f"{check_path}.id", seen_check_ids)
            dc_visibility = _text(
                check.get("dc_visibility"), f"{check_path}.dc_visibility"
            )
            if dc_visibility not in {"private", "public"}:
                raise CampaignValidationError(
                    f"{check_path}.dc_visibility must be private or public"
                )
            checks[check_id] = CheckDefinition(
                check_id=check_id,
                ability=_text(check.get("ability"), f"{check_path}.ability"),
                skill=_text(check.get("skill"), f"{check_path}.skill"),
                private_dc=_integer(check.get("dc"), f"{check_path}.dc", minimum=1),
                dc_visibility=dc_visibility,
                success=_text(check.get("success"), f"{check_path}.success"),
                fail_forward=_text(check.get("fail_forward"), f"{check_path}.fail_forward"),
            )

        clues: dict[str, ClueDefinition] = {}
        for clue_index, clue_item in enumerate(_array(value.get("clues", []), f"{path}.clues")):
            clue_path = f"{path}.clues[{clue_index}]"
            clue = _object(clue_item, clue_path)
            clue_id = _unique_id(clue.get("id"), f"{clue_path}.id", seen_clue_ids)
            counts_toward = clue.get("counts_toward")
            if counts_toward is not None:
                counts_toward = _text(counts_toward, f"{clue_path}.counts_toward")
            clues[clue_id] = ClueDefinition(
                clue_id=clue_id,
                find_when=_text(clue.get("find_when"), f"{clue_path}.find_when"),
                counts_toward=counts_toward,
            )

        final_choices: list[FinalChoiceDefinition] = []
        seen_choice_ids: set[str] = set()
        for choice_index, choice_item in enumerate(_array(value.get("final_choices", []), f"{path}.final_choices")):
            choice_path = f"{path}.final_choices[{choice_index}]"
            choice = _object(choice_item, choice_path)
            choice_id = _unique_id(choice.get("id"), f"{choice_path}.id", seen_choice_ids)
            final_choices.append(FinalChoiceDefinition(
                choice_id=choice_id,
                description=_text(choice.get("description"), f"{choice_path}.description"),
                cost=_text(choice.get("cost"), f"{choice_path}.cost"),
                ending=_text(choice.get("ending"), f"{choice_path}.ending"),
            ))

        agency_rule = value.get("agency_rule")
        if agency_rule is not None:
            agency_rule = _text(agency_rule, f"{path}.agency_rule")
        scenes[scene_id] = SceneDefinition(
            scene_id=scene_id,
            title=_text(value.get("title"), f"{path}.title"),
            public_goal=_text(value.get("public_goal"), f"{path}.public_goal"),
            entry_description=_text(value.get("entry_description"), f"{path}.entry_description"),
            available_npc_ids=_strings(value.get("available_npc_ids"), f"{path}.available_npc_ids"),
            player_approaches=_strings(value.get("player_approaches"), f"{path}.player_approaches"),
            checks=_freeze(checks),
            clues=_freeze(clues),
            exit_conditions=_strings(value.get("exit_conditions"), f"{path}.exit_conditions"),
            next_scene_ids=_strings(value.get("next_scene_ids"), f"{path}.next_scene_ids"),
            automatic_reveals=_strings(value.get("automatic_reveals"), f"{path}.automatic_reveals"),
            final_choices=tuple(final_choices),
            agency_rule=agency_rule,
        )
    if not scene_order:
        raise CampaignValidationError("scenes must contain at least one scene")
    return _freeze(scenes), tuple(scene_order)


def _validate_references(campaign: Campaign) -> None:
    fact_ids = set(campaign.facts)
    npc_ids = set(campaign.npcs)
    scene_ids = set(campaign.scenes)

    for npc in campaign.npcs.values():
        unknown_facts = (set(npc.knows_fact_ids) | set(npc.private_motive_ids)) - fact_ids
        if unknown_facts:
            raise CampaignValidationError(f"npc '{npc.npc_id}' references unknown facts: {sorted(unknown_facts)}")

    for scene in campaign.scenes.values():
        unknown_npcs = set(scene.available_npc_ids) - npc_ids
        if unknown_npcs:
            raise CampaignValidationError(f"scene '{scene.scene_id}' references unknown NPCs: {sorted(unknown_npcs)}")
        unknown_scenes = set(scene.next_scene_ids) - scene_ids
        if unknown_scenes:
            raise CampaignValidationError(f"scene '{scene.scene_id}' references unknown next scenes: {sorted(unknown_scenes)}")
        unknown_facts = set(scene.automatic_reveals) - fact_ids
        if unknown_facts:
            raise CampaignValidationError(f"scene '{scene.scene_id}' automatically reveals unknown facts: {sorted(unknown_facts)}")


def campaign_from_dict(raw: Any) -> Campaign:
    """Validate parsed JSON and return the private canonical campaign."""

    value = _object(raw, "campaign")
    schema_version = _integer(value.get("schema_version"), "schema_version", minimum=1)
    if schema_version != 1:
        raise CampaignValidationError(f"unsupported campaign schema_version {schema_version}")

    opening_raw = _object(value.get("opening"), "opening")
    dm_raw = _object(value.get("dm_contract"), "dm_contract")
    scenes, scene_order = _load_scenes(value.get("scenes"))
    campaign = Campaign(
        schema_version=schema_version,
        campaign_id=_text(value.get("id"), "id"),
        title=_text(value.get("title"), "title"),
        tagline=_text(value.get("tagline"), "tagline"),
        target_minutes=_integer(value.get("target_minutes"), "target_minutes", minimum=1),
        recommended_level=_integer(value.get("recommended_level"), "recommended_level", minimum=1),
        player_count=_integer(value.get("player_count"), "player_count", minimum=1),
        rules_baseline=_text(value.get("rules_baseline"), "rules_baseline"),
        tone=_strings(value.get("tone"), "tone"),
        content_notes=_strings(value.get("content_notes"), "content_notes"),
        opening=CampaignOpening(
            public=_text(opening_raw.get("public"), "opening.public"),
            prompt=_text(opening_raw.get("prompt"), "opening.prompt"),
        ),
        clocks=_load_clocks(value.get("clocks")),
        facts=_load_facts(value.get("facts")),
        npcs=_load_npcs(value.get("npcs")),
        scenes=scenes,
        scene_order=scene_order,
        dm_contract=DmContract(
            style=_strings(dm_raw.get("style"), "dm_contract.style"),
            turn_pattern=_strings(dm_raw.get("turn_pattern"), "dm_contract.turn_pattern"),
            never=_strings(dm_raw.get("never"), "dm_contract.never"),
            roll_policy=_text(dm_raw.get("roll_policy"), "dm_contract.roll_policy"),
            fail_forward_policy=_text(dm_raw.get("fail_forward_policy"), "dm_contract.fail_forward_policy"),
        ),
    )
    _validate_references(campaign)
    return campaign


def load_campaign(path: str | Path) -> Campaign:
    """Load a campaign file without exposing its raw dictionary to callers."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:
        raise CampaignValidationError(f"campaign file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise CampaignValidationError(
            f"campaign JSON is invalid at line {exc.lineno}, column {exc.colno}"
        ) from exc
    return campaign_from_dict(raw)
