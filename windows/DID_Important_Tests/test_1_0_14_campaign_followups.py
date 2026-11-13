"""Regression checks for v1.0.14 campaign UI and sharing follow-ups."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from campaign_admission import admit_character
from campaign_party import build_party_character_state_with_preferences
from campaign_privacy import _portrait_payload
from campaign_shared import build_shared_character_state_from_dict
from campaign_template import character_rule_mismatches
from character_template import CharacterCreationRules, CharacterTemplate
from backend_2_1 import Character


ROOT = Path(__file__).resolve().parents[1]


def example_character():
    return {
        "id": "scarlet-id",
        "name": "Scarlet Pride",
        "species_name": "Vampire",
        "HP": {"current_HP": 25, "max_hearts": 5, "max_HP": 25},
        "Adversity": {"current_AT": 1, "max_AT": 7},
        "progression": {"current_IP": 23, "used_IP": 0, "level": 4},
        "stats": {},
        "image": {"images": [], "current_index": 0},
        "improvements": [],
    }


class SharingFollowupTests(unittest.TestCase):
    def test_hearty_max_hp_is_shared_without_recalculation_from_hearts(self):
        data = example_character()
        shared = build_shared_character_state_from_dict(data)
        self.assertEqual(shared["resources"]["hearts"]["max"], 5)
        self.assertEqual(shared["resources"]["hearts"]["max_hp"], 25)
        party = build_party_character_state_with_preferences(data, {"share_hp": True})
        self.assertEqual(party["hp"], {"current": 25, "max": 25})

    def test_nested_legacy_portrait_dict(self):
        image = "data:image/png;base64,AAAA"
        data = {"image": {"images": [{"display": {"original": image}}], "current_index": 0}}
        self.assertEqual(_portrait_payload(data, True)["data"], image)

    def test_stringified_legacy_portrait_dict(self):
        image = "data:image/png;base64,AAAA"
        data = {"image": {"images": [{"display": repr({"original": image})}], "current_index": 0}}
        self.assertEqual(_portrait_payload(data, True)["data"], image)

    def test_creation_provenance_is_not_mislabeled_as_species_or_dice_violation(self):
        character = Character.create_new_character("Existing")
        character.species_name = "Aasimar"
        template = CharacterTemplate(
            name="Campaign",
            rules=CharacterCreationRules(
                species_mode="normal",
                allowed_ability_array_ids=["adventurer"],
            ),
        )
        mismatches = character_rule_mismatches(character, template)
        self.assertTrue(mismatches)
        self.assertFalse(any("Species rule" in item or "Allowed ability arrays" in item
                             for item in mismatches))

    def test_dashboards_sort_abilities_by_die_size(self):
        dm = (ROOT / "dm_dashboard" / "app.js").read_text(encoding="utf-8")
        party = (ROOT / "party_dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn(".sort((a, b) => (b.die - a.die)", dm)
        self.assertIn(".sort((a, b) => (b.die - a.die)", party)


class FakeClient:
    user_id = "owner-id"

    def __init__(self, old_status):
        self.old_status = old_status
        self.link = {"campaign_id": "old-campaign", "campaign_character_id": "old-record"}
        self.unlinked = False
        self.created = False

    def get_character_link(self, cid):
        return self.link

    def _request_json(self, method, path, query=None, **kwargs):
        if self.old_status == "offline":
            raise ConnectionError("Network unavailable")
        return ([{"active": True}] if self.old_status == "active" else [])

    def unlink_local_character(self, cid):
        self.unlinked = True
        self.link = None
        return True

    def link_character(self, campaign_id, shared, remember=True, *, creation_claim=None):
        self.created = True
        return {"id": "new-record"}


class AdmissionFollowupTests(unittest.TestCase):
    def test_confirmed_deleted_campaign_releases_link(self):
        client = FakeClient("removed")
        window = SimpleNamespace(character=SimpleNamespace(id="hero", name="Hero"))
        result = admit_character(window, {"id": "new-campaign"}, client,
                                 {"character_id": "hero", "name": "Hero"},
                                 mismatch_checker=lambda *_: [])
        self.assertEqual(result.status, "linked")
        self.assertTrue(client.unlinked)
        self.assertTrue(client.created)

    def test_active_old_campaign_remains_protected(self):
        client = FakeClient("active")
        window = SimpleNamespace(character=SimpleNamespace(id="hero", name="Hero"))
        result = admit_character(window, {"id": "new-campaign"}, client,
                                 {"character_id": "hero", "name": "Hero"},
                                 mismatch_checker=lambda *_: [])
        self.assertEqual(result.status, "linked_elsewhere")
        self.assertFalse(client.unlinked)

    def test_offline_does_not_remove_old_link(self):
        client = FakeClient("offline")
        window = SimpleNamespace(character=SimpleNamespace(id="hero", name="Hero"))
        with self.assertRaises(RuntimeError):
            admit_character(window, {"id": "new-campaign"}, client,
                            {"character_id": "hero", "name": "Hero"},
                            mismatch_checker=lambda *_: [])
        self.assertFalse(client.unlinked)


if __name__ == "__main__":
    unittest.main()
