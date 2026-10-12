"""Adapter between the finished DID desktop window and the mobile companion.

Windows remains authoritative. Every accepted phone mutation is applied to the
same in-memory character used by the desktop UI, then routed through the normal
``mark_dirty(auto_save=True)`` and refresh path. The adapter intentionally owns
no save files and duplicates no improvement/game rules.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional
from uuid import uuid4


class MobileSyncValidationError(ValueError):
    """User-facing validation failure returned to the Android companion."""


@dataclass
class FrontendHooks:
    """Optional explicit hooks for desktop operations with dedicated UI paths."""

    save_after_change: Optional[Callable[[], None]] = None
    refresh_after_change: Optional[Callable[[], None]] = None
    hp_change: Optional[Callable[[int], None]] = None
    adversity_change: Optional[Callable[[int], None]] = None
    ip_change: Optional[Callable[[int], None]] = None


class DesktopSyncAdapter:
    MAX_NAME_CHARS = 240
    MAX_BACKSTORY_CHARS = 50_000
    MAX_ITEM_DESCRIPTION_CHARS = 25_000

    _NOTE_COLORS = {
        "red": "#f3a6a6",
        "orange": "#ffc078",
        "yellow": "#ffe98a",
        "green": "#a8e6b0",
        "blue": "#9fcfe3",
        "purple": "#c8b6ff",
        "pink": "#f4b6cf",
    }

    def __init__(self, window: Any, storage_system: Any, hooks: Optional[FrontendHooks] = None) -> None:
        self.window = window
        self.storage_system = storage_system
        self.hooks = hooks or FrontendHooks()

    # ------------------------------------------------------------------
    # MobileSyncServer callbacks
    # ------------------------------------------------------------------
    def state_provider(self) -> Optional[dict]:
        character = getattr(self.window, "character", None)
        if character is None:
            return None

        state = self.storage_system.character_to_dict(character)
        if isinstance(state, dict):
            assets = self._load_mobile_assets()
            self._enrich_improvements(state, character)
            self._enrich_notes(state)
            state["_mobile_ui"] = {
                "icons": assets,
                "ability_options": self._mobile_ability_options(),
            }
        return state

    @staticmethod
    def _asset_key(value: str) -> str:
        value = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
        return value.strip("_")

    @staticmethod
    def _icon_match_key(value: str) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    @staticmethod
    def _read_svg_base64(path: str | None) -> str | None:
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
            return base64.b64encode(raw).decode("ascii") if raw else None
        except (OSError, ValueError):
            return None

    def _find_improvement_icon_path(self, improvement: Any, display_name: str = "") -> str | None:
        """Mirror the desktop improvement-icon matching rules on Windows."""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(app_dir, "icons", "improvements")
        if not os.path.isdir(icon_dir):
            return None

        candidates: list[str] = []
        choices = getattr(improvement, "choices", {}) or {}
        if str(getattr(improvement, "catalog_id", "")) == "custom":
            chosen = str(choices.get("_custom_icon", "") or "").strip()
            if chosen and os.path.basename(chosen) == chosen:
                candidates.append(chosen.removesuffix(".svg"))
        candidates.extend([
            str(getattr(improvement, "catalog_id", "") or ""),
            str(getattr(improvement, "name", "") or ""),
            str(display_name or ""),
        ])
        candidates = [value.strip() for value in candidates if value and value.strip()]

        for candidate in candidates:
            for filename in (
                f"{candidate}.svg",
                f"{candidate.lower()}.svg",
                f"{self._asset_key(candidate)}.svg",
            ):
                path = os.path.join(icon_dir, filename)
                if os.path.isfile(path):
                    return path

        wanted = {self._icon_match_key(candidate) for candidate in candidates}
        try:
            for filename in os.listdir(icon_dir):
                if filename.lower().endswith(".svg") and self._icon_match_key(os.path.splitext(filename)[0]) in wanted:
                    return os.path.join(icon_dir, filename)
        except OSError:
            return None
        return None

    @staticmethod
    def _required_choice_keys(option: dict | None) -> list[str]:
        if not isinstance(option, dict):
            return []
        required = option.get("required_choices")
        if isinstance(required, dict):
            return [str(key) for key in required.keys() if str(key) and not str(key).startswith("_")]
        if isinstance(required, (list, tuple)):
            keys = []
            for item in required:
                if isinstance(item, str):
                    key = item
                elif isinstance(item, dict):
                    key = str(item.get("key") or item.get("id") or item.get("name") or "")
                else:
                    key = ""
                if key and not key.startswith("_"):
                    keys.append(key)
            return keys
        return []

    def _enrich_improvements(self, state: dict, character: Any) -> None:
        state_items = (
            state.get("improvements", {}).get("list_of_taken_improvements", [])
            if isinstance(state.get("improvements"), dict) else []
        )
        character_system = getattr(character, "improvements", None)
        live_items = list(getattr(character_system, "list_of_taken_improvements", []) or [])
        if not isinstance(state_items, list) or not live_items:
            return

        try:
            from backend_2_1 import ImprovementSystem, ImprovementCatalogSystem  # type: ignore
        except ImportError:
            return

        live_by_id = {str(getattr(item, "id", "")): item for item in live_items if getattr(item, "id", None)}
        notes = list(getattr(getattr(character, "notes", None), "list_of_notes", []) or [])

        for index, serialized in enumerate(state_items):
            if not isinstance(serialized, dict):
                continue
            live = live_by_id.get(str(serialized.get("id", "")))
            if live is None and index < len(live_items):
                live = live_items[index]
            if live is None:
                continue

            try:
                display = ImprovementSystem.build_improvement_display(character, live) or {}
            except Exception:
                display = {}

            serialized["_mobile_display_summary"] = str(display.get("summary") or "")
            serialized["_mobile_display_details"] = str(display.get("details") or "")
            serialized["_mobile_display_choices"] = [str(line) for line in (display.get("choices") or []) if str(line).strip()]
            serialized["_mobile_display_upgrades"] = [str(line) for line in (display.get("upgrades") or []) if str(line).strip()]

            catalog_id = str(getattr(live, "catalog_id", "") or "")
            try:
                option = ImprovementCatalogSystem.get_option(catalog_id, character)
            except TypeError:
                option = ImprovementCatalogSystem.get_option(catalog_id)
            except Exception:
                option = None
            editable_keys = self._required_choice_keys(option)
            custom = catalog_id == "custom" or str(getattr(live, "source", "")) == "custom"
            serialized["_mobile_editable_choice_keys"] = editable_keys
            serialized["_mobile_editable"] = bool(custom or editable_keys)

            icon_path = self._find_improvement_icon_path(live, str(display.get("name") or ""))
            icon_svg = self._read_svg_base64(icon_path)
            if icon_svg:
                serialized["_mobile_icon_svg"] = icon_svg

            improvement_id = str(getattr(live, "id", "") or "")
            linked = next(
                (note for note in notes if str(getattr(note, "linked_improvement_id", "") or "") == improvement_id),
                None,
            )
            if linked is None:
                target_title = None
                if catalog_id in {"spellcasting", "magic_novice"}:
                    target_title = "spellcasting verbs"
                elif catalog_id == "sneak_attack":
                    target_title = "sneak attack"
                if target_title:
                    linked = next(
                        (note for note in notes if str(getattr(note, "title", "") or "").strip().lower() == target_title),
                        None,
                    )
            if linked is not None and getattr(linked, "id", None):
                serialized["_mobile_linked_note_id"] = str(linked.id)

    def _enrich_notes(self, state: dict) -> None:
        notes = state.get("notes", {}).get("list_of_notes", []) if isinstance(state.get("notes"), dict) else []
        if not isinstance(notes, list):
            return
        for note in notes:
            if not isinstance(note, dict):
                continue
            raw = str(note.get("color") or "").strip()
            if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
                note["_mobile_display_color"] = raw
            else:
                note["_mobile_display_color"] = self._NOTE_COLORS.get(raw.lower(), self._NOTE_COLORS["yellow"])

            title = str(note.get("title") or "").strip().lower()
            linked = bool(str(note.get("linked_improvement_id") or "").strip())
            system = title in {"spellcasting verbs", "sneak attack"} or (title == "animal buddy" and linked)
            note["_mobile_editable"] = not (linked or system)

    def _mobile_ability_options(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        provider = getattr(self.window, "_available_roll_modifier_options", None)
        if not callable(provider):
            return result
        for stat_key in ("agility", "finesse", "instinct", "knowledge", "presence", "strength"):
            try:
                options = provider(stat_key) or []
                result[stat_key] = [
                    {
                        "kind": str(item.get("kind") or "bonus_die"),
                        "label": str(item.get("label") or item.get("short_label") or "Die"),
                        "short_label": str(item.get("short_label") or "die"),
                        "sides": int(item.get("sides", 6)),
                        "sign": -1 if int(item.get("sign", 1)) < 0 else 1,
                        "explode": bool(item.get("explode", False)),
                    }
                    for item in options if isinstance(item, dict)
                ]
            except Exception:
                result[stat_key] = []
        return result

    def _frontend_presentation_globals(self) -> dict:
        """Read the exact constants used by the live desktop frontend."""
        for name in ("open_dice_options_for_stat", "show_character_page", "refresh_ui"):
            method = getattr(self.window, name, None)
            function = getattr(method, "__func__", method)
            namespace = getattr(function, "__globals__", None)
            if isinstance(namespace, dict):
                return namespace
        return {}

    def _load_mobile_assets(self) -> dict[str, str]:
        """Return desktop-owned artwork/help used by the Android presentation."""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        paths = {
            "agility": os.path.join(app_dir, "icons", "agility.svg"),
            "finesse": os.path.join(app_dir, "icons", "finesse.svg"),
            "instinct": os.path.join(app_dir, "icons", "instinct.svg"),
            "knowledge": os.path.join(app_dir, "icons", "knowledge.svg"),
            "presence": os.path.join(app_dir, "icons", "presence.svg"),
            "strength": os.path.join(app_dir, "icons", "strength.svg"),
            "bdv": os.path.join(app_dir, "icons", "defenses", "bdv.svg"),
            "dr": os.path.join(app_dir, "icons", "defenses", "dr.svg"),
            "inventory": os.path.join(app_dir, "icons", "headers", "inventory.svg"),
        }
        for candidate in (
            os.path.join(app_dir, "icons", "notes", "custom.svg"),
            os.path.join(app_dir, "icons", "headers", "notes.svg"),
            os.path.join(app_dir, "icons", "notes.svg"),
        ):
            if os.path.isfile(candidate):
                paths["notes"] = candidate
                break

        improvement_dir = os.path.join(app_dir, "icons", "improvements")
        if os.path.isdir(improvement_dir):
            for root, _dirs, files in os.walk(improvement_dir):
                for filename in files:
                    if not filename.lower().endswith(".svg"):
                        continue
                    path = os.path.join(root, filename)
                    stem = os.path.splitext(filename)[0]
                    key = self._asset_key(stem)
                    if key:
                        paths.setdefault(f"improvement:{key}", path)
                        paths.setdefault(f"improvement-name:{key}", path)

        result: dict[str, str] = {}
        for key, path in paths.items():
            encoded = self._read_svg_base64(path)
            if encoded:
                result[key] = encoded

        namespace = self._frontend_presentation_globals()
        ability_accents = namespace.get("ABILITY_ACCENTS", {})
        ability_descriptions = namespace.get("ABILITY_DESCRIPTIONS", {})
        rows = getattr(self.window, "stat_rows", {}) or {}
        stats = getattr(self._character(), "stats", None)

        for stat_key in ("agility", "finesse", "instinct", "knowledge", "presence", "strength"):
            row = rows.get(stat_key) if isinstance(rows, dict) else None
            help_text = getattr(row, "_ability_tooltip_text", None) if row is not None else None
            accent = getattr(row, "_ability_tooltip_accent", None) if row is not None else None

            if not isinstance(help_text, str) or not help_text.strip():
                help_text = ability_descriptions.get(stat_key) if isinstance(ability_descriptions, dict) else None
            if not accent:
                accent = ability_accents.get(stat_key) if isinstance(ability_accents, dict) else None

            if isinstance(help_text, str) and help_text.strip():
                result[f"ability-help:{stat_key}"] = help_text.strip()
            if isinstance(accent, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", accent.strip()):
                result[f"ability-color:{stat_key}"] = accent.strip()

            if f"ability-help:{stat_key}" not in result:
                stat = stats.get_stat(stat_key) if stats is not None and hasattr(stats, "get_stat") else None
                if stat is not None:
                    for attr in ("tooltip", "tool_tip", "help_text", "description", "info", "explanation"):
                        value = getattr(stat, attr, None)
                        if isinstance(value, str) and value.strip():
                            result[f"ability-help:{stat_key}"] = value.strip()
                            break

        return result

    def command_handler(self, action: str, payload: dict, base_revision: int, request_id: str) -> Optional[dict]:
        del base_revision, request_id
        self._ensure_editable()
        if not isinstance(payload, dict):
            raise MobileSyncValidationError("Command payload must be an object")

        try:
            from .mobile_sync_v7 import handle_mobile_v7_action
        except ImportError:
            from mobile_sync_v7 import handle_mobile_v7_action
        v7 = handle_mobile_v7_action(self, action, payload)
        if v7.handled:
            if v7.mutated:
                self._validate_character()
                self._persist_and_refresh()
            return v7.result

        if action == "resource.change":
            self._handle_resource_change(payload)
        elif action == "identity.set":
            self._set_identity(payload)
        elif action == "inventory.add":
            self._inventory_add(payload)
        elif action == "inventory.update":
            self._inventory_update(payload)
        elif action == "inventory.remove":
            self._inventory_remove(payload)
        else:
            raise MobileSyncValidationError(f"Unsupported mobile action: {action}")

        self._validate_character()
        self._persist_and_refresh()
        return None

    # ------------------------------------------------------------------
    # Shared validation helpers
    # ------------------------------------------------------------------
    def _ensure_editable(self) -> None:
        readonly_check = getattr(self.window, "is_readonly_character", None)
        if callable(readonly_check) and bool(readonly_check()):
            raise MobileSyncValidationError(
                "This character is read-only on the computer and cannot be changed from the phone"
            )

    def _character(self) -> Any:
        character = getattr(self.window, "character", None)
        if character is None:
            raise MobileSyncValidationError("No character is currently open on the computer")
        return character

    def _validate_character(self) -> None:
        validate = getattr(self._character(), "validate", None)
        if callable(validate):
            validate()

    @staticmethod
    def _required_id(payload: dict, field: str = "id") -> str:
        value = str(payload.get(field, "")).strip()
        if not value or len(value) > 160:
            raise MobileSyncValidationError(f"Invalid {field}")
        return value

    @staticmethod
    def _bounded_text(value: Any, *, label: str, maximum: int, strip: bool = False) -> str:
        text = str(value if value is not None else "")
        if strip:
            text = text.strip()
        if len(text) > maximum:
            raise MobileSyncValidationError(f"{label} is too long")
        return text

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------
    def _handle_resource_change(self, payload: dict) -> None:
        resource = str(payload.get("resource", ""))
        try:
            delta = int(payload.get("delta", 0))
        except (TypeError, ValueError) as exc:
            raise MobileSyncValidationError("Resource delta must be an integer") from exc

        if delta == 0:
            raise MobileSyncValidationError("Resource change cannot be zero")
        if abs(delta) > 100:
            raise MobileSyncValidationError("Resource change is too large")

        if resource == "HP":
            self._change_hp(delta)
        elif resource == "Adversity":
            self._change_adversity(delta)
        elif resource == "IP":
            self._change_ip(delta)
        else:
            raise MobileSyncValidationError(f"Unknown resource: {resource}")

    def _change_hp(self, delta: int) -> None:
        if self.hooks.hp_change is not None:
            self.hooks.hp_change(delta)
            return
        hp = getattr(self._character(), "HP", None)
        if hp is None:
            raise MobileSyncValidationError("This character has no HP resource")
        current = int(getattr(hp, "current_HP"))
        maximum = int(getattr(hp, "max_HP"))
        target = current + delta
        if target < 0 or target > maximum:
            raise MobileSyncValidationError(f"HP must stay between 0 and {maximum}")
        hp.current_HP = target

    def _change_adversity(self, delta: int) -> None:
        if self.hooks.adversity_change is not None:
            self.hooks.adversity_change(delta)
            return
        adversity = getattr(self._character(), "adversity", None)
        if adversity is None:
            raise MobileSyncValidationError("This character has no Adversity Token resource")
        current = int(getattr(adversity, "current_AT"))
        maximum = int(getattr(adversity, "max_AT"))
        target = current + delta
        if target < 0 or target > maximum:
            raise MobileSyncValidationError(f"Adversity Tokens must stay between 0 and {maximum}")
        adversity.current_AT = target

    def _change_ip(self, delta: int) -> None:
        if self.hooks.ip_change is not None:
            self.hooks.ip_change(delta)
            return
        progression = getattr(self._character(), "progression", None)
        if progression is None:
            raise MobileSyncValidationError("This character has no Improvement Point resource")
        current = int(getattr(progression, "current_IP"))
        target = current + delta
        if target < 0:
            raise MobileSyncValidationError("Improvement Points cannot be negative")
        progression.current_IP = target

    # ------------------------------------------------------------------
    # Simple direct editing: identity + inventory
    # ------------------------------------------------------------------
    def _set_identity(self, payload: dict) -> None:
        field = str(payload.get("field", "")).strip()
        character = self._character()
        if field == "name":
            character.name = self._bounded_text(payload.get("value", ""), label="Character name", maximum=self.MAX_NAME_CHARS, strip=True)
        elif field == "backstory":
            character.backstory = self._bounded_text(payload.get("value", ""), label="Backstory", maximum=self.MAX_BACKSTORY_CHARS)
        else:
            raise MobileSyncValidationError(f"Identity field cannot be edited from mobile: {field}")

    def _inventory(self) -> Any:
        inventory = getattr(self._character(), "inventory", None)
        if inventory is None or not hasattr(inventory, "list_of_items"):
            raise MobileSyncValidationError("This character has no inventory")
        return inventory

    def _inventory_add(self, payload: dict) -> None:
        name = self._bounded_text(payload.get("name", ""), label="Item name", maximum=self.MAX_NAME_CHARS, strip=True)
        description = self._bounded_text(payload.get("description", ""), label="Item description", maximum=self.MAX_ITEM_DESCRIPTION_CHARS)
        try:
            quantity = max(0, int(payload.get("quantity", 1)))
        except (TypeError, ValueError) as exc:
            raise MobileSyncValidationError("Item quantity must be a number") from exc
        if quantity > 1_000_000:
            raise MobileSyncValidationError("Item quantity is too large")

        inventory = self._inventory()
        item_type = self._inventory_item_type(inventory)
        inventory.list_of_items.append(item_type(id=str(uuid4()), name=name, description=description, quantity=quantity, expanded=True))

    def _inventory_update(self, payload: dict) -> None:
        item_id = self._required_id(payload)
        item = self._find_inventory_item(item_id)
        if "name" in payload:
            item.name = self._bounded_text(payload.get("name", ""), label="Item name", maximum=self.MAX_NAME_CHARS, strip=True)
        if "description" in payload:
            item.description = self._bounded_text(payload.get("description", ""), label="Item description", maximum=self.MAX_ITEM_DESCRIPTION_CHARS)
        if "quantity" in payload:
            try:
                quantity = max(0, int(payload.get("quantity", 0)))
            except (TypeError, ValueError) as exc:
                raise MobileSyncValidationError("Item quantity must be a number") from exc
            if quantity > 1_000_000:
                raise MobileSyncValidationError("Item quantity is too large")
            item.quantity = quantity
        if "expanded" in payload:
            item.expanded = bool(payload.get("expanded"))

    def _inventory_remove(self, payload: dict) -> None:
        item_id = self._required_id(payload)
        inventory = self._inventory()
        original_count = len(inventory.list_of_items)
        inventory.list_of_items = [item for item in inventory.list_of_items if str(item.id) != item_id]
        if len(inventory.list_of_items) == original_count:
            raise MobileSyncValidationError("Inventory item no longer exists")

    def _find_inventory_item(self, item_id: str) -> Any:
        for item in self._inventory().list_of_items:
            if str(getattr(item, "id", "")) == item_id:
                return item
        raise MobileSyncValidationError("Inventory item no longer exists")

    @staticmethod
    def _inventory_item_type(inventory: Any):
        existing = list(getattr(inventory, "list_of_items", []))
        if existing:
            return type(existing[0])
        try:
            from backend_2_1 import InventoryItem  # type: ignore
        except ImportError as exc:
            raise MobileSyncValidationError("The desktop build cannot create inventory items from mobile") from exc
        return InventoryItem

    # ------------------------------------------------------------------
    # Desktop persistence / refresh
    # ------------------------------------------------------------------
    def _persist_and_refresh(self) -> None:
        if self.hooks.save_after_change is not None:
            self.hooks.save_after_change()
        else:
            mark_dirty = getattr(self.window, "mark_dirty", None)
            if not callable(mark_dirty):
                raise RuntimeError("Desktop frontend does not expose mark_dirty; provide save_after_change hook")
            mark_dirty(auto_save=True)

        if self.hooks.refresh_after_change is not None:
            self.hooks.refresh_after_change()
        else:
            refresh = getattr(self.window, "refresh_ui", None)
            if callable(refresh):
                refresh()
