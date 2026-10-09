"""High-level installer/controller for Phase 8 mobile companion support.

The controller keeps finished-frontend changes intentionally small. It owns the
adapter/server/dialog, watches canonical desktop character state for changes,
and injects a Mobile Companion action into the existing DID Tools menu when that
menu is shown.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QMenu

try:  # package imports used by tests / repository tooling
    from .mobile_companion_dialog import MobileCompanionDialog
    from .mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
    from .mobile_sync_server import MobileSyncServer
except ImportError:  # sibling imports used by the packaged desktop app
    from mobile_companion_dialog import MobileCompanionDialog
    from mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
    from mobile_sync_server import MobileSyncServer


def normalize_menu_text(text: str) -> str:
    """Normalize Qt mnemonic markers without depending on a QWidget instance."""
    return str(text).replace("&", "").strip()


def is_did_tools_menu(action_texts: Iterable[str]) -> bool:
    """Return True only for the DID Tools menu signature used by the frontend."""
    texts = {normalize_menu_text(text) for text in action_texts}
    return "Check for Updates" in texts and "Load Character" in texts


def mobile_companion_insert_index(action_texts: Iterable[str]) -> Optional[int]:
    """Return where Mobile Companion belongs, or None when it should not be added."""
    texts = [normalize_menu_text(text) for text in action_texts]
    if not is_did_tools_menu(texts) or MobileCompanionController.TOOLS_ACTION_TEXT in texts:
        return None
    try:
        return texts.index("Check for Updates")
    except ValueError:
        return len(texts)


class MobileCompanionController(QObject):
    """Bind a finished DID main window to the Phase 8 sync transport."""

    POLL_INTERVAL_MS = 500
    TOOLS_ACTION_TEXT = "Mobile Companion"

    def __init__(
        self,
        *,
        window: Any,
        storage_system: Any,
        app_version: str,
        hooks: Optional[FrontendHooks] = None,
        install_tools_event_filter: bool = True,
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
        self._event_filter_installed = False

        # Paired phones must be able to reconnect as soon as the Windows app
        # starts, without requiring the user to open the pairing dialog first.
        self.server.start()
        self._capture_baseline()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_desktop_state)
        self._poll_timer.start()

        # Avoid forcing the finished frontend's existing toggle_tools_menu()
        # implementation to be rewritten. Its QMenu is parented to the main
        # window; when it is shown we recognize it by its normal DID actions and
        # add Mobile Companion once. Headless unit tests can explicitly disable
        # this global QApplication event filter while production keeps it on.
        if install_tools_event_filter:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
                self._event_filter_installed = True

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
        app = QApplication.instance()
        if self._event_filter_installed and app is not None:
            app.removeEventFilter(self)
            self._event_filter_installed = False
        self.server.stop()

    # ------------------------------------------------------------------
    # Existing Tools menu integration
    # ------------------------------------------------------------------
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QMenu):
            self._maybe_add_tools_action(watched)
        return super().eventFilter(watched, event)

    def _maybe_add_tools_action(self, menu: QMenu) -> None:
        if menu.parent() is not self.window:
            return

        actions = list(menu.actions())
        insertion_index = mobile_companion_insert_index(action.text() for action in actions)
        if insertion_index is None:
            return

        before = actions[insertion_index] if insertion_index < len(actions) else None
        companion_action = (
            menu.insertAction(before, self.TOOLS_ACTION_TEXT)
            if before is not None
            else menu.addAction(self.TOOLS_ACTION_TEXT)
        )
        companion_action.triggered.connect(self.show_dialog)

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
        # callback returns. Capture the new signature here so the poller does
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
