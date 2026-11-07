from __future__ import annotations

import unittest
from copy import deepcopy

from backend_2_1 import Character
from campaign_template import (
    CampaignTemplateService,
    campaign_template,
    character_rule_mismatches,
    template_from_campaign_dict,
    template_to_campaign_dict,
)
from character_template import CharacterCreationRules, CharacterTemplate, apply_template_to_character


class FakeClient:
    def __init__(self):
        self.user_id = "11111111-1111-1111-1111-111111111111"
        self.calls = []
        self.campaign = None

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
                "body": deepcopy(body),
                "query": deepcopy(query),
                "prefer": prefer,
            }
        )

        if method == "POST" and path == "/rest/v1/campaigns":
            self.campaign = {
                "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "name": body["name"],
                "invite_code": "ABC12345",
                "owner_user_id": self.user_id,
                "active": True,
                "created_at": "2026-10-10T00:00:00Z",
                "updated_at": "2026-10-10T00:00:00Z",
                "character_template": deepcopy(body["character_template"]),
            }
            return [deepcopy(self.campaign)]

        if method == "PATCH" and path == "/rest/v1/campaigns":
            self.campaign["character_template"] = deepcopy(body["character_template"])
            return [deepcopy(self.campaign)]

        if method == "GET" and path == "/rest/v1/campaigns":
            return [deepcopy(self.campaign)] if self.campaign else []

        if method == "GET" and path == "/rest/v1/campaign_members":
            return [{"role": "dm", "display_name": "DM"}]

        return []

    def join_campaign(self, invite_code, display_name="Player"):
        return {
            "id": self.campaign["id"],
            "name": self.campaign["name"],
            "invite_code": invite_code,
            "owner_user_id": self.campaign["owner_user_id"],
            "role": "player",
        }


def rich_template(name="QA Campaign Rules"):
    return CharacterTemplate(
        name=name,
        description="A rules description",
        player_instructions="Make a campaign hero.",
        rules=CharacterCreationRules(
            level=3,
            extra_ip=4,
            species_mode="required",
            starting_hearts=7,
            starting_at=9,
            allow_custom_improvements=False,
            allowed_ability_array_ids=["array_a", "array_b"],
            free_heightened_ability_slots=3,
            restrict_ability_dice_to_allowed_arrays=True,
            improvement_mode="allow_only",
            improvement_ids=["imp_a", "imp_b"],
            improvement_overrides={
                "imp_a": {
                    "name": "Campaign Improvement",
                    "cost": 2,
                    "description": "Campaign description",
                }
            },
            template_custom_improvements=[
                {
                    "id": "campaign_custom",
                    "name": "Campaign Custom",
                    "cost": 1,
                    "description": "Only in this campaign",
                    "purchase_rule": "single",
                    "requires_choices": [],
                    "effects": [],
                    "tags": ["template", "custom"],
                }
            ],
        ),
    )


class CampaignTemplateTests(unittest.TestCase):
    def test_campaign_uses_exact_template_codec(self):
        original = rich_template()
        encoded = template_to_campaign_dict(original)
        decoded = template_from_campaign_dict(encoded)
        self.assertEqual(template_to_campaign_dict(decoded), encoded)

    def test_campaign_service_sends_template_with_campaign(self):
        client = FakeClient()
        service = CampaignTemplateService(client)
        original = rich_template()

        campaign = service.create_campaign("QA Campaign", original)

        self.assertEqual(campaign["name"], "QA Campaign")
        self.assertEqual(
            campaign["character_template"],
            template_to_campaign_dict(original),
        )
        self.assertEqual(client.calls[0]["path"], "/rest/v1/campaigns")
        self.assertIn("character_template", client.calls[0]["body"])

    def test_campaign_template_applies_without_second_rules_implementation(self):
        template = rich_template()
        character = Character.create_new_character("QA Hero")
        apply_template_to_character(character, template)

        self.assertEqual(character.progression.level, 3)
        self.assertEqual(character.HP.max_hearts, 7)
        self.assertEqual(character.adversity.max_AT, 9)
        self.assertEqual(character.creation_species_mode, "required")
        self.assertFalse(character.creation_allow_custom_improvements)
        self.assertEqual(character.free_heightened_ability_slots, 3)
        self.assertTrue(character.creation_restrict_ability_dice_to_allowed_arrays)
        self.assertEqual(character.creation_improvement_mode, "allow_only")
        self.assertEqual(character_rule_mismatches(character, template), [])

    def test_existing_character_mismatch_is_reported_not_rewritten(self):
        template = rich_template()
        character = Character.create_new_character("Existing Hero")
        original_level = character.progression.level
        original_hearts = character.HP.max_hearts

        mismatches = character_rule_mismatches(character, template)

        self.assertTrue(mismatches)
        self.assertEqual(character.progression.level, original_level)
        self.assertEqual(character.HP.max_hearts, original_hearts)

    def test_rules_update_round_trip(self):
        client = FakeClient()
        service = CampaignTemplateService(client)
        created = service.create_campaign("QA Campaign", rich_template("First Rules"))

        updated_template = rich_template("Changed Rules")
        updated_template.rules.level = 5
        updated = service.update_campaign_template(created["id"], updated_template)

        decoded = campaign_template(updated)
        self.assertEqual(decoded.name, "Changed Rules")
        self.assertEqual(decoded.rules.level, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
