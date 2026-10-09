import json
import unittest

from campaign_shared import (
    build_shared_character_state_from_dict,
    build_shared_roll_event_from_summary,
)


class SharedCampaignDataTests(unittest.TestCase):
    def test_character_state_is_whitelisted(self):
        raw = {
            "id": "char-123",
            "name": "Luna",
            "species_name": "Human",
            "progression": {"level": 4, "current_IP": 12, "used_IP": 7},
            "HP": {"current_HP": 2, "max_hearts": 3},
            "Adversity": {"current_AT": 1, "max_AT": 4},
            "stats": {
                "agility": {"die_size": 8, "bonus": 2},
                "strength": {"die_size": 6, "bonus": 0},
                "finesse": {"die_size": 10, "bonus": 1},
                "instinct": {"die_size": 8, "bonus": 0},
                "presence": {"die_size": 12, "bonus": 0},
                "knowledge": {"die_size": 6, "bonus": 1},
            },
            "selected_defense_stat_name": "agility",
            "improvements": [
                {"catalog_id": "spellcasting", "name": "Spellcasting", "times_taken": 1}
            ],
            "image": {"images": [{"display": "PRIVATE_IMAGE_BYTES"}], "current_index": 0},
            "notes": [{"title": "Secret", "text": "PRIVATE NOTE"}],
            "inventory": [{"name": "Secret item"}],
            "backstory": "PRIVATE BACKSTORY",
            "creation_rules": {"secret": True},
            "roll_history": ["OLD PRIVATE HISTORY"],
            "local_path": "C:/Users/player/secret.didchar",
        }

        shared = build_shared_character_state_from_dict(
            raw,
            generated_utc="2026-10-09T12:00:00Z",
        )

        self.assertEqual(shared["character_id"], "char-123")
        self.assertEqual(shared["name"], "Luna")
        self.assertEqual(shared["resources"]["hearts"], {"current": 2, "max": 3})
        self.assertEqual(shared["resources"]["adversity_tokens"], {"current": 1, "max": 4})
        self.assertEqual(shared["resources"]["improvement_points"]["remaining"], 5)
        self.assertEqual(shared["abilities"]["agility"], {"die_size": 8, "bonus": 2})
        self.assertTrue(shared["portrait"]["available"])

        rendered = json.dumps(shared)
        for private_value in (
            "PRIVATE_IMAGE_BYTES",
            "PRIVATE NOTE",
            "Secret item",
            "PRIVATE BACKSTORY",
            "OLD PRIVATE HISTORY",
            "C:/Users/player/secret.didchar",
        ):
            self.assertNotIn(private_value, rendered)

    def test_ability_roll_keeps_structured_dice(self):
        summary = {
            "roll_type": "ability",
            "ability_name": "Agility",
            "flat_bonus": 2,
            "total": 18,
            "deed_success": True,
            "terms": [
                {
                    "label": "roll",
                    "kind": "ability",
                    "sides": 8,
                    "sign": 1,
                    "values": [8, 4],
                },
                {
                    "label": "adv.",
                    "kind": "advantage",
                    "sides": 6,
                    "sign": 1,
                    "values": [5],
                },
                {
                    "label": "dis.",
                    "kind": "disadvantage",
                    "sides": 6,
                    "sign": -1,
                    "values": [1],
                },
            ],
        }

        event = build_shared_roll_event_from_summary(
            "char-123",
            "Luna",
            summary,
            rolled_utc="2026-10-09T12:30:00Z",
            event_id="event-1",
        )

        self.assertEqual(event["event_id"], "event-1")
        self.assertEqual(event["ability_name"], "Agility")
        self.assertEqual(event["total"], 18)
        self.assertTrue(event["dice"][0]["exploded"])
        self.assertEqual(event["dice"][0]["values"], [8, 4])
        self.assertEqual(event["dice"][1]["kind"], "advantage")
        self.assertEqual(event["dice"][2]["sign"], -1)
        self.assertTrue(event["deed_success"])

    def test_other_dice_never_get_a_combined_total(self):
        summary = {
            "roll_type": "other_dice",
            "ability_name": "Other Dice",
            "flat_bonus": 0,
            "total": 999,
            "terms": [
                {"label": "d4", "kind": "other_die", "sides": 4, "sign": 1, "values": [3]},
                {"label": "d4", "kind": "other_die", "sides": 4, "sign": 1, "values": [2]},
                {"label": "d100", "kind": "other_die", "sides": 100, "sign": 1, "values": [81]},
            ],
        }

        event = build_shared_roll_event_from_summary(
            "char-123",
            "Luna",
            summary,
            rolled_utc="2026-10-09T12:45:00Z",
            event_id="event-2",
        )

        self.assertIsNone(event["total"])
        self.assertTrue(event["individual_only"])
        self.assertEqual(
            event["groups"],
            [
                {"sides": 4, "values": [3, 2]},
                {"sides": 100, "values": [81]},
            ],
        )

    def test_invalid_die_face_is_rejected(self):
        with self.assertRaises(ValueError):
            build_shared_roll_event_from_summary(
                "char-123",
                "Luna",
                {
                    "roll_type": "ability",
                    "ability_name": "Agility",
                    "flat_bonus": 0,
                    "total": 9,
                    "terms": [
                        {"label": "roll", "kind": "ability", "sides": 8, "sign": 1, "values": [9]}
                    ],
                },
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
