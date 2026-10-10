from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from campaign_privacy import (
    CampaignPrivacyStore,
    build_shared_character_state_with_preferences,
    normalize_privacy_preferences,
)


STAT_NAMES = ("agility", "strength", "finesse", "instinct", "presence", "knowledge")


def sample_character_dict():
    return {
        "id": "char-privacy-test",
        "name": "Luna",
        "species_name": "Human",
        "backstory": "SECRET BACKSTORY",
        "stats": {
            name: {"die_size": 6 + (index % 2) * 2, "bonus": index % 3}
            for index, name in enumerate(STAT_NAMES)
        },
        "HP": {"current_HP": 7, "max_hearts": 3, "max_HP": 12},
        "Adversity": {"current_AT": 2, "max_AT": 6},
        "progression": {"current_IP": 8, "used_IP": 3, "level": 3},
        "selected_defense_stat_name": "agility",
        "improvements": {
            "list_of_taken_improvements": [
                {
                    "id": "imp-1",
                    "catalog_id": "sturdy",
                    "name": "Sturdy",
                    "times_taken": 2,
                }
            ]
        },
        "inventory": {
            "list_of_items": [
                {"id": "item-share", "name": "Torch", "description": "Bright", "quantity": 2},
                {"id": "item-private", "name": "Secret Key", "description": "PRIVATE", "quantity": 1},
            ]
        },
        "notes": {
            "list_of_notes": [
                {"id": "note-share", "title": "Clue", "text": "Share this", "color": "yellow", "pinned": True},
                {"id": "note-private", "title": "Secret", "text": "PRIVATE NOTE", "color": "red", "pinned": False},
            ]
        },
        "image": {
            "images": [
                {"id": "portrait-1", "display": "data:image/png;base64,AAAA"}
            ],
            "current_index": 0,
        },
    }


class CampaignPrivacyTests(unittest.TestCase):
    def test_defaults_preserve_old_improvements_but_keep_private_categories_private(self):
        state = build_shared_character_state_with_preferences(sample_character_dict())
        self.assertEqual(state["name"], "Luna")
        self.assertEqual(state["resources"]["hearts"]["current"], 7)
        self.assertEqual(state["improvements"][0]["name"], "Sturdy")
        self.assertNotIn("backstory", state)
        self.assertNotIn("inventory", state)
        self.assertNotIn("notes", state)
        self.assertFalse(state["portrait"]["shared"])
        self.assertNotIn("data", state["portrait"])

    def test_explicit_sharing_includes_only_selected_inventory_and_notes(self):
        prefs = normalize_privacy_preferences(
            {
                "share_improvements": False,
                "share_portrait": True,
                "share_backstory": True,
                "share_inventory": True,
                "inventory_item_ids": ["item-share"],
                "share_notes": True,
                "note_ids": ["note-share"],
            }
        )
        state = build_shared_character_state_with_preferences(sample_character_dict(), prefs)
        self.assertNotIn("improvements", state)
        self.assertEqual(state["backstory"], "SECRET BACKSTORY")
        self.assertEqual([item["id"] for item in state["inventory"]], ["item-share"])
        self.assertEqual([note["id"] for note in state["notes"]], ["note-share"])
        self.assertNotIn("PRIVATE", str(state))
        self.assertTrue(state["portrait"]["shared"])
        self.assertEqual(state["portrait"]["data"], "data:image/png;base64,AAAA")

    def test_turning_category_off_removes_previous_values_from_payload(self):
        data = sample_character_dict()
        shared = build_shared_character_state_with_preferences(
            data,
            {"share_backstory": True, "share_inventory": True, "inventory_item_ids": ["item-share"]},
        )
        self.assertIn("backstory", shared)
        self.assertIn("inventory", shared)

        hidden = build_shared_character_state_with_preferences(
            data,
            {"share_backstory": False, "share_inventory": False},
        )
        self.assertNotIn("backstory", hidden)
        self.assertNotIn("inventory", hidden)

    def test_local_store_is_isolated_by_campaign_and_character(self):
        with tempfile.TemporaryDirectory() as folder:
            store = CampaignPrivacyStore(Path(folder))
            store.set(
                "campaign-a",
                "char-a",
                {"share_backstory": True, "note_ids": ["n1"]},
            )
            a = store.get("campaign-a", "char-a")
            b = store.get("campaign-b", "char-a")
            c = store.get("campaign-a", "char-b")
            self.assertTrue(a["share_backstory"])
            self.assertEqual(a["note_ids"], ["n1"])
            self.assertFalse(b["share_backstory"])
            self.assertFalse(c["share_backstory"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
