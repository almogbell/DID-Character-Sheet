"""UI for pairing and managing DID Android companion devices.

This dialog is intentionally thin: MobileSyncServer owns pairing/authentication,
while this widget only exposes those operations to the desktop user.
"""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    import qrcode
except Exception:  # Optional until packaging is updated.
    qrcode = None

try:  # package import used by tests / repository tooling
    from .mobile_sync_server import MobileSyncServer
except ImportError:  # sibling import used by the packaged desktop app
    from mobile_sync_server import MobileSyncServer


class MobileCompanionDialog(QDialog):
    """Pair phones and revoke previously paired companion devices."""

    def __init__(self, server: MobileSyncServer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("Mobile Companion")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        title = QLabel("Connect a phone")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        hint = QLabel(
            "Keep the computer and phone on the same Wi-Fi network. "
            "Choose Start pairing, then scan the code in the Android app."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.qr_label = QLabel("Pairing is not active.")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(250)
        layout.addWidget(self.qr_label)

        self.pairing_text = QLabel("")
        self.pairing_text.setWordWrap(True)
        self.pairing_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.pairing_text)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start pairing")
        self.start_button.clicked.connect(self._start_pairing)
        buttons.addWidget(self.start_button)

        self.copy_button = QPushButton("Copy pairing code")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_pairing)
        buttons.addWidget(self.copy_button)

        cancel_button = QPushButton("Cancel pairing")
        cancel_button.clicked.connect(self.server.cancel_pairing)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        devices_title = QLabel("Paired phones")
        devices_title.setStyleSheet("font-weight: 700; margin-top: 12px;")
        layout.addWidget(devices_title)

        self.devices = QListWidget()
        layout.addWidget(self.devices)

        revoke = QPushButton("Remove selected phone")
        revoke.clicked.connect(self._revoke_selected)
        layout.addWidget(revoke)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self._last_pairing_json = ""
        self.server.pairingChanged.connect(self._show_pairing)
        self.server.clientCountChanged.connect(self._show_client_count)
        self.server.statusChanged.connect(self.status.setText)
        self._refresh_devices()

    def _start_pairing(self) -> None:
        try:
            payload = self.server.begin_pairing()
        except Exception as exc:
            QMessageBox.warning(self, "Mobile Companion", str(exc))
            return
        self._show_pairing(payload)

    def _show_pairing(self, payload) -> None:
        if not payload:
            self._last_pairing_json = ""
            self.qr_label.setPixmap(QPixmap())
            self.qr_label.setText("Pairing is not active.")
            self.pairing_text.setText("")
            self.copy_button.setEnabled(False)
            self._refresh_devices()
            return

        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self._last_pairing_json = text
        self.copy_button.setEnabled(True)
        self.pairing_text.setText(
            "If scanning is unavailable, copy this pairing code into the Android app:\n" + text
        )

        pixmap = self._qr_pixmap(text)
        if pixmap is None:
            self.qr_label.setText("QR support is unavailable in this build.\nUse Copy pairing code instead.")
        else:
            self.qr_label.setText("")
            self.qr_label.setPixmap(
                pixmap.scaled(
                    240,
                    240,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _copy_pairing(self) -> None:
        if self._last_pairing_json:
            QGuiApplication.clipboard().setText(self._last_pairing_json)

    def _refresh_devices(self) -> None:
        self.devices.clear()
        for device in self.server.paired_devices():
            item = QListWidgetItem(device.get("device_name") or "Phone")
            item.setData(Qt.ItemDataRole.UserRole, device.get("device_id"))
            last_seen = device.get("last_seen")
            if last_seen:
                item.setToolTip(f"Last seen: {last_seen}")
            self.devices.addItem(item)

    def _revoke_selected(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        device_id = item.data(Qt.ItemDataRole.UserRole)
        if not device_id:
            return
        if QMessageBox.question(
            self,
            "Remove phone",
            f"Remove {item.text()}? It will have to be paired again before it can reconnect.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.server.revoke_device(str(device_id))
        self._refresh_devices()

    def _show_client_count(self, count: int) -> None:
        suffix = "phone" if count == 1 else "phones"
        self.status.setText(f"{count} connected {suffix}.")
        self._refresh_devices()

    @staticmethod
    def _qr_pixmap(text: str) -> Optional[QPixmap]:
        if qrcode is None:
            return None
        image = qrcode.make(text)
        try:
            import io

            raw = io.BytesIO()
            image.save(raw, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(QByteArray(raw.getvalue()), "PNG"):
                return None
            return pixmap
        except Exception:
            return None
