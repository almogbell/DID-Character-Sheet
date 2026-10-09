from __future__ import annotations

import unittest
from pathlib import Path

from campaign_session import CampaignSessionService


class FakeClient:
    def __init__(self):
        self.calls = []
        self.roll_sharing = True

    def _request_json(self, method, path, body=None, query=None, authenticated=True, prefer=None):
        self.calls.append({
            "method": method,
            "path": path,
            "body": body,
            "query": query,
            "prefer": prefer,
        })

        if path == "/rest/v1/campaign_sessions" and method == "GET":
            if query and query.get("ended_at") == "is.null":
                return [{
                    "id": "session-1",
                    "campaign_id": "campaign-1",
                    "session_number": 1,
                    "started_at": "2026-10-10T00:00:00Z",
                    "ended_at": None,
                }]
            return [{
                "id": "session-1",
                "campaign_id": "campaign-1",
                "session_number": 1,
                "started_at": "2026-10-10T00:00:00Z",
                "ended_at": None,
            }]

        if path == "/rest/v1/rpc/did_start_session":
            return [{"id": "session-1", "session_number": 1, "snapshot_count": 2}]

        if path == "/rest/v1/rpc/did_end_session":
            return [{
                "id": "session-1",
                "session_number": 1,
                "ended_at": "2026-10-10T02:00:00Z",
                "snapshot_count": 2,
            }]

        if path == "/rest/v1/campaign_characters" and method == "GET":
            return [{"id": "character-link-1", "share_session_rolls": self.roll_sharing}]

        if path == "/rest/v1/campaign_characters" and method == "PATCH":
            self.roll_sharing = bool(body.get("share_session_rolls"))
            return [{"id": "character-link-1", "share_session_rolls": self.roll_sharing}]

        if path == "/rest/v1/session_snapshots":
            return [
                {"snapshot_kind": "start", "campaign_character_id": "character-link-1"},
                {"snapshot_kind": "end", "campaign_character_id": "character-link-1"},
            ]

        return []


class CampaignSessionServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.service = CampaignSessionService(self.client)

    def test_active_session(self):
        row = self.service.active_session("campaign-1")
        self.assertEqual(row["id"], "session-1")
        self.assertEqual(self.client.calls[-1]["query"]["ended_at"], "is.null")

    def test_start_and_end_use_rpc(self):
        started = self.service.start_session("campaign-1")
        ended = self.service.end_session("campaign-1")
        self.assertEqual(started["snapshot_count"], 2)
        self.assertEqual(ended["snapshot_count"], 2)
        paths = [call["path"] for call in self.client.calls]
        self.assertIn("/rest/v1/rpc/did_start_session", paths)
        self.assertIn("/rest/v1/rpc/did_end_session", paths)

    def test_roll_sharing_round_trip(self):
        self.assertTrue(self.service.get_roll_sharing("character-link-1"))
        updated = self.service.set_roll_sharing("character-link-1", False)
        self.assertFalse(updated["share_session_rolls"])
        self.assertFalse(self.service.get_roll_sharing("character-link-1"))

    def test_snapshot_archive(self):
        rows = self.service.list_snapshots("session-1")
        self.assertEqual({row["snapshot_kind"] for row in rows}, {"start", "end"})

    def test_phase5_assets_contain_required_session_controls(self):
        root = Path(__file__).resolve().parent
        html = (root / "dm_dashboard" / "index.html").read_text(encoding="utf-8")
        js = (root / "dm_dashboard" / "app.js").read_text(encoding="utf-8")
        sql = (root / "campaign_supabase_phase5.sql").read_text(encoding="utf-8")

        for token in ("startSessionBtn", "endSessionBtn", "sessionSelect", "viewSnapshotsBtn"):
            self.assertIn(token, html)
        for token in ("did_start_session", "did_end_session", "session_snapshots", "session_id"):
            self.assertIn(token, js)
        for token in (
            "campaign_sessions",
            "session_snapshots",
            "did_assign_roll_session",
            "share_session_rolls",
            "did_one_active_session_per_campaign",
        ):
            self.assertIn(token, sql)


if __name__ == "__main__":
    unittest.main(verbosity=2)
