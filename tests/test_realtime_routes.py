from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.api.realtime_routes import GAMEPLAY_FUNCTION_TOOLS, _session_payload
from bot.api.server import create_app


class RealtimeRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.app = create_app(
            {
                "TESTING": True,
                "GAME_DATABASE_PATH": str(
                    Path(self.temporary_directory.name) / "game.sqlite3"
                ),
            }
        )
        self.client = self.app.test_client()

    def test_ephemeral_secret_route_never_returns_server_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-only-secret"}), patch(
            "bot.api.realtime_routes._request_client_secret",
            return_value=("ephemeral-client-secret", 123456),
        ) as request_secret:
            response = self.client.post("/api/realtime/client-secret")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["client_secret"], "ephemeral-client-secret")
        self.assertNotIn("server-only-secret", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
        request_secret.assert_called_once()

    def test_tool_schemas_exclude_engine_authority_fields(self):
        forbidden = {
            "dc",
            "engine_modifier",
            "modifier",
            "expected_state_version",
            "idempotency_key",
            "target_scene",
            "target_scene_id",
            "next_scene_id",
            "future_scene_id",
            "fact_id",
            "motive",
            "motives",
        }
        expected_names = [
            "read_public_game_state",
            "request_physical_roll",
            "apply_damage",
            "apply_healing",
            "award_character_currency",
            "use_character_resource",
            "restore_character_resource",
            "read_performer_context",
            "advance_campaign_scene",
            "record_npc_reaction",
            "record_scene_discovery",
        ]
        self.assertEqual(
            [tool["name"] for tool in GAMEPLAY_FUNCTION_TOOLS], expected_names
        )
        for tool in GAMEPLAY_FUNCTION_TOOLS:
            properties = set(tool["parameters"]["properties"])
            self.assertFalse(properties & forbidden, tool["name"])
            self.assertFalse(tool["parameters"]["additionalProperties"])

        tools = {tool["name"]: tool for tool in GAMEPLAY_FUNCTION_TOOLS}
        roll_tool = tools["request_physical_roll"]["parameters"]
        self.assertEqual(
            set(roll_tool["properties"]),
            {
                "player_id",
                "roll_kind",
                "check_key",
                "difficulty",
                "dc_visibility",
                "prompt",
            },
        )
        self.assertIn("difficulty", roll_tool["required"])
        self.assertIn("dc_visibility", roll_tool["required"])
        self.assertEqual(
            roll_tool["properties"]["difficulty"]["enum"],
            [
                "very_easy",
                "easy",
                "medium",
                "hard",
                "very_hard",
                "nearly_impossible",
            ],
        )
        self.assertEqual(
            roll_tool["properties"]["dc_visibility"]["enum"],
            ["public", "private"],
        )
        self.assertIn(
            "Never put a DC, target number, threshold",
            roll_tool["properties"]["prompt"]["description"],
        )
        self.assertEqual(
            tools["read_performer_context"]["parameters"]["properties"], {}
        )
        currency_tool = tools["award_character_currency"]["parameters"]
        self.assertEqual(
            set(currency_tool["properties"]),
            {"player_id", "amount", "denomination", "reason"},
        )
        self.assertEqual(
            currency_tool["properties"]["denomination"]["enum"],
            ["cp", "sp", "ep", "gp", "pp"],
        )
        self.assertEqual(currency_tool["properties"]["amount"]["minimum"], 1)
        self.assertEqual(currency_tool["properties"]["amount"]["maximum"], 10_000)
        self.assertEqual(
            set(currency_tool["required"]),
            {"player_id", "amount", "denomination", "reason"},
        )
        self.assertEqual(
            set(tools["advance_campaign_scene"]["parameters"]["properties"]),
            {"reason"},
        )
        self.assertIn(
            "before narrating arrival",
            tools["advance_campaign_scene"]["description"],
        )
        self.assertEqual(
            set(tools["record_npc_reaction"]["parameters"]["properties"]),
            {"npc_id", "reaction", "reason"},
        )
        self.assertEqual(
            tools["record_npc_reaction"]["parameters"]["properties"]["reaction"]["enum"],
            [
                "trusts_more",
                "trusts_less",
                "more_suspicious",
                "less_suspicious",
                "more_fearful",
                "less_fearful",
                "more_respectful",
                "less_respectful",
            ],
        )
        self.assertEqual(
            set(tools["record_scene_discovery"]["parameters"]["properties"]),
            {"discovery", "reason"},
        )
        self.assertEqual(
            tools["record_scene_discovery"]["parameters"]["properties"]["discovery"]["enum"],
            [
                "careful_observation",
                "thorough_search",
                "npc_trust_earned",
                "evidence_pair_completed",
                "echo_questioned",
            ],
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured"}):
            with self.app.test_request_context():
                from bot.api.realtime_routes import _load_settings

                payload = _session_payload(_load_settings())
        self.assertEqual(payload["session"]["model"], "gpt-realtime-2.1")
        self.assertEqual(payload["session"]["tool_choice"], "auto")
        self.assertEqual(len(payload["session"]["tools"]), 11)
        turn_detection = payload["session"]["audio"]["input"]["turn_detection"]
        self.assertEqual(turn_detection["type"], "semantic_vad")
        self.assertFalse(turn_detection["create_response"])
        self.assertTrue(turn_detection["interrupt_response"])


if __name__ == "__main__":
    unittest.main()
