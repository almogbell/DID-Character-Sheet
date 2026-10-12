from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

from campaign_cloud import CampaignCloudClient, CampaignCloudError, load_campaign_cloud_config


def _client(app_dir, config, folder):
    return CampaignCloudClient(app_dir=app_dir, user_data_dir=folder, config=config, timeout=20)


def _get(client, table, **query):
    rows = client._request_json("GET", f"/rest/v1/{table}", query=query)
    return rows if isinstance(rows, list) else []


def _insert(client, table, payload):
    rows = client._request_json(
        "POST",
        f"/rest/v1/{table}",
        query={"select": "*"},
        body=payload,
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"No row returned from {table}")
    return rows[0]


def main():
    app_dir = Path(__file__).resolve().parent
    config = load_campaign_cloud_config(app_dir)
    campaign_id = None

    with tempfile.TemporaryDirectory(prefix="did_phase8_dm_") as dm_dir, tempfile.TemporaryDirectory(prefix="did_phase8_player_") as player_dir:
        dm = _client(app_dir, config, dm_dir)
        player = _client(app_dir, config, player_dir)

        try:
            print("1/9 Creating DM and player sessions...")
            dm.ensure_session()
            player.ensure_session()

            print("2/9 Creating campaign and player character...")
            campaign = dm.create_campaign("Phase 8 Smoke")
            campaign_id = str(campaign["id"])
            player.join_campaign(campaign["invite_code"], "Phase 8 Player")

            character_id = str(uuid4())
            shared_state = {
                "schema_version": 1,
                "kind": "character_state",
                "character_id": character_id,
                "name": "Phase 8 Hero",
                "species": "Human",
                "level": 2,
                "resources": {
                    "hearts": {"current": 4, "max": 4},
                    "adversity_tokens": {"current": 1, "max": 6},
                    "improvement_points": {"used": 0, "total": 0, "remaining": 0},
                },
                "abilities": {},
                "defense_ability": "",
                "improvements": [],
                "portrait": {"available": False},
            }
            linked = player.link_character(campaign_id, shared_state, remember=False)
            campaign_character_id = str(linked["id"])

            print("3/9 DM creates private note and NPC...")
            note = _insert(dm, "campaign_dm_notes", {
                "campaign_id": campaign_id,
                "title": "Hidden Plan",
                "body": "Only the DM should ever see this.",
            })
            npc = _insert(dm, "campaign_npcs", {
                "campaign_id": campaign_id,
                "name": "Captain Ash",
                "status": "Suspicious",
                "description": "Harbor captain",
                "gm_notes": "Secretly works for the rival house.",
                "visible_to_players": False,
            })
            assert note["title"] == "Hidden Plan"
            assert npc["name"] == "Captain Ash"

            print("4/9 DM records NPC relationship...")
            relation = _insert(dm, "campaign_npc_relationships", {
                "campaign_id": campaign_id,
                "npc_id": npc["id"],
                "target_kind": "character",
                "target_campaign_character_id": campaign_character_id,
                "relationship": "Owes a favor to",
                "notes": "Player does not know yet.",
                "visible_to_players": False,
            })
            assert relation["relationship"] == "Owes a favor to"

            print("5/9 DM creates private secret and visible clue...")
            _insert(dm, "campaign_entries", {
                "campaign_id": campaign_id,
                "entry_type": "secret",
                "title": "The real murderer",
                "body": "Private DM information",
                "visible_to_players": False,
            })
            clue = _insert(dm, "campaign_entries", {
                "campaign_id": campaign_id,
                "entry_type": "clue",
                "title": "Broken signet",
                "body": "Found beside the warehouse door.",
                "visible_to_players": True,
            })
            assert clue["visible_to_players"] is True

            print("6/9 DM creates player-visible character effect...")
            effect = _insert(dm, "campaign_character_effects", {
                "campaign_id": campaign_id,
                "campaign_character_id": campaign_character_id,
                "name": "Marked by the Moon",
                "description": "The mark glows near hidden doors.",
                "status": "active",
                "visible_to_player": True,
            })
            assert effect["visible_to_player"] is True

            print("7/9 Player sees only explicitly revealed campaign information...")
            assert _get(player, "campaign_dm_notes", campaign_id=f"eq.{campaign_id}", select="id") == []
            assert _get(player, "campaign_npcs", campaign_id=f"eq.{campaign_id}", select="id") == []
            player_entries = _get(player, "campaign_entries", campaign_id=f"eq.{campaign_id}", select="title,entry_type,visible_to_players")
            assert [row["title"] for row in player_entries] == ["Broken signet"]
            player_effects = _get(player, "campaign_character_effects", campaign_id=f"eq.{campaign_id}", select="name,campaign_character_id,visible_to_player")
            assert len(player_effects) == 1 and player_effects[0]["name"] == "Marked by the Moon"

            print("8/9 Player cannot write DM campaign-layer data...")
            blocked = False
            try:
                _insert(player, "campaign_dm_notes", {
                    "campaign_id": campaign_id,
                    "title": "Should fail",
                    "body": "No player writes here",
                })
            except CampaignCloudError:
                blocked = True
            assert blocked, "Player unexpectedly wrote a DM note"

            print("9/9 DM can reveal NPC without changing the character file...")
            dm._request_json(
                "PATCH",
                "/rest/v1/campaign_npcs",
                query={"id": f"eq.{npc['id']}"},
                body={"visible_to_players": True},
                prefer="return=minimal",
            )
            revealed = _get(player, "campaign_npcs", campaign_id=f"eq.{campaign_id}", select="name,visible_to_players")
            assert len(revealed) == 1 and revealed[0]["name"] == "Captain Ash"

            print("PHASE 8 CLOUD SMOKE TEST: PASS")

        finally:
            if campaign_id:
                try:
                    dm._request_json("DELETE", "/rest/v1/campaigns", query={"id": f"eq.{campaign_id}"})
                    print("Temporary Phase 8 campaign removed.")
                except Exception as error:
                    print(f"Cleanup warning: {error}")


if __name__ == "__main__":
    main()
