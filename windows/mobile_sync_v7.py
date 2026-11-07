"""Authoritative mobile actions for the Windows DID app.

Android only sends intent/selections. Windows validates rules, performs dice
rolls, mutates the canonical Character object, and returns the accepted result.
"""
from __future__ import annotations

import base64
import random
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4


@dataclass
class MobileV7Result:
    handled: bool
    mutated: bool = False
    result: Optional[dict] = None


def _validation_error(adapter: Any, message: str):
    module = __import__(adapter.__class__.__module__, fromlist=["MobileSyncValidationError"])
    error_type = getattr(module, "MobileSyncValidationError", ValueError)
    raise error_type(message)


def _required_id(adapter: Any, payload: dict) -> str:
    return adapter._required_id(payload)


def _find_note(adapter: Any, note_id: str):
    notes = getattr(adapter._character(), "notes", None)
    if notes is None or not hasattr(notes, "list_of_notes"):
        _validation_error(adapter, "This character has no notes")
    for note in notes.list_of_notes:
        if str(getattr(note, "id", "")) == note_id:
            return note
    _validation_error(adapter, "Note no longer exists")


def _is_system_note(note: Any) -> bool:
    title = str(getattr(note, "title", "") or "").strip().lower()
    linked = bool(str(getattr(note, "linked_improvement_id", "") or "").strip())
    return title in {"spellcasting verbs", "sneak attack", "mighty"} or (
        title == "animal buddy" and linked
    )


def _protect_system_note(adapter: Any, note: Any) -> None:
    if _is_system_note(note):
        _validation_error(
            adapter,
            "System notes must be edited through their owning Improvement",
        )


def _valid_note_color(adapter: Any, value: Any) -> str:
    color = str(value or "yellow").strip()
    named = {"red", "orange", "yellow", "green", "blue", "purple", "pink"}
    if color in named:
        return color
    if (
        len(color) == 7
        and color.startswith("#")
        and all(ch in "0123456789abcdefABCDEF" for ch in color[1:])
    ):
        return color
    _validation_error(adapter, "Invalid note color")


def _note_add(adapter: Any, payload: dict) -> None:
    try:
        from backend_2_1 import CharacterNote  # type: ignore
    except ImportError as exc:
        _validation_error(adapter, f"Desktop build cannot create notes: {exc}")

    requested_id = str(payload.get("id") or "").strip()
    if requested_id and len(requested_id) > 160:
        _validation_error(adapter, "Invalid note id")

    note = CharacterNote(
        id=requested_id or str(uuid4()),
        title=adapter._bounded_text(
            payload.get("title", ""),
            label="Note title",
            maximum=240,
            strip=True,
        ),
        text=adapter._bounded_text(
            payload.get("text", ""),
            label="Note text",
            maximum=100_000,
        ),
        color=_valid_note_color(adapter, payload.get("color")),
        expanded=True,
        linked_improvement_id="",
        pinned=bool(payload.get("pinned", False)),
    )
    adapter._character().notes.list_of_notes.append(note)


def _note_update(adapter: Any, payload: dict) -> None:
    note = _find_note(adapter, _required_id(adapter, payload))
    _protect_system_note(adapter, note)

    if "title" in payload:
        note.title = adapter._bounded_text(
            payload.get("title", ""),
            label="Note title",
            maximum=240,
            strip=True,
        )
    if "text" in payload:
        note.text = adapter._bounded_text(
            payload.get("text", ""),
            label="Note text",
            maximum=100_000,
        )
    if "color" in payload:
        note.color = _valid_note_color(adapter, payload.get("color"))
    if "pinned" in payload:
        note.pinned = bool(payload.get("pinned"))


def _note_remove(adapter: Any, payload: dict) -> None:
    note_id = _required_id(adapter, payload)
    note = _find_note(adapter, note_id)
    _protect_system_note(adapter, note)

    notes = adapter._character().notes
    notes.list_of_notes = [
        item
        for item in notes.list_of_notes
        if str(getattr(item, "id", "")) != note_id
    ]


