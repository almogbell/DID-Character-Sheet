"""Offline Supabase approval API and local-link lifecycle tests."""
import tempfile
import unittest
from campaign_cloud import CampaignCloudClient


class ApprovalCloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = CampaignCloudClient(
            user_data_dir=self.tmp.name, config={"url": "https://test.supabase.co", "key": "x" * 32},
        )
        self.requests = []
        self.responses = []
        def stub(method, path, body=None, query=None, **kwargs):
            self.requests.append((method, path, body, query))
            return self.responses.pop(0)
        self.client._request_json = stub

    def test_request_is_pending_and_cannot_sync_active(self):
        self.responses.append({"id": "req1", "status": "pending"})
        self.client.request_character_approval("camp1", {"character_id": "aurora", "name": "Aurora"}, ["Bad rule"])
        self.assertIsNone(self.client.get_character_link("aurora"))
        self.assertEqual(self.client.get_pending_character_approval("aurora")["request_id"], "req1")
        path = self.requests[0][1]
        self.assertEqual(path, "/rest/v1/rpc/did_request_character_approval")

    def test_approved_request_activates_durable_local_link(self):
        self.responses.extend([
            {"id": "req1", "status": "pending"},
            [{"id": "req1", "status": "approved", "approved_character_id": "approved1", "campaign_id": "camp1", "display_name": "Aurora"}],
        ])
        self.client.request_character_approval("camp1", {"character_id": "aurora", "name": "Aurora"}, ["Level"])
        outcome = self.client.refresh_pending_character_approval("aurora")
        self.assertEqual(outcome["approval_status"], "approved")
        self.assertEqual(self.client.get_character_link("aurora")["campaign_character_id"], "approved1")
        self.assertIsNone(self.client.get_pending_character_approval("aurora"))

    def test_rejection_keeps_active_sync_disabled(self):
        self.responses.extend([
            {"id": "req1", "status": "pending"},
            [{"id": "req1", "status": "rejected", "campaign_id": "camp1", "display_name": "Aurora"}],
        ])
        self.client.request_character_approval("camp1", {"character_id": "aurora", "name": "Aurora"}, ["Level"])
        outcome = self.client.refresh_pending_character_approval("aurora")
        self.assertEqual(outcome["approval_status"], "rejected")
        self.assertIsNone(self.client.get_character_link("aurora"))

    def test_approved_rpc_immediately_sets_active_record(self):
        self.responses.append({"id": "req1", "status": "approved", "approved_character_id": "approved1"})
        self.client.request_character_approval("camp1", {"character_id": "aurora", "name": "Aurora"}, ["Level"])
        self.assertEqual(self.client.get_character_link("aurora")["campaign_character_id"], "approved1")

    def test_dm_decision_uses_rpc(self):
        self.responses.append({"id": "req1", "status": "rejected"})
        result = self.client.decide_character_approval("req1", False)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.requests[0][2], {"p_request_id": "req1", "p_approve": False})

if __name__ == '__main__':
    unittest.main()
