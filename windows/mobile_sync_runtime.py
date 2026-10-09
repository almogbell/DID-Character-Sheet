"""Runtime integration for the finished DID desktop window.

This is the only Phase 8 object the main frontend needs to own.  It wires the
existing character model to MobileSyncServer, opens the pairing/device dialog,
and observes desktop-originated state changes without replacing any DID rules.

The observer deliberately compares canonical CharacterStorageSystem snapshots.
That means edits made anywhere in the existing PySide6 UI are detected even if
they come from different widgets/mixins.  Android commands are still routed
through DesktopSyncAdapter and Windows remains authoritative.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer

try:
    from .mobile_companion_dialog import MobileCompanionDialog
    from .mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
    from .mobile_sync_server import MobileSyncServer
except ImportError:
    from mobile_companion_dialog import MobileCompanionDialog
    from mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
    from mobile_sync_server import MobileSyncServer


class MobileCompanionRuntime(QObject):
    """Own the desktop sync server for one running main window."""

    def __init__(
        self,
        *,
        window: Any,
        storage_system: Any,
        desktop_version: str,
        poll_interval_ms: int = 350,
        parent: Optional[QObject] = None,
    ) -> None:
        qt_parent = parent if parent is not None else window
        super().__init__(qt_parent)
        self.window = window
        self.storage_system = storage_system
        self._dialog: Optional[MobileCompanionDialog] = None

        hooks = FrontendHooks(
            save_after_change=self._save_mobile_change,
            refresh_after_change=self._refresh_after_mobile_change,
        )
        self.adapter = DesktopSyncAdapter(window, storage_system, hooks)
        self.server = MobileSyncServer(
            desktop_version=desktop_version,
            state_provider=self.adapter.state_provider,
            command_handler=self._handle_mobile_command,
            parent=self,
        )

        self._last_character_id: Optional[str] = None
        self._last_fingerprint: Optional[str] = None
        self._remember_current_state()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(max(150, int(poll_interval_ms)))
        self._poll_timer.timeout.connect(self._poll_desktop_state)
        self._poll_timer.start()

    # ------------------------------------------------------------------
    # Public UI API
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        if self._dialog is None:
            self._dialog = MobileCompanionDialog(self.server, self.window)
            self._dialog.finished.connect(self._dialog_closed)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def shutdown(self) -> None:
        self._poll_timer.stop()
        self.server.stop()
        if self._dialog is not None:
            try:
                self._dialog.close()
            except RuntimeError:
                pass
            self._dialog = None

    # ------------------------------------------------------------------
    # Mobile command path
    # ------------------------------------------------------------------
    def _handle_mobile_command(
        self,
        action: str,
        payload: dict,
        base_revision: int,
        request_id: str,
    ) -> None:
        self.adapter.command_handler(action, payload, base_revision, request_id)
        # MobileSyncServer increments/broadcasts this accepted command itself.
        # Updating our baseline prevents the observer from counting it twice.
        self._remember_current_state()

    def _save_mobile_change(self) -> None:
        mark_dirty = getattr(self.window, "mark_dirty", None)
        if not callable(mark_dirty):
            raise RuntimeError("DID frontend does not expose mark_dirty")
        mark_dirty(auto_save=True)

    def _refresh_after_mobile_change(self) -> None:
        refresh = getattr(self.window, "refresh_all", None)
        if not callable(refresh):
            raise RuntimeError("DID frontend does not expose refresh_all")
        refresh()

    # ------------------------------------------------------------------
    # Desktop-originated changes
    # ------------------------------------------------------------------
    def _poll_desktop_state(self) -> None:
        # There is no reason to serialize repeatedly before the companion server
        # has ever been started.  begin_pairing() starts it.
        if not self.server.is_listening():
            self._remember_current_state()
            return

        character_id, fingerprint = self._current_identity_and_fingerprint()
        if character_id != self._last_character_id:
            self._last_character_id = character_id
            self._last_fingerprint = fingerprint
            self.server.notify_active_character_changed()
            return

        if fingerprint != self._last_fingerprint:
            self._last_fingerprint = fingerprint
            self.server.notify_desktop_change()

    def _remember_current_state(self) -> None:
        character_id, fingerprint = self._current_identity_and_fingerprint()
        self._last_character_id = character_id
        self._last_fingerprint = fingerprint

    def _current_identity_and_fingerprint(self) -> tuple[Optional[str], str]:
        state = self.adapter.state_provider()
        if state is None:
            return None, "none"
        character_id = str(state.get("id") or "").strip() or None
        encoded = json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return character_id, hashlib.sha256(encoded).hexdigest()

    def _dialog_closed(self, *_args) -> None:
        # Keep the server alive when the management dialog is closed; paired
        # phones should continue to work for the rest of the desktop session.
        self._dialog = None
