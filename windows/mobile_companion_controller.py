"""Connect the finished Windows DID UI to the Android sync server."""
from __future__ import annotations

import hashlib
import json
import traceback
from typing import Any, Iterable, Optional

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

try:
    from .mobile_companion_dialog import MobileCompanionDialog
    from .mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
    from .mobile_sync_server import MobileSyncServer
except ImportError:
    from mobile_companion_dialog import MobileCompanionDialog
    from mobile_sync_frontend_adapter import DesktopSyncAdapter, FrontendHooks
    from mobile_sync_server import MobileSyncServer


def normalize_menu_text(text: str) -> str:
    return str(text).replace("&", "").strip()


def is_did_tools_menu(action_texts: Iterable[str]) -> bool:
    texts = {normalize_menu_text(text) for text in action_texts}
    return {"New Character", "Load Character", "Edit Abilities"}.issubset(texts)


def mobile_companion_insert_index(
    action_texts: Iterable[str],
) -> Optional[int]:
    texts = [normalize_menu_text(text) for text in action_texts]
    if (
        not is_did_tools_menu(texts)
        or MobileCompanionController.TOOLS_ACTION_TEXT in texts
    ):
        return None
    for anchor in ("Dice Roller", "Update Available", "Check for Updates"):
        try:
            return texts.index(anchor)
        except ValueError:
            pass
    return len(texts)


def insert_menu_action(
    menu: QMenu,
    before: Optional[QAction],
    text: str,
    callback,
) -> QAction:
    action = QAction(text, menu)
    action.triggered.connect(callback)
    if before is not None:
        menu.insertAction(before, action)
    else:
        menu.addAction(action)
    return action


