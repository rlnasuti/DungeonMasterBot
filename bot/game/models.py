"""Validated value objects for player characters and engine-owned rolls."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Mapping
from uuid import uuid4

from bot.game.errors import ValidationError


ABILITY_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)
SKILL_NAMES = {
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
}
SKILL_ABILITIES = {
    "acrobatics": "dexterity",
    "animal_handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
}
HIT_DIE_NAMES = {"d6", "d8", "d10", "d12"}
CURRENCY_DENOMINATIONS = ("cp", "sp", "ep", "gp", "pp")
CURRENCY_BALANCE_MAXIMUM = 999_999
CURRENCY_AWARD_MAXIMUM = 10_000
MOVEMENT_MODES = ("walk", "burrow", "climb", "fly", "swim")
ATTACK_TYPES = {
    "melee_weapon",
    "ranged_weapon",
    "melee_spell",
    "ranged_spell",
    "other",
}
SPELL_PREPARATION_MODES = {"known", "prepared", "spellbook", "innate"}
SPELL_COMPONENTS = {"V", "S", "M"}
DICE_EXPRESSION = re.compile(r"^[1-9][0-9]{0,2}d(?:4|6|8|10|12|20|100)$")


def normalize_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("State keys must be non-empty strings.")
    return "_".join(value.strip().lower().replace("-", " ").split())


def require_int(
    value: Any,
    field_name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer.")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{field_name} must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field_name} must be no more than {maximum}.")
    return value


def require_text(value: Any, field_name: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string.")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValidationError(f"{field_name} must be no more than {maximum} characters.")
    return normalized


def require_number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Return a finite JSON number while rejecting booleans and coercion."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field_name} must be a number.")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValidationError(f"{field_name} must be finite.")
    if minimum is not None and normalized < minimum:
        raise ValidationError(f"{field_name} must be at least {minimum}.")
    if maximum is not None and normalized > maximum:
        raise ValidationError(f"{field_name} must be no more than {maximum}.")
    return normalized


def _optional_text(value: Any, field_name: str, *, maximum: int = 200) -> str | None:
    if value is None:
        return None
    return require_text(value, field_name, maximum=maximum)


def _unique_text_values(
    value: Any,
    field_name: str,
    *,
    maximum_items: int = 100,
    item_maximum: int = 200,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be an array.")
    if len(value) > maximum_items:
        raise ValidationError(f"{field_name} must contain no more than {maximum_items} entries.")
    result: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = require_text(raw, f"{field_name}[{index}]", maximum=item_maximum)
        identity = item.casefold()
        if identity in seen:
            raise ValidationError(f"{field_name} cannot contain duplicate entries.")
        seen.add(identity)
        result.append(item)
    return tuple(result)


@dataclass
class ResourcePool:
    maximum: int
    current: int

    @classmethod
    def from_value(cls, value: Any, field_name: str) -> "ResourcePool":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        unknown = set(value) - {"maximum", "max", "current"}
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        maximum_raw = value.get("maximum", value.get("max"))
        maximum = require_int(maximum_raw, f"{field_name}.maximum", minimum=0, maximum=999)
        current = require_int(value.get("current", maximum), f"{field_name}.current", minimum=0, maximum=999)
        if current > maximum:
            raise ValidationError(f"{field_name}.current cannot exceed its maximum.")
        return cls(maximum=maximum, current=current)

    def to_dict(self) -> dict[str, int]:
        return {"maximum": self.maximum, "current": self.current}


@dataclass(frozen=True)
class DeathSaves:
    successes: int = 0
    failures: int = 0

    @classmethod
    def from_value(
        cls, value: Any, field_name: str = "character.death_saves"
    ) -> "DeathSaves":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        unknown = set(value) - {"successes", "failures"}
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        return cls(
            successes=require_int(
                value.get("successes", 0),
                f"{field_name}.successes",
                minimum=0,
                maximum=3,
            ),
            failures=require_int(
                value.get("failures", 0),
                f"{field_name}.failures",
                minimum=0,
                maximum=3,
            ),
        )

    def to_dict(self) -> dict[str, int]:
        return {"successes": self.successes, "failures": self.failures}


@dataclass(frozen=True)
class Speed:
    """A public movement-speed block, measured in feet."""

    walk: int = 30
    burrow: int = 0
    climb: int = 0
    fly: int = 0
    swim: int = 0
    hover: bool = False

    @classmethod
    def from_value(cls, value: Any, field_name: str = "character.speed") -> "Speed":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        unknown = set(value) - {*MOVEMENT_MODES, "hover"}
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        hover = value.get("hover", False)
        if not isinstance(hover, bool):
            raise ValidationError(f"{field_name}.hover must be a boolean.")
        modes = {
            mode: require_int(
                value.get(mode, 30 if mode == "walk" else 0),
                f"{field_name}.{mode}",
                minimum=0,
                maximum=1000,
            )
            for mode in MOVEMENT_MODES
        }
        if hover and modes["fly"] == 0:
            raise ValidationError(f"{field_name}.hover requires a fly speed.")
        return cls(**modes, hover=hover)

    def to_dict(self) -> dict[str, Any]:
        return {
            "walk": self.walk,
            "burrow": self.burrow,
            "climb": self.climb,
            "fly": self.fly,
            "swim": self.swim,
            "hover": self.hover,
        }


@dataclass(frozen=True)
class Proficiencies:
    """Player-visible proficiency labels, kept as structured categories."""

    armor: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()

    @classmethod
    def from_value(
        cls, value: Any, field_name: str = "character.proficiencies"
    ) -> "Proficiencies":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        categories = {"armor", "weapons", "tools", "languages"}
        unknown = set(value) - categories
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        return cls(
            **{
                category: _unique_text_values(
                    value.get(category, []), f"{field_name}.{category}", maximum_items=100
                )
                for category in categories
            }
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "armor": list(self.armor),
            "weapons": list(self.weapons),
            "tools": list(self.tools),
            "languages": list(self.languages),
        }


@dataclass(frozen=True)
class ArmorClassCalculation:
    """The public arithmetic behind the cached armor-class total."""

    base: int
    use_dexterity: bool
    dexterity_cap: int | None
    shield_bonus: int
    misc_bonus: int
    source_item_ids: tuple[str, ...]

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        armor_class: int,
        dexterity_modifier: int,
        field_name: str = "character.armor_class_calculation",
    ) -> "ArmorClassCalculation":
        # A legacy sheet only cached its final AC. Treat that total as a manual
        # base so old campaigns remain readable without fabricating equipment.
        if value is None:
            return cls(
                base=armor_class,
                use_dexterity=False,
                dexterity_cap=None,
                shield_bonus=0,
                misc_bonus=0,
                source_item_ids=(),
            )
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        allowed = {
            "base",
            "use_dexterity",
            "dexterity_cap",
            "shield_bonus",
            "misc_bonus",
            "source_item_ids",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        use_dexterity = value.get("use_dexterity", False)
        if not isinstance(use_dexterity, bool):
            raise ValidationError(f"{field_name}.use_dexterity must be a boolean.")
        dexterity_cap_raw = value.get("dexterity_cap")
        dexterity_cap = None
        if dexterity_cap_raw is not None:
            dexterity_cap = require_int(
                dexterity_cap_raw,
                f"{field_name}.dexterity_cap",
                minimum=0,
                maximum=20,
            )
            if not use_dexterity:
                raise ValidationError(
                    f"{field_name}.dexterity_cap requires use_dexterity to be true."
                )
        calculation = cls(
            base=require_int(value.get("base"), f"{field_name}.base", minimum=0, maximum=50),
            use_dexterity=use_dexterity,
            dexterity_cap=dexterity_cap,
            shield_bonus=require_int(
                value.get("shield_bonus", 0),
                f"{field_name}.shield_bonus",
                minimum=0,
                maximum=20,
            ),
            misc_bonus=require_int(
                value.get("misc_bonus", 0),
                f"{field_name}.misc_bonus",
                minimum=-20,
                maximum=20,
            ),
            source_item_ids=_unique_text_values(
                value.get("source_item_ids", []),
                f"{field_name}.source_item_ids",
                maximum_items=20,
            ),
        )
        calculated_total = calculation.total(dexterity_modifier)
        if calculated_total != armor_class:
            raise ValidationError(
                f"{field_name} totals {calculated_total}, but character.armor_class is {armor_class}."
            )
        return calculation

    def dexterity_contribution(self, dexterity_modifier: int) -> int:
        if not self.use_dexterity:
            return 0
        if self.dexterity_cap is None:
            return dexterity_modifier
        return min(dexterity_modifier, self.dexterity_cap)

    def total(self, dexterity_modifier: int) -> int:
        return (
            self.base
            + self.dexterity_contribution(dexterity_modifier)
            + self.shield_bonus
            + self.misc_bonus
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "use_dexterity": self.use_dexterity,
            "dexterity_cap": self.dexterity_cap,
            "shield_bonus": self.shield_bonus,
            "misc_bonus": self.misc_bonus,
            "source_item_ids": list(self.source_item_ids),
        }


@dataclass(frozen=True)
class DamageProfile:
    dice: str
    bonus: int
    damage_type: str

    @classmethod
    def from_value(cls, value: Any, field_name: str) -> "DamageProfile":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        unknown = set(value) - {"dice", "bonus", "damage_type"}
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        dice = require_text(value.get("dice"), f"{field_name}.dice", maximum=10).lower()
        if not DICE_EXPRESSION.fullmatch(dice):
            raise ValidationError(
                f"{field_name}.dice must be a simple dice expression such as '1d8'."
            )
        return cls(
            dice=dice,
            bonus=require_int(
                value.get("bonus", 0), f"{field_name}.bonus", minimum=-20, maximum=50
            ),
            damage_type=normalize_key(
                require_text(value.get("damage_type"), f"{field_name}.damage_type")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"dice": self.dice, "bonus": self.bonus, "damage_type": self.damage_type}


@dataclass(frozen=True)
class AttackProfile:
    """A public roll-ready attack summary without encounter-only information."""

    attack_id: str
    name: str
    attack_type: str
    attack_bonus: int
    damage: tuple[DamageProfile, ...]
    reach: int | None
    range_normal: int | None
    range_long: int | None
    source_item_id: str | None
    properties: tuple[str, ...]

    @classmethod
    def from_value(cls, value: Any, index: int) -> "AttackProfile":
        field_name = f"character.attacks[{index}]"
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        allowed = {
            "attack_id",
            "name",
            "attack_type",
            "attack_bonus",
            "damage",
            "reach",
            "range_normal",
            "range_long",
            "source_item_id",
            "properties",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        attack_type = normalize_key(value.get("attack_type", "other"))
        if attack_type not in ATTACK_TYPES:
            raise ValidationError(f"Unsupported attack type: {value.get('attack_type')}")
        damage_raw = value.get("damage")
        if not isinstance(damage_raw, list) or not damage_raw:
            raise ValidationError(f"{field_name}.damage must be a non-empty array.")
        if len(damage_raw) > 10:
            raise ValidationError(f"{field_name}.damage must contain no more than 10 entries.")
        reach = cls._optional_distance(value.get("reach"), f"{field_name}.reach")
        range_normal = cls._optional_distance(
            value.get("range_normal"), f"{field_name}.range_normal"
        )
        range_long = cls._optional_distance(
            value.get("range_long"), f"{field_name}.range_long"
        )
        if reach is None and range_normal is None:
            raise ValidationError(f"{field_name} requires reach or range_normal.")
        if range_long is not None and range_normal is None:
            raise ValidationError(f"{field_name}.range_long requires range_normal.")
        if range_long is not None and range_long < range_normal:
            raise ValidationError(f"{field_name}.range_long cannot be shorter than range_normal.")
        return cls(
            attack_id=require_text(value.get("attack_id"), f"{field_name}.attack_id"),
            name=require_text(value.get("name"), f"{field_name}.name"),
            attack_type=attack_type,
            attack_bonus=require_int(
                value.get("attack_bonus"),
                f"{field_name}.attack_bonus",
                minimum=-20,
                maximum=50,
            ),
            damage=tuple(
                DamageProfile.from_value(raw, f"{field_name}.damage[{damage_index}]")
                for damage_index, raw in enumerate(damage_raw)
            ),
            reach=reach,
            range_normal=range_normal,
            range_long=range_long,
            source_item_id=_optional_text(
                value.get("source_item_id"), f"{field_name}.source_item_id"
            ),
            properties=_unique_text_values(
                value.get("properties", []), f"{field_name}.properties", maximum_items=30
            ),
        )

    @staticmethod
    def _optional_distance(value: Any, field_name: str) -> int | None:
        if value is None:
            return None
        return require_int(value, field_name, minimum=0, maximum=10_000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attack_id": self.attack_id,
            "name": self.name,
            "attack_type": self.attack_type,
            "attack_bonus": self.attack_bonus,
            "damage": [profile.to_dict() for profile in self.damage],
            "reach": self.reach,
            "range_normal": self.range_normal,
            "range_long": self.range_long,
            "source_item_id": self.source_item_id,
            "properties": list(self.properties),
        }


@dataclass
class InventoryItem:
    item_id: str
    name: str
    quantity: int = 1
    equipped: bool = False
    notes: str = ""
    rules_ref: str | None = None
    category: str = "other"
    weight: float = 0.0

    @classmethod
    def from_value(cls, value: Any, index: int) -> "InventoryItem":
        if not isinstance(value, Mapping):
            raise ValidationError(f"inventory[{index}] must be an object.")
        unknown = set(value) - {
            "item_id",
            "name",
            "quantity",
            "equipped",
            "notes",
            "rules_ref",
            "category",
            "weight",
        }
        if unknown:
            raise ValidationError(f"inventory[{index}] has unknown fields: {sorted(unknown)}")
        equipped = value.get("equipped", False)
        if not isinstance(equipped, bool):
            raise ValidationError(f"inventory[{index}].equipped must be a boolean.")
        notes = value.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 500:
            raise ValidationError(f"inventory[{index}].notes must be a string of at most 500 characters.")
        return cls(
            item_id=require_text(value.get("item_id", str(uuid4())), f"inventory[{index}].item_id"),
            name=require_text(value.get("name"), f"inventory[{index}].name"),
            quantity=require_int(value.get("quantity", 1), f"inventory[{index}].quantity", minimum=0, maximum=9999),
            equipped=equipped,
            notes=notes,
            rules_ref=_optional_text(
                value.get("rules_ref"), f"inventory[{index}].rules_ref", maximum=500
            ),
            category=normalize_key(value.get("category", "other")),
            weight=require_number(
                value.get("weight", 0),
                f"inventory[{index}].weight",
                minimum=0,
                maximum=100_000,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "quantity": self.quantity,
            "equipped": self.equipped,
            "notes": self.notes,
            "rules_ref": self.rules_ref,
            "category": self.category,
            "weight": self.weight,
        }


@dataclass(frozen=True)
class CharacterFeature:
    """Concise public feature metadata; detailed licensed rules stay external."""

    feature_id: str
    name: str
    source: str
    rules_ref: str | None
    summary: str | None
    resource_key: str | None

    @classmethod
    def from_value(cls, value: Any, index: int) -> "CharacterFeature":
        field_name = f"character.features[{index}]"
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        allowed = {"feature_id", "name", "source", "rules_ref", "summary", "resource_key"}
        unknown = set(value) - allowed
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        summary = _optional_text(value.get("summary"), f"{field_name}.summary", maximum=300)
        resource_key_raw = value.get("resource_key")
        resource_key = None
        if resource_key_raw is not None:
            resource_key = normalize_key(resource_key_raw)
        if summary is None and resource_key is None:
            raise ValidationError(f"{field_name} requires summary or resource_key.")
        return cls(
            feature_id=require_text(value.get("feature_id"), f"{field_name}.feature_id"),
            name=require_text(value.get("name"), f"{field_name}.name"),
            source=require_text(value.get("source"), f"{field_name}.source"),
            rules_ref=_optional_text(
                value.get("rules_ref"), f"{field_name}.rules_ref", maximum=500
            ),
            summary=summary,
            resource_key=resource_key,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "name": self.name,
            "source": self.source,
            "rules_ref": self.rules_ref,
            "summary": self.summary,
            "resource_key": self.resource_key,
        }


@dataclass(frozen=True)
class SpellDefinition:
    """Compact public spell metadata, deliberately excluding full rules text."""

    spell_id: str
    name: str
    level: int
    school: str
    casting_time: str
    range: str
    duration: str
    components: tuple[str, ...]
    concentration: bool
    ritual: bool
    rules_ref: str | None
    source: str | None

    @classmethod
    def from_value(cls, value: Any, index: int) -> "SpellDefinition":
        field_name = f"character.spellcasting.spells[{index}]"
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        allowed = {
            "spell_id",
            "name",
            "level",
            "school",
            "casting_time",
            "range",
            "duration",
            "components",
            "concentration",
            "ritual",
            "rules_ref",
            "source",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        components_raw = value.get("components", [])
        if not isinstance(components_raw, list):
            raise ValidationError(f"{field_name}.components must be an array.")
        components: list[str] = []
        for component_index, raw_component in enumerate(components_raw):
            component = require_text(
                raw_component,
                f"{field_name}.components[{component_index}]",
                maximum=1,
            ).upper()
            if component not in SPELL_COMPONENTS:
                raise ValidationError(f"Unsupported spell component: {raw_component}")
            if component in components:
                raise ValidationError(f"{field_name}.components cannot contain duplicates.")
            components.append(component)
        concentration = value.get("concentration", False)
        ritual = value.get("ritual", False)
        if not isinstance(concentration, bool):
            raise ValidationError(f"{field_name}.concentration must be a boolean.")
        if not isinstance(ritual, bool):
            raise ValidationError(f"{field_name}.ritual must be a boolean.")
        return cls(
            spell_id=require_text(value.get("spell_id"), f"{field_name}.spell_id"),
            name=require_text(value.get("name"), f"{field_name}.name"),
            level=require_int(value.get("level"), f"{field_name}.level", minimum=0, maximum=9),
            school=normalize_key(value.get("school")),
            casting_time=require_text(
                value.get("casting_time"), f"{field_name}.casting_time", maximum=100
            ),
            range=require_text(value.get("range"), f"{field_name}.range", maximum=100),
            duration=require_text(
                value.get("duration"), f"{field_name}.duration", maximum=100
            ),
            components=tuple(components),
            concentration=concentration,
            ritual=ritual,
            rules_ref=_optional_text(
                value.get("rules_ref"), f"{field_name}.rules_ref", maximum=500
            ),
            source=_optional_text(value.get("source"), f"{field_name}.source"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell_id": self.spell_id,
            "name": self.name,
            "level": self.level,
            "school": self.school,
            "casting_time": self.casting_time,
            "range": self.range,
            "duration": self.duration,
            "components": list(self.components),
            "concentration": self.concentration,
            "ritual": self.ritual,
            "rules_ref": self.rules_ref,
            "source": self.source,
        }


@dataclass(frozen=True)
class Spellcasting:
    ability: str
    save_dc: int
    attack_bonus: int
    preparation_mode: str
    spells: tuple[SpellDefinition, ...]
    known_spell_ids: frozenset[str]
    prepared_spell_ids: frozenset[str]
    always_prepared_spell_ids: frozenset[str]
    spellbook_spell_ids: frozenset[str]
    ritual_casting: bool
    focus_item_id: str | None

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        abilities: Mapping[str, int],
        proficiency_bonus: int,
        field_name: str = "character.spellcasting",
    ) -> "Spellcasting":
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        allowed = {
            "ability",
            "save_dc",
            "attack_bonus",
            "preparation_mode",
            "spells",
            "known_spell_ids",
            "prepared_spell_ids",
            "always_prepared_spell_ids",
            "spellbook_spell_ids",
            "ritual_casting",
            "focus_item_id",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValidationError(f"{field_name} has unknown fields: {sorted(unknown)}")
        ability = normalize_key(value.get("ability"))
        if ability not in ABILITY_NAMES:
            raise ValidationError(f"Unsupported spellcasting ability: {value.get('ability')}")
        ability_modifier = (abilities[ability] - 10) // 2
        computed_save_dc = 8 + proficiency_bonus + ability_modifier
        computed_attack_bonus = proficiency_bonus + ability_modifier
        if "save_dc" in value:
            cached_save_dc = require_int(
                value["save_dc"], f"{field_name}.save_dc", minimum=0, maximum=50
            )
            if cached_save_dc != computed_save_dc:
                raise ValidationError(
                    f"{field_name}.save_dc must equal the computed value {computed_save_dc}."
                )
        if "attack_bonus" in value:
            cached_attack_bonus = require_int(
                value["attack_bonus"], f"{field_name}.attack_bonus", minimum=-20, maximum=50
            )
            if cached_attack_bonus != computed_attack_bonus:
                raise ValidationError(
                    f"{field_name}.attack_bonus must equal the computed value {computed_attack_bonus}."
                )
        preparation_mode = normalize_key(value.get("preparation_mode"))
        if preparation_mode not in SPELL_PREPARATION_MODES:
            raise ValidationError(
                f"Unsupported spell preparation mode: {value.get('preparation_mode')}"
            )
        spells_raw = value.get("spells", [])
        if not isinstance(spells_raw, list):
            raise ValidationError(f"{field_name}.spells must be an array.")
        if len(spells_raw) > 500:
            raise ValidationError(f"{field_name}.spells must contain no more than 500 entries.")
        spells = tuple(
            SpellDefinition.from_value(raw_spell, index)
            for index, raw_spell in enumerate(spells_raw)
        )
        spell_ids = [spell.spell_id for spell in spells]
        if len(set(spell_ids)) != len(spell_ids):
            raise ValidationError(f"{field_name}.spells cannot contain duplicate spell_id values.")
        available_ids = set(spell_ids)
        id_sets = {
            set_name: frozenset(
                _unique_text_values(
                    value.get(set_name, []),
                    f"{field_name}.{set_name}",
                    maximum_items=500,
                )
            )
            for set_name in (
                "known_spell_ids",
                "prepared_spell_ids",
                "always_prepared_spell_ids",
                "spellbook_spell_ids",
            )
        }
        for set_name, references in id_sets.items():
            unknown_references = references - available_ids
            if unknown_references:
                raise ValidationError(
                    f"{field_name}.{set_name} references undefined spells: "
                    f"{sorted(unknown_references)}"
                )
        if preparation_mode == "spellbook" and not id_sets["prepared_spell_ids"].issubset(
            id_sets["spellbook_spell_ids"]
        ):
            raise ValidationError(
                f"{field_name}.prepared_spell_ids must be a subset of spellbook_spell_ids."
            )
        if preparation_mode == "known" and not id_sets["prepared_spell_ids"].issubset(
            id_sets["known_spell_ids"]
        ):
            raise ValidationError(
                f"{field_name}.prepared_spell_ids must be a subset of known_spell_ids."
            )
        if preparation_mode == "innate" and (
            id_sets["prepared_spell_ids"] or id_sets["spellbook_spell_ids"]
        ):
            raise ValidationError(
                f"{field_name} innate casting cannot have prepared or spellbook spells."
            )
        ritual_casting = value.get("ritual_casting", False)
        if not isinstance(ritual_casting, bool):
            raise ValidationError(f"{field_name}.ritual_casting must be a boolean.")
        return cls(
            ability=ability,
            save_dc=computed_save_dc,
            attack_bonus=computed_attack_bonus,
            preparation_mode=preparation_mode,
            spells=spells,
            known_spell_ids=id_sets["known_spell_ids"],
            prepared_spell_ids=id_sets["prepared_spell_ids"],
            always_prepared_spell_ids=id_sets["always_prepared_spell_ids"],
            spellbook_spell_ids=id_sets["spellbook_spell_ids"],
            ritual_casting=ritual_casting,
            focus_item_id=_optional_text(
                value.get("focus_item_id"), f"{field_name}.focus_item_id"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ability": self.ability,
            "save_dc": self.save_dc,
            "attack_bonus": self.attack_bonus,
            "preparation_mode": self.preparation_mode,
            "spells": [spell.to_dict() for spell in self.spells],
            "known_spell_ids": sorted(self.known_spell_ids),
            "prepared_spell_ids": sorted(self.prepared_spell_ids),
            "always_prepared_spell_ids": sorted(self.always_prepared_spell_ids),
            "spellbook_spell_ids": sorted(self.spellbook_spell_ids),
            "ritual_casting": self.ritual_casting,
            "focus_item_id": self.focus_item_id,
        }


@dataclass
class CharacterState:
    character_id: str
    name: str
    class_name: str
    level: int
    ancestry: str
    background: str
    hp: int
    max_hp: int
    temp_hp: int
    armor_class: int
    proficiency_bonus: int
    abilities: dict[str, int]
    saving_throws: dict[str, int]
    skills: dict[str, int]
    ruleset_id: str = "manual"
    subclass_name: str | None = None
    alignment: str | None = None
    experience_points: int = 0
    size: str = "Medium"
    heroic_inspiration: bool = False
    death_saves: DeathSaves = field(default_factory=DeathSaves)
    speed: Speed = field(default_factory=Speed)
    proficiencies: Proficiencies = field(default_factory=Proficiencies)
    armor_class_calculation: ArmorClassCalculation = field(
        default_factory=lambda: ArmorClassCalculation(10, False, None, 0, 0, ())
    )
    attacks: list[AttackProfile] = field(default_factory=list)
    features: list[CharacterFeature] = field(default_factory=list)
    spellcasting: Spellcasting | None = None
    hit_dice: dict[str, ResourcePool] = field(default_factory=dict)
    spell_slots: dict[str, ResourcePool] = field(default_factory=dict)
    class_resources: dict[str, ResourcePool] = field(default_factory=dict)
    conditions: list[str] = field(default_factory=list)
    inventory: list[InventoryItem] = field(default_factory=list)
    currency: dict[str, int] = field(default_factory=lambda: {
        denomination: 0 for denomination in CURRENCY_DENOMINATIONS
    })

    @classmethod
    def from_dict(cls, value: Any) -> "CharacterState":
        if not isinstance(value, Mapping):
            raise ValidationError("character must be an object.")
        allowed = {
            "character_id",
            "name",
            "class_name",
            "subclass_name",
            "ruleset_id",
            "alignment",
            "experience_points",
            "size",
            "heroic_inspiration",
            "death_saves",
            "level",
            "ancestry",
            "background",
            "hp",
            "max_hp",
            "temp_hp",
            "armor_class",
            "armor_class_calculation",
            "proficiency_bonus",
            "speed",
            "proficiencies",
            "abilities",
            "saving_throws",
            "skills",
            "attacks",
            "features",
            "spellcasting",
            "hit_dice",
            "spell_slots",
            "class_resources",
            "conditions",
            "inventory",
            "currency",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValidationError(f"character has unknown fields: {sorted(unknown)}")

        level = require_int(value.get("level"), "character.level", minimum=1, maximum=20)
        max_hp = require_int(value.get("max_hp"), "character.max_hp", minimum=1, maximum=9999)
        hp = require_int(value.get("hp", max_hp), "character.hp", minimum=0, maximum=9999)
        if hp > max_hp:
            raise ValidationError("character.hp cannot exceed character.max_hp.")
        heroic_inspiration = value.get("heroic_inspiration", False)
        if not isinstance(heroic_inspiration, bool):
            raise ValidationError("character.heroic_inspiration must be a boolean.")

        abilities = cls._modifier_map(value.get("abilities"), "character.abilities", set(ABILITY_NAMES), exact=True, minimum=1, maximum=30)
        saving_throws = cls._modifier_map(value.get("saving_throws"), "character.saving_throws", set(ABILITY_NAMES), exact=True)
        skills = cls._modifier_map(value.get("skills", {}), "character.skills", SKILL_NAMES, exact=False)
        proficiency_default = 2 + ((level - 1) // 4)
        proficiency_bonus = require_int(
            value.get("proficiency_bonus", proficiency_default),
            "character.proficiency_bonus",
            minimum=0,
            maximum=20,
        )
        armor_class = require_int(
            value.get("armor_class"), "character.armor_class", minimum=1, maximum=50
        )

        hit_dice_raw = value.get("hit_dice", {})
        if not isinstance(hit_dice_raw, Mapping):
            raise ValidationError("character.hit_dice must be an object.")
        hit_dice: dict[str, ResourcePool] = {}
        for raw_key, pool in hit_dice_raw.items():
            key = normalize_key(raw_key)
            if key not in HIT_DIE_NAMES:
                raise ValidationError(f"Unsupported hit die: {raw_key}")
            hit_dice[key] = ResourcePool.from_value(pool, f"character.hit_dice.{key}")

        spell_slots_raw = value.get("spell_slots", {})
        if not isinstance(spell_slots_raw, Mapping):
            raise ValidationError("character.spell_slots must be an object.")
        spell_slots: dict[str, ResourcePool] = {}
        for raw_level, pool in spell_slots_raw.items():
            try:
                slot_level = int(raw_level)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Spell-slot levels must be integers from 1 through 9.") from exc
            if slot_level < 1 or slot_level > 9:
                raise ValidationError("Spell-slot levels must be integers from 1 through 9.")
            key = str(slot_level)
            spell_slots[key] = ResourcePool.from_value(pool, f"character.spell_slots.{key}")

        resources_raw = value.get("class_resources", {})
        if not isinstance(resources_raw, Mapping):
            raise ValidationError("character.class_resources must be an object.")
        class_resources = {
            normalize_key(raw_key): ResourcePool.from_value(pool, f"character.class_resources.{normalize_key(raw_key)}")
            for raw_key, pool in resources_raw.items()
        }

        conditions_raw = value.get("conditions", [])
        if not isinstance(conditions_raw, list):
            raise ValidationError("character.conditions must be an array.")
        conditions: list[str] = []
        for index, condition in enumerate(conditions_raw):
            normalized = require_text(condition, f"character.conditions[{index}]", maximum=100)
            if normalized not in conditions:
                conditions.append(normalized)

        inventory_raw = value.get("inventory", [])
        if not isinstance(inventory_raw, list):
            raise ValidationError("character.inventory must be an array.")
        inventory = [InventoryItem.from_value(item, index) for index, item in enumerate(inventory_raw)]
        inventory_ids = [item.item_id for item in inventory]
        if len(set(inventory_ids)) != len(inventory_ids):
            raise ValidationError("character.inventory cannot contain duplicate item_id values.")
        inventory_id_set = set(inventory_ids)

        speed = Speed.from_value(value.get("speed", {"walk": 30}))
        proficiencies = Proficiencies.from_value(value.get("proficiencies", {}))
        armor_class_calculation = ArmorClassCalculation.from_value(
            value.get("armor_class_calculation"),
            armor_class=armor_class,
            dexterity_modifier=(abilities["dexterity"] - 10) // 2,
        )
        missing_ac_sources = set(armor_class_calculation.source_item_ids) - inventory_id_set
        if missing_ac_sources:
            raise ValidationError(
                "character.armor_class_calculation.source_item_ids references missing inventory "
                f"items: {sorted(missing_ac_sources)}"
            )

        attacks_raw = value.get("attacks", [])
        if not isinstance(attacks_raw, list):
            raise ValidationError("character.attacks must be an array.")
        if len(attacks_raw) > 100:
            raise ValidationError("character.attacks must contain no more than 100 entries.")
        attacks = [AttackProfile.from_value(attack, index) for index, attack in enumerate(attacks_raw)]
        attack_ids = [attack.attack_id for attack in attacks]
        if len(set(attack_ids)) != len(attack_ids):
            raise ValidationError("character.attacks cannot contain duplicate attack_id values.")
        missing_attack_sources = {
            attack.source_item_id
            for attack in attacks
            if attack.source_item_id is not None and attack.source_item_id not in inventory_id_set
        }
        if missing_attack_sources:
            raise ValidationError(
                "character.attacks references missing inventory items: "
                f"{sorted(missing_attack_sources)}"
            )

        features_raw = value.get("features", [])
        if not isinstance(features_raw, list):
            raise ValidationError("character.features must be an array.")
        if len(features_raw) > 200:
            raise ValidationError("character.features must contain no more than 200 entries.")
        features = [
            CharacterFeature.from_value(feature, index)
            for index, feature in enumerate(features_raw)
        ]
        feature_ids = [feature.feature_id for feature in features]
        if len(set(feature_ids)) != len(feature_ids):
            raise ValidationError("character.features cannot contain duplicate feature_id values.")
        missing_feature_resources = {
            feature.resource_key
            for feature in features
            if feature.resource_key is not None and feature.resource_key not in class_resources
        }
        if missing_feature_resources:
            raise ValidationError(
                "character.features references missing class_resources: "
                f"{sorted(missing_feature_resources)}"
            )

        spellcasting_raw = value.get("spellcasting")
        spellcasting = None
        if spellcasting_raw is not None:
            spellcasting = Spellcasting.from_value(
                spellcasting_raw,
                abilities=abilities,
                proficiency_bonus=proficiency_bonus,
            )
            if (
                spellcasting.focus_item_id is not None
                and spellcasting.focus_item_id not in inventory_id_set
            ):
                raise ValidationError(
                    "character.spellcasting.focus_item_id references a missing inventory item."
                )

        currency_raw = value.get("currency", {})
        if not isinstance(currency_raw, Mapping):
            raise ValidationError("character.currency must be an object.")
        currency = {denomination: 0 for denomination in CURRENCY_DENOMINATIONS}
        seen_denominations: set[str] = set()
        for raw_denomination, raw_balance in currency_raw.items():
            if not isinstance(raw_denomination, str):
                raise ValidationError("Currency denominations must be strings.")
            denomination = normalize_key(raw_denomination)
            if denomination not in CURRENCY_DENOMINATIONS:
                raise ValidationError(
                    f"Unsupported currency denomination: {raw_denomination}"
                )
            if denomination in seen_denominations:
                raise ValidationError(
                    f"Duplicate currency denomination: {raw_denomination}"
                )
            seen_denominations.add(denomination)
            currency[denomination] = require_int(
                raw_balance,
                f"character.currency.{denomination}",
                minimum=0,
                maximum=CURRENCY_BALANCE_MAXIMUM,
            )

        return cls(
            character_id=require_text(value.get("character_id", str(uuid4())), "character.character_id"),
            name=require_text(value.get("name"), "character.name"),
            class_name=require_text(value.get("class_name"), "character.class_name"),
            subclass_name=_optional_text(
                value.get("subclass_name"), "character.subclass_name"
            ),
            ruleset_id=require_text(
                value.get("ruleset_id", "manual"), "character.ruleset_id", maximum=100
            ),
            alignment=_optional_text(value.get("alignment"), "character.alignment"),
            experience_points=require_int(
                value.get("experience_points", 0),
                "character.experience_points",
                minimum=0,
            ),
            size=require_text(value.get("size", "Medium"), "character.size", maximum=100),
            heroic_inspiration=heroic_inspiration,
            death_saves=DeathSaves.from_value(value.get("death_saves", {})),
            level=level,
            ancestry=require_text(value.get("ancestry", "Unspecified"), "character.ancestry"),
            background=require_text(value.get("background", "Unspecified"), "character.background"),
            hp=hp,
            max_hp=max_hp,
            temp_hp=require_int(value.get("temp_hp", 0), "character.temp_hp", minimum=0, maximum=9999),
            armor_class=armor_class,
            armor_class_calculation=armor_class_calculation,
            proficiency_bonus=proficiency_bonus,
            speed=speed,
            proficiencies=proficiencies,
            abilities=abilities,
            saving_throws=saving_throws,
            skills=skills,
            attacks=attacks,
            features=features,
            spellcasting=spellcasting,
            hit_dice=hit_dice,
            spell_slots=spell_slots,
            class_resources=class_resources,
            conditions=conditions,
            inventory=inventory,
            currency=currency,
        )

    @staticmethod
    def _modifier_map(
        value: Any,
        field_name: str,
        allowed_keys: set[str],
        *,
        exact: bool,
        minimum: int = -20,
        maximum: int = 30,
    ) -> dict[str, int]:
        if not isinstance(value, Mapping):
            raise ValidationError(f"{field_name} must be an object.")
        normalized: dict[str, int] = {}
        for raw_key, raw_modifier in value.items():
            key = normalize_key(raw_key)
            if key not in allowed_keys:
                raise ValidationError(f"Unsupported key in {field_name}: {raw_key}")
            normalized[key] = require_int(raw_modifier, f"{field_name}.{key}", minimum=minimum, maximum=maximum)
        if exact and set(normalized) != allowed_keys:
            missing = sorted(allowed_keys - set(normalized))
            raise ValidationError(f"{field_name} is missing required keys: {missing}")
        return normalized

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "class_name": self.class_name,
            "subclass_name": self.subclass_name,
            "ruleset_id": self.ruleset_id,
            "alignment": self.alignment,
            "experience_points": self.experience_points,
            "size": self.size,
            "heroic_inspiration": self.heroic_inspiration,
            "death_saves": self.death_saves.to_dict(),
            "level": self.level,
            "ancestry": self.ancestry,
            "background": self.background,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "temp_hp": self.temp_hp,
            "armor_class": self.armor_class,
            "armor_class_calculation": self.armor_class_calculation.to_dict(),
            "proficiency_bonus": self.proficiency_bonus,
            "speed": self.speed.to_dict(),
            "proficiencies": self.proficiencies.to_dict(),
            "abilities": dict(self.abilities),
            "saving_throws": dict(self.saving_throws),
            "skills": dict(self.skills),
            "attacks": [attack.to_dict() for attack in self.attacks],
            "features": [feature.to_dict() for feature in self.features],
            "spellcasting": self.spellcasting.to_dict() if self.spellcasting else None,
            "hit_dice": {key: pool.to_dict() for key, pool in self.hit_dice.items()},
            "spell_slots": {key: pool.to_dict() for key, pool in self.spell_slots.items()},
            "class_resources": {key: pool.to_dict() for key, pool in self.class_resources.items()},
            "conditions": list(self.conditions),
            "inventory": [item.to_dict() for item in self.inventory],
            "currency": dict(self.currency),
        }

    def roll_modifier(self, roll_kind: str, key: str | None = None) -> int:
        kind = normalize_key(roll_kind)
        if kind == "ability":
            ability = normalize_key(key or "")
            if ability not in self.abilities:
                raise ValidationError(f"Unknown ability check: {key}")
            return (self.abilities[ability] - 10) // 2
        if kind in {"saving_throw", "save"}:
            ability = normalize_key(key or "")
            if ability not in self.saving_throws:
                raise ValidationError(f"Unknown saving throw: {key}")
            return self.saving_throws[ability]
        if kind == "skill":
            skill = normalize_key(key or "")
            if skill in self.skills:
                return self.skills[skill]
            ability = SKILL_ABILITIES.get(skill)
            if ability is None:
                raise ValidationError(f"Unknown skill check: {key}")
            return (self.abilities[ability] - 10) // 2
        if kind == "attack":
            attack_key = normalize_key(key or "")
            matches = [
                attack
                for attack in self.attacks
                if normalize_key(attack.attack_id) == attack_key
                or normalize_key(attack.name) == attack_key
            ]
            # One attack commonly matches both its ID and display name; dedupe
            # by ID before deciding whether a human-readable name is ambiguous.
            matches_by_id = {attack.attack_id: attack for attack in matches}
            if not matches_by_id:
                raise ValidationError(f"Unknown attack: {key}")
            if len(matches_by_id) > 1:
                raise ValidationError(
                    f"Attack name '{key}' is ambiguous; use an attack_id instead."
                )
            return next(iter(matches_by_id.values())).attack_bonus
        if kind == "initiative":
            return (self.abilities["dexterity"] - 10) // 2
        if kind == "death_save":
            return 0
        raise ValidationError(f"roll_kind '{roll_kind}' requires an engine_modifier.")