def _image_add(adapter: Any, payload: dict) -> None:
    data = str(payload.get("data", ""))
    if not data.startswith("data:image/") or ";base64," not in data:
        _validation_error(adapter, "Character picture must be an image")

    header, encoded = data.split(",", 1)
    if len(encoded) > 11_000_000:
        _validation_error(adapter, "Character picture is too large")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        _validation_error(adapter, "Character picture contains invalid image data")

    if not raw or len(raw) > 8_000_000:
        _validation_error(adapter, "Character picture is too large")

    try:
        from backend_2_1 import ImageSystem  # type: ignore
    except ImportError as exc:
        _validation_error(adapter, f"Desktop build cannot add character pictures: {exc}")

    character = adapter._character()
    before = list(getattr(getattr(character, "image", None), "images", []) or [])
    if not ImageSystem.add_image(character, f"{header},{encoded}"):
        _validation_error(adapter, "Could not add character picture")

    requested_id = str(payload.get("id") or "").strip()
    if requested_id:
        if len(requested_id) > 160:
            _validation_error(adapter, "Invalid image id")
        after = list(getattr(getattr(character, "image", None), "images", []) or [])
        new_entries = [entry for entry in after if entry not in before]
        if new_entries:
            try:
                new_entries[-1].id = requested_id
            except Exception:
                pass


def _image_remove(adapter: Any, payload: dict) -> None:
    image_id = _required_id(adapter, payload)
    image = getattr(adapter._character(), "image", None)
    if image is None or not hasattr(image, "images"):
        _validation_error(adapter, "This character has no picture collection")

    before = len(image.images)
    image.images = [
        entry
        for entry in image.images
        if str(getattr(entry, "id", "")) != image_id
    ]
    if len(image.images) == before:
        _validation_error(adapter, "Character picture no longer exists")

    image.current_index = min(
        max(0, int(getattr(image, "current_index", 0))),
        max(0, len(image.images) - 1),
    )


def _resource_set(adapter: Any, payload: dict) -> None:
    resource = str(payload.get("resource", ""))
    try:
        value = int(payload.get("value"))
    except (TypeError, ValueError):
        _validation_error(adapter, "Resource value must be an integer")

    character = adapter._character()
    if resource == "HP":
        maximum = int(character.HP.max_HP)
        if not 0 <= value <= maximum:
            _validation_error(adapter, f"HP must stay between 0 and {maximum}")
        character.HP.current_HP = value
    elif resource == "Adversity":
        maximum = int(character.adversity.max_AT)
        if not 0 <= value <= maximum:
            _validation_error(adapter, f"Adversity Tokens must stay between 0 and {maximum}")
        character.adversity.current_AT = value
    elif resource == "IP":
        if value < int(character.progression.used_IP):
            _validation_error(adapter, "Total IP cannot be lower than spent IP")
        character.progression.current_IP = value
    else:
        _validation_error(adapter, f"Unknown resource: {resource}")


def _resource_adjust(adapter: Any, payload: dict) -> None:
    try:
        hearts = int(payload.get("max_hearts"))
        total_ip = int(payload.get("total_ip"))
        max_at = int(payload.get("max_at"))
    except (TypeError, ValueError):
        _validation_error(adapter, "Resource values must be integers")

    if not 0 <= hearts <= 999 or not 0 <= max_at <= 999:
        _validation_error(adapter, "Hearts and AT must be between 0 and 999")

    character = adapter._character()
    used_ip = int(character.progression.used_IP)
    if total_ip < used_ip:
        _validation_error(
            adapter,
            f"Total IP cannot be lower than the {used_ip} IP already spent",
        )

    character.HP.max_hearts = hearts
    character.progression.current_IP = total_ip
    character.adversity.max_AT = max_at


