import json
import unittest
from pathlib import Path

from bot.director import CampaignDirector, ProjectionContext


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PATH = ROOT / "campaigns" / "the_bell_beneath_briar_glen.json"


def all_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from all_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from all_keys(nested)


class ProjectionLeakageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.director = CampaignDirector.from_json(CAMPAIGN_PATH)
        cls.campaign = cls.director.canonical_campaign
        cls.secret_truths = tuple(fact.private_truth for fact in cls.campaign.facts.values())
        cls.motive_ids = tuple(
            motive_id
            for npc in cls.campaign.npcs.values()
            for motive_id in npc.private_motive_ids
        )

    def assert_private_material_absent(self, payload, *, allowed_truths=()):
        serialized = json.dumps(payload, sort_keys=True)
        for truth in self.secret_truths:
            if truth not in allowed_truths:
                self.assertNotIn(truth, serialized)
        for motive_id in self.motive_ids:
            self.assertNotIn(motive_id, serialized)
        forbidden_keys = {
            "truth",
            "private_truth",
            "private_motive_ids",
            "goals",
            "knowledge_limits",
            "checks",
            "dc",
            "private_dc",
            "dc_visibility",
            "success",
            "fail_forward",
            "exit_conditions",
            "next_scene_ids",
            "final_choices",
            "player_approaches",
        }
        self.assertTrue(forbidden_keys.isdisjoint(set(all_keys(payload))))

    def test_campaign_start_brief_contains_only_safe_opening_material(self):
        payload = self.director.campaign_start_brief().to_dict()

        self.assertIn("Rain needles the slate roofs", json.dumps(payload))
        self.assertIn("whole table", payload["opening"]["prompt"])
        self.assertIn("one open question", payload["opening"]["prompt"])
        self.assertIn("Stop and wait after that single prompt", payload["opening"]["prompt"])
        self.assertIn(
            "offer one open-ended handoff to the whole table unless rules or fiction focus one character",
            payload["performance_contract"]["turn_pattern"],
        )
        self.assertNotIn(
            "ask what each player does",
            payload["performance_contract"]["turn_pattern"],
        )
        self.assertNotIn("Briar roots stitch the chapel doors", json.dumps(payload))
        self.assertNotIn("The bronze bell hangs above a black pool", json.dumps(payload))
        self.assert_private_material_absent(payload)

    def test_current_scene_brief_excludes_secrets_future_scenes_and_hidden_dcs(self):
        payload = self.director.performer_brief(ProjectionContext(
            scene_id="rainy-square",
            npc_relationships={"mara-finch": {"trust": 2}},
        )).to_dict()
        serialized = json.dumps(payload)

        self.assertIn("The buried bell tolls", serialized)
        self.assertIn("Quick, practical sentences", serialized)
        self.assertIn("Open and cooperative", serialized)
        self.assertNotIn("follow fresh tracks", serialized)
        self.assertNotIn("accept or reject Voss's offer", serialized)
        self.assertNotIn("keep the grain theft secret", serialized)
        self.assertNotIn("Briar roots stitch the chapel doors", serialized)
        self.assertNotIn("The bronze bell hangs above a black pool", serialized)
        self.assert_private_material_absent(payload)

    def test_explicitly_empty_present_npc_set_does_not_restore_scene_defaults(self):
        payload = self.director.performer_brief(ProjectionContext(
            scene_id="rainy-square",
            present_npc_ids=(),
        )).to_dict()

        self.assertEqual([], payload["npcs"])
        self.assert_private_material_absent(payload)

    def test_fact_statement_appears_only_after_direct_reveal_gate(self):
        fact = self.campaign.facts["bell-restores-as-well-as-erases"]
        before = self.director.performer_brief(ProjectionContext(
            scene_id="ruined-chapel",
        )).to_dict()
        self.assertNotIn(fact.private_truth, json.dumps(before))

        evaluation = self.director.evaluate_reveals(
            committed_event_ids={"inspect-chapel-mural"},
            current_scene_id="ruined-chapel",
        )
        self.assertIn(fact.fact_id, evaluation.revealable_fact_ids)
        after = self.director.performer_brief(ProjectionContext(
            scene_id="ruined-chapel",
            revealed_fact_ids=evaluation.revealable_fact_ids,
        )).to_dict()

        self.assertIn(fact.private_truth, json.dumps(after))
        self.assert_private_material_absent(after, allowed_truths={fact.private_truth})

    def test_composite_clue_gate_requires_every_counted_clue(self):
        secret = self.campaign.facts["voss-awakened-the-bell"]
        one_clue = self.director.evaluate_reveals(
            committed_clue_ids={"grain-sack-thread"},
            current_scene_id="ruined-chapel",
        )
        self.assertNotIn(secret.fact_id, one_clue.revealable_fact_ids)

        both_clues = self.director.evaluate_reveals(
            committed_clue_ids={"grain-sack-thread", "magistrate-seal-wax"},
            current_scene_id="ruined-chapel",
        )
        self.assertIn("collect-two-voss-clues", both_clues.satisfied_gate_ids)
        self.assertIn(secret.fact_id, both_clues.revealable_fact_ids)
        after = self.director.performer_brief(ProjectionContext(
            scene_id="ruined-chapel",
            revealed_fact_ids=both_clues.revealable_fact_ids,
        )).to_dict()
        self.assertIn(secret.private_truth, json.dumps(after))
        self.assert_private_material_absent(after, allowed_truths={secret.private_truth})

    def test_scene_automatic_reveal_does_not_unlock_other_facts(self):
        payload = self.director.performer_brief(ProjectionContext(
            scene_id="bell-vault",
        )).to_dict()
        serialized = json.dumps(payload)

        self.assertIn(self.campaign.facts["finn-is-safe"].private_truth, serialized)
        self.assertNotIn(self.campaign.facts["voss-awakened-the-bell"].private_truth, serialized)
        self.assertNotIn(self.campaign.facts["bell-restores-as-well-as-erases"].private_truth, serialized)
        self.assert_private_material_absent(
            payload,
            allowed_truths={self.campaign.facts["finn-is-safe"].private_truth},
        )
        current_scene = payload["current_scene"]
        self.assertEqual(len(current_scene["decision_options"]), 3)
        self.assertIn("Accept any coherent alternative plan", current_scene["agency_rule"])
        for option in current_scene["decision_options"]:
            self.assertEqual(set(option), {"description", "cost"})
        self.assertNotIn("Briar Glen remembers", serialized)


if __name__ == "__main__":
    unittest.main()
