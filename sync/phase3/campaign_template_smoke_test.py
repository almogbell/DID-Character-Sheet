from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

from campaign_cloud import CampaignCloudClient, CampaignCloudError
from campaign_template import CampaignTemplateService, campaign_template
from character_template import CharacterCreationRules, CharacterTemplate


def smoke_template(name="DID Smoke Rules"):
    return CharacterTemplate(
        name=name,
        description="Phase 3 cloud template smoke test",
        player_instructions="This text should survive the campaign round trip.",
        rules=CharacterCreationRules(
            level=2,
            extra_ip=3,
            species_mode="required",
            starting_hearts=6,
            starting_at=8,
            allow_custom_improvements=False,
            allowed_ability_array_ids=[],
            free_heightened_ability_slots=3,
            restrict_ability_dice_to_allowed_arrays=False,
            improvement_mode="all",
            improvement_ids=[],
            improvement_overrides={},
            template_custom_improvements=[],
        ),
    )


def main():
    app_dir = Path.cwd()
    dm = None
    campaign_id = None

    with tempfile.TemporaryDirectory(prefix="did_phase3_smoke_") as temporary:
        root = Path(temporary)
        try:
            print("1/6  Creating separate DM and player identities...")
            dm = CampaignCloudClient(app_dir=app_dir, user_data_dir=root / "dm")
            player = CampaignCloudClient(app_dir=app_dir, user_data_dir=root / "player")
            dm.ensure_session()
            player.ensure_session()

            dm_service = CampaignTemplateService(dm)
            player_service = CampaignTemplateService(player)

            print("2/6  Creating a campaign WITH its Creation Rules...")
            campaign = dm_service.create_campaign(
                "DID Phase 3 Smoke Test",
                smoke_template(),
            )
            campaign_id = campaign["id"]
            invite_code = campaign["invite_code"]
            stored = campaign_template(campaign)
            assert stored.rules.level == 2
            assert stored.rules.extra_ip == 3
            assert stored.rules.species_mode == "required"
            assert stored.rules.free_heightened_ability_slots == 3
            assert stored.description == "Phase 3 cloud template smoke test"

            print("3/6  Joining as a player and receiving the same rules...")
            joined = player_service.join_campaign(invite_code, "Phase 3 Player")
            joined_template = campaign_template(joined)
            assert joined["id"] == campaign_id
            assert joined["role"] == "player"
            assert joined_template.rules.level == 2
            assert joined_template.rules.starting_hearts == 6
            assert joined_template.player_instructions.startswith("This text")

            print("4/6  Verifying the player cannot edit campaign rules...")
            forbidden = False
            try:
                player_service.update_campaign_template(
                    campaign_id,
                    smoke_template("Player Must Not Save This"),
                )
            except CampaignCloudError:
                forbidden = True
            assert forbidden, "Player was unexpectedly allowed to edit campaign rules"

            print("5/6  Updating the rules as DM...")
            changed = smoke_template("Updated DID Smoke Rules")
            changed.rules.level = 4
            changed.rules.extra_ip = 7
            updated = dm_service.update_campaign_template(campaign_id, changed)
            updated_template = campaign_template(updated)
            assert updated_template.name == "Updated DID Smoke Rules"
            assert updated_template.rules.level == 4
            assert updated_template.rules.extra_ip == 7

            print("6/6  Verifying the joined player sees the updated campaign rules...")
            player_view = player_service.get_campaign(campaign_id)
            player_template = campaign_template(player_view)
            assert player_template.name == "Updated DID Smoke Rules"
            assert player_template.rules.level == 4

            print("\nPHASE 3 CAMPAIGN + CREATION RULES SMOKE TEST: PASS")
            print("Campaign creation, join, rule visibility, DM-only editing and template round-trip all work.")

        except Exception:
            print("\nPHASE 3 CAMPAIGN + CREATION RULES SMOKE TEST: FAILED")
            traceback.print_exc()
            raise

        finally:
            if dm is not None and campaign_id:
                try:
                    dm._request_json(
                        "DELETE",
                        "/rest/v1/campaigns",
                        query={"id": f"eq.{campaign_id}"},
                        prefer="return=minimal",
                    )
                    print("Temporary Phase 3 campaign removed.")
                except CampaignCloudError as error:
                    print(f"Warning: could not remove temporary campaign: {error}")


if __name__ == "__main__":
    main()
