from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from campaign_dashboard_bridge import (
    create_dashboard_access,
    prepare_dashboard_config,
    touch_character_presence,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    def _request_json(self, method, path, body=None, query=None, authenticated=True, prefer=None):
        self.calls.append({
            "method": method,
            "path": path,
            "body": body,
            "query": query,
            "authenticated": authenticated,
            "prefer": prefer,
        })
        if path.endswith("/did_create_dashboard_code"):
            return [{
                "dashboard_code": "A1B2C3D4E5",
                "expires_at": "2026-10-10T02:00:00Z",
            }]
        return None


class CampaignDashboardTests(unittest.TestCase):
    def test_dashboard_access_uses_rpc(self):
        client = FakeClient()
        result = create_dashboard_access(client, "campaign-123")
        self.assertEqual(result["code"], "A1B2C3D4E5")
        self.assertEqual(client.calls[-1]["path"], "/rest/v1/rpc/did_create_dashboard_code")
        self.assertEqual(
            client.calls[-1]["body"],
            {"p_campaign_id": "campaign-123"},
        )

    def test_presence_updates_only_link_row(self):
        client = FakeClient()
        self.assertTrue(touch_character_presence(client, "linked-123"))
        call = client.calls[-1]
        self.assertEqual(call["method"], "PATCH")
        self.assertEqual(call["path"], "/rest/v1/campaign_characters")
        self.assertEqual(call["query"], {"id": "eq.linked-123"})
        self.assertIn("last_seen_at", call["body"])

    def test_dashboard_config_contains_only_public_browser_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "campaign_config.json").write_text(
                json.dumps({
                    "supabase_url": "https://example.supabase.co",
                    "supabase_publishable_key": "sb_publishable_test_public",
                }),
                encoding="utf-8",
            )
            target = prepare_dashboard_config(root)
            text = target.read_text(encoding="utf-8")
            self.assertIn("https://example.supabase.co", text)
            self.assertIn("sb_publishable_test_public", text)
            self.assertNotIn("service_role", text)
            self.assertNotIn("refresh_token", text)

    def test_dashboard_assets_have_live_data_sources(self):
        root = Path(__file__).resolve().parent / "dm_dashboard"
        html = (root / "index.html").read_text(encoding="utf-8")
        js = (root / "app.js").read_text(encoding="utf-8")
        css = (root / "styles.css").read_text(encoding="utf-8")

        self.assertIn("DM Dashboard", html)
        self.assertIn("campaign_characters", js)
        self.assertIn("character_state", js)
        self.assertIn("campaign_rolls", js)
        self.assertIn("postgres_changes", js)
        self.assertIn("did_claim_dashboard", js)
        self.assertIn("Recent Rolls", html)
        self.assertIn("character-card", css)


if __name__ == "__main__":
    unittest.main(verbosity=2)