class MobileCompanionController(QObject):
    POLL_INTERVAL_MS = 1100  # UI hooks provide immediate updates; fallback poll is lightweight.
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
                refresh_after_change=(refresh if callable(refresh) else None),
            )

        self.adapter = DesktopSyncAdapter(
            window,
            storage_system,
            hooks=hooks,
        )
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
        self._shutdown = False
        self._last_phone_count: Optional[int] = None
        self._last_phone_devices: frozenset[str] = frozenset()
        self._last_phone_label = None

        # The signal is emitted after authentication/disconnect by the
        # WebSocket server. Always re-read the live sockets, not a cached
        # pairing count or a possibly stale signal argument.
        self.server.clientCountChanged.connect(self._refresh_phone_status)
        self.server.start()
        self._refresh_phone_status()
        self._capture_baseline()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_desktop_state)
        # A connection may be restored without a count-change event (e.g.
        # reconnect after a dropped socket). Keep the top-bar badge current.
        self._poll_timer.timeout.connect(self._refresh_phone_status)
        self._poll_timer.start()

        app = QApplication.instance()
        if install_tools_event_filter and app is not None:
            app.installEventFilter(self)
            self._event_filter_installed = True
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def show_dialog(self) -> None:
        if self._dialog is None:
            self._dialog = MobileCompanionDialog(self.server, self.window)
            self._dialog.finished.connect(self._dialog_finished)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def desktop_state_changed(self) -> None:
        self._capture_and_broadcast(force_character_event=False)

    def active_character_changed(self) -> None:
        self._capture_and_broadcast(force_character_event=True)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._poll_timer.stop()
        app = QApplication.instance()
        if self._event_filter_installed and app is not None:
            app.removeEventFilter(self)
            self._event_filter_installed = False
        self.server.stop()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QMenu):
            try:
                self._maybe_add_tools_action(watched)
            except Exception:
                traceback.print_exc()
        return super().eventFilter(watched, event)

    def _maybe_add_tools_action(self, menu: QMenu) -> None:
        if menu.parent() is not self.window:
            return
        actions = list(menu.actions())
        insertion_index = mobile_companion_insert_index(
            action.text() for action in actions
        )
        if insertion_index is None:
            return
        before = (
            actions[insertion_index]
            if insertion_index < len(actions)
            else None
        )
        insert_menu_action(
            menu,
            before,
            self.TOOLS_ACTION_TEXT,
            self.show_dialog,
        )

    def _handle_mobile_command(
        self,
        action: str,
        payload: dict,
        base_revision: int,
        request_id: str,
    ) -> Optional[dict]:
        result = self.adapter.command_handler(
            action,
            payload,
            base_revision,
            request_id,
        )
        self._capture_baseline()
        return result

    def _poll_desktop_state(self) -> None:
        # Reconnecting Android clients receive a canonical state in hello_ok.
        # Avoid serializing the entire character ~2 times/sec while offline.
        if not self.server.is_listening() or not self.server.connected_device_ids():
            return
        self._capture_and_broadcast(force_character_event=False)

    def _capture_and_broadcast(
        self,
        *,
        force_character_event: bool,
    ) -> None:
        state = self.adapter.state_provider()
        signature = self._signature(state)
        character_id = self._character_id(state)

        if self._last_signature is None:
            self._last_signature = signature
            self._last_character_id = character_id
            return
        if signature == self._last_signature and not force_character_event:
            return

        character_changed = (
            force_character_event
            or character_id != self._last_character_id
        )
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

    def _refresh_phone_status(self, *_signal_args) -> None:
        """Synchronize the Saved-area badge with *authenticated live sockets*.

        The server signals immediately on login/disconnect. The lightweight
        timer also heals a missed signal or a header widget replaced by Qt.
        Paired-but-offline phones are deliberately not counted.
        """
        if self._shutdown:
            return
        try:
            live_ids = frozenset(self.server.connected_device_ids())
        except RuntimeError:
            live_ids = frozenset()
        self._update_phone_status(live_ids)

    def _update_phone_status(self, live_ids) -> None:
        """Render a compact status without changing the header's geometry.

        In particular, do not shortcut on count alone: replacing the header
        QLabel or swapping one connected phone for another must repaint it.
        """
        if isinstance(live_ids, int):
            # Compatibility with older tests/callers that supplied a count.
            # The real device identities, not an untrusted count, determine
            # what the user sees.
            try:
                live_ids = self.server.connected_device_ids()
            except RuntimeError:
                live_ids = set()
        devices = frozenset(str(x) for x in live_ids if x)
        count = len(devices)
        self._last_phone_count = count
        label = getattr(self.window, "phone_connection_label", None)
        if label is None:
            self._last_phone_label = None
            self._last_phone_devices = devices
            return

        badge_text = (
            "● Phone connected" if count == 1
            else f"● {count} phones" if count else ""
        )
        tooltip = (
            f"{count} currently connected Pocket DID phone(s) • live sync active"
            if count else "No phone connected • paired phones may be offline"
        )
        try:
            already_rendered = (
                label is self._last_phone_label
                and devices == self._last_phone_devices
                and label.text() == badge_text
                and label.toolTip() == tooltip
                and not label.isHidden()
            )
            if already_rendered:
                return
            # The fixed-width label stays present (but blank while offline),
            # so connecting/disconnecting cannot push neighboring controls.
            label.setText(badge_text)
            label.setToolTip(tooltip)
            label.setVisible(True)
        except (RuntimeError, ReferenceError):
            # The main window can replace a header while it is being rebuilt.
            # The next count event or fallback poll will bind the new label.
            self._last_phone_label = None
            return
        self._last_phone_label = label
        self._last_phone_devices = devices

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

    def _dialog_finished(self, *_args) -> None:
        self._dialog = None


def install_mobile_companion(
    window: Any,
    storage_system: Any,
    app_version: str,
    *,
    hooks: Optional[FrontendHooks] = None,
) -> MobileCompanionController:
    existing = getattr(window, "mobile_companion", None)
    if isinstance(existing, MobileCompanionController):
        return existing
    controller = MobileCompanionController(
        window=window,
        storage_system=storage_system,
        app_version=app_version,
        hooks=hooks,
    )
    window.mobile_companion = controller
    return controller
