"""Authoritative Phase 9 V7 mobile actions for the Windows DID app.

This module deliberately mutates the same in-memory Character object used by the
finished desktop application. The adapter remains responsible for validation,
autosave, and UI refresh after mutating commands.
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
    # Avoid a hard import cycle while still returning the adapter's user-facing
    # validation exception type.
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


def _protect_linked_note(adapter: Any, note: Any) -> None:
    title = str(getattr(note, "title", "") or "").strip().lower()
    linked = str(getattr(note, "linked_improvement_id", "") or "").strip()
    is_system = title in {"spellcasting verbs", "sneak attack"} or (
        title == "animal buddy" and bool(linked)
    )
    if linked or is_system:
        _validation_error(adapter, "System/Improvement notes must be edited through their Improvement")


def _valid_note_color(adapter: Any, value: Any) -> str:
    color = str(value or "yellow").strip()
    named = {"red", "orange", "yellow", "green", "blue", "purple", "pink"}
    if color in named:
        return color
    if len(color) == 7 and color.startswith("#") and all(ch in "0123456789abcdefABCDEF" for ch in color[1:]):
        return color
    _validation_error(adapter, "Invalid note color")


def _note_add(adapter: Any, payload: dict) -> None:
    try:
        from backend_2_1 import CharacterNote  # type: ignore
    except ImportError as exc:
        _validation_error(adapter, f"Desktop build cannot create notes: {exc}")
    title = adapter._bounded_text(payload.get("title", ""), label="Note title", maximum=240, strip=True)
    text = adapter._bounded_text(payload.get("text", ""), label="Note text", maximum=100_000)
    note = CharacterNote(
        id=str(uuid4()),
        title=title,
        text=text,
        color=_valid_note_color(adapter, payload.get("color")),
        expanded=True,
        linked_improvement_id="",
        pinned=bool(payload.get("pinned", False)),
    )
    adapter._character().notes.list_of_notes.append(note)


def _note_update(adapter: Any, payload: dict) -> None:
    note = _find_note(adapter, _required_id(adapter, payload))
    _protect_linked_note(adapter, note)
    if "title" in payload:
        note.title = adapter._bounded_text(payload.get("title", ""), label="Note title", maximum=240, strip=True)
    if "text" in payload:
        note.text = adapter._bounded_text(payload.get("text", ""), label="Note text", maximum=100_000)
    if "color" in payload:
        note.color = _valid_note_color(adapter, payload.get("color"))
    if "pinned" in payload:
        note.pinned = bool(payload.get("pinned"))


def _note_remove(adapter: Any, payload: dict) -> None:
    note_id = _required_id(adapter, payload)
    note = _find_note(adapter, note_id)
    _protect_linked_note(adapter, note)
    notes = adapter._character().notes
    notes.list_of_notes = [item for item in notes.list_of_notes if str(getattr(item, "id", "")) != note_id]


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
    if not ImageSystem.add_image(adapter._character(), f"{header},{encoded}"):
        _validation_error(adapter, "Could not add character picture")


def _image_remove(adapter: Any, payload: dict) -> None:
    image_id = _required_id(adapter, payload)
    image = getattr(adapter._character(), "image", None)
    if image is None or not hasattr(image, "images"):
        _validation_error(adapter, "This character has no picture collection")
    before = len(image.images)
    image.images = [entry for entry in image.images if str(getattr(entry, "id", "")) != image_id]
    if len(image.images) == before:
        _validation_error(adapter, "Character picture no longer exists")
    image.current_index = min(max(0, int(getattr(image, "current_index", 0))), max(0, len(image.images) - 1))


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
        _validation_error(adapter, f"Total IP cannot be lower than the {used_ip} IP already spent")
    character.HP.max_hearts = hearts
    character.progression.current_IP = total_ip
    character.adversity.max_AT = max_at


def _find_improvement(adapter: Any, improvement_id: str):
    improvements = getattr(adapter._character(), "improvements", None)
    for improvement in list(getattr(improvements, "list_of_taken_improvements", [])):
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
            option = ImprovementCatalogSystem.get_option(catalog_id, adapter._character()) or {}
        except TypeError:
            option = ImprovementCatalogSystem.get_option(catalog_id) or {}
        required = option.get("required_choices", {})
        if isinstance(required, dict):
            allowed.update(str(key) for key in required.keys() if str(key) and not str(key).startswith("_"))
        elif isinstance(required, (list, tuple)):
            for item in required:
                if isinstance(item, str):
                    key = item
                elif isinstance(item, dict):
                    key = str(item.get("key") or item.get("id") or item.get("name") or "")
                else:
                    key = ""
                if key and not key.startswith("_"):
                    allowed.add(key)
    except Exception:
        # Older desktop builds may not expose the catalog helper. In that case
        # only existing public fields can be changed, still validated on Windows.
        allowed.update(str(key) for key in existing if not str(key).startswith("_"))

    for key, value in incoming.items():
        key = str(key)
        if key.startswith("_") or key not in allowed:
            continue
        text = str(value)
        if len(text) > 10_000:
            _validation_error(adapter, "Improvement choice is too long")
        existing[key] = text
    improvement.choices = existing

    if str(getattr(improvement, "catalog_id", "")) == "custom" or str(getattr(improvement, "source", "")) == "custom":
        if "name" in payload:
            improvement.name = adapter._bounded_text(payload.get("name", ""), label="Improvement name", maximum=240, strip=True)
        if "description" in payload:
            improvement.description = adapter._bounded_text(payload.get("description", ""), label="Improvement description", maximum=50_000)


def _roll_exploding(sides: int, rng: random.Random) -> tuple[int, list[int]]:
    total = 0
    faces = []
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
        return [item for item in (provider(stat_key) or []) if isinstance(item, dict)]
    except Exception:
        return []


def _selected_modifier_options(adapter: Any, stat_key: str, payload: dict) -> list[dict]:
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
            _validation_error(adapter, "That ability roll option is no longer available")
        seen.add(index)
        selected.append(available[index])
    return selected


def _roll_signed_extra(rng: random.Random, option: dict) -> tuple[int, str]:
    sides = int(option.get("sides", 6))
    if sides not in {4, 6, 8, 10, 12, 20, 100}:
        sides = 6
    sign = -1 if int(option.get("sign", 1)) < 0 else 1
    explode = bool(option.get("explode", False))
    if explode:
        subtotal, faces = _roll_exploding(sides, rng)
    else:
        face = rng.randint(1, sides)
        subtotal, faces = face, [face]
    label = str(option.get("short_label") or option.get("label") or f"d{sides}")
    sign_text = "+" if sign > 0 else "−"
    face_text = "+".join(str(face) for face in faces)
    return sign * subtotal, f"{sign_text}{label} d{sides}: {face_text}"


def _dice_roll(adapter: Any, payload: dict) -> dict:
    mode = str(payload.get("mode", "ability"))
    rng = random.SystemRandom()
    if mode == "ability":
        stat_key = str(payload.get("stat", "")).strip().lower()
        stat = adapter._character().stats.get_stat(stat_key)
        if stat is None:
            _validation_error(adapter, "Unknown ability")
        sides = int(stat.die_size)
        if sides < 2:
            _validation_error(adapter, "This ability has no rollable die")

        die_total, faces = _roll_exploding(sides, rng)
        bonus = int(getattr(stat, "bonus", 0))
        total = die_total + bonus
        detail_parts = [f"d{sides}: " + " + ".join(str(face) for face in faces)]
        if bonus:
            detail_parts.append(f"{'+' if bonus > 0 else '−'} bonus {abs(bonus)}")

        advantage = _bounded_roll_count(adapter, payload, "advantage_count")
        disadvantage = _bounded_roll_count(adapter, payload, "disadvantage_count")
        # The desktop dice roller cancels opposite d6s before rolling them.
        cancelled = min(advantage, disadvantage)
        advantage -= cancelled
        disadvantage -= cancelled

        for _ in range(advantage):
            face = rng.randint(1, 6)
            total += face
            detail_parts.append(f"+adv. d6: {face}")
        for _ in range(disadvantage):
            face = rng.randint(1, 6)
            total -= face
            detail_parts.append(f"−dis. d6: {face}")

        for option in _selected_modifier_options(adapter, stat_key, payload):
            delta, detail = _roll_signed_extra(rng, option)
            total += delta
            detail_parts.append(detail)

        return {"title": str(stat_key).title(), "total": total, "detail": "  •  ".join(detail_parts)}

    if mode == "other":
        counts = payload.get("dice", {})
        if not isinstance(counts, dict):
            _validation_error(adapter, "Dice selection must be an object")
        allowed = {4, 6, 8, 10, 12, 20, 100}
        parts = []
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
            total += sum(faces)
            rolled += count
            parts.append(f"{count}d{sides}: " + ", ".join(str(face) for face in faces))
        if rolled == 0:
            _validation_error(adapter, "Choose at least one die")
        return {"title": "Other Dice", "total": total, "detail": "  •  ".join(parts)}
    _validation_error(adapter, "Unknown dice roll type")


def handle_mobile_v7_action(adapter: Any, action: str, payload: dict) -> MobileV7Result:
    """Handle Phase 9 V7 actions not owned by the original Phase 8 adapter."""
    if action == "resource.set":
        _resource_set(adapter, payload); return MobileV7Result(True, True)
    if action == "resource.adjust":
        _resource_adjust(adapter, payload); return MobileV7Result(True, True)
    if action == "note.add":
        _note_add(adapter, payload); return MobileV7Result(True, True)
    if action == "note.update":
        _note_update(adapter, payload); return MobileV7Result(True, True)
    if action == "note.remove":
        _note_remove(adapter, payload); return MobileV7Result(True, True)
    if action == "image.add":
        _image_add(adapter, payload); return MobileV7Result(True, True)
    if action == "image.remove":
        _image_remove(adapter, payload); return MobileV7Result(True, True)
    if action == "improvement.edit":
        _improvement_edit(adapter, payload); return MobileV7Result(True, True)
    if action == "dice.roll":
        return MobileV7Result(True, False, _dice_roll(adapter, payload))
    return MobileV7Result(False)
