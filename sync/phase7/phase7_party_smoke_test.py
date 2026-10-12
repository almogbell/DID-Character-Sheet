from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from campaign_cloud import CampaignCloudClient, load_campaign_cloud_config
from campaign_party import upload_party_state
from campaign_party_bridge import create_party_dashboard_access
from campaign_session import CampaignSessionService


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _client(app_dir, config, folder):
    return CampaignCloudClient(
        app_dir=app_dir,
        user_data_dir=folder,
        config=config,
        timeout=20,
    )


def _get(client, path, **query):
    result = client._request_json("GET", path, query=query)
    return result if isinstance(result, list) else []


def main():
    app_dir = Path(__file__).resolve().parent
    config = load_campaign_cloud_config(app_dir)
    campaign_id = None

    # This smoke test deliberately uses only two temporary anonymous users:
    # one DM and one player. The player also exercises the Party Dashboard
    # pairing RPC, so repeated test runs do not create a third browser user.
    with tempfile.TemporaryDirectory(prefix="did_phase7_dm_") as dm_dir, tempfile.TemporaryDirectory(
        prefix="did_phase7_player_"
    ) as player_dir:
        dm = _client(app_dir, config, dm_dir)
        player = _client(app_dir, config, player_dir)

        try:
            print("1/10 Creating DM and player anonymous sessions...")
            dm.ensure_session()
            player.ensure_session()

            print("2/10 DM creates campaign; player joins...")
            campaign = dm.create_campaign("Phase 7 Party Smoke")
            campaign_id = str(campaign["id"])
            joined = player.join_campaign(campaign["invite_code"], "Smoke Player")
            assert str(joined["id"]) == campaign_id
            assert joined.get("role") == "player"

            print("3/10 Player links a character and publishes party-safe state...")
            character_id = str(uuid4())
            shared_state = {
                "schema_version": 1,
                "kind": "character_state",
                "character_id": character_id,
                "name": "Phase 7 Smoke Hero",
                "species": "Human",
                "level": 3,
                "resources": {
                    "hearts": {"current": 4, "max": 4},
                    "adversity_tokens": {"current": 2, "max": 6},
                    "improvement_points": {"used": 0, "total": 0, "remaining": 0},
                },
                "abilities": {
                    "agility": {"die_size": 8, "bonus": 0},
                    "strength": {"die_size": 10, "bonus": 1},
                    "finesse": {"die_size": 6, "bonus": 0},
                    "instinct": {"die_size": 4, "bonus": 0},
                    "presence": {"die_size": 8, "bonus": 0},
                    "knowledge": {"die_size": 6, "bonus": 0},
                },
                "defense_ability": "agility",
                "improvements": [],
                "portrait": {"available": False},
            }
            linked = player.link_character(campaign_id, shared_state, remember=False)
            campaign_character_id = str(linked["id"])
            party_state = {
                "schema_version": 1,
                "kind": "party_character_state",
                "character_id": character_id,
                "name": "Phase 7 Smoke Hero",
                "species": "Human",
                "level": 3,
                "sharing": {
                    "hp": True,
                    "at": True,
                    "abilities": True,
                    "improvements": False,
                    "portrait": False,
                    "inventory": False,
                    "notes": False,
                },
                "hp": {"current": 16, "max": 16},
                "at": {"current": 2, "max": 6},
                "abilities": shared_state["abilities"],
                "portrait": {"shared": False},
            }
            upload_party_state(player, campaign_id, campaign_character_id, party_state)

            print("4/10 Player exercises Party Dashboard pairing and reads shared state...")
            access = create_party_dashboard_access(player, campaign_id)
            claim = player._request_json(
                "POST",
                "/rest/v1/rpc/did_claim_party_dashboard",
                body={"p_dashboard_code": access["code"]},
            )
            assert isinstance(claim, list) and claim
            assert str(claim[0]["id"]) == campaign_id
            assert claim[0]["role"] == "player"
            party_rows = _get(
                player,
                "/rest/v1/party_character_state",
                campaign_id=f"eq.{campaign_id}",
                select="campaign_character_id,campaign_id,state,updated_at",
            )
            assert len(party_rows) == 1
            assert party_rows[0]["state"]["name"] == "Phase 7 Smoke Hero"
            assert "inventory" not in party_rows[0]["state"]

            print("5/10 DM starts a live session...")
            dm_sessions = CampaignSessionService(dm)
            player_sessions = CampaignSessionService(player)
            started = dm_sessions.start_session(campaign_id)
            session_id = str(started["id"])
            visible_active = player_sessions.active_session(campaign_id)
            assert visible_active and str(visible_active["id"]) == session_id

            print("6/10 Player shares a roll; Party feed receives it...")
            player_sessions.set_roll_sharing(campaign_character_id, True)
            first_event_id = str(uuid4())
            first_event = {
                "schema_version": 1,
                "kind": "roll_event",
                "event_id": first_event_id,
                "rolled_utc": _utc_now(),
                "character_id": character_id,
                "character_name": "Phase 7 Smoke Hero",
                "roll_type": "ability",
                "ability_name": "Agility",
                "flat_bonus": 0,
                "dice": [
                    {
                        "label": "Agility",
                        "kind": "ability",
                        "sides": 8,
                        "sign": 1,
                        "values": [6],
                        "exploded": False,
                    }
                ],
                "deed_success": None,
                "total": 6,
                "individual_only": False,
                "groups": [],
            }
            player.upload_roll_event(campaign_character_id, first_event)
            party_rolls = _get(
                player,
                "/rest/v1/party_session_rolls",
                campaign_id=f"eq.{campaign_id}",
                session_id=f"eq.{session_id}",
                select="event_id,campaign_id,session_id,campaign_character_id,rolled_at,event",
                order="rolled_at.desc",
            )
            assert any(str(row["event_id"]) == first_event_id for row in party_rolls)

            print("7/10 Player disables roll sharing; next roll stays private...")
            player_sessions.set_roll_sharing(campaign_character_id, False)
            second_event_id = str(uuid4())
            second_event = dict(first_event)
            second_event["event_id"] = second_event_id
            second_event["rolled_utc"] = _utc_now()
            second_event["total"] = 4
            second_event["dice"] = [dict(first_event["dice"][0], values=[4])]
            player.upload_roll_event(campaign_character_id, second_event)
            party_rolls_after = _get(
                player,
                "/rest/v1/party_session_rolls",
                campaign_id=f"eq.{campaign_id}",
                session_id=f"eq.{session_id}",
                select="event_id",
            )
            assert not any(str(row["event_id"]) == second_event_id for row in party_rolls_after)

            print("8/10 DM ends the session; player sees no active session...")
            dm_sessions.end_session(campaign_id)
            assert player_sessions.active_session(campaign_id) is None

            print("9/10 DM removes the character; party state disappears...")
            removed = dm._request_json(
                "POST",
                "/rest/v1/rpc/did_remove_campaign_character",
                body={"p_campaign_character_id": campaign_character_id},
            )
            assert removed is True
            remaining_party = _get(
                player,
                "/rest/v1/party_character_state",
                campaign_id=f"eq.{campaign_id}",
                select="campaign_character_id",
            )
            assert not remaining_party

            print("10/10 End-to-end Phase 7 checks complete.")
            print("PHASE 7 PARTY DASHBOARD SMOKE TEST: PASS")

        finally:
            if campaign_id:
                try:
                    dm._request_json(
                        "DELETE",
                        "/rest/v1/campaigns",
                        query={"id": f"eq.{campaign_id}"},
                    )
                    print("Temporary smoke-test campaign removed.")
                except Exception as cleanup_error:
                    print(f"Cleanup warning: {cleanup_error}")


if __name__ == "__main__":
    main()