def _find_improvement(adapter: Any, improvement_id: str):
    improvements = getattr(adapter._character(), "improvements", None)
    for improvement in list(
        getattr(improvements, "list_of_taken_improvements", []) or []
    ):
        if str(getattr(improvement, "id", "")) == improvement_id:
            return improvement
    _validation_error(adapter, "Improvement no longer exists")


def _improvement_edit(adapter: Any, payload: dict) -> None:
    improvement = _find_improvement(adapter, _required_id(adapter, payload))
    existing = dict(getattr(improvement, "choices", {}) or {})
    incoming = payload.get("choices", {})
    if not isinstance(incoming, dict):
        _validation_error(adapter, "Improvement choices must be an object")

    allowed = set()
    try:
        from backend_2_1 import ImprovementCatalogSystem  # type: ignore

        catalog_id = str(getattr(improvement, "catalog_id", ""))
        try:
            option = ImprovementCatalogSystem.get_option(
                catalog_id,
                adapter._character(),
            ) or {}
        except TypeError:
            option = ImprovementCatalogSystem.get_option(catalog_id) or {}

        required = option.get("required_choices", {})
        if isinstance(required, dict):
            allowed.update(
                str(key)
                for key in required.keys()
                if str(key) and not str(key).startswith("_")
            )
        elif isinstance(required, (list, tuple)):
            for item in required:
                if isinstance(item, str):
                    key = item
                elif isinstance(item, dict):
                    key = str(
                        item.get("key")
                        or item.get("id")
                        or item.get("name")
                        or ""
                    )
                else:
                    key = ""
                if key and not key.startswith("_"):
                    allowed.add(key)
    except Exception:
        allowed.update(
            str(key)
            for key in existing
            if not str(key).startswith("_")
        )

    for key, value in incoming.items():
        key = str(key)
        if key.startswith("_") or key not in allowed:
            continue
        value = str(value)
        if len(value) > 10_000:
            _validation_error(adapter, "Improvement choice is too long")
        existing[key] = value

    improvement.choices = existing

    custom = (
        str(getattr(improvement, "catalog_id", "")) == "custom"
        or str(getattr(improvement, "source", "")) == "custom"
    )
    if custom:
        if "name" in payload:
            improvement.name = adapter._bounded_text(
                payload.get("name", ""),
                label="Improvement name",
                maximum=240,
                strip=True,
            )
        if "description" in payload:
            improvement.description = adapter._bounded_text(
                payload.get("description", ""),
                label="Improvement description",
                maximum=50_000,
            )


