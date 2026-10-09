from __future__ import annotations

import json
import tempfile
import traceback
from pathlib import Path
from uuid import uuid4

from campaign_cloud import CampaignCloudClient, CampaignCloudError


def fake_state(character_id, name):
    return {
        "schema_version": 1,
        "kind": "character_state",
        "generated_utc": "2026-10-10T00:00:00Z",
        "character_id": character_id,
        "name": name,
        "species": "Smoke Test",
        "level": 1,
        "resources": {
            "hearts": {"current": 2, "max": 3},
            "adversity_tokens": {"current": 1, "max": 3},
            "improvement_points": {"used": 0, "total": 0, "remaining": 0},
        },
        "abilities": {
            "agility": {"die_size": 8, "bonus": 1},
            "strength": {"die_size": 6, "bonus": 0},
            "finesse": {"die_size": 6, "bonus": 0},
            "instinct": {"die_size": 6, "bonus": 0},
            "presence": {"die_size": 6, "bonus": 0},
            "knowledge": {"die_size": 6, "bonus": 0},
        },
        "defense_ability": "agility",
        "improvements": [],
        "portrait": {"available": False},
    }


def fake_roll(character_id, name):
    return {
        "schema_version": 1,
        "kind": "roll_event",
        "event_id": str(uuid4()),
        "rolled_utc": "2026-10-10T00:00:01Z",
        "character_id": character_id,
        "character_name": name,
        "roll_type": "ability",
        "ability_name": "Agility",
        "flat_bonus": 1,
        "dice": [
            {
                "label": "roll",
                "kind": "die",
                "sides": 8,
                "sign": 1,
                "values": [6],
                "exploded": False,
            }
        ],
        "deed_success": None,
        "total": 7,
        "individual_only": False,
        "groups": [],
    }


def main():
    app_dir = Path.cwd()
    cleanup_campaign_id = None
    dm = None

    with tempfile.TemporaryDirectory(prefix="did_phase2_smoke_") as temporary:
        root = Path(temporary)
        try:
            print("1/7  Creating two anonymous Supabase users...")
            dm = CampaignCloudClient(app_dir=app_dir, user_data_dir=root / "dm")
            player = CampaignCloudClient(app_dir=app_dir, user_data_dir=root / "player")
            dm_session = dm.ensure_session()
            player_session = player.ensure_session()
            assert dm_session.get("user_id")
            assert player_session.get("user_id")
            assert dm_session["user_id"] != player_session["user_id"]

            print("2/7  Creating a temporary campaign as DM...")
            campaign = dm.create_campaign("DID Phase 2 Smoke Test")
            cleanup_campaign_id = campaign["id"]
            invite_code = campaign["invite_code"]
            assert invite_code

            print("3/7  Joining that campaign as a second player...")
            joined = player.join_campaign(invite_code, "Smoke Player")
            assert joined["id"] == campaign["id"]
            assert joined["role"] == "player"

            print("4/7  Linking a character and uploading its safe state...")
            character_id = "smoke-" + uuid4().hex
            state = fake_state(character_id, "Smoke Hero")
            linked = player.link_character(campaign["id"], state, remember=False)
            assert linked["campaign_id"] == campaign["id"]

            print("5/7  Uploading a structured roll event...")
            event = fake_roll(character_id, "Smoke Hero")
            uploaded = player.upload_roll_event(linked["id"], event)
            assert uploaded["event_id"] == event["event_id"]

            print("6/7  Verifying the DM can read the player's live data...")
            characters = dm.list_campaign_characters(campaign["id"])
            assert any(row.get("id") == linked["id"] for row in characters), characters
            rolls = dm.list_recent_rolls(campaign["id"], limit=20)
            assert any(row.get("event_id") == event["event_id"] for row in rolls), rolls

            print("7/7  Verifying the player cannot see the DM's campaign roster as DM data...")
            # Player can see their own linked character, but RLS must not grant DM-wide
            # access. With only one player character in this smoke campaign, the
            # visible list should contain exactly that character.
            player_characters = player.list_campaign_characters(campaign["id"])
            visible_ids = {row.get("id") for row in player_characters}
            assert visible_ids == {linked["id"]}, visible_ids

            print("\nPHASE 2 SUPABASE SMOKE TEST: PASS")
            print("Campaign creation, join, character state, roll upload and DM read all work.")

        except Exception:
            print("\nPHASE 2 SUPABASE SMOKE TEST: FAILED")
            traceback.print_exc()
            raise

        finally:
            if dm is not None and cleanup_campaign_id:
                try:
                    dm._request_json(
                        "DELETE",
                        "/rest/v1/campaigns",
                        query={"id": f"eq.{cleanup_campaign_id}"},
                        prefer="return=minimal",
                    )
                    print("Temporary smoke-test campaign removed.")
                except CampaignCloudError as error:
                    print(f"Warning: could not remove temporary campaign: {error}")


if __name__ == "__main__":
    main()
