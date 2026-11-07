"""Offline character admission regression tests; no PySide6 or cloud credentials."""
import unittest
from types import SimpleNamespace

from campaign_admission import admit_character
from campaign_join_flow import join_campaign_and_publish

CAMPAIGN = {"id": "camp1", "name": "Campaign"}


class Client:
    def __init__(self):
        self.links = {}
        self.uploads = []
        self.created = []
        self.requested = []
        self.cancelled = []
        self.reply = {"id": "request1", "status": "pending"}

    def get_character_link(self, cid):
        link = self.links.get(cid)
        return link if link and link.get("approval_status") != "pending" else None

    def get_pending_character_approval(self, cid):
        link = self.links.get(cid)
        return link if link and link.get("approval_status") == "pending" else None

    def link_character(self, camp, shared, remember=True, *, creation_claim=None):
        assert isinstance(creation_claim, dict)
        self.created.append((camp, shared))
        self.links[shared["character_id"]] = {"campaign_id": camp, "campaign_character_id": "active1"}
        return {"id": "active1"}

    def upload_character_state(self, record, shared):
        self.uploads.append((record, shared))

    def request_character_approval(self, camp, shared, mismatches):
        self.requested.append((camp, shared, tuple(mismatches)))
        self.links[shared["character_id"]] = {"campaign_id": camp, "request_id": "request1", "approval_status": "pending"}
        return self.reply

    def refresh_pending_character_approval(self, cid):
        return self.get_pending_character_approval(cid)

    def cancel_character_approval(self, req):
        self.cancelled.append(req)
        return True

    def unlink_local_character(self, cid):
        self.links.pop(cid, None)


class Service:
    def join_campaign(self, code, name):
        return dict(CAMPAIGN)


def state():
    return {"character_id": "aurora", "name": "Aurora"}


def obj():
    return SimpleNamespace(character=SimpleNamespace(id="aurora", name="Aurora"))


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.window = obj()

    def submit(self, problems):
        return admit_character(
            self.window, CAMPAIGN, self.client, state(),
            mismatch_checker=lambda char, camp: problems,
        )

    def test_compliant_character_immediately_links(self):
        result = self.submit([])
        self.assertEqual(result.status, "linked")
        self.assertEqual(len(self.client.created), 1)
        self.assertEqual(self.client.requested, [])

    def test_noncompliant_character_never_publishes(self):
        result = self.submit(["Starting level too low", "Custom improvements forbidden"])
        self.assertEqual(result.status, "approval_pending")
        self.assertEqual(len(result.mismatches), 2)
        self.assertEqual(len(self.client.requested), 1)
        self.assertEqual(self.client.created, [])
        self.assertEqual(self.client.uploads, [])

    def test_repeated_noncompliant_join_reuses_request(self):
        self.submit(["Level"])
        self.submit(["Level"])
        self.assertEqual(len(self.client.requested), 2)
        self.assertEqual(self.client.created, [])

    def test_approved_existing_character_skips_new_validation(self):
        self.client.links["aurora"] = {"campaign_id": "camp1", "campaign_character_id": "existing"}
        result = self.submit(["Changed rules since joining"])
        self.assertEqual(result.status, "linked")
        self.assertEqual(len(self.client.uploads), 1)
        self.assertEqual(self.client.requested, [])

    def test_linked_elsewhere_not_submitted(self):
        self.client.links["aurora"] = {"campaign_id": "other", "campaign_character_id": "existing"}
        result = self.submit(["Level"])
        self.assertEqual(result.status, "linked_elsewhere")
        self.assertEqual(self.client.requested, [])

    def test_pending_elsewhere_not_overwritten(self):
        self.client.links["aurora"] = {"campaign_id": "other", "request_id": "otherrequest", "approval_status": "pending"}
        result = self.submit(["Level"])
        self.assertEqual(result.status, "linked_elsewhere")
        self.assertEqual(self.client.requested, [])

    def test_compatible_character_cancels_stale_pending_before_link(self):
        self.submit(["Level"])
        result = self.submit([])
        self.assertEqual(result.status, "linked")
        self.assertEqual(self.client.cancelled, ["request1"])
        self.assertEqual(len(self.client.created), 1)

    def test_join_reports_pending_without_party_publication(self):
        calls = []
        result = join_campaign_and_publish(
            self.window, Service(), self.client, "CODE", "Alice",
            shared_state_builder=lambda window, campaign_id: state(),
            party_state_builder=lambda window, campaign_id: calls.append("party"),
            party_state_uploader=lambda *args: calls.append("published"),
            connection_restorer=lambda window: calls.append("connected"),
            mismatch_checker=lambda char, camp: ["Custom improvements forbidden"],
        )
        self.assertEqual(result.status, "approval_pending")
        self.assertEqual(self.client.created, [])
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
