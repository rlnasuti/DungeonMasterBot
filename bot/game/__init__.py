"""Authoritative, persistent game-state primitives for DungeonMasterBot."""

from bot.game.errors import (
    ConflictError,
    GameStateError,
    NotFoundError,
    StaleVersionError,
    ValidationError,
)
from bot.game.models import (
    ArmorClassCalculation,
    AttackProfile,
    CharacterFeature,
    CharacterState,
    DamageProfile,
    DeathSaves,
    InventoryItem,
    Proficiencies,
    ResourcePool,
    Speed,
    Spellcasting,
    SpellDefinition,
)
from bot.game.store import GameStore

__all__ = [
    "ArmorClassCalculation",
    "AttackProfile",
    "CharacterFeature",
    "CharacterState",
    "ConflictError",
    "DamageProfile",
    "DeathSaves",
    "GameStateError",
    "GameStore",
    "InventoryItem",
    "NotFoundError",
    "Proficiencies",
    "ResourcePool",
    "Speed",
    "Spellcasting",
    "SpellDefinition",
    "StaleVersionError",
    "ValidationError",
]
