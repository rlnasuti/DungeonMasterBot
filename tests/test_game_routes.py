from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from bot.api.game_routes import STORE_EXTENSION_KEY, game_blueprint
from bot.game.demo import CASTER_PLAYER_ID, demo_character_payloads
from bot.game.store import GameStore


class GameRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.store = GameStore(Path(self.temp_dir.name) / "routes.sqlite3")
        self.app.extensions[STORE_EXTENSION_KEY] = self.store
        self.app.register_blueprint(game_blueprint)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_demo_view_and_frontend_roll_contract(self) -> None:
        created = self.client.post("/api/demo-sessions", json={"session_id": "ui-demo"})
        self.assertEqual(created.status_code, 201)
        snapshot = created.get_json()
        self.assertEqual(snapshot["state_version"], 5)
        roll = snapshot["pending_rolls"][0]

        view = self.client.get("/api/sessions/ui-demo/view?since_version=3")
        self.assertEqual(view.status_code, 200)
        view_json = view.get_json()
        self.assertEqual(view_json["state_version"], 5)
        self.assertEqual([event["state_version"] for event in view_json["events"]], [4, 5])
        self.assertNotIn("lantern opens", json.dumps(view_json).lower())

        payload = {
            "player_id": roll["player_id"],
            "natural_roll": 12,
            "expected_state_version": 5,
        }
        submitted = self.client.post(
            f"/api/sessions/ui-demo/rolls/{roll['roll_id']}",
            json=payload,
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.get_json()["roll_result"]["total"], 17)
        replay = self.client.post(
            f"/api/sessions/ui-demo/rolls/{roll['roll_id']}",
            json=payload,
        )
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.get_json(), submitted.get_json())

    def test_character_sheet_route_exposes_complete_public_rules_metadata(self) -> None:
        created = self.client.post("/api/demo-sessions", json={"session_id": "sheet-route"})
        self.assertEqual(created.status_code, 201)
        snapshot = created.get_json()
        fighter = next(
            player["character"]
            for player in snapshot["players"]
            if player["player_id"] == "player-martial"
        )
        wizard = next(
            player["character"]
            for player in snapshot["players"]
            if player["player_id"] == "player-caster"
        )

        self.assertEqual(fighter["ruleset_id"], "srd-5.2.1")
        self.assertEqual(fighter["alignment"], "Neutral Good")
        self.assertEqual(fighter["experience_points"], 450)
        self.assertEqual(fighter["size"], "Medium")
        self.assertTrue(fighter["heroic_inspiration"])
        self.assertEqual(fighter["death_saves"], {"successes": 0, "failures": 0})
        self.assertEqual(fighter["armor_class_calculation"]["source_item_ids"], [
            "item-chain-mail"
        ])
        self.assertEqual(fighter["inventory"][1]["category"], "armor")
        self.assertEqual(fighter["attacks"][0]["attack_bonus"], 5)
        self.assertTrue(fighter["features"])
        self.assertIsNone(fighter["spellcasting"])
        self.assertEqual(wizard["spellcasting"]["ability"], "intelligence")
        self.assertEqual(wizard["spellcasting"]["save_dc"], 13)
        self.assertIn("shield", wizard["spellcasting"]["prepared_spell_ids"])
        self.assertEqual(wizard["spellcasting"]["always_prepared_spell_ids"], [])
        self.assertTrue(all(
            spell["source"] == "Wizard" for spell in wizard["spellcasting"]["spells"]
        ))
        self.assertEqual(wizard["spellcasting"]["focus_item_id"], "item-arcane-focus")

        read_back = self.client.get("/api/sessions/sheet-route")
        self.assertEqual(read_back.status_code, 200)
        self.assertEqual(read_back.get_json()["players"], snapshot["players"])
        public_text = read_back.get_data(as_text=True).lower()
        self.assertNotIn("motives", public_text)
        self.assertNotIn("secrets", public_text)

    def test_character_stage_route_rejects_unmodeled_private_sheet_fields(self) -> None:
        created = self.client.post(
            "/api/sessions",
            headers={"Idempotency-Key": "create-strict-sheet"},
            json={
                "session_id": "strict-sheet",
                "players": [
                    {"player_id": "p1", "display_name": "One"},
                    {"player_id": "p2", "display_name": "Two"},
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        payload = demo_character_payloads()[CASTER_PLAYER_ID]
        payload["dm_secret"] = "Do not cross the public character boundary."
        staged = self.client.post(
            "/api/sessions/strict-sheet/players/p1/character",
            headers={"Idempotency-Key": "bad-private-sheet"},
            json={
                "character": payload,
                "source": "imported",
                "expected_state_version": 0,
            },
        )
        self.assertEqual(staged.status_code, 400)
        self.assertEqual(staged.get_json()["error"], "validation_error")
        self.assertNotIn(
            "Do not cross",
            json.dumps(self.store.get_public_session("strict-sheet")),
        )

    def test_roll_submission_rejects_client_modifier_or_dc(self) -> None:
        snapshot = self.client.post("/api/demo-sessions", json={"session_id": "strict-roll"}).get_json()
        roll = snapshot["pending_rolls"][0]
        response = self.client.post(
            f"/api/sessions/strict-roll/rolls/{roll['roll_id']}",
            json={
                "player_id": roll["player_id"],
                "natural_roll": 10,
                "modifier": 99,
                "dc": 1,
                "expected_state_version": 5,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "validation_error")
        self.assertEqual(self.store.get_public_session("strict-roll")["state_version"], 5)

    def test_stale_version_maps_to_conflict_response(self) -> None:
        self.client.post("/api/demo-sessions", json={"session_id": "stale-demo"})
        response = self.client.post(
            "/api/sessions/stale-demo/players/player-martial/damage",
            headers={"Idempotency-Key": "stale-route"},
            json={"amount": 1, "expected_state_version": 4},
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["error"], "stale_state_version")
        self.assertEqual(payload["details"]["current_version"], 5)

    def test_create_route_never_echoes_private_world(self) -> None:
        response = self.client.post(
            "/api/sessions",
            headers={"Idempotency-Key": "private-create"},
            json={
                "session_id": "private-route",
                "players": [
                    {"player_id": "p1", "display_name": "One"},
                    {"player_id": "p2", "display_name": "Two"},
                ],
                "public_world": {"campaign": {"title": "Public Title"}},
                "private_world": {"campaign": {"secrets": ["Never echo this"]}},
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("Never echo this", response.get_data(as_text=True))
        events = self.client.get("/api/sessions/private-route/events?after_version=-1")
        self.assertNotIn("Never echo this", events.get_data(as_text=True))

    def test_latest_session_route_returns_only_one_public_snapshot(self) -> None:
        missing = self.client.get("/api/sessions/latest")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["error"], "not_found")

        for session_id in ("older-route", "latest-route"):
            created = self.client.post(
                "/api/sessions",
                headers={"Idempotency-Key": f"create-{session_id}"},
                json={
                    "session_id": session_id,
                    "players": [
                        {"player_id": "p1", "display_name": "One"},
                        {"player_id": "p2", "display_name": "Two"},
                    ],
                    "public_world": {"marker": session_id},
                    "private_world": {"secret": f"never-return-{session_id}"},
                },
            )
            self.assertEqual(created.status_code, 201)

        with self.store._connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                ("2026-01-01T00:00:00.000+00:00", "older-route"),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                ("2026-02-01T00:00:00.000+00:00", "latest-route"),
            )

        response = self.client.get("/api/sessions/latest")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["session_id"], "latest-route")
        self.assertEqual(payload["world"], {"marker": "latest-route"})
        self.assertNotIn("sessions", payload)
        self.assertNotIn("private", response.get_data(as_text=True).lower())
        self.assertNotIn("never-return", response.get_data(as_text=True))

        self.assertEqual(
            self.client.get("/api/sessions/latest?all=true").status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/api/sessions/latest", json={}).status_code,
            400,
        )

    def test_conversation_routes_persist_finalized_text_in_chronological_order(self) -> None:
        snapshot = self.client.post(
            "/api/demo-sessions", json={"session_id": "conversation-route"}
        ).get_json()
        before_events = self.client.get(
            "/api/sessions/conversation-route/events?after_version=-1"
        ).get_json()
        base = "/api/sessions/conversation-route/conversation"

        empty = self.client.get(base)
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.get_json(), {
            "session_id": "conversation-route",
            "messages": [],
        })

        first = self.client.put(
            f"{base}/messages/assistant-intro",
            json={
                "role": "assistant",
                "text": "  Magistrate Voss folds his hands.  ",
            },
        )
        second = self.client.put(
            f"{base}/messages/user-answer",
            json={"role": "user", "text": "Cendien watches him carefully."},
        )
        replay = self.client.put(
            f"{base}/messages/assistant-intro",
            json={
                "role": "assistant",
                "text": "  Magistrate Voss folds his hands.  ",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.get_json(), first.get_json())
        listed = self.client.get(base).get_json()["messages"]
        self.assertEqual([message["message_id"] for message in listed], [
            "assistant-intro",
            "user-answer",
        ])
        self.assertEqual([message["sequence"] for message in listed], [1, 2])
        self.assertEqual(listed[0]["text"], "  Magistrate Voss folds his hands.  ")

        current = self.client.get("/api/sessions/conversation-route").get_json()
        self.assertEqual(current["state_version"], snapshot["state_version"])
        self.assertEqual(current["updated_at"], snapshot["updated_at"])
        after_events = self.client.get(
            "/api/sessions/conversation-route/events?after_version=-1"
        ).get_json()
        self.assertEqual(after_events, before_events)

    def test_conversation_routes_reject_conflicts_invalid_payloads_and_missing_sessions(self) -> None:
        self.client.post(
            "/api/demo-sessions", json={"session_id": "conversation-errors"}
        )
        path = "/api/sessions/conversation-errors/conversation/messages/reused"
        inserted = self.client.put(path, json={"role": "user", "text": "We agree."})
        self.assertEqual(inserted.status_code, 200)

        for payload in (
            {"role": "assistant", "text": "We agree."},
            {"role": "user", "text": "We decline."},
        ):
            with self.subTest(conflicting_payload=payload):
                conflict = self.client.put(path, json=payload)
                self.assertEqual(conflict.status_code, 409)
                self.assertEqual(conflict.get_json()["error"], "conflict")

        invalid_payloads = (
            {},
            {"role": "user"},
            {"text": "Missing role"},
            {"role": "system", "text": "Hidden instructions"},
            {"role": "assistant", "text": ""},
            {"role": "assistant", "text": "Valid", "status": "streaming"},
        )
        for index, payload in enumerate(invalid_payloads):
            with self.subTest(invalid_payload=payload):
                invalid = self.client.put(
                    f"/api/sessions/conversation-errors/conversation/messages/invalid-{index}",
                    json=payload,
                )
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(invalid.get_json()["error"], "validation_error")

        for method, path in (
            (self.client.get, "/api/sessions/missing/conversation"),
            (self.client.delete, "/api/sessions/missing/conversation"),
        ):
            missing = method(path)
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.get_json()["error"], "not_found")
        missing_put = self.client.put(
            "/api/sessions/missing/conversation/messages/one",
            json={"role": "user", "text": "No session"},
        )
        self.assertEqual(missing_put.status_code, 404)
        self.assertEqual(missing_put.get_json()["error"], "not_found")

    def test_conversation_clear_is_scoped_strict_and_version_independent(self) -> None:
        snapshot = self.client.post(
            "/api/demo-sessions", json={"session_id": "conversation-clear"}
        ).get_json()
        base = "/api/sessions/conversation-clear/conversation"
        self.client.put(
            f"{base}/messages/one",
            json={"role": "assistant", "text": "A persisted line."},
        )

        query_rejected = self.client.get(f"{base}?after=1")
        self.assertEqual(query_rejected.status_code, 400)
        get_body_rejected = self.client.get(base, json={})
        self.assertEqual(get_body_rejected.status_code, 400)
        put_query_rejected = self.client.put(
            f"{base}/messages/two?overwrite=true",
            json={"role": "user", "text": "This must not be stored."},
        )
        self.assertEqual(put_query_rejected.status_code, 400)
        body_rejected = self.client.delete(base, json={})
        self.assertEqual(body_rejected.status_code, 400)
        delete_query_rejected = self.client.delete(f"{base}?force=true")
        self.assertEqual(delete_query_rejected.status_code, 400)

        cleared = self.client.delete(base)
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.get_json(), {
            "session_id": "conversation-clear",
            "deleted_count": 1,
        })
        replay = self.client.delete(base)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.get_json()["deleted_count"], 0)
        self.assertEqual(self.client.get(base).get_json()["messages"], [])
        current = self.client.get("/api/sessions/conversation-clear").get_json()
        self.assertEqual(current["state_version"], snapshot["state_version"])
        self.assertEqual(current["updated_at"], snapshot["updated_at"])

    def test_player_identity_route_persists_display_and_confirmed_character_names(self) -> None:
        snapshot = self.client.post(
            "/api/demo-sessions", json={"session_id": "rename-route"}
        ).get_json()
        target = snapshot["players"][0]
        original_character = target["character"]
        response = self.client.patch(
            f"/api/sessions/rename-route/players/{target['player_id']}",
            headers={"Idempotency-Key": "rename-route-player"},
            json={
                "display_name": "Robert",
                "character_name": "Juicebox",
                "expected_state_version": snapshot["state_version"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["state_version"], snapshot["state_version"] + 1)
        self.assertEqual(payload["display_name"], "Robert")
        self.assertEqual(payload["character_name"], "Juicebox")
        updated = self.client.get("/api/sessions/rename-route").get_json()
        player = next(
            player for player in updated["players"] if player["player_id"] == target["player_id"]
        )
        self.assertEqual(player["display_name"], "Robert")
        self.assertEqual(player["character"]["name"], "Juicebox")
        self.assertEqual(player["character"]["class_name"], original_character["class_name"])

        replay = self.client.patch(
            f"/api/sessions/rename-route/players/{target['player_id']}",
            headers={"Idempotency-Key": "rename-route-player"},
            json={
                "display_name": "Robert",
                "character_name": "Juicebox",
                "expected_state_version": snapshot["state_version"],
            },
        )
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.get_json(), payload)

    def test_player_identity_route_rejects_stale_and_empty_updates(self) -> None:
        snapshot = self.client.post(
            "/api/demo-sessions", json={"session_id": "rename-errors"}
        ).get_json()
        player_id = snapshot["players"][0]["player_id"]
        empty = self.client.patch(
            f"/api/sessions/rename-errors/players/{player_id}",
            headers={"Idempotency-Key": "empty-rename"},
            json={"expected_state_version": snapshot["state_version"]},
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.get_json()["error"], "validation_error")

        stale = self.client.patch(
            f"/api/sessions/rename-errors/players/{player_id}",
            headers={"Idempotency-Key": "stale-rename"},
            json={"display_name": "Robert", "expected_state_version": 0},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["error"], "stale_state_version")

    def test_currency_award_route_persists_and_replays_exactly_once(self) -> None:
        snapshot = self.client.post(
            "/api/demo-sessions", json={"session_id": "currency-route"}
        ).get_json()
        player_id = snapshot["players"][0]["player_id"]
        path = f"/api/sessions/currency-route/players/{player_id}/currency/award"
        body = {
            "amount": 75,
            "denomination": "gp",
            "reason": "Voss pays the promised advance.",
            "expected_state_version": snapshot["state_version"],
        }
        response = self.client.post(
            path,
            headers={"Idempotency-Key": "currency-route-award"},
            json=body,
        )
        replay = self.client.post(
            path,
            headers={"Idempotency-Key": "currency-route-award"},
            json=body,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.get_json(), payload)
        self.assertEqual(payload["state_version"], snapshot["state_version"] + 1)
        self.assertEqual(payload["amount"], 75)
        self.assertEqual(payload["denomination"], "gp")
        self.assertEqual(payload["balance"], 75)
        updated = self.client.get("/api/sessions/currency-route/view").get_json()
        character = next(
            player["character"]
            for player in updated["players"]
            if player["player_id"] == player_id
        )
        self.assertEqual(character["currency"]["gp"], 75)
        awards = [
            event for event in updated["events"]
            if event["event_type"] == "currency_awarded"
        ]
        self.assertEqual(len(awards), 1)

    def test_currency_award_route_rejects_invalid_or_untrusted_fields(self) -> None:
        snapshot = self.client.post(
            "/api/demo-sessions", json={"session_id": "currency-errors"}
        ).get_json()
        player_id = snapshot["players"][0]["player_id"]
        path = f"/api/sessions/currency-errors/players/{player_id}/currency/award"
        invalid = self.client.post(
            path,
            headers={"Idempotency-Key": "bad-currency"},
            json={
                "amount": 1,
                "denomination": "gp",
                "reason": "Invalid hidden override.",
                "private_reason": "A secret should never be accepted here.",
                "expected_state_version": snapshot["state_version"],
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["error"], "validation_error")
        self.assertEqual(
            self.store.get_public_session("currency-errors")["state_version"],
            snapshot["state_version"],
        )


if __name__ == "__main__":
    unittest.main()
