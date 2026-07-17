import json
import unittest
from pathlib import Path

from bot.director import CampaignValidationError, campaign_from_dict, load_campaign


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PATH = ROOT / "campaigns" / "the_bell_beneath_briar_glen.json"


class CampaignLoaderTests(unittest.TestCase):
    def test_loads_private_canonical_campaign_and_freezes_indexes(self):
        campaign = load_campaign(CAMPAIGN_PATH)

        self.assertEqual("the-bell-beneath-briar-glen", campaign.campaign_id)
        self.assertEqual("rainy-square", campaign.start_scene_id)
        self.assertEqual(12, campaign.scenes["rainy-square"].checks["read-voss"].private_dc)
        self.assertEqual(
            "public",
            campaign.scenes["ruined-chapel"].checks["open-root-door"].dc_visibility,
        )
        self.assertIn("winter grain fund", campaign.facts["voss-awakened-the-bell"].private_truth)
        with self.assertRaises(TypeError):
            campaign.facts["new-fact"] = campaign.facts["finn-is-safe"]

    def test_rainy_square_checks_cover_supported_approaches_with_fail_forward_outcomes(self):
        campaign = load_campaign(CAMPAIGN_PATH)
        scene = campaign.scenes["rainy-square"]
        expected = {
            "read-voss": ("Insight", 12),
            "notice-square-details": ("Perception", 11),
            "connect-square-evidence": ("Investigation", 12),
            "win-voss-cooperation": ("Persuasion", 12),
            "pressure-voss": ("Intimidation", 13),
            "misdirect-voss": ("Deception", 13),
        }

        for check_id, (skill, private_dc) in expected.items():
            with self.subTest(check_id=check_id):
                check = scene.checks[check_id]
                self.assertEqual(check.skill, skill)
                self.assertEqual(check.private_dc, private_dc)
                self.assertTrue(check.success)
                self.assertTrue(check.fail_forward)

        protected_truths = tuple(fact.private_truth for fact in campaign.facts.values())
        for check in scene.checks.values():
            outcomes = f"{check.success} {check.fail_forward}"
            for protected_truth in protected_truths:
                self.assertNotIn(protected_truth, outcomes)

    def test_rejects_cross_references_to_unknown_npcs(self):
        with CAMPAIGN_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["scenes"][0]["available_npc_ids"].append("unknown-npc")

        with self.assertRaisesRegex(CampaignValidationError, "unknown NPCs"):
            campaign_from_dict(raw)

    def test_rejects_private_facts_without_reveal_conditions(self):
        with CAMPAIGN_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["facts"][0]["reveal_conditions"] = []

        with self.assertRaisesRegex(CampaignValidationError, "reveal condition"):
            campaign_from_dict(raw)

    def test_rejects_unknown_check_dc_visibility(self):
        with CAMPAIGN_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["scenes"][0]["checks"][0]["dc_visibility"] = "sometimes"

        with self.assertRaisesRegex(CampaignValidationError, "private or public"):
            campaign_from_dict(raw)


if __name__ == "__main__":
    unittest.main()
