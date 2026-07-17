from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from flask import Flask

from bot.api.director_routes import director_blueprint
from bot.api.game_routes import STORE_EXTENSION_KEY
from bot.director import CampaignDirector
from bot.game.demo import bootstrap_demo_session
from bot.game.store import GameStore


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_PATH = ROOT / "campaigns" / "the_bell_beneath_briar_glen.json"


def all_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from all_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from all_keys(nested)


class DirectorRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.store = GameStore(Path(self.temp_dir.name) / "director.sqlite3")
        bootstrap_demo_session(self.store, session_id="runtime")
        self.director = CampaignDirector.from_json(CAMPAIGN_PATH)
        self.campaign = self.director.canonical_campaign
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.app.extensions[STORE_EXTENSION_KEY] = self.store
        self.app.extensions["campaign_director"] = self.director
        self.app.register_blueprint(director_blueprint)
        self.client = self.app.test_client()

    def assert_safe_payload(self, payload, *, allowed_fact_ids=()) -> None:
        serialized = json.dumps(payload, sort_keys=True)
        for fact_id, fact in self.campaign.facts.items():
            if fact_id not in allowed_fact_ids:
                self.assertNotIn(fact.private_truth, serialized)
            self.assertNotIn(fact_id, serialized)
            for condition in fact.reveal_conditions:
                self.assertNotIn(condition, serialized)
        for scene_id, scene in self.campaign.scenes.items():
            if scene_id != payload["performer_context"]["current_scene"]["id"]:
                self.assertNotIn(scene.entry_description, serialized)
        forbidden_keys = {
            "motives",
            "private_motive_ids",
            "goals",
            "knowledge_limits",
            "relationship",
            "trust",
            "suspicion",
            "fear",
            "respect",
            "checks",
            "dc",
            "private_dc",
            "dc_visibility",
            "success",
            "fail_forward",
            "next_scene_ids",
            "exit_conditions",
            "final_choices",
            "player_approaches",
        }
        self.assertTrue(forbidden_keys.isdisjoint(set(all_keys(payload))))

    def post(self, suffix: str, payload: dict):
        return self.client.post(f"/api/sessions/runtime/director/{suffix}", json=payload)

    def test_get_context_is_scene_local_and_performer_safe(self) -> None:
        response = self.client.get("/api/sessions/runtime/director")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["state_version"], 5)
        self.assertEqual(payload["performer_context"]["current_scene"]["id"], "rainy-square")
        self.assertEqual(payload["public_state"]["campaign"]["scene_title"], "The Toll in the Rain")
        self.assertEqual(len(payload["performer_context"]["npcs"]), 2)
        self.assertNotIn(
            "player_approaches",
            payload["performer_context"]["current_scene"],
        )
        self.assert_safe_payload(payload)

    def test_campaign_roll_injects_current_dc_without_returning_it(self) -> None:
        response = self.client.post(
            "/api/sessions/runtime/director/roll",
            json={
                "player_id": "player-martial",
                "roll_kind": "skill",
                "check_key": "insight",
                "prompt": "Read Voss's guarded reaction.",
                "expected_state_version": 5,
                "idempotency_key": "read-voss-roll",
            },
        )

        self.assertEqual(response.status_code, 201)
        serialized = response.get_data(as_text=True)
        self.assertNotIn('"dc"', serialized)
        self.assertNotIn("modifier", serialized)
        private_roll = next(
            roll
            for roll in self.store.get_engine_session("runtime")["engine_roll_state"]
            if roll["roll_id"] == response.get_json()["pending_roll"]["roll_id"]
        )
        self.assertEqual(private_roll["dc"], 12)
        self.assertEqual(private_roll["modifier"], 1)  # untrained Wisdom (Insight)
        self.assertEqual(response.get_json()["pending_roll"]["dc_visibility"], "private")
        self.assertNotIn("target_total", response.get_json()["pending_roll"])

    def test_canonical_check_overrides_model_difficulty_and_visibility(self) -> None:
        response = self.client.post(
            "/api/sessions/runtime/director/roll",
            json={
                "player_id": "player-martial",
                "roll_kind": "skill",
                "check_key": "insight",
                "difficulty": "nearly_impossible",
                "dc_visibility": "public",
                "prompt": "Read Voss's guarded reaction.",
                "expected_state_version": 5,
                "idempotency_key": "canonical-overrides-model",
            },
        )

        self.assertEqual(response.status_code, 201)
        pending = response.get_json()["pending_roll"]
        self.assertEqual(pending["dc_visibility"], "private")
        self.assertNotIn("target_total", pending)
        private_roll = next(
            roll
            for roll in self.store.get_engine_session("runtime")["engine_roll_state"]
            if roll["roll_id"] == pending["roll_id"]
        )
        self.assertEqual(private_roll["dc"], 12)

    def test_improvised_check_uses_standard_tier_and_commits_boolean_outcome(self) -> None:
        expected_dcs = {
            "very_easy": 5,
            "easy": 10,
            "medium": 15,
            "hard": 20,
            "very_hard": 25,
            "nearly_impossible": 30,
        }
        for difficulty, expected_dc in expected_dcs.items():
            with self.subTest(difficulty=difficulty):
                session_id = f"improvised-{difficulty}"
                bootstrap_demo_session(self.store, session_id=session_id)
                response = self.client.post(
                    f"/api/sessions/{session_id}/director/roll",
                    json={
                        "player_id": "player-martial",
                        "roll_kind": "skill",
                        "check_key": "stealth",
                        "difficulty": difficulty,
                        "dc_visibility": "private",
                        "prompt": "Move quietly without knowing whether anyone noticed.",
                        "expected_state_version": 5,
                        "idempotency_key": f"improvised-{difficulty}",
                    },
                )

                self.assertEqual(response.status_code, 201)
                payload = response.get_json()
                pending = payload["pending_roll"]
                self.assertEqual(pending["dc_visibility"], "private")
                self.assertNotIn("target_total", pending)
                private_roll = next(
                    roll
                    for roll in self.store.get_engine_session(session_id)["engine_roll_state"]
                    if roll["roll_id"] == pending["roll_id"]
                )
                self.assertEqual(private_roll["dc"], expected_dc)
                resolved = self.store.submit_roll(
                    session_id,
                    pending["roll_id"],
                    "player-martial",
                    raw_d20=10,
                    expected_version=payload["state_version"],
                    idempotency_key=f"resolve-{difficulty}",
                )["roll_result"]
                self.assertIs(type(resolved["success"]), bool)
                self.assertEqual(resolved["dc_visibility"], "private")
                self.assertNotIn("target_total", resolved)

    def test_improvised_public_check_exposes_target_but_never_modifier(self) -> None:
        response = self.client.post(
            "/api/sessions/runtime/director/roll",
            json={
                "player_id": "player-martial",
                "roll_kind": "skill",
                "check_key": "acrobatics",
                "difficulty": "medium",
                "dc_visibility": "public",
                "prompt": "Cross the visibly unstable beam.",
                "expected_state_version": 5,
                "idempotency_key": "public-improvised-check",
            },
        )

        self.assertEqual(response.status_code, 201)
        pending = response.get_json()["pending_roll"]
        self.assertEqual(pending["dc_visibility"], "public")
        self.assertEqual(pending["target_total"], 15)
        self.assertNotIn("modifier", response.get_data(as_text=True))

    def test_improvised_binary_check_rejects_missing_difficulty(self) -> None:
        response = self.client.post(
            "/api/sessions/runtime/director/roll",
            json={
                "player_id": "player-martial",
                "roll_kind": "skill",
                "check_key": "stealth",
                "dc_visibility": "private",
                "prompt": "Move quietly.",
                "expected_state_version": 5,
                "idempotency_key": "missing-difficulty",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("requires difficulty", response.get_json()["message"])
        self.assertEqual(self.store.get_public_session("runtime")["state_version"], 5)

    def test_death_save_is_binary_but_initiative_is_total_only(self) -> None:
        death_session = "death-save-roll"
        bootstrap_demo_session(self.store, session_id=death_session)
        death_response = self.client.post(
            f"/api/sessions/{death_session}/director/roll",
            json={
                "player_id": "player-martial",
                "roll_kind": "death_save",
                "difficulty": "hard",
                "dc_visibility": "private",
                "prompt": "Roll a death saving throw.",
                "expected_state_version": 5,
                "idempotency_key": "request-death-save",
            },
        )
        self.assertEqual(death_response.status_code, 201)
        death_payload = death_response.get_json()
        self.assertEqual(death_payload["pending_roll"]["dc_visibility"], "public")
        self.assertEqual(death_payload["pending_roll"]["target_total"], 10)
        death_result = self.store.submit_roll(
            death_session,
            death_payload["pending_roll"]["roll_id"],
            "player-martial",
            raw_d20=9,
            expected_version=death_payload["state_version"],
            idempotency_key="resolve-death-save",
        )["roll_result"]
        self.assertIs(death_result["success"], False)

        initiative_session = "initiative-roll"
        bootstrap_demo_session(self.store, session_id=initiative_session)
        initiative_response = self.client.post(
            f"/api/sessions/{initiative_session}/director/roll",
            json={
                "player_id": "player-martial",
                "roll_kind": "initiative",
                "difficulty": "medium",
                "dc_visibility": "public",
                "prompt": "Roll initiative.",
                "expected_state_version": 5,
                "idempotency_key": "request-initiative",
            },
        )
        self.assertEqual(initiative_response.status_code, 201)
        initiative_payload = initiative_response.get_json()
        self.assertEqual(initiative_payload["pending_roll"]["dc_visibility"], "private")
        self.assertNotIn("target_total", initiative_payload["pending_roll"])
        initiative_result = self.store.submit_roll(
            initiative_session,
            initiative_payload["pending_roll"]["roll_id"],
            "player-martial",
            raw_d20=10,
            expected_version=initiative_payload["state_version"],
            idempotency_key="resolve-initiative",
        )["roll_result"]
        self.assertIsNone(initiative_result["success"])
        self.assertEqual(initiative_result["total"], 11)

    def test_rainy_square_supported_approaches_receive_one_private_dc(self) -> None:
        supported_checks = {
            "perception": 11,
            "investigation": 12,
            "persuasion": 12,
            "intimidation": 13,
            "deception": 13,
        }

        for check_key, expected_dc in supported_checks.items():
            with self.subTest(check_key=check_key):
                session_id = f"rainy-square-{check_key}"
                bootstrap_demo_session(self.store, session_id=session_id)
                response = self.client.post(
                    f"/api/sessions/{session_id}/director/roll",
                    json={
                        "player_id": "player-martial",
                        "roll_kind": "skill",
                        "check_key": check_key,
                        "prompt": f"Resolve the supported {check_key} approach.",
                        "expected_state_version": 5,
                        "idempotency_key": f"{check_key}-roll",
                    },
                )

                self.assertEqual(response.status_code, 201)
                serialized = response.get_data(as_text=True)
                self.assertNotIn('"dc"', serialized)
                self.assertNotIn("modifier", serialized)
                self.assertNotIn("success", serialized)
                self.assertNotIn("fail_forward", serialized)
                roll_id = response.get_json()["pending_roll"]["roll_id"]
                private_roll = next(
                    roll
                    for roll in self.store.get_engine_session(session_id)["engine_roll_state"]
                    if roll["roll_id"] == roll_id
                )
                self.assertEqual(private_roll["dc"], expected_dc)

    def test_advance_is_linear_idempotent_and_rejects_stale_or_terminal_calls(self) -> None:
        request_payload = {
            "reason": "The party follows Finn's tracks to the chapel.",
            "expected_state_version": 5,
            "idempotency_key": "advance-to-chapel",
        }
        first = self.post("advance", request_payload)
        replay = self.post("advance", request_payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.get_json(), replay.get_json())
        payload = first.get_json()
        self.assertEqual(payload["state_version"], 6)
        self.assertEqual(payload["performer_context"]["current_scene"]["id"], "ruined-chapel")
        self.assertEqual(
            self.store.get_public_session("runtime")["world"]["campaign"]["scene_title"],
            "The Chapel of Borrowed Names",
        )
        self.assert_safe_payload(payload)

        stale = self.post(
            "advance",
            {
                "reason": request_payload["reason"],
                "expected_state_version": 5,
                "idempotency_key": "different-command",
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["error"], "stale_state_version")

        final_scene = self.post(
            "advance",
            {
                "reason": "The heroes descend into the vault.",
                "expected_state_version": 6,
                "idempotency_key": "advance-to-vault",
            },
        )
        self.assertEqual(final_scene.status_code, 200)
        final_payload = final_scene.get_json()
        self.assertEqual(final_payload["state_version"], 7)
        self.assertIn(
            self.campaign.facts["finn-is-safe"].private_truth,
            json.dumps(final_payload),
        )
        self.assert_safe_payload(final_payload, allowed_fact_ids={"finn-is-safe"})
        private_ids = self.store.get_engine_session("runtime")["private_world"]["campaign"][
            "revealed_fact_ids"
        ]
        self.assertEqual(private_ids, ["finn-is-safe"])

        terminal = self.post(
            "advance",
            {
                "reason": "Try to continue beyond the ending.",
                "expected_state_version": 7,
                "idempotency_key": "past-ending",
            },
        )
        self.assertEqual(terminal.status_code, 409)
        self.assertNotIn("next_scene", terminal.get_data(as_text=True))

    def test_advance_rejects_non_linear_campaign_without_changing_state(self) -> None:
        campaign = self.director.canonical_campaign
        first_id = campaign.scene_order[0]
        altered_first = replace(
            campaign.scenes[first_id],
            next_scene_ids=(campaign.scene_order[1], campaign.scene_order[2]),
        )
        altered_scenes = dict(campaign.scenes)
        altered_scenes[first_id] = altered_first
        self.app.extensions["campaign_director"] = CampaignDirector(
            replace(campaign, scenes=MappingProxyType(altered_scenes))
        )
        response = self.post(
            "advance",
            {
                "reason": "Attempt a branching transition.",
                "expected_state_version": 5,
                "idempotency_key": "branching",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.get_public_session("runtime")["state_version"], 5)
        self.assertNotIn(campaign.scene_order[2], response.get_data(as_text=True))

    def test_npc_reaction_updates_private_clamped_score_and_only_coarse_public_attitude(self) -> None:
        request_payload = {
            "npc_id": "mara-finch",
            "reaction": "trusts_more",
            "public_reason": "The heroes promise to bring Finn home.",
            "expected_state_version": 5,
            "idempotency_key": "mara-trust-one",
        }
        first = self.post("npc-reaction", request_payload)
        replay = self.post("npc-reaction", request_payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json(), replay.get_json())
        payload = first.get_json()
        self.assertEqual(payload["state_version"], 6)
        self.assertEqual(
            payload["public_state"]["npcs"]["mara-finch"]["visible_attitude"],
            "Open and cooperative",
        )
        self.assert_safe_payload(payload)
        relationship = self.store.get_engine_session("runtime")["private_world"]["npcs"][
            "mara-finch"
        ]["relationship"]
        self.assertEqual(relationship["trust"], 2)

        for expected_version, key in ((6, "mara-trust-two"), (7, "mara-trust-three")):
            response = self.post(
                "npc-reaction",
                {
                    **request_payload,
                    "expected_state_version": expected_version,
                    "idempotency_key": key,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assert_safe_payload(response.get_json())
        clamped = self.store.get_engine_session("runtime")["private_world"]["npcs"][
            "mara-finch"
        ]["relationship"]["trust"]
        self.assertEqual(clamped, 3)

    def test_npc_reaction_validates_enum_and_current_presence(self) -> None:
        invalid = self.post(
            "npc-reaction",
            {
                "npc_id": "mara-finch",
                "reaction": "reveals_everything",
                "public_reason": "Unsafe request.",
                "expected_state_version": 5,
                "idempotency_key": "invalid-reaction",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.store.get_public_session("runtime")["state_version"], 5)

        advanced = self.post(
            "advance",
            {
                "reason": "The party enters the empty chapel.",
                "expected_state_version": 5,
                "idempotency_key": "leave-npcs",
            },
        )
        self.assertEqual(advanced.status_code, 200)
        absent = self.post(
            "npc-reaction",
            {
                "npc_id": "mara-finch",
                "reaction": "trusts_more",
                "public_reason": "Mara is not in this scene.",
                "expected_state_version": 6,
                "idempotency_key": "absent-npc",
            },
        )
        self.assertEqual(absent.status_code, 409)
        self.assertNotIn("relationship", absent.get_data(as_text=True))

    def test_discovery_reveals_only_mapped_fact_and_is_idempotent(self) -> None:
        request_payload = {
            "discovery": "careful_observation",
            "public_reason": "The party follows the child's fresh tracks.",
            "expected_state_version": 5,
            "idempotency_key": "find-tracks",
        }
        first = self.post("discovery", request_payload)
        replay = self.post("discovery", request_payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json(), replay.get_json())
        payload = first.get_json()
        self.assertEqual(payload["state_version"], 6)
        self.assertIn(self.campaign.facts["finn-is-safe"].private_truth, json.dumps(payload))
        self.assert_safe_payload(payload, allowed_fact_ids={"finn-is-safe"})

        engine_campaign = self.store.get_engine_session("runtime")["private_world"]["campaign"]
        self.assertEqual(engine_campaign["revealed_fact_ids"], ["finn-is-safe"])
        self.assertIn("find-finn-tracks", engine_campaign["committed_event_ids"])
        public_world = self.store.get_public_session("runtime")["world"]
        self.assertNotIn("finn-is-safe", json.dumps(public_world))

    def test_discovery_evidence_pair_reveals_voss_without_gate_or_fact_ids(self) -> None:
        advanced = self.post(
            "advance",
            {
                "reason": "The party reaches the chapel.",
                "expected_state_version": 5,
                "idempotency_key": "chapel-first",
            },
        )
        self.assertEqual(advanced.status_code, 200)
        discovered = self.post(
            "discovery",
            {
                "discovery": "evidence_pair_completed",
                "public_reason": "Two matching pieces of evidence implicate the magistrate.",
                "expected_state_version": 6,
                "idempotency_key": "pair-evidence",
            },
        )
        self.assertEqual(discovered.status_code, 200)
        payload = discovered.get_json()
        self.assertIn(
            self.campaign.facts["voss-awakened-the-bell"].private_truth,
            json.dumps(payload),
        )
        self.assert_safe_payload(payload, allowed_fact_ids={"voss-awakened-the-bell"})
        serialized = json.dumps(payload)
        self.assertNotIn("collect-two-voss-clues", serialized)
        self.assertNotIn("grain-sack-thread", serialized)
        self.assertNotIn("magistrate-seal-wax", serialized)


if __name__ == "__main__":
    unittest.main()
