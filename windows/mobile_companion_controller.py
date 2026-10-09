"""High-level installer/controller for Phase 8 mobile companion support.

The controller keeps finished-frontend changes intentionally small.  It owns the
adapter/server/dialog and watches the canonical desktop character state for
changes, so existing HP/AT/IP/UI code does not need to be individually patched
just to notify Android.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer

from mobile_companion_dialog import MobileCompanionDialog
from mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
from mobile_sync_server import MobileSyncServer


class MobileCompanionController(QObject):
    """Bind a finished DID main window to the Phase 8 sync transport."""

    POLL_INTERVAL_MS = 500

    def __init__(
        self,
        *,
        window: Any,
        storage_system: Any,
        app_version: str,
        hooks: Optional[FrontendHooks] = None,
    ) -> None:
        super().__init__(window)
        self.window = window

        if hooks is None:
            refresh = getattr(window, "refresh_all", None)
            hooks = FrontendHooks(
                refresh_after_change=refresh if callable(refresh) else None,
            )

        self.adapter = DesktopSyncAdapter(window, storage_system, hooks=hooks)
        self.server = MobileSyncServer(
            desktop_version=app_version,
            state_provider=self.adapter.state_provider,
            command_handler=self._handle_mobile_command,
            parent=self,
        )
        self._dialog: Optional[MobileCompanionDialog] = None
        self._last_signature: Optional[str] = None
        self._last_character_id: Optional[str] = None

        # Paired phones must be able to reconnect as soon as the Windows app
        # starts, without requiring the user to open the pairing dialog first.
        self.server.start()
        self._capture_baseline()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_desktop_state)
        self._poll_timer.start()

    def show_dialog(self) -> None:
        if self._dialog is None:
            self._dialog = MobileCompanionDialog(self.server, self.window)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def desktop_state_changed(self) -> None:
        """Optional explicit notification; polling already covers this path."""
        self._capture_and_broadcast(force_character_event=False)

    def active_character_changed(self) -> None:
        """Optional explicit notification; polling already covers this path."""
        self._capture_and_broadcast(force_character_event=True)

    def shutdown(self) -> None:
        self._poll_timer.stop()
        self.server.stop()

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
        # MobileSyncServer will increment/broadcast immediately after this
        # callback returns.  Capture the new signature here so the poller does
        # not interpret the same mobile mutation as a second desktop mutation.
        self._capture_baseline()

    # ------------------------------------------------------------------
    # Desktop-originated state watcher
    # ------------------------------------------------------------------
    def _poll_desktop_state(self) -> None:
        if not self.server.is_listening():
            return
        self._capture_and_broadcast(force_character_event=False)

    def _capture_and_broadcast(self, *, force_character_event: bool) -> None:
        state = self.adapter.state_provider()
        signature = self._signature(state)
        character_id = self._character_id(state)

        if self._last_signature is None:
            self._last_signature = signature
            self._last_character_id = character_id
            return

        if signature == self._last_signature and not force_character_event:
            return

        character_changed = force_character_event or character_id != self._last_character_id
        self._last_signature = signature
        self._last_character_id = character_id

        if character_changed:
            self.server.notify_active_character_changed()
        else:
            self.server.notify_desktop_change()

    def _capture_baseline(self) -> None:
        state = self.adapter.state_provider()
        self._last_signature = self._signature(state)
        self._last_character_id = self._character_id(state)

    @staticmethod
    def _signature(state: Optional[dict]) -> str:
        raw = json.dumps(
            state,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _character_id(state: Optional[dict]) -> Optional[str]:
        if not isinstance(state, dict):
            return None
        value = state.get("id")
        return str(value) if value is not None else None


def install_mobile_companion(
    window: Any,
    storage_system: Any,
    app_version: str,
    *,
    hooks: Optional[FrontendHooks] = None,
) -> MobileCompanionController:
    """Convenience entry point used by the finished frontend."""
    controller = MobileCompanionController(
        window=window,
        storage_system=storage_system,
        app_version=app_version,
        hooks=hooks,
    )
    # Keep a strong lifetime reference on the window. Qt parent ownership is
    # also present, but this makes the integration explicit and easy to inspect.
    window.mobile_companion = controller
    return controller
