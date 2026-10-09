"""Adapter between the finished DID desktop window and MobileSyncServer.

This module deliberately keeps the network layer separate from DID rules. It
wraps the existing desktop object model and uses CharacterStorageSystem for the
canonical state snapshot.

The adapter is intentionally conservative: it only implements the Phase 8
resource slice (HP / Adversity / IP), validates bounds before mutation, respects
read-only characters, marks the character dirty through the desktop window's
normal path, and asks the desktop UI to refresh. It does not read or write
.didchar files itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


class MobileSyncValidationError(ValueError):
    """User-facing validation failure returned to the Android companion."""


@dataclass
class FrontendHooks:
    """Optional explicit hooks for the finished desktop frontend.

    Supplying hooks is preferred when the final app has a dedicated method for a
    resource change or refresh. If a hook is omitted, the adapter falls back to
    the stable object-model fields which have existed in the desktop app.
    """

    save_after_change: Optional[Callable[[], None]] = None
    refresh_after_change: Optional[Callable[[], None]] = None
    hp_change: Optional[Callable[[int], None]] = None
    adversity_change: Optional[Callable[[int], None]] = None
    ip_change: Optional[Callable[[int], None]] = None


class DesktopSyncAdapter:
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
        return self.storage_system.character_to_dict(character)

    def command_handler(self, action: str, payload: dict, base_revision: int, request_id: str) -> None:
        del base_revision, request_id  # revision validation belongs to MobileSyncServer
        self._ensure_editable()

        if action != "resource.change":
            raise MobileSyncValidationError(f"Unsupported mobile action: {action}")

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

        self._persist_and_refresh()

    # ------------------------------------------------------------------
    # Resource mutations
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

    def _change_hp(self, delta: int) -> None:
        if self.hooks.hp_change is not None:
            self.hooks.hp_change(delta)
            return

        character = self._character()
        hp = getattr(character, "HP", None)
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

        character = self._character()
        adversity = getattr(character, "adversity", None)
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

        character = self._character()
        progression = getattr(character, "progression", None)
        if progression is None:
            raise MobileSyncValidationError("This character has no Improvement Point resource")
        current = int(getattr(progression, "current_IP"))
        target = current + delta
        if target < 0:
            raise MobileSyncValidationError("Improvement Points cannot be negative")
        progression.current_IP = target

    # ------------------------------------------------------------------
    # Desktop persistence / refresh
    # ------------------------------------------------------------------
    def _persist_and_refresh(self) -> None:
        # Prefer the finished app's existing dirty/autosave path. This preserves
        # recovery/history behavior instead of making the mobile layer invent a
        # second save implementation.
        if self.hooks.save_after_change is not None:
            self.hooks.save_after_change()
        else:
            mark_dirty = getattr(self.window, "mark_dirty", None)
            if not callable(mark_dirty):
                raise RuntimeError("Desktop frontend does not expose mark_dirty; provide save_after_change hook")
            mark_dirty(auto_save=True)

        if self.hooks.refresh_after_change is not None:
            self.hooks.refresh_after_change()