def _improvement_purchase(adapter: Any, payload: dict) -> None:
    """Buy exactly one option from Windows' current authoritative purchase list."""
    try:
        from backend_2_1 import ImprovementSystem  # type: ignore
    except ImportError as exc:
        _validation_error(adapter, f"Desktop build cannot buy Improvements: {exc}")

    character = adapter._character()
    kind = str(payload.get("kind") or "base")
    catalog_id = str(payload.get("catalog_id") or "").strip()
    improvement_id = str(payload.get("improvement_id") or "").strip()
    group_id = str(payload.get("group_id") or "").strip()
    if not catalog_id:
        _validation_error(adapter, "Invalid Improvement selection")

    choices = payload.get("choices", {})
    if not isinstance(choices, dict):
        _validation_error(adapter, "Improvement choices must be an object")
    safe_choices = {}
    for key, value in choices.items():
        key = str(key).strip()
        if not key or key.startswith("_"):
            continue
        value = str(value)
        if len(value) > 10_000:
            _validation_error(adapter, "Improvement choice is too long")
        safe_choices[key] = value

    # Rebuild the authoritative list at purchase time. Never trust cost,
    # description, effects, or eligibility sent by Android.
    options = [
        option for option in (ImprovementSystem.get_available_purchases(character) or [])
        if isinstance(option, dict)
        and option.get("source") != "species"
        and "species" not in (option.get("tags") or [])
    ]

    def matches(option: dict) -> bool:
        if str(option.get("kind") or "base") != kind:
            return False
        if str(option.get("catalog_id") or "") != catalog_id:
            return False
        if kind == "empowerment":
            if str(option.get("improvement_id") or "") != improvement_id:
                return False
            if str(option.get("group_id") or "") != group_id:
                return False
        return True

    selected = next((option for option in options if matches(option)), None)
    if selected is None:
        _validation_error(
            adapter,
            "That Improvement or empowerment is no longer available to buy",
        )

    required = []
    for item in selected.get("requires_choices", []) or []:
        if isinstance(item, str):
            key = item
        elif isinstance(item, dict):
            key = str(item.get("key") or item.get("id") or item.get("name") or "")
        else:
            key = ""
        key = key.strip()
        if key:
            required.append(key)

    missing = [key for key in required if not str(safe_choices.get(key, "")).strip()]
    if missing:
        _validation_error(adapter, "Complete the required choices before buying")

    existing_ids = {
        str(getattr(improvement, "id", ""))
        for improvement in character.improvements.list_of_taken_improvements
    }

    if not ImprovementSystem.buy_purchase(character, selected, choices=safe_choices):
        _validation_error(adapter, "Could not buy this Improvement or empowerment")

    # Match the desktop flow for Spellcasting's managed reference note.
    if catalog_id == "spellcasting" and kind != "empowerment":
        purchased = next(
            (
                improvement
                for improvement in character.improvements.list_of_taken_improvements
                if str(getattr(improvement, "id", "")) not in existing_ids
                and str(getattr(improvement, "catalog_id", "")) == "spellcasting"
            ),
            None,
        )
        offer_note = getattr(adapter.window, "offer_spellcasting_verbs_note", None)
        if purchased is not None and callable(offer_note):
            try:
                offer_note(purchased)
            except Exception:
                pass

def _roll_exploding(sides: int, rng: random.Random) -> tuple[int, list[int]]:
    total = 0
    faces: list[int] = []
    for _ in range(100):
        face = rng.randint(1, sides)
        faces.append(face)
        total += face
        if face != sides:
            break
    return total, faces


def _bounded_roll_count(adapter: Any, payload: dict, field: str) -> int:
    try:
        value = int(payload.get(field, 0))
    except (TypeError, ValueError):
        _validation_error(adapter, "Ability roll option count must be an integer")
    if not 0 <= value <= 20:
        _validation_error(adapter, "Ability roll option count is invalid")
    return value


def _current_roll_modifier_options(adapter: Any, stat_key: str) -> list[dict]:
    provider = getattr(adapter.window, "_available_roll_modifier_options", None)
    if not callable(provider):
        return []

    try:
        options = provider(stat_key)
    except TypeError:
        try:
            options = provider()
        except Exception:
            return []
    except Exception:
        return []

    return [item for item in (options or []) if isinstance(item, dict)]


def _selected_modifier_options(
    adapter: Any,
    stat_key: str,
    payload: dict,
) -> list[dict]:
    raw_indexes = payload.get("option_indexes", [])
    if raw_indexes is None:
        return []
    if not isinstance(raw_indexes, list):
        _validation_error(adapter, "Ability roll options must be a list")
    if len(raw_indexes) > 20:
        _validation_error(adapter, "Too many ability roll options")

    available = _current_roll_modifier_options(adapter, stat_key)
    selected: list[dict] = []
    seen = set()

    for raw in raw_indexes:
        try:
            index = int(raw)
        except (TypeError, ValueError):
            _validation_error(adapter, "Invalid ability roll option")

        if index in seen or not 0 <= index < len(available):
            _validation_error(
                adapter,
                "That ability roll option is no longer available",
            )
        seen.add(index)
        selected.append(available[index])

    return selected


