"""Offline regression checks for join -> DM character publication.

No account credentials, real Supabase data, or Qt runtime required.
"""
import unittest
from types import SimpleNamespace

from campaign_join_flow import join_campaign_and_publish, JoinedButCharacterNotPublished


CAMPAIGN = {"id": "campaign-1", "name": "The Campaign", "role": "player"}


class FakeService:
    def __init__(self):
        self.calls = []

    def join_campaign(self, code, name):
        self.calls.append((code, name))
        return dict(CAMPAIGN)


class FakeClient:
    def __init__(self, previous=None, fail=False):
        self.previous = previous
        self.fail = fail
        self.created = []
        self.updated = []
        self.links = {}

    def get_character_link(self, character_id):
        return self.previous

    def link_character(self, campaign_id, shared, remember=True, *, creation_claim=None):
        assert isinstance(creation_claim, dict)
        if self.fail:
            raise ConnectionError('network unavailable')
        self.created.append((campaign_id, shared, remember))
        return {"id": "linked-1"}

    def upload_character_state(self, record_id, shared):
        self.updated.append((record_id, shared))


def run(character, client=None, party_uploader=None):
    service = FakeService()
    client = client or FakeClient()
    calls = []
    result = join_campaign_and_publish(
        SimpleNamespace(character=character), service, client,
        "ABCD1234", "Alice",
        shared_state_builder=lambda window, campaign_id: {
            "character_id": window.character.id, "name": window.character.name,
            "audience": "dm", "campaign_id": campaign_id,
        },
        party_state_builder=lambda window, campaign_id: {
            "character_id": window.character.id, "audience": "party", "shared_hp": False,
        },
        party_state_uploader=party_uploader or (lambda *args: calls.append(args)),
        connection_restorer=lambda window: calls.append("restored"),
        mismatch_checker=lambda character, campaign: [],
    )
    return result, service, client, calls


class CampaignJoinPublicationTests(unittest.TestCase):
    def test_named_character_is_published_without_separate_save(self):
        result, service, client, calls = run(SimpleNamespace(id="c1", name="Aurora"))
        self.assertEqual(result.status, "linked")
        self.assertEqual(service.calls, [("ABCD1234", "Alice")])
        self.assertEqual(client.created[0][0], CAMPAIGN["id"])
        self.assertEqual(client.created[0][1]["audience"], "dm")
        self.assertEqual(calls[0], "restored")
        self.assertEqual(calls[1][3]["audience"], "party")

    def test_no_character_does_not_publish(self):
        result, _, client, _ = run(None)
        self.assertEqual(result.status, "needs_character")
        self.assertFalse(client.created)

    def test_placeholder_character_does_not_publish(self):
        result, _, client, _ = run(SimpleNamespace(id="c1", name="Unnamed Character"))
        self.assertEqual(result.status, "needs_character")
        self.assertFalse(client.created)

    def test_other_campaign_link_never_reassigned(self):
        client = FakeClient(previous={"campaign_id": "different-campaign", "campaign_character_id": "other-id"})
        result, _, client, calls = run(SimpleNamespace(id="c1", name="Aurora"), client)
        self.assertEqual(result.status, "linked_elsewhere")
        self.assertFalse(client.created)
        self.assertFalse(client.updated)
        self.assertFalse(calls)

    def test_repeat_join_updates_existing_link_without_duplicate(self):
        client = FakeClient(previous={"campaign_id": CAMPAIGN["id"], "campaign_character_id": "existing-id"})
        result, _, client, _ = run(SimpleNamespace(id="c1", name="Aurora"), client)
        self.assertEqual(result.status, "linked")
        self.assertEqual(client.created, [])
        self.assertEqual(client.updated[0][0], "existing-id")

    def test_join_success_upload_failure_is_not_mislabeled_join_failure(self):
        service = FakeService()
        client = FakeClient(fail=True)
        with self.assertRaises(JoinedButCharacterNotPublished) as raised:
            join_campaign_and_publish(
                SimpleNamespace(character=SimpleNamespace(id="c1", name="Aurora")),
                service, client, "CODE", "Alice",
                shared_state_builder=lambda *args, **kwargs: {"character_id": "c1", "name": "Aurora"},
                party_state_builder=lambda *args, **kwargs: {},
                party_state_uploader=lambda *args: None,
                connection_restorer=lambda window: None,
                mismatch_checker=lambda character, campaign: [],
            )
        self.assertEqual(raised.exception.campaign["id"], CAMPAIGN["id"])
        self.assertEqual(len(service.calls), 1)

    def test_party_error_warns_but_does_not_undo_dm_link(self):
        def broken_party(*args):
            raise PermissionError("party privacy upload denied")
        result, _, client, _ = run(
            SimpleNamespace(id="c1", name="Aurora"), party_uploader=broken_party
        )
        self.assertEqual(result.status, "linked")
        self.assertEqual(len(client.created), 1)
        self.assertIn("Party Dashboard sharing failed", result.warning)


if __name__ == '__main__':
    unittest.main()
