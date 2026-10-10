"""Adapter between the finished DID desktop window and the mobile companion.

Windows remains authoritative. Every accepted phone mutation is applied to the
same in-memory character used by the desktop UI, then routed through the normal
``mark_dirty(auto_save=True)`` and refresh path. The adapter intentionally owns
no save files and duplicates no improvement/game rules.
"""

from __future__ import annotations

import base64
import os
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
            # The phone should use the exact current desktop artwork instead of
            # reimplementing or freezing fallback icons in Kotlin. These extra
            # mobile-only keys never enter the .didchar save format.
            state["_mobile_ui"] = {
                "icons": self._load_mobile_svg_assets(),
            }
        return state

    def _load_mobile_svg_assets(self) -> dict[str, str]:
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
        }
        result: dict[str, str] = {}
        for key, path in paths.items():
            try:
                with open(path, "rb") as handle:
                    raw = handle.read()
                if raw:
                    result[key] = base64.b64encode(raw).decode("ascii")
            except (OSError, ValueError):
                # A missing custom asset should not break synchronization. The
                # Android UI has a conservative fallback for absent artwork.
                continue
        return result

    def command_handler(self, action: str, payload: dict, base_revision: int, request_id: str) -> None:
        del base_revision, request_id  # revision validation belongs to MobileSyncServer
        self._ensure_editable()
        if not isinstance(payload, dict):
            raise MobileSyncValidationError("Command payload must be an object")

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
            character.name = self._bounded_text(
                payload.get("value", ""),
                label="Character name",
                maximum=self.MAX_NAME_CHARS,
                strip=True,
            )
        elif field == "backstory":
            character.backstory = self._bounded_text(
                payload.get("value", ""),
                label="Backstory",
                maximum=self.MAX_BACKSTORY_CHARS,
            )
        else:
            raise MobileSyncValidationError(f"Identity field cannot be edited from mobile: {field}")

    def _inventory(self) -> Any:
        inventory = getattr(self._character(), "inventory", None)
        if inventory is None or not hasattr(inventory, "list_of_items"):
            raise MobileSyncValidationError("This character has no inventory")
        return inventory

    def _inventory_add(self, payload: dict) -> None:
        name = self._bounded_text(
            payload.get("name", ""),
            label="Item name",
            maximum=self.MAX_NAME_CHARS,
            strip=True,
        )
        description = self._bounded_text(
            payload.get("description", ""),
            label="Item description",
            maximum=self.MAX_ITEM_DESCRIPTION_CHARS,
        )
        try:
            quantity = max(0, int(payload.get("quantity", 1)))
        except (TypeError, ValueError) as exc:
            raise MobileSyncValidationError("Item quantity must be a number") from exc
        if quantity > 1_000_000:
            raise MobileSyncValidationError("Item quantity is too large")

        inventory = self._inventory()
        item_type = self._inventory_item_type(inventory)
        inventory.list_of_items.append(
            item_type(
                id=str(uuid4()),
                name=name,
                description=description,
                quantity=quantity,
                expanded=True,
            )
        )

    def _inventory_update(self, payload: dict) -> None:
        item_id = self._required_id(payload)
        item = self._find_inventory_item(item_id)

        if "name" in payload:
            item.name = self._bounded_text(
                payload.get("name", ""),
                label="Item name",
                maximum=self.MAX_NAME_CHARS,
                strip=True,
            )
        if "description" in payload:
            item.description = self._bounded_text(
                payload.get("description", ""),
                label="Item description",
                maximum=self.MAX_ITEM_DESCRIPTION_CHARS,
            )
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
            raise MobileSyncValidationError(
                "The desktop build cannot create inventory items from mobile"
            ) from exc
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
