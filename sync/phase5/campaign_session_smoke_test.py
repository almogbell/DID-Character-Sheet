from __future__ import annotations

import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from campaign_cloud import CampaignCloudClient, CampaignCloudError
from campaign_session import CampaignSessionService


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_state(character_id, name="Session Hero", hp=8):
    abilities = {
        key: {"die_size": 6, "bonus": 0}
        for key in ("agility", "strength", "finesse", "instinct", "presence", "knowledge")
    }
    return {
        "schema_version": 1,
        "kind": "character_state",
        "generated_utc": utc_now(),
        "character_id": character_id,
        "name": name,
        "species": "Human",
        "level": 1,
        "resources": {
            "hearts": {"current": hp, "max": 2},
            "adversity_tokens": {"current": 0, "max": 3},
            "improvement_points": {"used": 0, "total": 5, "remaining": 5},
        },
        "abilities": abilities,
        "defense_ability": "agility",
        "improvements": [],
        "portrait": {"available": False},
    }


def make_roll(character_id, name, total=7):
    return {
        "schema_version": 1,
        "kind": "roll_event",
        "event_id": str(uuid4()),
        "rolled_utc": utc_now(),
        "character_id": character_id,
        "character_name": name,
        "roll_type": "ability",
        "ability_name": "Agility",
        "flat_bonus": 1,
        "dice": [
            {
                "label": "base",
                "kind": "base",
                "sides": 6,
                "sign": 1,
                "values": [total - 1],
                "exploded": False,
            }
        ],
        "deed_success": None,
        "total": total,
        "individual_only": False,
        "groups": [],
    }


def rows_for_event(client, event_id):
    rows = client._request_json(
        "GET",
        "/rest/v1/campaign_rolls",
        query={
            "event_id": f"eq.{event_id}",
            "select": "event_id,campaign_character_id,session_id,rolled_at,event",
        },
    )
    return rows if isinstance(rows, list) else []


def main():
    root = Path(__file__).resolve().parent
    campaign = None

    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        dm = CampaignCloudClient(app_dir=root, user_data_dir=temp / "dm")
        player = CampaignCloudClient(app_dir=root, user_data_dir=temp / "player")

        try:
            print("1/10 Creating separate DM and player users...")
            dm.ensure_session()
            player.ensure_session()
            assert dm.user_id and player.user_id and dm.user_id != player.user_id

            print("2/10 Creating campaign and joining as player...")
            campaign = dm.create_campaign("DID Phase 5 Session Smoke Test")
            player.join_campaign(campaign["invite_code"], "Smoke Player")

            print("3/10 Linking character and uploading starting state...")
            character_id = str(uuid4())
            character_name = "Session Hero"
            start_state = make_state(character_id, character_name, hp=8)
            linked = player.link_character(campaign["id"], start_state, remember=False)
            campaign_character_id = linked["id"]

            dm_sessions = CampaignSessionService(dm)
            player_sessions = CampaignSessionService(player)

            print("4/10 Starting Session 1 as DM...")
            started = dm_sessions.start_session(campaign["id"])
            assert int(started["session_number"]) == 1
            assert int(started["snapshot_count"]) >= 1
            session_id = started["id"]

            start_snapshots = dm_sessions.list_snapshots(session_id)
            start_rows = [row for row in start_snapshots if row.get("snapshot_kind") == "start"]
            assert len(start_rows) >= 1
            own_start = next(row for row in start_rows if row.get("campaign_character_id") == campaign_character_id)
            assert own_start["state"]["resources"]["hearts"]["current"] == 8

            print("5/10 Verifying a shared roll is attached to the active session...")
            first_roll = make_roll(character_id, character_name, total=6)
            player.upload_roll_event(campaign_character_id, first_roll)
            stored_first = rows_for_event(dm, first_roll["event_id"])
            assert len(stored_first) == 1
            assert stored_first[0]["session_id"] == session_id

            print("6/10 Turning session roll sharing off and verifying privacy...")
            player_sessions.set_roll_sharing(campaign_character_id, False)
            assert player_sessions.get_roll_sharing(campaign_character_id) is False
            private_roll = make_roll(character_id, character_name, total=5)
            player.upload_roll_event(campaign_character_id, private_roll)
            assert rows_for_event(dm, private_roll["event_id"]) == []

            print("7/10 Updating character state and ending the session...")
            end_state = make_state(character_id, character_name, hp=4)
            player.upload_character_state(campaign_character_id, end_state)
            ended = dm_sessions.end_session(campaign["id"])
            assert ended["id"] == session_id
            assert ended["ended_at"]
            assert int(ended["snapshot_count"]) >= 1

            snapshots = dm_sessions.list_snapshots(session_id)
            own_end = next(
                row for row in snapshots
                if row.get("snapshot_kind") == "end"
                and row.get("campaign_character_id") == campaign_character_id
            )
            assert own_end["state"]["resources"]["hearts"]["current"] == 4

            print("8/10 Verifying the ended session and rolls remain archived...")
            sessions = dm_sessions.list_sessions(campaign["id"])
            archived = next(row for row in sessions if row["id"] == session_id)
            assert archived["ended_at"]
            stored_first = rows_for_event(dm, first_roll["event_id"])
            assert len(stored_first) == 1 and stored_first[0]["session_id"] == session_id

            print("9/10 Verifying players cannot start DM sessions...")
            denied = False
            try:
                player_sessions.start_session(campaign["id"])
            except CampaignCloudError:
                denied = True
            assert denied, "Player unexpectedly started a DM session"

            print("10/10 Re-enabling rolls and verifying Session 2 numbering...")
            player_sessions.set_roll_sharing(campaign_character_id, True)
            second = dm_sessions.start_session(campaign["id"])
            assert int(second["session_number"]) == 2
            dm_sessions.end_session(campaign["id"])

            print("\nPHASE 5 SESSION MODE SMOKE TEST: PASS")

        except Exception:
            print("\nPHASE 5 SESSION MODE SMOKE TEST: FAILED")
            traceback.print_exc()
            raise
        finally:
            if campaign:
                try:
                    dm._request_json(
                        "DELETE",
                        "/rest/v1/campaigns",
                        query={"id": f"eq.{campaign['id']}"},
                        prefer="return=minimal",
                    )
                    print("Temporary smoke-test campaign removed.")
                except Exception:
                    pass


if __name__ == "__main__":
    main()
