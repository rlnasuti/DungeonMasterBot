from __future__ import annotations

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from bot.game.demo import CASTER_PLAYER_ID, bootstrap_demo_session, demo_character_payloads
from bot.game.errors import ConflictError, NotFoundError, StaleVersionError, ValidationError
from bot.game.models import (
    CURRENCY_AWARD_MAXIMUM,
    CURRENCY_BALANCE_MAXIMUM,
    CURRENCY_DENOMINATIONS,
    CharacterState,
)
from bot.game.store import GameStore


class GameStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "game.sqlite3"
        self.store = GameStore(self.database_path)
        self.session_id = "test-session"
        self.store.create_session(
            session_id=self.session_id,
            idempotency_key="create-test-session",
            players=[
                {"player_id": "p1", "display_name": "Ada"},
                {"player_id": "p2", "display_name": "Lin"},
            ],
            public_world={
                "campaign": {"title": "Test One-Shot", "current_scene": "Character Creation"},
                "npcs": {"guide": {"name": "The Guide", "visible_attitude": "Neutral"}},
            },
            private_world={
                "campaign": {"secrets": ["The guide serves the lich."]},
                "npcs": {"guide": {"motives": ["Lead the party into a trap"]}},
            },
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def character_payload(name: str = "Aster") -> dict:
        return {
            "character_id": f"character-{name.lower()}",
            "name": name,
            "class_name": "Cleric",
            "subclass_name": None,
            "ruleset_id": "srd-5.2.1",
            "alignment": "Lawful Good",
            "experience_points": 300,
            "size": "Medium",
            "heroic_inspiration": True,
            "death_saves": {"successes": 1, "failures": 0},
            "level": 2,
            "ancestry": "Dwarf",
            "background": "Acolyte",
            "hp": 8,
            "max_hp": 10,
            "temp_hp": 3,
            "armor_class": 16,
            "armor_class_calculation": {
                "base": 14,
                "use_dexterity": True,
                "dexterity_cap": 2,
                "shield_bonus": 2,
                "misc_bonus": 0,
                "source_item_ids": ["scale-mail", "shield"],
            },
            "proficiency_bonus": 2,
            "speed": {"walk": 30},
            "proficiencies": {
                "armor": ["Light armor", "Medium armor", "Shields"],
                "weapons": ["Simple weapons"],
                "tools": ["Brewer's supplies"],
                "languages": ["Common", "Dwarvish"],
            },
            "abilities": {
                "strength": 12,
                "dexterity": 10,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 16,
                "charisma": 8,
            },
            "saving_throws": {
                "strength": 1,
                "dexterity": 0,
                "constitution": 2,
                "intelligence": 0,
                "wisdom": 5,
                "charisma": -1,
            },
            "skills": {"medicine": 5, "perception": 4, "religion": 2},
            "attacks": [
                {
                    "attack_id": "mace",
                    "name": "Mace",
                    "attack_type": "melee_weapon",
                    "attack_bonus": 3,
                    "damage": [{"dice": "1d6", "bonus": 1, "damage_type": "bludgeoning"}],
                    "reach": 5,
                    "range_normal": None,
                    "range_long": None,
                    "source_item_id": "mace",
                    "properties": [],
                }
            ],
            "hit_dice": {"d8": {"maximum": 2, "current": 1}},
            "spell_slots": {
                "1": {"maximum": 2, "current": 2},
                "2": {"maximum": 1, "current": 0},
            },
            "class_resources": {"channel_divinity": {"maximum": 1, "current": 1}},
            "features": [
                {
                    "feature_id": "channel-divinity",
                    "name": "Channel Divinity",
                    "source": "Cleric 2",
                    "rules_ref": "srd-5.2.1:feature:channel-divinity",
                    "summary": "Use a limited divine class feature.",
                    "resource_key": "channel_divinity",
                }
            ],
            "spellcasting": {
                "ability": "wisdom",
                "save_dc": 13,
                "attack_bonus": 5,
                "preparation_mode": "prepared",
                "spells": [
                    {
                        "spell_id": "guidance",
                        "name": "Guidance",
                        "level": 0,
                        "school": "Divination",
                        "casting_time": "1 action",
                        "range": "Touch",
                        "duration": "Concentration, up to 1 minute",
                        "components": ["V", "S"],
                        "concentration": True,
                        "ritual": False,
                        "rules_ref": "srd-5.2.1:spell:guidance",
                        "source": "Cleric",
                    },
                    {
                        "spell_id": "bless",
                        "name": "Bless",
                        "level": 1,
                        "school": "Enchantment",
                        "casting_time": "1 action",
                        "range": "30 feet",
                        "duration": "Concentration, up to 1 minute",
                        "components": ["V", "S", "M"],
                        "concentration": True,
                        "ritual": False,
                        "rules_ref": "srd-5.2.1:spell:bless",
                        "source": "Cleric",
                    },
                    {
                        "spell_id": "healing-word",
                        "name": "Healing Word",
                        "level": 1,
                        "school": "Abjuration",
                        "casting_time": "1 bonus action",
                        "range": "60 feet",
                        "duration": "Instantaneous",
                        "components": ["V"],
                        "concentration": False,
                        "ritual": False,
                        "rules_ref": "srd-5.2.1:spell:healing-word",
                        "source": "Acolyte background",
                    },
                ],
                "known_spell_ids": ["guidance"],
                "prepared_spell_ids": ["bless"],
                "always_prepared_spell_ids": ["healing-word"],
                "spellbook_spell_ids": [],
                "ritual_casting": True,
                "focus_item_id": "holy-symbol",
            },
            "conditions": ["Blessed"],
            "inventory": [
                {
                    "item_id": "mace",
                    "name": "Mace",
                    "quantity": 1,
                    "equipped": True,
                    "notes": "",
                    "rules_ref": "srd-5.2.1:weapon:mace",
                    "category": "weapon",
                    "weight": 4,
                },
                {
                    "item_id": "scale-mail",
                    "name": "Scale Mail",
                    "quantity": 1,
                    "equipped": True,
                    "notes": "",
                    "rules_ref": "srd-5.2.1:armor:scale-mail",
                    "category": "armor",
                    "weight": 45,
                },
                {
                    "item_id": "shield",
                    "name": "Shield",
                    "quantity": 1,
                    "equipped": True,
                    "notes": "",
                    "rules_ref": "srd-5.2.1:armor:shield",
                    "category": "shield",
                    "weight": 6,
                },
                {
                    "item_id": "holy-symbol",
                    "name": "Holy Symbol",
                    "quantity": 1,
                    "equipped": True,
                    "notes": "",
                    "rules_ref": "srd-5.2.1:gear:holy-symbol",
                    "category": "spellcasting_focus",
                    "weight": 1,
                }
            ],
        }

    def confirm_character(self, *, player_id: str = "p1", start_version: int = 0) -> int:
        staged = self.store.stage_character(
            self.session_id,
            player_id,
            character=self.character_payload(),
            source="created",
            expected_version=start_version,
            idempotency_key=f"stage-{player_id}",
        )
        confirmed = self.store.confirm_character(
            self.session_id,
            player_id,
            expected_version=staged["state_version"],
            idempotency_key=f"confirm-{player_id}",
        )
        return confirmed["state_version"]

    def character_from_snapshot(self, player_id: str = "p1") -> dict:
        snapshot = self.store.get_public_session(self.session_id)
        return next(player["character"] for player in snapshot["players"] if player["player_id"] == player_id)

    def test_latest_public_session_is_deterministic_and_404s_when_empty(self) -> None:
        empty_store = GameStore(Path(self.temp_dir.name) / "empty.sqlite3")
        with self.assertRaises(NotFoundError):
            empty_store.get_latest_public_session()

        for session_id in ("alpha-session", "zeta-session"):
            self.store.create_session(
                session_id=session_id,
                idempotency_key=f"create-{session_id}",
                players=[
                    {"player_id": "p1", "display_name": "One"},
                    {"player_id": "p2", "display_name": "Two"},
                ],
                public_world={"marker": session_id},
                private_world={"secret": f"private-{session_id}"},
            )

        with self.store._connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = ?, created_at = ? WHERE session_id = ?",
                ("2026-01-01T00:00:00.000+00:00", "2026-01-01T00:00:00.000+00:00", self.session_id),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ?, created_at = ? WHERE session_id = ?",
                ("2026-02-01T00:00:00.000+00:00", "2026-01-02T00:00:00.000+00:00", "alpha-session"),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ?, created_at = ? WHERE session_id = ?",
                ("2026-02-01T00:00:00.000+00:00", "2026-01-03T00:00:00.000+00:00", "zeta-session"),
            )

        latest = self.store.get_latest_public_session()
        self.assertEqual(latest["session_id"], "zeta-session")
        self.assertEqual(latest["world"], {"marker": "zeta-session"})
        self.assertNotIn("private_world", latest)
        self.assertNotIn("secret", json.dumps(latest))

        with self.store._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?, created_at = ?
                WHERE session_id IN (?, ?)
                """,
                (
                    "2026-03-01T00:00:00.000+00:00",
                    "2026-03-01T00:00:00.000+00:00",
                    "alpha-session",
                    "zeta-session",
                ),
            )
        self.assertEqual(
            self.store.get_latest_public_session()["session_id"],
            "alpha-session",
        )

    def test_conversation_messages_are_durable_ordered_and_state_version_independent(self) -> None:
        before = self.store.get_public_session(self.session_id)
        events_before = self.store.get_public_events(self.session_id)
        self.assertEqual(self.store.get_conversation_messages(self.session_id), [])

        first = self.store.put_conversation_message(
            self.session_id,
            "assistant-intro",
            role="assistant",
            text="  The rain needles Hawksmith's windows.  ",
        )
        second = self.store.put_conversation_message(
            self.session_id,
            "user-answer",
            role="user",
            text="Cendien studies the magistrate.",
        )

        self.assertEqual(first["sequence"], 1)
        self.assertEqual(first["text"], "  The rain needles Hawksmith's windows.  ")
        self.assertEqual(first["created_at"], first["updated_at"])
        self.assertEqual(second["sequence"], 2)
        messages = self.store.get_conversation_messages(self.session_id)
        self.assertEqual([message["message_id"] for message in messages], [
            "assistant-intro",
            "user-answer",
        ])

        replay = self.store.put_conversation_message(
            self.session_id,
            "assistant-intro",
            role="assistant",
            text="  The rain needles Hawksmith's windows.  ",
        )
        self.assertEqual(replay, first)
        self.assertEqual(len(self.store.get_conversation_messages(self.session_id)), 2)

        after = self.store.get_public_session(self.session_id)
        self.assertEqual(after["state_version"], before["state_version"])
        self.assertEqual(after["updated_at"], before["updated_at"])
        self.assertEqual(self.store.get_public_events(self.session_id), events_before)

        reopened = GameStore(self.database_path)
        self.assertEqual(reopened.get_conversation_messages(self.session_id), messages)

    def test_conversation_message_id_reuse_conflicts_and_input_is_strict(self) -> None:
        self.store.put_conversation_message(
            self.session_id,
            "same-id",
            role="user",
            text="We accept.",
        )
        for role, text in (
            ("assistant", "We accept."),
            ("user", "We refuse."),
        ):
            with self.subTest(role=role, text=text):
                with self.assertRaises(ConflictError):
                    self.store.put_conversation_message(
                        self.session_id,
                        "same-id",
                        role=role,
                        text=text,
                    )

        invalid_messages = (
            {"message_id": " padded ", "role": "user", "text": "Valid text"},
            {"message_id": "bad\ncontrol", "role": "user", "text": "Valid text"},
            {"message_id": "valid-id", "role": "system", "text": "Valid text"},
            {"message_id": "valid-id", "role": "User", "text": "Valid text"},
            {"message_id": "valid-id", "role": "assistant", "text": "  "},
            {"message_id": "valid-id", "role": "assistant", "text": 123},
        )
        for payload in invalid_messages:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    self.store.put_conversation_message(
                        self.session_id,
                        payload["message_id"],
                        role=payload["role"],
                        text=payload["text"],
                    )

    def test_conversation_clear_is_scoped_and_requires_an_existing_session(self) -> None:
        self.store.put_conversation_message(
            self.session_id,
            "one",
            role="assistant",
            text="First message.",
        )
        before = self.store.get_public_session(self.session_id)

        self.assertEqual(self.store.clear_conversation_messages(self.session_id), 1)
        self.assertEqual(self.store.clear_conversation_messages(self.session_id), 0)
        self.assertEqual(self.store.get_conversation_messages(self.session_id), [])
        after = self.store.get_public_session(self.session_id)
        self.assertEqual(after["state_version"], before["state_version"])
        self.assertEqual(after["updated_at"], before["updated_at"])

        for operation in (
            lambda: self.store.get_conversation_messages("missing-session"),
            lambda: self.store.put_conversation_message(
                "missing-session", "one", role="user", text="No session"
            ),
            lambda: self.store.clear_conversation_messages("missing-session"),
        ):
            with self.assertRaises(NotFoundError):
                operation()

    def test_conversation_schema_is_added_when_an_existing_database_is_reopened(self) -> None:
        with self.store._connect() as connection:
            connection.execute("DROP TABLE conversation_messages")

        migrated = GameStore(self.database_path)
        inserted = migrated.put_conversation_message(
            self.session_id,
            "after-migration",
            role="assistant",
            text="Welcome back.",
        )
        self.assertEqual(inserted["sequence"], 1)
        self.assertEqual(
            migrated.get_conversation_messages(self.session_id)[0]["message_id"],
            "after-migration",
        )

    def test_roll_visibility_schema_is_added_when_an_existing_database_is_reopened(self) -> None:
        with self.store._connect() as connection:
            connection.execute("ALTER TABLE pending_rolls DROP COLUMN dc_visibility")

        migrated = GameStore(self.database_path)
        with migrated._connect() as connection:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(pending_rolls)")
            }
        self.assertIn("dc_visibility", columns)

    def test_character_validation_and_hp_bounds(self) -> None:
        invalid = self.character_payload()
        invalid["hp"] = invalid["max_hp"] + 1
        with self.assertRaises(ValidationError):
            CharacterState.from_dict(invalid)

        version = self.confirm_character()
        damaged = self.store.apply_damage(
            self.session_id,
            "p1",
            amount=5,
            expected_version=version,
            idempotency_key="damage-five",
        )
        self.assertEqual((damaged["temp_hp"], damaged["hp"]), (0, 6))
        damaged_again = self.store.apply_damage(
            self.session_id,
            "p1",
            amount=100,
            expected_version=damaged["state_version"],
            idempotency_key="damage-one-hundred",
        )
        self.assertEqual(damaged_again["hp"], 0)
        healed = self.store.apply_healing(
            self.session_id,
            "p1",
            amount=100,
            expected_version=damaged_again["state_version"],
            idempotency_key="heal-one-hundred",
        )
        self.assertEqual(healed["hp"], 10)
        self.assertEqual(healed["hp_restored"], 10)

    def test_full_character_domain_round_trips_computed_public_sheet_data(self) -> None:
        character = CharacterState.from_dict(self.character_payload())
        serialized = character.to_dict()

        self.assertEqual(serialized["ruleset_id"], "srd-5.2.1")
        self.assertIsNone(serialized["subclass_name"])
        self.assertEqual(serialized["alignment"], "Lawful Good")
        self.assertEqual(serialized["experience_points"], 300)
        self.assertEqual(serialized["size"], "Medium")
        self.assertTrue(serialized["heroic_inspiration"])
        self.assertEqual(serialized["death_saves"], {"successes": 1, "failures": 0})
        self.assertEqual(serialized["speed"], {
            "walk": 30,
            "burrow": 0,
            "climb": 0,
            "fly": 0,
            "swim": 0,
            "hover": False,
        })
        self.assertEqual(serialized["proficiencies"]["languages"], ["Common", "Dwarvish"])
        self.assertEqual(serialized["armor_class_calculation"]["source_item_ids"], [
            "scale-mail",
            "shield",
        ])
        self.assertEqual(character.armor_class_calculation.total(0), character.armor_class)
        self.assertEqual(serialized["attacks"][0]["damage"][0], {
            "dice": "1d6",
            "bonus": 1,
            "damage_type": "bludgeoning",
        })
        self.assertEqual(character.roll_modifier("attack", "mace"), 3)
        self.assertEqual(character.roll_modifier("attack", "Mace"), 3)
        with self.assertRaises(ValidationError):
            character.roll_modifier("attack", "missing attack")
        self.assertEqual(serialized["inventory"][0]["category"], "weapon")
        self.assertEqual(serialized["inventory"][0]["weight"], 4.0)
        self.assertEqual(serialized["features"][0]["resource_key"], "channel_divinity")
        self.assertEqual(serialized["spellcasting"]["save_dc"], 13)
        self.assertEqual(serialized["spellcasting"]["attack_bonus"], 5)
        self.assertEqual(
            set(serialized["spellcasting"]["prepared_spell_ids"]),
            {"bless"},
        )
        self.assertEqual(
            serialized["spellcasting"]["always_prepared_spell_ids"],
            ["healing-word"],
        )
        healing_word = next(
            spell
            for spell in serialized["spellcasting"]["spells"]
            if spell["spell_id"] == "healing-word"
        )
        self.assertEqual(healing_word["source"], "Acolyte background")
        self.assertEqual(CharacterState.from_dict(serialized).to_dict(), serialized)

    def test_rules_profile_enriches_confirmed_sheet_and_preserves_play_state(self) -> None:
        version = self.confirm_character()
        spent_slot = self.store.change_resource(
            self.session_id,
            "p1",
            resource_type="spell_slot",
            resource_key="1",
            amount=1,
            restore=False,
            expected_version=version,
            idempotency_key="profile-spend-slot",
        )
        spent_feature = self.store.change_resource(
            self.session_id,
            "p1",
            resource_type="class_resource",
            resource_key="channel_divinity",
            amount=1,
            restore=False,
            expected_version=spent_slot["state_version"],
            idempotency_key="profile-spend-feature",
        )
        damaged = self.store.apply_damage(
            self.session_id,
            "p1",
            amount=5,
            expected_version=spent_feature["state_version"],
            idempotency_key="profile-damage",
        )
        awarded = self.store.award_currency(
            self.session_id,
            "p1",
            amount=17,
            denomination="gp",
            reason="Keep this award through the profile upgrade.",
            expected_version=damaged["state_version"],
            idempotency_key="profile-award",
        )

        profile = deepcopy(self.character_payload(name="Profile Must Not Rename"))
        profile["subclass_name"] = "Life Domain"
        profile["heroic_inspiration"] = False
        profile["death_saves"] = {"successes": 0, "failures": 0}
        profile["conditions"] = []
        profile["class_resources"]["channel_divinity"] = {
            "maximum": 2,
            "current": 2,
        }
        profile["inventory"].append({
            "item_id": "healers-kit",
            "name": "Healer's Kit",
            "quantity": 1,
            "equipped": False,
            "notes": "Added by rules profile",
            "rules_ref": "srd-5.2.1:gear:healers-kit",
            "category": "adventuring_gear",
            "weight": 3,
        })

        upgraded = self.store.apply_character_rules_profile(
            self.session_id,
            "p1",
            profile=profile,
            expected_version=awarded["state_version"],
            idempotency_key="apply-rules-profile",
        )
        replay = self.store.apply_character_rules_profile(
            self.session_id,
            "p1",
            profile=profile,
            expected_version=awarded["state_version"],
            idempotency_key="apply-rules-profile",
        )
        self.assertEqual(replay, upgraded)

        character = upgraded["character"]
        self.assertEqual(character["name"], "Aster")
        self.assertEqual(character["subclass_name"], "Life Domain")
        self.assertEqual((character["hp"], character["temp_hp"]), (6, 0))
        self.assertEqual(character["currency"]["gp"], 17)
        self.assertTrue(character["heroic_inspiration"])
        self.assertEqual(character["death_saves"], {"successes": 1, "failures": 0})
        self.assertEqual(character["conditions"], ["Blessed"])
        self.assertEqual(character["spell_slots"]["1"]["current"], 1)
        self.assertEqual(
            character["class_resources"]["channel_divinity"],
            {"maximum": 2, "current": 1},
        )
        self.assertIn("healers-kit", {item["item_id"] for item in character["inventory"]})
        self.assertEqual(
            self.store.get_public_events(self.session_id)[-1]["event_type"],
            "character_rules_profile_applied",
        )

    def test_rules_profile_rejects_manual_or_core_character_changes(self) -> None:
        version = self.confirm_character()
        manual = deepcopy(self.character_payload())
        manual["ruleset_id"] = "manual"
        with self.assertRaises(ValidationError):
            self.store.apply_character_rules_profile(
                self.session_id,
                "p1",
                profile=manual,
                expected_version=version,
                idempotency_key="manual-profile",
            )

        changed = deepcopy(self.character_payload())
        changed["abilities"]["wisdom"] = 18
        changed["spellcasting"]["save_dc"] = 14
        changed["spellcasting"]["attack_bonus"] = 6
        with self.assertRaises(ConflictError) as context:
            self.store.apply_character_rules_profile(
                self.session_id,
                "p1",
                profile=changed,
                expected_version=version,
                idempotency_key="respec-disguised-as-profile",
            )
        self.assertIn("abilities", context.exception.details["mismatched_fields"])
        self.assertEqual(self.store.get_public_session(self.session_id)["state_version"], version)

    def test_legacy_character_rows_gain_safe_additive_defaults(self) -> None:
        legacy = self.character_payload()
        for field_name in (
            "ruleset_id",
            "subclass_name",
            "alignment",
            "experience_points",
            "size",
            "heroic_inspiration",
            "death_saves",
            "speed",
            "proficiencies",
            "armor_class_calculation",
            "attacks",
            "features",
            "spellcasting",
        ):
            legacy.pop(field_name, None)
        legacy["inventory"] = [
            {
                key: value
                for key, value in legacy["inventory"][0].items()
                if key in {"item_id", "name", "quantity", "equipped", "notes"}
            }
        ]

        character = CharacterState.from_dict(legacy)
        public = character.to_dict()

        self.assertEqual(public["ruleset_id"], "manual")
        self.assertIsNone(public["subclass_name"])
        self.assertIsNone(public["alignment"])
        self.assertEqual(public["experience_points"], 0)
        self.assertEqual(public["size"], "Medium")
        self.assertFalse(public["heroic_inspiration"])
        self.assertEqual(public["death_saves"], {"successes": 0, "failures": 0})
        self.assertEqual(public["speed"]["walk"], 30)
        self.assertEqual(public["proficiencies"], {
            "armor": [],
            "weapons": [],
            "tools": [],
            "languages": [],
        })
        self.assertEqual(public["armor_class_calculation"], {
            "base": 16,
            "use_dexterity": False,
            "dexterity_cap": None,
            "shield_bonus": 0,
            "misc_bonus": 0,
            "source_item_ids": [],
        })
        self.assertEqual(public["attacks"], [])
        self.assertEqual(public["features"], [])
        self.assertIsNone(public["spellcasting"])
        self.assertEqual(public["inventory"][0]["category"], "other")
        self.assertEqual(public["inventory"][0]["weight"], 0.0)
        self.assertIsNone(public["inventory"][0]["rules_ref"])

    def test_character_domain_rejects_inconsistent_or_private_sheet_fields(self) -> None:
        invalid_cases: list[tuple[str, object]] = []

        bad_ruleset = self.character_payload()
        bad_ruleset["ruleset_id"] = "  "
        invalid_cases.append(("empty ruleset", bad_ruleset))

        bad_alignment = self.character_payload()
        bad_alignment["alignment"] = "  "
        invalid_cases.append(("blank alignment", bad_alignment))

        bad_experience = self.character_payload()
        bad_experience["experience_points"] = -1
        invalid_cases.append(("negative experience", bad_experience))

        boolean_experience = self.character_payload()
        boolean_experience["experience_points"] = True
        invalid_cases.append(("boolean experience", boolean_experience))

        bad_size = self.character_payload()
        bad_size["size"] = ""
        invalid_cases.append(("blank size", bad_size))

        bad_inspiration = self.character_payload()
        bad_inspiration["heroic_inspiration"] = 1
        invalid_cases.append(("non-boolean inspiration", bad_inspiration))

        bad_death_save = self.character_payload()
        bad_death_save["death_saves"]["failures"] = 4
        invalid_cases.append(("too many death-save failures", bad_death_save))

        unknown_death_save_field = self.character_payload()
        unknown_death_save_field["death_saves"]["stabilized"] = True
        invalid_cases.append(("unknown death-save field", unknown_death_save_field))

        bad_speed = self.character_payload()
        bad_speed["speed"] = {"walk": 30, "hover": True}
        invalid_cases.append(("hover without flight", bad_speed))

        duplicate_language = self.character_payload()
        duplicate_language["proficiencies"]["languages"] = ["Common", "common"]
        invalid_cases.append(("duplicate proficiency", duplicate_language))

        bad_ac = self.character_payload()
        bad_ac["armor_class_calculation"]["shield_bonus"] = 1
        invalid_cases.append(("AC arithmetic mismatch", bad_ac))

        missing_ac_item = self.character_payload()
        missing_ac_item["armor_class_calculation"]["source_item_ids"] = ["missing-armor"]
        invalid_cases.append(("AC missing source", missing_ac_item))

        bad_weight = self.character_payload()
        bad_weight["inventory"][0]["weight"] = True
        invalid_cases.append(("boolean item weight", bad_weight))

        bad_attack_dice = self.character_payload()
        bad_attack_dice["attacks"][0]["damage"][0]["dice"] = "1d7"
        invalid_cases.append(("unsupported attack dice", bad_attack_dice))

        missing_attack_item = self.character_payload()
        missing_attack_item["attacks"][0]["source_item_id"] = "missing-weapon"
        invalid_cases.append(("attack missing source", missing_attack_item))

        bad_feature = self.character_payload()
        bad_feature["features"][0]["resource_key"] = "missing_resource"
        invalid_cases.append(("feature missing resource", bad_feature))

        bad_save_dc = self.character_payload()
        bad_save_dc["spellcasting"]["save_dc"] = 99
        invalid_cases.append(("incorrect save DC", bad_save_dc))

        undefined_spell = self.character_payload()
        undefined_spell["spellcasting"]["prepared_spell_ids"].append("secret-spell")
        invalid_cases.append(("undefined prepared spell", undefined_spell))

        undefined_always_prepared_spell = self.character_payload()
        undefined_always_prepared_spell["spellcasting"][
            "always_prepared_spell_ids"
        ].append("secret-spell")
        invalid_cases.append(("undefined always-prepared spell", undefined_always_prepared_spell))

        blank_spell_source = self.character_payload()
        blank_spell_source["spellcasting"]["spells"][0]["source"] = "  "
        invalid_cases.append(("blank spell source", blank_spell_source))

        missing_focus = self.character_payload()
        missing_focus["spellcasting"]["focus_item_id"] = "secret-focus"
        invalid_cases.append(("missing spell focus", missing_focus))

        private_character_field = self.character_payload()
        private_character_field["dm_secret"] = "Never expose this."
        invalid_cases.append(("private top-level field", private_character_field))

        private_spell_field = self.character_payload()
        private_spell_field["spellcasting"]["spells"][0]["secret_effect"] = "Never expose this."
        invalid_cases.append(("private spell field", private_spell_field))

        for label, invalid in invalid_cases:
            with self.subTest(label=label):
                with self.assertRaises(ValidationError):
                    CharacterState.from_dict(invalid)

    def test_attack_roll_uses_authoritative_profile_bonus_and_hides_it(self) -> None:
        version = self.confirm_character()
        requested = self.store.request_roll(
            self.session_id,
            "p1",
            roll_kind="attack",
            check_key="mace",
            prompt="Roll a physical d20 for Aster's mace attack.",
            dc=14,
            engine_modifier=None,
            expected_version=version,
            idempotency_key="request-mace-attack",
        )
        self.assertNotIn("modifier", requested["pending_roll"])
        submitted = self.store.submit_roll(
            self.session_id,
            requested["pending_roll"]["roll_id"],
            "p1",
            raw_d20=11,
            expected_version=requested["state_version"],
            idempotency_key="submit-mace-attack",
        )
        self.assertEqual(submitted["roll_result"]["total"], 14)
        self.assertTrue(submitted["roll_result"]["success"])

    def test_binary_roll_requires_dc_and_public_visibility_projects_target(self) -> None:
        version = self.confirm_character()
        with self.assertRaisesRegex(ValidationError, "requires a difficulty class"):
            self.store.request_roll(
                self.session_id,
                "p1",
                roll_kind="skill",
                check_key="perception",
                prompt="Look for a hidden seam.",
                dc=None,
                engine_modifier=None,
                dc_visibility="private",
                expected_version=version,
                idempotency_key="missing-binary-dc",
            )

        requested = self.store.request_roll(
            self.session_id,
            "p1",
            roll_kind="ability",
            check_key="wisdom",
            prompt="Hold steady against the visible force.",
            dc=15,
            engine_modifier=None,
            dc_visibility="public",
            expected_version=version,
            idempotency_key="public-ability-dc",
        )
        pending = requested["pending_roll"]
        self.assertEqual(pending["dc_visibility"], "public")
        self.assertEqual(pending["target_total"], 15)
        self.assertNotIn("modifier", pending)

        resolved = self.store.submit_roll(
            self.session_id,
            pending["roll_id"],
            "p1",
            raw_d20=12,
            expected_version=requested["state_version"],
            idempotency_key="resolve-public-ability-dc",
        )["roll_result"]
        self.assertIs(type(resolved["success"]), bool)
        self.assertEqual(resolved["dc_visibility"], "public")
        self.assertEqual(resolved["target_total"], 15)

    def test_private_roll_result_has_boolean_success_without_target(self) -> None:
        version = self.confirm_character()
        requested = self.store.request_roll(
            self.session_id,
            "p1",
            roll_kind="skill",
            check_key="perception",
            prompt="Search for a hidden trap.",
            dc=15,
            engine_modifier=None,
            dc_visibility="private",
            expected_version=version,
            idempotency_key="private-perception-dc",
        )
        self.assertNotIn("target_total", requested["pending_roll"])

        resolved = self.store.submit_roll(
            self.session_id,
            requested["pending_roll"]["roll_id"],
            "p1",
            raw_d20=1,
            expected_version=requested["state_version"],
            idempotency_key="resolve-private-perception-dc",
        )["roll_result"]
        self.assertIs(resolved["success"], False)
        self.assertEqual(resolved["dc_visibility"], "private")
        self.assertNotIn("target_total", resolved)

    def test_always_prepared_spell_can_come_from_outside_a_spellbook(self) -> None:
        wizard = demo_character_payloads()[CASTER_PLAYER_ID]
        self.assertNotIn("fire-bolt", wizard["spellcasting"]["spellbook_spell_ids"])
        wizard["spellcasting"]["always_prepared_spell_ids"] = ["fire-bolt"]

        character = CharacterState.from_dict(wizard)

        self.assertEqual(character.spellcasting.always_prepared_spell_ids, {"fire-bolt"})
        self.assertNotIn("fire-bolt", character.spellcasting.spellbook_spell_ids)

        invalid = demo_character_payloads()[CASTER_PLAYER_ID]
        invalid["spellcasting"]["prepared_spell_ids"].append("fire-bolt")
        with self.assertRaises(ValidationError):
            CharacterState.from_dict(invalid)

    def test_prior_spellcasting_rows_default_source_and_always_prepared(self) -> None:
        prior = self.character_payload()
        prior["spellcasting"].pop("always_prepared_spell_ids")
        for spell in prior["spellcasting"]["spells"]:
            spell.pop("source")

        spellcasting = CharacterState.from_dict(prior).to_dict()["spellcasting"]

        self.assertEqual(spellcasting["always_prepared_spell_ids"], [])
        self.assertTrue(all(spell["source"] is None for spell in spellcasting["spells"]))

    def test_character_currency_defaults_validation_and_serialization(self) -> None:
        character = CharacterState.from_dict(self.character_payload())
        expected_empty_purse = {
            denomination: 0 for denomination in CURRENCY_DENOMINATIONS
        }
        self.assertEqual(character.currency, expected_empty_purse)
        self.assertEqual(character.to_dict()["currency"], expected_empty_purse)

        with_currency = self.character_payload()
        with_currency["currency"] = {"gp": 25, "SP": 8}
        normalized = CharacterState.from_dict(with_currency)
        self.assertEqual(normalized.currency["gp"], 25)
        self.assertEqual(normalized.currency["sp"], 8)
        self.assertEqual(normalized.currency["cp"], 0)

        for invalid_currency in (
            {"gp": -1},
            {"gp": True},
            {"gp": CURRENCY_BALANCE_MAXIMUM + 1},
            {"dragon_coin": 1},
            {"gp": 1, "GP": 2},
        ):
            invalid = self.character_payload()
            invalid["currency"] = invalid_currency
            with self.subTest(currency=invalid_currency):
                with self.assertRaises(ValidationError):
                    CharacterState.from_dict(invalid)

    def test_public_snapshot_backfills_default_currency_for_legacy_sheets(self) -> None:
        self.confirm_character()
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT character_json FROM players WHERE session_id = ? AND player_id = ?",
                (self.session_id, "p1"),
            ).fetchone()
            legacy_character = json.loads(row["character_json"])
            for field_name in (
                "currency",
                "ruleset_id",
                "subclass_name",
                "alignment",
                "experience_points",
                "size",
                "heroic_inspiration",
                "death_saves",
                "speed",
                "proficiencies",
                "armor_class_calculation",
                "attacks",
                "features",
                "spellcasting",
            ):
                legacy_character.pop(field_name, None)
            for item in legacy_character["inventory"]:
                item.pop("rules_ref", None)
                item.pop("category", None)
                item.pop("weight", None)
            connection.execute(
                "UPDATE players SET character_json = ? WHERE session_id = ? AND player_id = ?",
                (json.dumps(legacy_character), self.session_id, "p1"),
            )

        snapshot = self.character_from_snapshot()

        self.assertEqual(
            snapshot["currency"],
            {denomination: 0 for denomination in CURRENCY_DENOMINATIONS},
        )
        self.assertEqual(snapshot["ruleset_id"], "manual")
        self.assertIsNone(snapshot["alignment"])
        self.assertEqual(snapshot["experience_points"], 0)
        self.assertEqual(snapshot["size"], "Medium")
        self.assertFalse(snapshot["heroic_inspiration"])
        self.assertEqual(snapshot["death_saves"], {"successes": 0, "failures": 0})
        self.assertEqual(snapshot["speed"]["walk"], 30)
        self.assertEqual(snapshot["armor_class_calculation"]["base"], 16)
        self.assertEqual(snapshot["attacks"], [])
        self.assertIsNone(snapshot["spellcasting"])
        self.assertEqual(snapshot["inventory"][0]["category"], "other")

    def test_currency_award_is_bounded_public_persistent_and_idempotent(self) -> None:
        version = self.confirm_character()
        first = self.store.award_currency(
            self.session_id,
            "p1",
            amount=75,
            denomination="GP",
            reason="Voss pays an advance from the purse he offered.",
            expected_version=version,
            idempotency_key="voss-advance",
        )
        replay = self.store.award_currency(
            self.session_id,
            "p1",
            amount=75,
            denomination="gp",
            reason="Voss pays an advance from the purse he offered.",
            expected_version=version,
            idempotency_key="voss-advance",
        )

        self.assertEqual(first, replay)
        self.assertEqual(first["balance"], 75)
        self.assertEqual(first["currency"]["gp"], 75)
        self.assertEqual(first["character_name"], "Aster")
        self.assertEqual(self.character_from_snapshot()["currency"]["gp"], 75)
        events = self.store.get_public_events(self.session_id, after_version=version)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "currency_awarded")
        self.assertEqual(events[0]["payload"]["reason"], first["reason"])
        self.assertNotIn("private", json.dumps(events[0]).lower())

        reloaded = GameStore(self.database_path)
        reloaded_character = next(
            player["character"]
            for player in reloaded.get_public_session(self.session_id)["players"]
            if player["player_id"] == "p1"
        )
        self.assertEqual(reloaded_character["currency"]["gp"], 75)

        for invalid in (
            {"amount": 0, "denomination": "gp"},
            {"amount": CURRENCY_AWARD_MAXIMUM + 1, "denomination": "gp"},
            {"amount": 1, "denomination": "credits"},
        ):
            with self.subTest(award=invalid):
                with self.assertRaises(ValidationError):
                    self.store.award_currency(
                        self.session_id,
                        "p1",
                        reason="Invalid award.",
                        expected_version=first["state_version"],
                        idempotency_key=f"invalid-award-{invalid['amount']}-{invalid['denomination']}",
                        **invalid,
                    )
        self.assertEqual(
            self.store.get_public_session(self.session_id)["state_version"],
            first["state_version"],
        )

    def test_currency_award_requires_confirmed_character_and_cannot_overflow(self) -> None:
        with self.assertRaises(ConflictError):
            self.store.award_currency(
                self.session_id,
                "p1",
                amount=1,
                denomination="gp",
                reason="No character can receive this.",
                expected_version=0,
                idempotency_key="award-before-character",
            )

        payload = self.character_payload()
        payload["currency"] = {"gp": CURRENCY_BALANCE_MAXIMUM}
        staged = self.store.stage_character(
            self.session_id,
            "p1",
            character=payload,
            source="created",
            expected_version=0,
            idempotency_key="stage-rich-character",
        )
        confirmed = self.store.confirm_character(
            self.session_id,
            "p1",
            expected_version=staged["state_version"],
            idempotency_key="confirm-rich-character",
        )
        with self.assertRaises(ConflictError):
            self.store.award_currency(
                self.session_id,
                "p1",
                amount=1,
                denomination="gp",
                reason="The purse cannot hold another coin.",
                expected_version=confirmed["state_version"],
                idempotency_key="overflow-rich-character",
            )
        self.assertEqual(
            self.store.get_public_session(self.session_id)["state_version"],
            confirmed["state_version"],
        )

    def test_spell_slot_consumption_and_restore_are_bounded(self) -> None:
        version = self.confirm_character()
        used = self.store.change_resource(
            self.session_id,
            "p1",
            resource_type="spell_slot",
            resource_key="1",
            amount=1,
            restore=False,
            expected_version=version,
            idempotency_key="cast-one",
        )
        self.assertEqual(used["current"], 1)
        with self.assertRaises(ConflictError):
            self.store.change_resource(
                self.session_id,
                "p1",
                resource_type="spell_slot",
                resource_key="1",
                amount=2,
                restore=False,
                expected_version=used["state_version"],
                idempotency_key="cast-too-many",
            )
        restored = self.store.change_resource(
            self.session_id,
            "p1",
            resource_type="spell_slot",
            resource_key="1",
            amount=9,
            restore=True,
            expected_version=used["state_version"],
            idempotency_key="restore-slots",
        )
        self.assertEqual(restored["current"], 2)
        self.assertEqual(restored["changed_amount"], 1)

    def test_idempotent_mutation_is_applied_once(self) -> None:
        version = self.confirm_character()
        first = self.store.apply_damage(
            self.session_id,
            "p1",
            amount=2,
            expected_version=version,
            idempotency_key="network-retry",
        )
        replay = self.store.apply_damage(
            self.session_id,
            "p1",
            amount=2,
            expected_version=version,
            idempotency_key="network-retry",
        )
        self.assertEqual(first, replay)
        snapshot = self.store.get_public_session(self.session_id)
        self.assertEqual(snapshot["state_version"], version + 1)
        self.assertEqual(self.character_from_snapshot()["temp_hp"], 1)
        with self.assertRaises(ConflictError):
            self.store.apply_damage(
                self.session_id,
                "p1",
                amount=3,
                expected_version=version,
                idempotency_key="network-retry",
            )

    def test_player_identity_update_renames_confirmed_character_and_is_idempotent(self) -> None:
        version = self.confirm_character()
        before = self.character_from_snapshot()
        renamed = self.store.update_player_identity(
            self.session_id,
            "p1",
            display_name="Robert",
            character_name="Juicebox",
            expected_version=version,
            idempotency_key="rename-player-one",
        )
        replay = self.store.update_player_identity(
            self.session_id,
            "p1",
            display_name="Robert",
            character_name="Juicebox",
            expected_version=version,
            idempotency_key="rename-player-one",
        )

        self.assertEqual(renamed, replay)
        self.assertEqual(renamed["state_version"], version + 1)
        self.assertEqual(renamed["display_name"], "Robert")
        self.assertEqual(renamed["character_name"], "Juicebox")
        snapshot = self.store.get_public_session(self.session_id)
        player = next(player for player in snapshot["players"] if player["player_id"] == "p1")
        self.assertEqual(player["display_name"], "Robert")
        self.assertEqual(player["character"]["name"], "Juicebox")
        self.assertEqual(player["character"]["hp"], before["hp"])
        self.assertEqual(player["character"]["spell_slots"], before["spell_slots"])
        events = self.store.get_public_events(self.session_id, after_version=version)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "player_identity_updated")
        self.assertEqual(events[0]["payload"]["character_name"], "Juicebox")

        with self.assertRaises(ConflictError):
            self.store.update_player_identity(
                self.session_id,
                "p1",
                character_name="Different name",
                expected_version=version,
                idempotency_key="rename-player-one",
            )

    def test_player_identity_update_requires_a_name_and_existing_character(self) -> None:
        with self.assertRaises(ValidationError):
            self.store.update_player_identity(
                self.session_id,
                "p1",
                expected_version=0,
                idempotency_key="empty-identity-update",
            )
        with self.assertRaises(ConflictError):
            self.store.update_player_identity(
                self.session_id,
                "p1",
                character_name="Juicebox",
                expected_version=0,
                idempotency_key="rename-missing-character",
            )
        self.assertEqual(self.store.get_public_session(self.session_id)["state_version"], 0)

    def test_stale_state_version_is_rejected_without_mutation(self) -> None:
        version = self.confirm_character()
        with self.assertRaises(StaleVersionError) as context:
            self.store.apply_damage(
                self.session_id,
                "p1",
                amount=1,
                expected_version=version - 1,
                idempotency_key="stale-damage",
            )
        self.assertEqual(context.exception.details["current_version"], version)
        self.assertEqual(self.character_from_snapshot()["temp_hp"], 3)

    def test_physical_roll_accepts_only_d20_face_and_hides_engine_fields(self) -> None:
        version = self.confirm_character()
        requested = self.store.request_roll(
            self.session_id,
            "p1",
            roll_kind="skill",
            check_key="perception",
            prompt="Roll Perception.",
            dc=15,
            engine_modifier=None,
            expected_version=version,
            idempotency_key="request-perception",
        )
        roll_id = requested["pending_roll"]["roll_id"]
        self.assertNotIn("dc", requested["pending_roll"])
        self.assertNotIn("modifier", requested["pending_roll"])
        roll_version = requested["state_version"]
        for invalid_roll in (0, 21, True):
            with self.assertRaises(ValidationError):
                self.store.submit_roll(
                    self.session_id,
                    roll_id,
                    "p1",
                    raw_d20=invalid_roll,
                    expected_version=roll_version,
                    idempotency_key=f"invalid-{invalid_roll!r}",
                )
        self.assertEqual(self.store.get_public_session(self.session_id)["state_version"], roll_version)
        submitted = self.store.submit_roll(
            self.session_id,
            roll_id,
            "p1",
            raw_d20=11,
            expected_version=roll_version,
            idempotency_key="submit-perception",
        )
        self.assertEqual(submitted["roll_result"]["total"], 15)
        self.assertTrue(submitted["roll_result"]["success"])
        public_json = json.dumps(self.store.get_public_events(self.session_id))
        self.assertNotIn('"dc"', public_json)
        self.assertNotIn('"modifier"', public_json)
        self.assertEqual(self.store.get_public_session(self.session_id)["pending_rolls"], [])

    def test_private_world_and_npc_state_never_cross_public_boundary(self) -> None:
        public_json = json.dumps(self.store.get_public_session(self.session_id))
        self.assertNotIn("serves the lich", public_json)
        self.assertNotIn("Lead the party", public_json)
        engine = self.store.get_engine_session(self.session_id)
        self.assertIn("serves the lich", json.dumps(engine["private_world"]))

        updated = self.store.update_world_state(
            self.session_id,
            public_patch={"campaign": {"current_scene": "Old Bridge"}},
            private_patch={"npcs": {"guide": {"ulterior_motives": ["Steal the relic"]}}},
            expected_version=0,
            idempotency_key="move-scene",
        )
        self.assertNotIn("Steal the relic", json.dumps(updated))
        self.assertNotIn("Steal the relic", json.dumps(self.store.get_public_events(self.session_id)))
        self.assertIn("Steal the relic", json.dumps(self.store.get_engine_session(self.session_id)))
        with self.assertRaises(ValidationError):
            self.store.update_world_state(
                self.session_id,
                public_patch={"npcs": {"guide": {"secrets": ["leak"]}}},
                private_patch={},
                expected_version=updated["state_version"],
                idempotency_key="bad-public-secret",
            )

    def test_state_persists_across_store_reloads(self) -> None:
        version = self.confirm_character()
        damaged = self.store.apply_damage(
            self.session_id,
            "p1",
            amount=4,
            expected_version=version,
            idempotency_key="persistent-damage",
        )
        reloaded = GameStore(self.database_path)
        snapshot = reloaded.get_public_session(self.session_id)
        character = next(player["character"] for player in snapshot["players"] if player["player_id"] == "p1")
        self.assertEqual(snapshot["state_version"], damaged["state_version"])
        self.assertEqual((character["temp_hp"], character["hp"]), (0, 7))
        self.assertIn("serves the lich", json.dumps(reloaded.get_engine_session(self.session_id)))

    def test_sessions_require_exactly_two_distinct_players(self) -> None:
        with self.assertRaises(ValidationError):
            self.store.create_session(
                session_id="one-player",
                idempotency_key="one-player-key",
                players=[{"player_id": "solo", "display_name": "Solo"}],
            )
        with self.assertRaises(ValidationError):
            self.store.create_session(
                session_id="duplicate-players",
                idempotency_key="duplicate-player-key",
                players=[
                    {"player_id": "same", "display_name": "One"},
                    {"player_id": "same", "display_name": "Two"},
                ],
            )

    def test_demo_bootstrap_is_repeatable_and_exercises_ui_state(self) -> None:
        demo = bootstrap_demo_session(self.store, session_id="demo-test")
        replay = bootstrap_demo_session(self.store, session_id="demo-test")
        self.assertEqual(demo, replay)
        self.assertEqual(demo["state_version"], 5)
        self.assertEqual(len(demo["players"]), 2)
        self.assertEqual(len(demo["pending_rolls"]), 1)
        characters = [player["character"] for player in demo["players"]]
        self.assertTrue(any(character["spell_slots"] for character in characters))
        self.assertTrue(all(character["hit_dice"] for character in characters))
        self.assertTrue(all(character["class_resources"] for character in characters))
        self.assertTrue(all(character["conditions"] for character in characters))
        self.assertTrue(all(character["ruleset_id"] == "srd-5.2.1" for character in characters))
        self.assertTrue(all(character["speed"]["walk"] > 0 for character in characters))
        self.assertTrue(all(character["proficiencies"] for character in characters))
        self.assertTrue(all(character["armor_class_calculation"] for character in characters))
        self.assertTrue(all(character["attacks"] for character in characters))
        self.assertTrue(all(character["features"] for character in characters))
        self.assertTrue(any(character["spellcasting"] for character in characters))
        self.assertTrue(all(character["size"] == "Medium" for character in characters))
        self.assertTrue(all(character["experience_points"] >= 0 for character in characters))
        self.assertTrue(all(character["death_saves"] == {
            "successes": 0,
            "failures": 0,
        } for character in characters))
        martial = next(character for character in characters if character["class_name"] == "Fighter")
        caster = next(character for character in characters if character["class_name"] == "Wizard")
        self.assertEqual(martial["class_resources"]["second_wind"]["maximum"], 2)
        sleep = next(
            spell for spell in caster["spellcasting"]["spells"] if spell["spell_id"] == "sleep"
        )
        self.assertEqual(sleep["range"], "60 feet")
        self.assertTrue(sleep["concentration"])
        self.assertEqual(sleep["source"], "Wizard")
        self.assertEqual(caster["spellcasting"]["always_prepared_spell_ids"], [])


if __name__ == "__main__":
    unittest.main()
