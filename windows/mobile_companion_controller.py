"""High-level installer/controller for Phase 8 mobile companion support.

This module keeps the finished frontend changes intentionally small.  The final
Windows main window can create one controller and expose its dialog from the
existing Tools menu.  The controller owns the adapter/server/dialog and provides
explicit notifications for desktop-originated state changes.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QObject

from mobile_companion_dialog import MobileCompanionDialog
from mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
from mobile_sync_server import MobileSyncServer


class MobileCompanionController(QObject):
    """Bind a finished DID main window to the Phase 8 sync transport."""

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
        self.adapter = DesktopSyncAdapter(window, storage_system, hooks=hooks)
        self.server = MobileSyncServer(
            desktop_version=app_version,
            state_provider=self.adapter.state_provider,
            command_handler=self.adapter.command_handler,
            parent=self,
        )
        self._dialog: Optional[MobileCompanionDialog] = None

    def show_dialog(self) -> None:
        if self._dialog is None:
            self._dialog = MobileCompanionDialog(self.server, self.window)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def desktop_state_changed(self) -> None:
        """Call after a desktop-originated mutation has reached canonical state."""
        if self.server.is_listening():
            self.server.notify_desktop_change()

    def active_character_changed(self) -> None:
        """Call after new/load/restore replaces the active character."""
        if self.server.is_listening():
            self.server.notify_active_character_changed()

    def shutdown(self) -> None:
        self.server.stop()


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
    # Keep a strong lifetime reference on the window.  Qt parent ownership is
    # also present, but this makes the integration explicit and easy to inspect.
    window.mobile_companion = controller
    return controller
