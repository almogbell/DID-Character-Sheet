from __future__ import annotations

from copy import deepcopy

from campaign_cloud import CampaignCloudError
from character_template import (
    CharacterTemplate,
    CharacterTemplateStorage,
    apply_template_to_character,
)


CAMPAIGN_SELECT = (
    "id,name,invite_code,created_at,updated_at,owner_user_id,active,character_template"
)


def template_to_campaign_dict(template: CharacterTemplate) -> dict:
    """Serialize a campaign's creation rules with the existing template codec."""
    if not isinstance(template, CharacterTemplate):
        raise TypeError("Expected CharacterTemplate")
    template.validate()
    return deepcopy(CharacterTemplateStorage.template_to_dict(template))


def template_from_campaign_dict(data: dict | None) -> CharacterTemplate:
    """Deserialize campaign rules with the same codec used by .didtemplate."""
    if not isinstance(data, dict):
        data = {}
    return CharacterTemplateStorage.template_from_dict(deepcopy(data))


def campaign_template(campaign: dict) -> CharacterTemplate:
    if not isinstance(campaign, dict):
        raise ValueError("Campaign record must be a dictionary")
    return template_from_campaign_dict(campaign.get("character_template"))


def character_rule_mismatches(character, template: CharacterTemplate) -> list[str]:
    """Return creation-rule differences without silently changing a character.

    Campaign rules are creation rules, so mutable live resources are not required
    to remain exactly equal forever. We check the persistent restrictions copied
    into a character, plus minimum starting level/resources where meaningful.
    """
    template.validate()
    rules = template.rules
    mismatches: list[str] = []

    if not bool(getattr(character, "creation_rules_active", False)):
        mismatches.append("Character was not created with Creation Rules enabled.")

    comparisons = (
        (
            "Species rule",
            str(getattr(character, "creation_species_mode", "normal")),
            str(rules.species_mode),
        ),
        (
            "Custom Improvements rule",
            bool(getattr(character, "creation_allow_custom_improvements", True)),
            bool(rules.allow_custom_improvements),
        ),
        (
            "Allowed ability arrays",
            sorted(str(x) for x in getattr(character, "creation_allowed_ability_array_ids", []) or []),
            sorted(str(x) for x in rules.allowed_ability_array_ids or []),
        ),
        (
            "Ability-die restriction",
            bool(getattr(character, "creation_restrict_ability_dice_to_allowed_arrays", False)),
            bool(getattr(rules, "restrict_ability_dice_to_allowed_arrays", False)),
        ),
        (
            "Improvement availability mode",
            str(getattr(character, "creation_improvement_mode", "all")),
            str(rules.improvement_mode),
        ),
        (
            "Improvement list",
            sorted(str(x) for x in getattr(character, "creation_improvement_ids", []) or []),
            sorted(str(x) for x in rules.improvement_ids or []),
        ),
        (
            "Improvement overrides",
            deepcopy(getattr(character, "creation_improvement_overrides", {}) or {}),
            deepcopy(getattr(rules, "improvement_overrides", {}) or {}),
        ),
        (
            "Template-only Improvements",
            deepcopy(getattr(character, "creation_template_custom_improvements", []) or []),
            deepcopy(getattr(rules, "template_custom_improvements", []) or []),
        ),
    )

    for label, actual, expected in comparisons:
        if actual != expected:
            mismatches.append(f"{label} does not match the campaign rules.")

    expected_free = int(getattr(rules, "free_heightened_ability_slots", 2))
    actual_free = int(getattr(character, "free_heightened_ability_slots", 2))
    if actual_free != expected_free:
        mismatches.append(
            f"Free Heightened Abilities: character has {actual_free}, campaign starts with {expected_free}."
        )

    progression = getattr(character, "progression", None)
    actual_level = int(getattr(progression, "level", 1) or 1)
    if actual_level < int(rules.level):
        mismatches.append(
            f"Character level {actual_level} is below the campaign starting level {int(rules.level)}."
        )

    hp = getattr(character, "HP", None)
    if rules.starting_hearts is not None:
        actual_hearts = int(getattr(hp, "max_hearts", 0) or 0)
        if actual_hearts < int(rules.starting_hearts):
            mismatches.append(
                f"Character has {actual_hearts} Hearts; campaign starts with {int(rules.starting_hearts)}."
            )

    adversity = getattr(character, "adversity", None)
    if rules.starting_at is not None:
        actual_at = int(getattr(adversity, "max_AT", 0) or 0)
        if actual_at < int(rules.starting_at):
            mismatches.append(
                f"Character maximum AT is {actual_at}; campaign starts with {int(rules.starting_at)}."
            )

    return mismatches


def create_character_from_campaign(character_factory, campaign: dict):
    template = campaign_template(campaign)
    character = character_factory()
    apply_template_to_character(character, template)
    return character, template


class CampaignTemplateService:
    """Campaign operations where Creation Rules are part of the campaign itself."""

    def __init__(self, client):
        self.client = client

    def create_campaign(self, name: str, template: CharacterTemplate) -> dict:
        name = str(name or "").strip()
        if not name:
            raise CampaignCloudError("Campaign name cannot be empty")
        if len(name) > 100:
            raise CampaignCloudError("Campaign name is too long")

        template_data = template_to_campaign_dict(template)
        rows = self.client._request_json(
            "POST",
            "/rest/v1/campaigns",
            query={"select": CAMPAIGN_SELECT},
            body={
                "name": name,
                "character_template": template_data,
            },
            prefer="return=representation",
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("Campaign was created but no record was returned")
        return rows[0]

    def get_campaign(self, campaign_id: str) -> dict:
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id:
            raise CampaignCloudError("Campaign ID is required")
        rows = self.client._request_json(
            "GET",
            "/rest/v1/campaigns",
            query={
                "id": f"eq.{campaign_id}",
                "select": CAMPAIGN_SELECT,
                "limit": "1",
            },
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("Campaign was not found or is not accessible")
        return rows[0]

    def list_campaigns(self) -> list[dict]:
        rows = self.client._request_json(
            "GET",
            "/rest/v1/campaigns",
            query={
                "select": CAMPAIGN_SELECT,
                "order": "created_at.desc",
            },
        )
        return rows if isinstance(rows, list) else []

    def join_campaign(self, invite_code: str, display_name: str = "Player") -> dict:
        joined = self.client.join_campaign(invite_code, display_name)
        campaign = self.get_campaign(joined["id"])
        campaign["role"] = joined.get("role", "player")
        return campaign

    def role_for_campaign(self, campaign_id: str) -> str:
        rows = self.client._request_json(
            "GET",
            "/rest/v1/campaign_members",
            query={
                "campaign_id": f"eq.{campaign_id}",
                "user_id": f"eq.{self.client.user_id}",
                "select": "role,display_name",
                "limit": "1",
            },
        )
        if isinstance(rows, list) and rows:
            return str(rows[0].get("role") or "player")
        return ""

    def update_campaign_template(
        self,
        campaign_id: str,
        template: CharacterTemplate,
    ) -> dict:
        campaign_id = str(campaign_id or "").strip()
        template_data = template_to_campaign_dict(template)
        rows = self.client._request_json(
            "PATCH",
            "/rest/v1/campaigns",
            query={
                "id": f"eq.{campaign_id}",
                "select": CAMPAIGN_SELECT,
            },
            body={"character_template": template_data},
            prefer="return=representation",
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError(
                "Campaign rules could not be updated. Only the campaign DM can edit them."
            )
        return rows[0]
