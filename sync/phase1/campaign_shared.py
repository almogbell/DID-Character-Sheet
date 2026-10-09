from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from backend_2_1 import CharacterStorageSystem, STAT_NAMES


SHARED_SCHEMA_VERSION = 1


def _utc_iso(value=None):
    if value is None:
        value = datetime.now(timezone.utc)
    elif isinstance(value, str):
        return value
    elif value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _as_int(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _as_text(value, default=""):
    text = str(value if value is not None else default).strip()
    return text


def _character_storage_dict(character_or_dict):
    if isinstance(character_or_dict, dict):
        return deepcopy(character_or_dict)
    return CharacterStorageSystem.character_to_dict(character_or_dict)


def _portrait_available(image_data):
    if not isinstance(image_data, dict):
        return bool(image_data)

    current_index = _as_int(image_data.get("current_index"), 0)
    images = image_data.get("images")
    if isinstance(images, list) and images:
        if 0 <= current_index < len(images):
            entry = images[current_index]
        else:
            entry = images[0]
        if isinstance(entry, dict):
            return bool(entry.get("display") or entry.get("original"))
        return bool(entry)

    return bool(
        image_data.get("display")
        or image_data.get("original")
        or image_data.get("image")
    )


def build_shared_character_state_from_dict(data, generated_utc=None):
    """Build the deliberately whitelisted character state visible to a DM.

    This function does NOT copy the character dictionary wholesale. Private
    notes, backstory, inventory contents, local file paths, creation rules,
    recovery data, and roll history are intentionally absent.
    """
    if not isinstance(data, dict):
        raise ValueError("Character data must be a dictionary")

    progression = data.get("progression") or {}
    hp = data.get("HP") or {}
    adversity = data.get("Adversity") or {}
    stats = data.get("stats") or {}

    abilities = {}
    for stat_name in STAT_NAMES:
        raw = stats.get(stat_name) or {}
        abilities[str(stat_name)] = {
            "die_size": _as_int(raw.get("die_size"), 4),
            "bonus": _as_int(raw.get("bonus"), 0),
        }

    improvements = []
    for raw in data.get("improvements") or []:
        if not isinstance(raw, dict):
            continue
        catalog_id = _as_text(raw.get("catalog_id"))
        name = _as_text(raw.get("name"))
        if not catalog_id and not name:
            continue
        improvements.append(
            {
                "catalog_id": catalog_id,
                "name": name,
                "times_taken": max(1, _as_int(raw.get("times_taken"), 1)),
            }
        )

    total_ip = _as_int(progression.get("current_IP"), 0)
    used_ip = _as_int(progression.get("used_IP"), 0)

    return {
        "schema_version": SHARED_SCHEMA_VERSION,
        "kind": "character_state",
        "generated_utc": _utc_iso(generated_utc),
        "character_id": _as_text(data.get("id")),
        "name": _as_text(data.get("name"), "Unnamed Character"),
        "species": _as_text(data.get("species_name")),
        "level": max(1, _as_int(progression.get("level"), 1)),
        "resources": {
            "hearts": {
                "current": max(0, _as_int(hp.get("current_HP"), 0)),
                "max": max(0, _as_int(hp.get("max_hearts"), 0)),
            },
            "adversity_tokens": {
                "current": max(0, _as_int(adversity.get("current_AT"), 0)),
                "max": max(0, _as_int(adversity.get("max_AT"), 0)),
            },
            "improvement_points": {
                "used": max(0, used_ip),
                "total": max(0, total_ip),
                "remaining": max(0, total_ip - used_ip),
            },
        },
        "abilities": abilities,
        "defense_ability": _as_text(data.get("selected_defense_stat_name")),
        "improvements": improvements,
        # Phase 1 deliberately sends no image bytes or local paths. The web
        # dashboard can use this flag now; portrait upload/storage comes later.
        "portrait": {
            "available": _portrait_available(data.get("image")),
        },
    }


def build_shared_character_state(character, generated_utc=None):
    return build_shared_character_state_from_dict(
        _character_storage_dict(character),
        generated_utc=generated_utc,
    )


def _clean_roll_term(term):
    if not isinstance(term, dict):
        raise ValueError("Invalid die entry")

    sides = _as_int(term.get("sides"), 0)
    sign = -1 if _as_int(term.get("sign"), 1) < 0 else 1
    values = term.get("values")

    if sides < 2 or sides > 100:
        raise ValueError("Invalid die size")
    if not isinstance(values, list) or not values:
        raise ValueError("Die entry has no values")

    clean_values = []
    for raw in values:
        face = _as_int(raw, 0)
        if face < 1 or face > sides:
            raise ValueError("Die result is outside its die range")
        clean_values.append(face)

    return {
        "label": _as_text(term.get("label"), "die"),
        "kind": _as_text(term.get("kind"), "die"),
        "sides": sides,
        "sign": sign,
        "values": clean_values,
        "exploded": len(clean_values) > 1,
    }


def build_shared_roll_event_from_summary(
    character_id,
    character_name,
    summary,
    rolled_utc=None,
    event_id=None,
):
    """Convert one completed DiceBox summary into dashboard-safe roll data."""
    if not isinstance(summary, dict):
        raise ValueError("Dice roll summary must be a dictionary")

    raw_terms = summary.get("terms")
    if not isinstance(raw_terms, list) or not raw_terms:
        raise ValueError("Dice roll summary has no terms")

    terms = [_clean_roll_term(term) for term in raw_terms]
    roll_type = _as_text(summary.get("roll_type"), "ability") or "ability"
    flat_bonus = _as_int(summary.get("flat_bonus"), 0)

    event = {
        "schema_version": SHARED_SCHEMA_VERSION,
        "kind": "roll_event",
        "event_id": _as_text(event_id) or str(uuid4()),
        "rolled_utc": _utc_iso(rolled_utc),
        "character_id": _as_text(character_id),
        "character_name": _as_text(character_name, "Unnamed Character"),
        "roll_type": roll_type,
        "ability_name": _as_text(summary.get("ability_name")),
        "flat_bonus": flat_bonus,
        "dice": terms,
        "deed_success": (
            bool(summary.get("deed_success"))
            if summary.get("deed_success") is not None
            else None
        ),
    }

    if roll_type == "other_dice":
        # Other Dice intentionally have no combined total in DID.
        groups = {}
        for term in terms:
            groups.setdefault(term["sides"], []).extend(term["values"])
        event["total"] = None
        event["individual_only"] = True
        event["groups"] = [
            {"sides": sides, "values": groups[sides]}
            for sides in sorted(groups)
        ]
        return event

    total = _as_int(summary.get("total"), 0)
    calculated_total = flat_bonus + sum(
        term["sign"] * sum(term["values"])
        for term in terms
    )
    if total != calculated_total:
        raise ValueError("Roll summary total does not match its dice")

    event["total"] = total
    event["individual_only"] = False
    event["groups"] = []
    return event


def build_shared_roll_event(character, summary, rolled_utc=None, event_id=None):
    if isinstance(character, dict):
        character_id = character.get("id")
        character_name = character.get("name")
    else:
        character_id = getattr(character, "id", "")
        character_name = getattr(character, "name", "")

    return build_shared_roll_event_from_summary(
        character_id,
        character_name,
        summary,
        rolled_utc=rolled_utc,
        event_id=event_id,
    )
