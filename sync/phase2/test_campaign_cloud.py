from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from campaign_cloud import (
    CampaignCloudClient,
    CampaignCloudError,
    CampaignLinkStore,
    load_campaign_cloud_config,
)


class FakeCampaignCloudClient(CampaignCloudClient):
    def __init__(self, root):
        self.calls = []
        super().__init__(
            app_dir=root,
            user_data_dir=Path(root) / "userdata",
            config={
                "url": "https://example.supabase.co",
                "key": "sb_publishable_test_key",
            },
        )
        self._save_session(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at": int(time.time()) + 3600,
                "user_id": "00000000-0000-0000-0000-000000000001",
                "is_anonymous": True,
            }
        )

    def _request_json(
        self,
        method,
        path,
        body=None,
        query=None,
        authenticated=True,
        prefer=None,
    ):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "query": query,
                "authenticated": authenticated,
                "prefer": prefer,
            }
        )

        if path == "/rest/v1/campaigns" and method == "POST":
            return [{
                "id": "10000000-0000-0000-0000-000000000001",
                "name": body["name"],
                "invite_code": "AB12CD34",
                "owner_user_id": self.user_id,
                "created_at": "2026-10-10T00:00:00Z",
            }]

        if path == "/rest/v1/rpc/did_join_campaign":
            return [{
                "id": "10000000-0000-0000-0000-000000000002",
                "name": "Test Campaign",
                "invite_code": body["p_invite_code"],
                "owner_user_id": "20000000-0000-0000-0000-000000000001",
                "role": "player",
            }]

        if path == "/rest/v1/campaign_characters":
            return [{
                "id": "30000000-0000-0000-0000-000000000001",
                "campaign_id": body["campaign_id"],
                "character_id": body["character_id"],
                "display_name": body["display_name"],
                "active": True,
                "created_at": "2026-10-10T00:00:00Z",
                "updated_at": "2026-10-10T00:00:00Z",
            }]

        if path == "/rest/v1/character_state":
            return [{
                "campaign_character_id": body["campaign_character_id"],
                "updated_at": "2026-10-10T00:00:00Z",
            }]

        if path == "/rest/v1/campaign_rolls":
            return [{
                "event_id": body["event_id"],
                "campaign_character_id": body["campaign_character_id"],
                "rolled_at": body["rolled_at"],
            }]

        if path == "/rest/v1/campaigns" and method == "GET":
            return []

        return []


class CampaignCloudTests(unittest.TestCase):
    def test_reuses_existing_suggestions_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "suggestions_config.json").write_text(
                json.dumps({
                    "supabase_url": "https://abc.supabase.co",
                    "supabase_anon_key": "sb_publishable_abc",
                }),
                encoding="utf-8",
            )
            config = load_campaign_cloud_config(root)
            self.assertEqual(config["url"], "https://abc.supabase.co")
            self.assertEqual(config["key"], "sb_publishable_abc")
            self.assertTrue(config["source"].endswith("suggestions_config.json"))

    def test_rejects_secret_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "campaign_config.json").write_text(
                json.dumps({
                    "url": "https://abc.supabase.co",
                    "key": "sb_secret_do_not_ship",
                }),
                encoding="utf-8",
            )
            with self.assertRaises(CampaignCloudError):
                load_campaign_cloud_config(root)

    def test_link_store_is_per_character(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CampaignLinkStore(Path(temporary))
            store.set("char-1", {"campaign_id": "camp-1"})
            store.set("char-2", {"campaign_id": "camp-2"})
            self.assertEqual(store.get("char-1")["campaign_id"], "camp-1")
            self.assertEqual(store.get("char-2")["campaign_id"], "camp-2")
            self.assertTrue(store.remove("char-1"))
            self.assertIsNone(store.get("char-1"))
            self.assertIsNotNone(store.get("char-2"))

    def test_create_campaign(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = FakeCampaignCloudClient(temporary)
            campaign = client.create_campaign("The Verge")
            self.assertEqual(campaign["name"], "The Verge")
            self.assertEqual(campaign["invite_code"], "AB12CD34")
            call = client.calls[-1]
            self.assertEqual(call["path"], "/rest/v1/campaigns")
            self.assertEqual(call["body"], {"name": "The Verge"})

    def test_join_campaign_normalises_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = FakeCampaignCloudClient(temporary)
            campaign = client.join_campaign(" ab12 cd34 ", "Luna Player")
            self.assertEqual(campaign["role"], "player")
            call = client.calls[-1]
            self.assertEqual(call["body"]["p_invite_code"], "AB12CD34")
            self.assertEqual(call["body"]["p_display_name"], "Luna Player")

    def test_link_character_uploads_safe_state_and_remembers_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = FakeCampaignCloudClient(temporary)
            state = {
                "kind": "character_state",
                "character_id": "char-123",
                "name": "Luna",
                "resources": {"hearts": {"current": 2, "max": 3}},
            }
            record = client.link_character(
                "10000000-0000-0000-0000-000000000001",
                state,
            )
            self.assertEqual(record["character_id"], "char-123")
            link = client.get_character_link("char-123")
            self.assertEqual(link["campaign_character_id"], record["id"])
            paths = [call["path"] for call in client.calls]
            self.assertIn("/rest/v1/campaign_characters", paths)
            self.assertIn("/rest/v1/character_state", paths)

    def test_roll_event_upload_preserves_structured_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = FakeCampaignCloudClient(temporary)
            event = {
                "kind": "roll_event",
                "event_id": "40000000-0000-0000-0000-000000000001",
                "rolled_utc": "2026-10-10T00:00:00Z",
                "character_id": "char-123",
                "character_name": "Luna",
                "roll_type": "ability",
                "ability_name": "Agility",
                "flat_bonus": 2,
                "dice": [{
                    "label": "roll",
                    "kind": "die",
                    "sides": 8,
                    "sign": 1,
                    "values": [8, 3],
                    "exploded": True,
                }],
                "total": 13,
            }
            result = client.upload_roll_event(
                "30000000-0000-0000-0000-000000000001",
                event,
            )
            self.assertEqual(result["event_id"], event["event_id"])
            call = client.calls[-1]
            self.assertIs(call["body"]["event"], event)
            self.assertEqual(call["body"]["rolled_at"], event["rolled_utc"])

    def test_blank_campaign_name_is_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = FakeCampaignCloudClient(temporary)
            with self.assertRaises(CampaignCloudError):
                client.create_campaign("   ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
