import unittest
from dataclasses import asdict
from pathlib import Path

from bot.director import (
    CampaignDirector,
    DirectorError,
    RequestRollCommand,
    TransitionSceneCommand,
)


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PATH = ROOT / "campaigns" / "the_bell_beneath_briar_glen.json"


class GatesAndCommandsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.director = CampaignDirector.from_json(CAMPAIGN_PATH)

    def test_transition_command_is_validated_but_not_applied(self):
        original_start = self.director.canonical_campaign.start_scene_id
        command = self.director.commands.transition_scene(
            session_id="session-1",
            expected_state_version=7,
            idempotency_key="turn-4-transition",
            from_scene_id="rainy-square",
            to_scene_id="ruined-chapel",
            reason_event_id="party-chooses-chapel",
        )

        self.assertIsInstance(command, TransitionSceneCommand)
        self.assertEqual(7, command.expected_state_version)
        self.assertEqual(original_start, self.director.canonical_campaign.start_scene_id)
        with self.assertRaises(DirectorError):
            self.director.commands.transition_scene(
                session_id="session-1",
                expected_state_version=7,
                idempotency_key="invalid-transition",
                from_scene_id="rainy-square",
                to_scene_id="bell-vault",
                reason_event_id="skip-ahead",
            )

    def test_relationship_clue_and_reveal_commands_are_pure_values(self):
        relationship = self.director.commands.adjust_npc_relationship(
            session_id="session-1",
            expected_state_version=8,
            idempotency_key="turn-5-mara-trust",
            npc_id="mara-finch",
            deltas={"trust": 1, "respect": 1},
            reason_event_id="promise-to-find-finn",
        )
        clue = self.director.commands.record_clue(
            session_id="session-1",
            expected_state_version=9,
            idempotency_key="turn-5-clue",
            clue_id="mural-shows-silver-clapper",
            source_event_id="inspect-chapel-mural",
        )
        reveal = self.director.commands.record_reveal(
            session_id="session-1",
            expected_state_version=10,
            idempotency_key="turn-5-reveal",
            fact_id="bell-restores-as-well-as-erases",
            satisfied_gate_id="inspect-chapel-mural",
        )

        self.assertEqual(1, relationship.deltas["trust"])
        self.assertEqual("mural-shows-silver-clapper", clue.clue_id)
        self.assertEqual("bell-restores-as-well-as-erases", reveal.fact_id)

    def test_public_roll_command_has_no_dc_or_resolution_details(self):
        command = self.director.commands.request_roll(
            session_id="session-1",
            expected_state_version=11,
            idempotency_key="turn-6-read-voss",
            roll_id="roll-1",
            player_id="player-1",
            scene_id="rainy-square",
            check_id="read-voss",
            public_reason="Read Voss's reaction to the missing clapper.",
        )
        payload = asdict(command)

        self.assertIsInstance(command, RequestRollCommand)
        self.assertEqual("Wisdom", command.ability)
        self.assertEqual("Insight", command.skill)
        self.assertNotIn("dc", payload)
        self.assertNotIn("private_dc", payload)
        self.assertNotIn("success", payload)
        self.assertNotIn("fail_forward", payload)


if __name__ == "__main__":
    unittest.main()
