from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

from campaign_cloud import CampaignCloudClient
from campaign_privacy import build_shared_character_state_with_preferences


STAT_NAMES = ("agility", "strength", "finesse", "instinct", "presence", "knowledge")


def sample_character_dict():
    return {
        "id": "phase6-smoke-character",
        "name": "Privacy Test Character",
        "species_name": "Human",
        "backstory": "PHASE6_SECRET_BACKSTORY",
        "stats": {
            name: {"die_size": 6, "bonus": 0}
            for name in STAT_NAMES
        },
        "HP": {"current_HP": 8, "max_hearts": 3, "max_HP": 12},
        "Adversity": {"current_AT": 2, "max_AT": 6},
        "progression": {"current_IP": 5, "used_IP": 1, "level": 2},
        "selected_defense_stat_name": "agility",
        "improvements": {
            "list_of_taken_improvements": [
                {"id": "imp-1", "catalog_id": "sturdy", "name": "Sturdy", "times_taken": 1}
            ]
        },
        "inventory": {
            "list_of_items": [
                {"id": "share-item", "name": "Rope", "description": "Shared rope", "quantity": 1},
                {"id": "private-item", "name": "Private Token", "description": "PHASE6_PRIVATE_ITEM", "quantity": 1},
            ]
        },
        "notes": {
            "list_of_notes": [
                {"id": "share-note", "title": "Shared clue", "text": "Shared note text", "color": "yellow", "pinned": False},
                {"id": "private-note", "title": "Private clue", "text": "PHASE6_PRIVATE_NOTE", "color": "red", "pinned": False},
            ]
        },
        "image": {"images": [], "current_index": 0},
    }


def read_state(client, campaign_character_id):
    rows = client._request_json(
        "GET",
        "/rest/v1/character_state",
        query={
            "campaign_character_id": f"eq.{campaign_character_id}",
            "select": "state,updated_at",
            "limit": "1",
        },
    )
    if not isinstance(rows, list) or not rows:
        raise AssertionError("DM could not read the character state")
    state = rows[0].get("state")
    if not isinstance(state, dict):
        raise AssertionError("Character state was not a JSON object")
    return state


def main():
    root = Path(__file__).resolve().parent
    campaign = None
    dm = None

    with tempfile.TemporaryDirectory() as dm_dir, tempfile.TemporaryDirectory() as player_dir:
        try:
            print("1/6  Creating temporary DM and player identities...")
            dm = CampaignCloudClient(app_dir=root, user_data_dir=Path(dm_dir))
            player = CampaignCloudClient(app_dir=root, user_data_dir=Path(player_dir))
            dm.ensure_session()
            player.ensure_session()

            print("2/6  Creating and joining a temporary campaign...")
            campaign = dm.create_campaign("Phase 6 Privacy Smoke Test")
            player.join_campaign(campaign["invite_code"], "Privacy Player")

            print("3/6  Uploading a state with only explicitly selected private categories...")
            state = build_shared_character_state_with_preferences(
                sample_character_dict(),
                {
                    "share_improvements": True,
                    "share_backstory": True,
                    "share_inventory": True,
                    "inventory_item_ids": ["share-item"],
                    "share_notes": True,
                    "note_ids": ["share-note"],
                    "share_portrait": False,
                },
            )
            linked = player.link_character(campaign["id"], state, remember=False)

            print("4/6  Verifying the DM sees only the selected values...")
            seen = read_state(dm, linked["id"])
            text = str(seen)
            assert seen.get("backstory") == "PHASE6_SECRET_BACKSTORY"
            assert [item.get("id") for item in seen.get("inventory", [])] == ["share-item"]
            assert [note.get("id") for note in seen.get("notes", [])] == ["share-note"]
            assert "PHASE6_PRIVATE_ITEM" not in text
            assert "PHASE6_PRIVATE_NOTE" not in text
            assert seen.get("portrait", {}).get("shared") is False

            print("5/6  Turning all optional categories off and replacing cloud state...")
            hidden = build_shared_character_state_with_preferences(
                sample_character_dict(),
                {
                    "share_improvements": False,
                    "share_backstory": False,
                    "share_inventory": False,
                    "share_notes": False,
                    "share_portrait": False,
                },
            )
            player.upload_character_state(linked["id"], hidden)
            seen_hidden = read_state(dm, linked["id"])
            assert "backstory" not in seen_hidden
            assert "inventory" not in seen_hidden
            assert "notes" not in seen_hidden
            assert "improvements" not in seen_hidden
            assert seen_hidden.get("sharing", {}).get("core") is True

            print("6/6  Core tactical data remains visible...")
            assert seen_hidden.get("name") == "Privacy Test Character"
            assert seen_hidden.get("resources", {}).get("hearts", {}).get("current") == 8
            assert "abilities" in seen_hidden

            print("\nPHASE 6 PRIVACY & SHARING SMOKE TEST: PASS")

        except Exception:
            print("\nPHASE 6 PRIVACY & SHARING SMOKE TEST: FAILED")
            traceback.print_exc()
            raise
        finally:
            if dm is not None and campaign is not None:
                try:
                    dm._request_json(
                        "DELETE",
                        "/rest/v1/campaigns",
                        query={"id": f"eq.{campaign['id']}"},
                        prefer="return=minimal",
                    )
                    print("Temporary privacy-test campaign removed.")
                except Exception:
                    print("WARNING: temporary privacy-test campaign could not be removed automatically.")


if __name__ == "__main__":
    main()