def _roll_extra(
    rng: random.Random,
    option: dict,
) -> tuple[int, str]:
    sides = int(option.get("sides", 6))
    if sides not in {4, 6, 8, 10, 12, 20, 100}:
        sides = 6

    sign = -1 if int(option.get("sign", 1)) < 0 else 1

    # Desktop rule: only the main ability die explodes. Magic, martial,
    # mighty, advantage, disadvantage and all selected extras do not.
    face = rng.randint(1, sides)
    label = str(
        option.get("short_label")
        or option.get("label")
        or f"d{sides}"
    )
    sign_text = "+" if sign > 0 else "−"
    return sign * face, f"{sign_text}{label} d{sides}: {face}"


def _dice_roll(adapter: Any, payload: dict) -> dict:
    """Roll on Windows and return both the canonical total and physical die faces.

    Android may animate these already-decided faces, but it never chooses the
    result. This keeps the Windows desktop authoritative.
    """
    mode = str(payload.get("mode", "ability"))
    rng = random.SystemRandom()

    if mode == "ability":
        stat_key = str(payload.get("stat", "")).strip().lower()
        stats = getattr(adapter._character(), "stats", None)
        stat = (
            stats.get_stat(stat_key)
            if stats is not None and hasattr(stats, "get_stat")
            else None
        )
        if stat is None:
            _validation_error(adapter, "Unknown ability")

        sides = int(getattr(stat, "die_size", 0))
        if sides < 2:
            _validation_error(adapter, "This ability has no rollable die")

        dice_visuals: list[dict] = []

        # Main ability die explodes. Every explosion is another physical die.
        die_total, faces = _roll_exploding(sides, rng)
        for face in faces:
            dice_visuals.append({
                "sides": sides,
                "face": int(face),
                "sign": 1,
                "kind": "ability",
                "label": stat_key,
            })

        bonus = int(getattr(stat, "bonus", 0))
        total = die_total + bonus
        detail_parts = [f"d{sides}: " + " + ".join(str(face) for face in faces)]
        if bonus:
            detail_parts.append(f"{'+' if bonus > 0 else '−'} bonus {abs(bonus)}")

        advantage = _bounded_roll_count(adapter, payload, "advantage_count")
        disadvantage = _bounded_roll_count(adapter, payload, "disadvantage_count")
        cancelled = min(advantage, disadvantage)
        advantage -= cancelled
        disadvantage -= cancelled

        for _ in range(advantage):
            face = rng.randint(1, 6)
            total += face
            dice_visuals.append({
                "sides": 6, "face": face, "sign": 1,
                "kind": "advantage", "label": "adv.",
            })
            detail_parts.append(f"+adv. d6: {face}")

        for _ in range(disadvantage):
            face = rng.randint(1, 6)
            total -= face
            dice_visuals.append({
                "sides": 6, "face": face, "sign": -1,
                "kind": "disadvantage", "label": "dis.",
            })
            detail_parts.append(f"−dis. d6: {face}")

        for option in _selected_modifier_options(adapter, stat_key, payload):
            sides = int(option.get("sides", 6))
            if sides not in {4, 6, 8, 10, 12, 20, 100}:
                sides = 6
            sign = -1 if int(option.get("sign", 1)) < 0 else 1
            face = rng.randint(1, sides)
            total += sign * face
            label = str(option.get("short_label") or option.get("label") or f"d{sides}")
            kind = str(option.get("kind") or "bonus_die")
            dice_visuals.append({
                "sides": sides,
                "face": face,
                "sign": sign,
                "kind": kind,
                "label": label,
            })
            detail_parts.append(
                f"{'+' if sign > 0 else '−'}{label} d{sides}: {face}"
            )

        return {
            "title": str(stat_key).title(),
            "total": total,
            "detail": "  •  ".join(detail_parts),
            "dice": dice_visuals,
            "flat_bonus": bonus,
        }

    if mode == "buddy":
        improvement_id = str(payload.get("improvement_id") or "").strip()
        stat_key = str(payload.get("stat") or "").strip().lower()
        character = adapter._character()

        buddy = next(
            (
                improvement
                for improvement in character.improvements.list_of_taken_improvements
                if str(getattr(improvement, "catalog_id", "")) == "animal_buddy"
                and str(getattr(improvement, "id", "")) == improvement_id
            ),
            None,
        )
        if buddy is None:
            _validation_error(adapter, "Animal Buddy not found")

        try:
            from notes_ui import buddy_state  # type: ignore
            state = buddy_state(buddy, character.BDV)
        except Exception:
            _validation_error(adapter, "Could not read Animal Buddy state")

        stat_name = next(
            (name for name in state["dice"] if name.lower() == stat_key),
            None,
        )
        if stat_name is None:
            _validation_error(adapter, "Unknown Animal Buddy ability")

        sides = int(state["dice"][stat_name])
        bonus = int(state["training"].get(stat_name, 0))
        die_total, faces = _roll_exploding(sides, rng)
        total = die_total + bonus

        visuals = [
            {
                "sides": sides,
                "face": int(face),
                "sign": 1,
                "kind": "ability",
                "label": f"buddy {stat_key}",
            }
            for face in faces
        ]

        detail = f"d{sides}: " + " + ".join(str(face) for face in faces)
        if bonus:
            detail += f"  •  + bonus {bonus}"

        return {
            "title": f"Animal Buddy — {stat_name}",
            "total": total,
            "detail": detail,
            "dice": visuals,
            "flat_bonus": bonus,
        }

    if mode == "other":
        counts = payload.get("dice", {})
        if not isinstance(counts, dict):
            _validation_error(adapter, "Dice selection must be an object")

        allowed = {4, 6, 8, 10, 12, 20, 100}
        parts: list[str] = []
        dice_visuals: list[dict] = []
        total = 0
        rolled = 0

        for key, count_raw in counts.items():
            try:
                sides = int(key)
                count = int(count_raw)
            except (TypeError, ValueError):
                _validation_error(adapter, "Invalid dice selection")

            if sides not in allowed or not 0 <= count <= 20:
                _validation_error(adapter, "Invalid dice selection")
            if rolled + count > 50:
                _validation_error(adapter, "Too many dice")
            if count <= 0:
                continue

            faces = [rng.randint(1, sides) for _ in range(count)]
            for face in faces:
                dice_visuals.append({
                    "sides": sides,
                    "face": face,
                    "sign": 1,
                    "kind": "other",
                    "label": f"d{sides}",
                })
            total += sum(faces)
            rolled += count
            parts.append(f"{count}d{sides}: " + ", ".join(str(face) for face in faces))

        if rolled == 0:
            _validation_error(adapter, "Choose at least one die")

        return {
            "title": "Other Dice",
            "total": total,
            "detail": "  •  ".join(parts),
            "dice": dice_visuals,
            "flat_bonus": 0,
        }

    _validation_error(adapter, "Unknown dice roll type")

def handle_mobile_v7_action(
    adapter: Any,
    action: str,
    payload: dict,
) -> MobileV7Result:
    if action == "resource.set":
        _resource_set(adapter, payload)
        return MobileV7Result(True, True)

    if action == "resource.adjust":
        _resource_adjust(adapter, payload)
        return MobileV7Result(True, True)

    if action == "note.add":
        _note_add(adapter, payload)
        return MobileV7Result(True, True)

    if action == "note.update":
        _note_update(adapter, payload)
        return MobileV7Result(True, True)

    if action == "note.remove":
        _note_remove(adapter, payload)
        return MobileV7Result(True, True)

    if action == "image.add":
        _image_add(adapter, payload)
        return MobileV7Result(True, True)

    if action == "image.remove":
        _image_remove(adapter, payload)
        return MobileV7Result(True, True)

    if action == "improvement.edit":
        _improvement_edit(adapter, payload)
        return MobileV7Result(True, True)

    if action == "improvement.purchase":
        _improvement_purchase(adapter, payload)
        return MobileV7Result(True, True)

    if action == "dice.roll":
        return MobileV7Result(True, False, _dice_roll(adapter, payload))

    return MobileV7Result(False)
