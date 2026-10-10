from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from backend_2_1 import CharacterStorageSystem
from campaign_shared import build_shared_character_state_from_dict


PRIVACY_FILENAME = "campaign_privacy.json"
PRIVACY_SCHEMA_VERSION = 1
MAX_PORTRAIT_CHARS = 3_000_000

DEFAULT_PRIVACY = {
    "schema_version": PRIVACY_SCHEMA_VERSION,
    # Improvements were already shared before Phase 6, so keep that behavior
    # unless the player explicitly turns it off.
    "share_improvements": True,
    "share_portrait": False,
    "share_backstory": False,
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
    except FileNotFoundError:
        return copy.deepcopy(default)
    except (OSError, json.JSONDecodeError):
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
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def normalize_privacy_preferences(value=None):
    result = copy.deepcopy(DEFAULT_PRIVACY)
    if isinstance(value, dict):
        for key in (
            "share_improvements",
            "share_portrait",
            "share_backstory",
            "share_inventory",
            "share_notes",
        ):
            if key in value:
                result[key] = bool(value[key])
        result["inventory_item_ids"] = _clean_id_list(
            value.get("inventory_item_ids", [])
        )
        result["note_ids"] = _clean_id_list(value.get("note_ids", []))
    result["schema_version"] = PRIVACY_SCHEMA_VERSION
    return result


class CampaignPrivacyStore:
    """Local-only sharing choices, keyed by campaign + stable character ID.

    These preferences intentionally do not become part of the .didchar file.
    Turning a category off causes the next state upload to omit that category,
    which also removes previously shared values from the cloud JSON state.
    """

    def __init__(self, user_data_dir=None):
        self.user_data_dir = Path(user_data_dir or _default_user_data_dir())
        self.path = self.user_data_dir / PRIVACY_FILENAME

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
            return normalize_privacy_preferences()
        return normalize_privacy_preferences(self._all().get(key))

    def set(self, campaign_id, character_id, preferences):
        key = self._key(campaign_id, character_id)
        if not key:
            raise ValueError("Campaign ID and character ID are required")
        entries = self._all()
        clean = normalize_privacy_preferences(preferences)
        entries[key] = clean
        _write_json(
            self.path,
            {
                "schema_version": PRIVACY_SCHEMA_VERSION,
                "entries": entries,
            },
        )
        return copy.deepcopy(clean)

    def remove(self, campaign_id, character_id):
        key = self._key(campaign_id, character_id)
        if not key:
            return False
        entries = self._all()
        removed = entries.pop(key, None) is not None
        _write_json(
            self.path,
            {
                "schema_version": PRIVACY_SCHEMA_VERSION,
                "entries": entries,
            },
        )
        return removed


def privacy_store_for_window(window):
    existing = getattr(window, "_campaign_privacy_store", None)
    if isinstance(existing, CampaignPrivacyStore):
        return existing

    client = getattr(window, "_campaign_cloud_client", None)
    user_data_dir = getattr(client, "user_data_dir", None)
    store = CampaignPrivacyStore(user_data_dir=user_data_dir)
    window._campaign_privacy_store = store
    return store


def _taken_improvements(data):
    raw = data.get("improvements", [])
    if isinstance(raw, dict):
        raw = raw.get("list_of_taken_improvements", [])
    return raw if isinstance(raw, list) else []


def _safe_improvements(data):
    result = []
    for raw in _taken_improvements(data):
        if not isinstance(raw, dict):
            continue
        catalog_id = str(raw.get("catalog_id") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not catalog_id and not name:
            continue
        try:
            times_taken = max(1, int(raw.get("times_taken") or 1))
        except (TypeError, ValueError, OverflowError):
            times_taken = 1
        result.append(
            {
                "catalog_id": catalog_id,
                "name": name,
                "times_taken": times_taken,
            }
        )
    return result


def _safe_inventory(data, selected_ids):
    selected_ids = set(_clean_id_list(selected_ids))
    raw_inventory = data.get("inventory", {})
    rows = raw_inventory.get("list_of_items", []) if isinstance(raw_inventory, dict) else []
    result = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("id") or "").strip()
        if item_id not in selected_ids:
            continue
        try:
            quantity = max(0, int(raw.get("quantity") or 0))
        except (TypeError, ValueError, OverflowError):
            quantity = 0
        result.append(
            {
                "id": item_id,
                "name": str(raw.get("name") or "")[:500],
                "description": str(raw.get("description") or "")[:10000],
                "quantity": quantity,
            }
        )
    return result


def _safe_notes(data, selected_ids):
    selected_ids = set(_clean_id_list(selected_ids))
    raw_notes = data.get("notes", {})
    rows = raw_notes.get("list_of_notes", []) if isinstance(raw_notes, dict) else []
    result = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        note_id = str(raw.get("id") or "").strip()
        if note_id not in selected_ids:
            continue
        result.append(
            {
                "id": note_id,
                "title": str(raw.get("title") or "")[:500],
                "text": str(raw.get("text") or "")[:50000],
                "color": str(raw.get("color") or "")[:100],
                "pinned": bool(raw.get("pinned", False)),
            }
        )
    return result


def _portrait_payload(data, enabled):
    if not enabled:
        return {"shared": False}

    image_data = data.get("image", {})
    if not isinstance(image_data, dict):
        return {"shared": True, "available": False}

    images = image_data.get("images", [])
    if not isinstance(images, list) or not images:
        return {"shared": True, "available": False}

    try:
        index = int(image_data.get("current_index") or 0)
    except (TypeError, ValueError, OverflowError):
        index = 0
    if index < 0 or index >= len(images):
        index = 0

    entry = images[index]
    if isinstance(entry, dict):
        raw = entry.get("display") or entry.get("original") or entry.get("image")
    else:
        raw = entry
    raw = str(raw or "")
    if not raw:
        return {"shared": True, "available": False}
    if len(raw) > MAX_PORTRAIT_CHARS:
        return {
            "shared": True,
            "available": True,
            "data_omitted": "portrait_too_large",
        }
    return {
        "shared": True,
        "available": True,
        "data": raw,
    }


def build_shared_character_state_with_preferences(
    character_or_dict,
    preferences=None,
    generated_utc=None,
):
    prefs = normalize_privacy_preferences(preferences)
    if isinstance(character_or_dict, dict):
        data = copy.deepcopy(character_or_dict)
    else:
        data = CharacterStorageSystem.character_to_dict(character_or_dict)

    # Reuse the original deliberate core whitelist, then explicitly replace
    # every optional Phase 6 category below.
    state = build_shared_character_state_from_dict(
        data,
        generated_utc=generated_utc,
    )

    state["sharing"] = {
        "schema_version": PRIVACY_SCHEMA_VERSION,
        "core": True,
        "improvements": bool(prefs["share_improvements"]),
        "portrait": bool(prefs["share_portrait"]),
        "backstory": bool(prefs["share_backstory"]),
        "inventory": bool(prefs["share_inventory"]),
        "notes": bool(prefs["share_notes"]),
    }

    if prefs["share_improvements"]:
        state["improvements"] = _safe_improvements(data)
    else:
        state.pop("improvements", None)

    state["portrait"] = _portrait_payload(data, prefs["share_portrait"])

    if prefs["share_backstory"]:
        state["backstory"] = str(data.get("backstory") or "")[:100000]
    else:
        state.pop("backstory", None)

    if prefs["share_inventory"]:
        state["inventory"] = _safe_inventory(
            data,
            prefs["inventory_item_ids"],
        )
    else:
        state.pop("inventory", None)

    if prefs["share_notes"]:
        state["notes"] = _safe_notes(data, prefs["note_ids"])
    else:
        state.pop("notes", None)

    return state


def build_window_shared_state(window, campaign_id=None, link=None):
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

    store = privacy_store_for_window(window)
    prefs = store.get(resolved_campaign_id, character_id)
    return build_shared_character_state_with_preferences(character, prefs)


def sharing_summary(preferences):
    prefs = normalize_privacy_preferences(preferences)
    parts = ["Core"]
    if prefs["share_improvements"]:
        parts.append("Improvements")
    if prefs["share_portrait"]:
        parts.append("Portrait")
    if prefs["share_backstory"]:
        parts.append("Backstory")
    if prefs["share_inventory"]:
        count = len(prefs["inventory_item_ids"])
        parts.append(f"Inventory ({count})")
    if prefs["share_notes"]:
        count = len(prefs["note_ids"])
        parts.append(f"Notes ({count})")
    return "Shared with DM: " + ", ".join(parts)
