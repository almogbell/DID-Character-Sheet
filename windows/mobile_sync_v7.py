"""Authoritative Phase 9 V7 mobile actions for the Windows DID app.

This module deliberately mutates the same in-memory Character object used by the
finished desktop application.  The adapter remains responsible for validation,
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


def _error(adapter: Any, message: str):
    raise adapter.__class__.__module__ and ValueError(message)


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
    if str(getattr(note, "linked_improvement_id", "") or "").strip():
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
    # Mobile may edit public choice values, but private runtime/system keys are
    # never accepted from the phone and are preserved verbatim.
    public_existing = {key for key in existing if not str(key).startswith("_")}
    allowed = set(public_existing)
    try:
        from character_API import IMPROVEMENT_CATALOG  # type: ignore
        option = IMPROVEMENT_CATALOG.get(str(getattr(improvement, "catalog_id", "")), {})
        allowed.update(str(key) for key in option.get("required_choices", []) if str(key))
    except Exception:
        pass
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
    # Hard cap protects against pathological/mock RNGs while preserving normal
    # exploding-die behavior.
    for _ in range(100):
        face = rng.randint(1, sides)
        faces.append(face)
        total += face
        if face != sides:
            break
    return total, faces


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
        detail = f"d{sides}: " + " + ".join(str(face) for face in faces)
        if bonus:
            detail += f"  {'+' if bonus > 0 else '-'} {abs(bonus)}"
        return {"title": str(stat_key).title(), "total": total, "detail": detail}

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
