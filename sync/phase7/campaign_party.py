from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from backend_2_1 import CharacterStorageSystem
from campaign_privacy import (
    _portrait_payload,
    _safe_improvements,
    _safe_inventory,
    _safe_notes,
)
from campaign_shared import build_shared_character_state_from_dict


PARTY_PRIVACY_FILENAME = "campaign_party_privacy.json"
PARTY_PRIVACY_SCHEMA_VERSION = 1
PARTY_STATE_SCHEMA_VERSION = 1

# Party sharing is deliberately opt-in.  Character identity is visible once a
# character is on the Party Dashboard; every gameplay/detail category below is
# controlled by the player.
DEFAULT_PARTY_PRIVACY = {
    "schema_version": PARTY_PRIVACY_SCHEMA_VERSION,
    "share_hp": False,
    "share_at": False,
    "share_abilities": False,
    "share_improvements": False,
    "share_portrait": False,
    "share_inventory": False,
    "inventory_item_ids": [],
    "share_notes": False,
    "note_ids": [],
}


def _default_user_data_dir():
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "DID Character Sheet"
    return Path.home() / ".did_character_sheet"


def _read_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return copy.deepcopy(default)


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def _clean_id_list(value):
    if not isinstance(value, (list, tuple, set)):
        return []
    result = []
    seen = set()
    for raw in value:
        text = str(raw or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def normalize_party_preferences(value=None):
    result = copy.deepcopy(DEFAULT_PARTY_PRIVACY)
    if isinstance(value, dict):
        for key in (
            "share_hp",
            "share_at",
            "share_abilities",
            "share_improvements",
            "share_portrait",
            "share_inventory",
            "share_notes",
        ):
            if key in value:
                result[key] = bool(value[key])
        result["inventory_item_ids"] = _clean_id_list(
            value.get("inventory_item_ids", [])
        )
        result["note_ids"] = _clean_id_list(value.get("note_ids", []))
    result["schema_version"] = PARTY_PRIVACY_SCHEMA_VERSION
    return result


class PartyPrivacyStore:
    def __init__(self, user_data_dir=None):
        self.user_data_dir = Path(user_data_dir or _default_user_data_dir())
        self.path = self.user_data_dir / PARTY_PRIVACY_FILENAME

    @staticmethod
    def _key(campaign_id, character_id):
        campaign_id = str(campaign_id or "").strip()
        character_id = str(character_id or "").strip()
        if not campaign_id or not character_id:
            return ""
        return f"{campaign_id}:{character_id}"

    def _all(self):
        raw = _read_json(self.path, {"entries": {}})
        if not isinstance(raw, dict):
            return {}
        entries = raw.get("entries", {})
        return entries if isinstance(entries, dict) else {}

    def get(self, campaign_id, character_id):
        key = self._key(campaign_id, character_id)
        if not key:
            return normalize_party_preferences()
        return normalize_party_preferences(self._all().get(key))

    def set(self, campaign_id, character_id, preferences):
        key = self._key(campaign_id, character_id)
        if not key:
            raise ValueError("Campaign ID and character ID are required")
        entries = self._all()
        clean = normalize_party_preferences(preferences)
        entries[key] = clean
        _write_json(
            self.path,
            {
                "schema_version": PARTY_PRIVACY_SCHEMA_VERSION,
                "entries": entries,
            },
        )
        return copy.deepcopy(clean)


def party_privacy_store_for_window(window):
    existing = getattr(window, "_campaign_party_privacy_store", None)
    if isinstance(existing, PartyPrivacyStore):
        return existing
    client = getattr(window, "_campaign_cloud_client", None)
    user_data_dir = getattr(client, "user_data_dir", None)
    store = PartyPrivacyStore(user_data_dir=user_data_dir)
    window._campaign_party_privacy_store = store
    return store


def build_party_character_state_with_preferences(character_or_dict, preferences=None):
    prefs = normalize_party_preferences(preferences)
    if isinstance(character_or_dict, dict):
        data = copy.deepcopy(character_or_dict)
    else:
        data = CharacterStorageSystem.character_to_dict(character_or_dict)

    core = build_shared_character_state_from_dict(data)
    resources = core.get("resources", {}) if isinstance(core, dict) else {}
    hearts = resources.get("hearts", {}) if isinstance(resources, dict) else {}
    at = resources.get("adversity_tokens", {}) if isinstance(resources, dict) else {}

    try:
        current_hp = max(0, int(hearts.get("current") or 0))
    except (TypeError, ValueError, OverflowError):
        current_hp = 0
    try:
        max_hp = max(0, int(hearts.get("max") or 0) * 4)
    except (TypeError, ValueError, OverflowError):
        max_hp = 0
    try:
        current_at = max(0, int(at.get("current") or 0))
    except (TypeError, ValueError, OverflowError):
        current_at = 0
    try:
        max_at = max(0, int(at.get("max") or 0))
    except (TypeError, ValueError, OverflowError):
        max_at = 0

    state = {
        "schema_version": PARTY_STATE_SCHEMA_VERSION,
        "kind": "party_character_state",
        "character_id": str(core.get("character_id") or ""),
        "name": str(core.get("name") or "Unnamed Character"),
        "species": str(core.get("species") or ""),
        "level": int(core.get("level") or 1),
        "sharing": {
            "hp": bool(prefs["share_hp"]),
            "at": bool(prefs["share_at"]),
            "abilities": bool(prefs["share_abilities"]),
            "improvements": bool(prefs["share_improvements"]),
            "portrait": bool(prefs["share_portrait"]),
            "inventory": bool(prefs["share_inventory"]),
            "notes": bool(prefs["share_notes"]),
        },
    }

    if prefs["share_hp"]:
        state["hp"] = {"current": current_hp, "max": max_hp}
    if prefs["share_at"]:
        state["at"] = {"current": current_at, "max": max_at}
    if prefs["share_abilities"]:
        abilities = core.get("abilities", {})
        state["abilities"] = abilities if isinstance(abilities, dict) else {}
    if prefs["share_improvements"]:
        state["improvements"] = _safe_improvements(data)

    state["portrait"] = _portrait_payload(data, prefs["share_portrait"])

    if prefs["share_inventory"]:
        state["inventory"] = _safe_inventory(data, prefs["inventory_item_ids"])
    if prefs["share_notes"]:
        state["notes"] = _safe_notes(data, prefs["note_ids"])

    return state


def build_window_party_state(window, campaign_id=None, link=None):
    character = getattr(window, "character", None)
    if character is None:
        raise ValueError("No active character")

    character_id = str(getattr(character, "id", "") or "").strip()
    if not character_id:
        raise ValueError("Character has no stable ID")

    if not isinstance(link, dict):
        client = getattr(window, "_campaign_cloud_client", None)
        if client is not None:
            try:
                link = client.get_character_link(character_id)
            except Exception:
                link = None

    resolved_campaign_id = str(campaign_id or "").strip()
    if not resolved_campaign_id and isinstance(link, dict):
        resolved_campaign_id = str(link.get("campaign_id") or "").strip()

    store = party_privacy_store_for_window(window)
    prefs = store.get(resolved_campaign_id, character_id)
    return build_party_character_state_with_preferences(character, prefs)


def upload_party_state(client, campaign_id, campaign_character_id, state):
    rows = client._request_json(
        "POST",
        "/rest/v1/party_character_state",
        query={
            "on_conflict": "campaign_character_id",
            "select": "campaign_character_id,campaign_id,updated_at",
        },
        body={
            "campaign_character_id": str(campaign_character_id),
            "campaign_id": str(campaign_id),
            "state": state,
        },
        prefer="resolution=merge-duplicates,return=representation",
    )
    return rows[0] if isinstance(rows, list) and rows else None


def party_sharing_summary(preferences):
    prefs = normalize_party_preferences(preferences)
    labels = []
    for key, label in (
        ("share_hp", "HP"),
        ("share_at", "AT"),
        ("share_abilities", "Abilities"),
        ("share_improvements", "Improvements"),
        ("share_portrait", "Portrait"),
    ):
        if prefs[key]:
            labels.append(label)
    if prefs["share_inventory"]:
        labels.append(f"Inventory ({len(prefs['inventory_item_ids'])})")
    if prefs["share_notes"]:
        labels.append(f"Notes ({len(prefs['note_ids'])})")
    return "Party: " + (", ".join(labels) if labels else "name only")
