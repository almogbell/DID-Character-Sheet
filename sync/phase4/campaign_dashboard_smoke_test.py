from __future__ import annotations

import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from campaign_cloud import CampaignCloudClient, CampaignCloudError, load_campaign_cloud_config
from campaign_dashboard_bridge import create_dashboard_access, touch_character_presence


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_client(root, label):
    return CampaignCloudClient(
        app_dir=root,
        user_data_dir=root / f".phase4_{label}",
        config=load_campaign_cloud_config(root),
    )


def main():
    root = Path(__file__).resolve().parent
    campaign = None
    dm = None

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            print("1/8  Creating DM, player and browser sessions...")
            dm = CampaignCloudClient(
                app_dir=root,
                user_data_dir=temp / "dm",
                config=load_campaign_cloud_config(root),
            )
            player = CampaignCloudClient(
                app_dir=root,
                user_data_dir=temp / "player",
                config=load_campaign_cloud_config(root),
            )
            browser = CampaignCloudClient(
                app_dir=root,
                user_data_dir=temp / "browser",
                config=load_campaign_cloud_config(root),
            )
            dm.ensure_session()
            player.ensure_session()
            browser.ensure_session()

            print("2/8  Creating a temporary campaign and joining as player...")
            campaign = dm.create_campaign("DID Phase 4 Dashboard Smoke Test")
            joined = player.join_campaign(campaign["invite_code"], "Smoke Player")
            if str(joined.get("id")) != str(campaign.get("id")):
                raise AssertionError("Player joined the wrong campaign")

            print("3/8  Sharing a character state and a roll...")
            character_id = f"phase4-{uuid4()}"
            state = {
                "schema_version": 1,
                "kind": "character_state",
                "generated_utc": utc_now(),
                "character_id": character_id,
                "name": "Dashboard Smoke Hero",
                "species": "Test Species",
                "level": 3,
                "resources": {
                    "hearts": {"current": 10, "max": 3},
                    "adversity_tokens": {"current": 2, "max": 8},
                    "improvement_points": {"used": 4, "total": 10, "remaining": 6},
                },
                "abilities": {
                    "agility": {"die_size": 8, "bonus": 1},
                    "strength": {"die_size": 6, "bonus": 0},
                    "finesse": {"die_size": 10, "bonus": 0},
                    "instinct": {"die_size": 6, "bonus": 0},
                    "presence": {"die_size": 4, "bonus": 0},
                    "knowledge": {"die_size": 8, "bonus": 0},
                },
                "defense_ability": "finesse",
                "improvements": [],
                "portrait": {"available": False},
            }
            linked = player.link_character(campaign["id"], state, remember=False)
            event = {
                "schema_version": 1,
                "kind": "roll_event",
                "event_id": str(uuid4()),
                "rolled_utc": utc_now(),
                "character_id": character_id,
                "character_name": "Dashboard Smoke Hero",
                "roll_type": "ability",
                "ability_name": "Finesse",
                "flat_bonus": 0,
                "dice": [
                    {
                        "label": "finesse",
                        "kind": "ability",
                        "sides": 10,
                        "sign": 1,
                        "values": [7],
                        "exploded": False,
                    }
                ],
                "deed_success": None,
                "total": 7,
                "individual_only": False,
                "groups": [],
            }
            player.upload_roll_event(linked["id"], event)
            touch_character_presence(player, linked["id"])

            print("4/8  Creating a one-time DM dashboard code...")
            access = create_dashboard_access(dm, campaign["id"])
            if not access.get("code"):
                raise AssertionError("No dashboard access code returned")

            print("5/8  Claiming dashboard access as a separate browser user...")
            claimed = browser._request_json(
                "POST",
                "/rest/v1/rpc/did_claim_dashboard",
                body={"p_dashboard_code": access["code"]},
            )
            if not isinstance(claimed, list) or not claimed:
                raise AssertionError("Browser could not claim DM dashboard access")
            if str(claimed[0].get("id")) != str(campaign["id"]):
                raise AssertionError("Dashboard claim returned the wrong campaign")
            if claimed[0].get("role") != "dm":
                raise AssertionError("Dashboard browser was not granted DM role")

            print("6/8  Verifying the dashboard can read party state and rolls...")
            chars = browser._request_json(
                "GET",
                "/rest/v1/campaign_characters",
                query={
                    "campaign_id": f"eq.{campaign['id']}",
                    "select": "id,display_name,last_seen_at",
                },
            )
            if not isinstance(chars, list) or len(chars) != 1:
                raise AssertionError("Dashboard could not read the shared character")
            if not chars[0].get("last_seen_at"):
                raise AssertionError("Presence heartbeat was not visible to the dashboard")

            states = browser._request_json(
                "GET",
                "/rest/v1/character_state",
                query={
                    "campaign_character_id": f"eq.{linked['id']}",
                    "select": "campaign_character_id,state,updated_at",
                },
            )
            if not isinstance(states, list) or not states:
                raise AssertionError("Dashboard could not read character state")
            if states[0].get("state", {}).get("name") != "Dashboard Smoke Hero":
                raise AssertionError("Dashboard state payload did not match")

            rolls = browser._request_json(
                "GET",
                "/rest/v1/campaign_rolls",
                query={
                    "campaign_character_id": f"eq.{linked['id']}",
                    "select": "event_id,rolled_at,event",
                },
            )
            if not isinstance(rolls, list) or not rolls:
                raise AssertionError("Dashboard could not read the roll")

            print("7/8  Verifying the dashboard code is single-use...")
            second_browser = CampaignCloudClient(
                app_dir=root,
                user_data_dir=temp / "browser2",
                config=load_campaign_cloud_config(root),
            )
            second_browser.ensure_session()
            reused = second_browser._request_json(
                "POST",
                "/rest/v1/rpc/did_claim_dashboard",
                body={"p_dashboard_code": access["code"]},
            )
            if isinstance(reused, list) and reused:
                raise AssertionError("A one-time dashboard code was reusable")

            print("8/8  Verifying a player cannot mint a DM dashboard code...")
            player_was_blocked = False
            try:
                create_dashboard_access(player, campaign["id"])
            except CampaignCloudError:
                player_was_blocked = True
            if not player_was_blocked:
                raise AssertionError("A player was able to create a DM dashboard code")

            print("\nPHASE 4 DM DASHBOARD SMOKE TEST: PASS")

    except Exception:
        print("\nPHASE 4 DM DASHBOARD SMOKE TEST: FAILED")
        traceback.print_exc()
        raise
    finally:
        if campaign and dm:
            try:
                dm._request_json(
                    "DELETE",
                    "/rest/v1/campaigns",
                    query={"id": f"eq.{campaign['id']}"},
                )
                print("Temporary smoke-test campaign removed.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
