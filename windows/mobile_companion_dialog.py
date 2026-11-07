"""Compact connection/pairing and phone-management dialog for Pocket DID."""
from __future__ import annotations

import json
import math
import os
import time
from collections import Counter
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QByteArray, QEvent, Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, QScrollArea, QVBoxLayout, QWidget,
)

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
except ImportError:
    qrcode = None
    ERROR_CORRECT_M = None

try:
    from .mobile_sync_server import MobileSyncServer
    from .mobile_pairing_link import make_pairing_landing_url
    from . import ui_theme
except ImportError:
    from mobile_sync_server import MobileSyncServer
    from mobile_pairing_link import make_pairing_landing_url
    import ui_theme

RELEASES_URL = 'https://github.com/almogbell/DID-Character-Sheet/releases/latest'
DEFAULT_PAIRING_LANDING_URL = 'https://almogbell.github.io/DID-Character-Sheet/pair/'


def _theme_style(dark: bool) -> str:
    page, surface, text, muted, border, hover, selected, status = (
        ('#101c29', '#192b3a', '#f6f0e4', '#b7c4cf', '#b28b45', '#254355', '#2d5369', '#182c3c')
        if dark else
        ('#f7f1e5', '#fffdf7', '#25190f', '#765d34', '#c79a3b', '#fff4df', '#fff1d6', '#fffaf0')
    )
    return f'''
        QDialog#MobileCompanion, QDialog#PhoneManagementDialog {{ background: {page}; }}
        QLabel {{ color: {text}; background: transparent; font-family: Georgia; }}
        QLabel#SubtleText {{ color: {muted}; }}
        QLabel#ConnectionBanner {{ background: {status}; border: 1px solid {border};
            border-radius: 8px; padding: 7px 10px; font-weight: bold; }}
        QLabel#QRPanel {{ background: {surface}; color: {text};
            border: 1px solid {border}; border-radius: 10px; padding: 2px; }}
        QScrollArea {{ background: transparent; border: none; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QListWidget {{ background: {surface}; color: {text}; border: 1px solid {border};
            border-radius: 8px; padding: 3px; font-family: Georgia; }}
        QListWidget::item {{ padding: 6px; }}
        QListWidget::item:selected {{ background: {selected}; color: {text}; }}
        QComboBox {{ background: {surface}; color: {text}; border: 1px solid {border};
            border-radius: 7px; padding: 5px; min-height: 25px; }}
        QComboBox#PairingAddressSelector {{ padding-right: 25px; }}
        QComboBox#PairingAddressSelector::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 23px;
            border: none;
            background: transparent;
        }}
        QComboBox QAbstractItemView {{ background: {surface}; color: {text}; }}
        QLineEdit {{ background: {surface}; color: {text}; border: 1px solid {border};
            border-radius: 7px; padding: 7px; font-family: Georgia; min-height: 23px; }}
        QLineEdit:focus {{ border: 2px solid {border}; }}
        QLabel#ValidationWarning {{ color: {'#ffac9f' if dark else '#a12525'}; }}
        QPushButton {{ background: {surface}; color: {text}; border: 1px solid {border};
            border-radius: 8px; min-height: 28px; padding: 4px 9px;
            font-family: Georgia; font-weight: 700; }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:pressed {{ background: {selected}; }}
        QPushButton:focus {{ border: 2px solid {border}; }}
        QPushButton:disabled {{ color: {muted}; border-color: {muted}; background: {page}; }}
        QPushButton#StartPairing {{ background: {selected}; }}
        QPushButton#RemovePhone {{ color: {'#ffac9f' if dark else '#aa0000'}; }}
    '''


def _device_rows(paired_devices, connected_ids):
    """Stable, unique-by-identity rows; identical names aren't proof of duplication.

    Never merge different authenticated identities just because they share a
    manufacturer-assigned display name (e.g. two phones called '22101320G').
    """
    by_id = {}
    for device in paired_devices:
        if not isinstance(device, dict):
            continue
        device_id = str(device.get('device_id') or '').strip()
        if not device_id:
            continue
        # If an inconsistent provider returns the same ID twice, retain its
        # newest last-seen record instead of showing duplicate list entries.
        previous = by_id.get(device_id)
        def seen_number(record):
            try:
                return int(record.get('last_seen') or 0)
            except (TypeError, ValueError, OverflowError):
                return 0
        if previous is None or seen_number(device) > seen_number(previous):
            by_id[device_id] = device

    name_counts = Counter(str(record.get('device_name') or 'Phone').strip().casefold()
                          for record in by_id.values())
    rows = []
    for device_id, device in by_id.items():
        name = str(device.get('device_name') or 'Phone').strip() or 'Phone'
        # Repeated names may belong to genuinely different phones. Show a
        # short identifier to help users select the correct one to remove.
        display = name if name_counts[name.casefold()] == 1 else f'{name} (…{device_id[-6:]})'
        rows.append({
            'device_id': device_id,
            'name': name,
            'display_name': display,
            'last_seen': device.get('last_seen'),
            'status': 'Connected' if device_id in connected_ids else 'Paired but offline',
            'connected': device_id in connected_ids,
        })
    return sorted(rows, key=lambda row: (not row['connected'], row['name'].casefold(), row['device_id']))


class MobileCompanionDialog(QDialog):
    QR_DISPLAY_SIZE = 212
    QR_FRAME_PADDING = 16
    MIN_QR_FRAME_SIZE = 184  # retain a reasonably scannable QR on smaller windows

    def __init__(self, server: MobileSyncServer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.server = server
        self.setObjectName('MobileCompanion')
        self.setWindowTitle('Mobile Companion')
        self.setStyleSheet(_theme_style(ui_theme.CURRENT_THEME == 'dark'))
        self._last_pairing_json = ''
        self._pairing_explanation = ''
        self._display_expires_at = 0.0
        self._displayed_count = None
        self._last_device_status = None
        self._qr_original_pixmap = None
        self._qr_fit_scheduled = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        title = QLabel('Mobile Companion')
        title.setStyleSheet('font-size: 20px; font-weight: 800;')
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch()
        self.install_button = QPushButton('Get Pocket DID ↗')
        self.install_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL)))
        title_row.addWidget(self.install_button)
        outer.addLayout(title_row)
        self.connection_banner = QLabel()
        self.connection_banner.setObjectName('ConnectionBanner')
        self.connection_banner.setWordWrap(True)
        outer.addWidget(self.connection_banner)

        summary = QLabel('Keep Windows and Pocket DID on the same Wi-Fi network. '
                         'Start pairing, then scan the code in Pocket DID.')
        summary.setObjectName('SubtleText')
        summary.setWordWrap(True)
        outer.addWidget(summary)

        # Only the middle area may scroll at cramped display scales. The
        # connection banner and bottom pairing buttons remain visible.
        self.content_scroll = QScrollArea(self)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Scroll only on genuinely cramped windows, not at the default size.
        self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_scroll.viewport().installEventFilter(self)
        content_body = QWidget(self.content_scroll)
        # Responsive content: keep the familiar two-column presentation on
        # normal screens; stack QR above devices if the window is narrow.
        # The content remains inside the scroll area, and the action buttons
        # stay outside it, always accessible at the bottom.
        self.content_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, content_body)
        content = self.content_layout
        content.setContentsMargins(0, 2, 0, 2)
        content.setSpacing(10)
        qr_column = QVBoxLayout()
        qr_column.setSpacing(7)
        qr_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        network_label = QLabel('Phone connection network')
        qr_column.addWidget(network_label)
        address_row = QHBoxLayout()
        self.address_selector = QComboBox()
        self.address_selector.setObjectName('PairingAddressSelector')
        self.address_selector.setToolTip('Select the same Wi-Fi or LAN as your phone, not a VPN.')
        address_row.addWidget(self.address_selector, 1)
        self.refresh_addresses_button = QPushButton('↻')
        self.refresh_addresses_button.setToolTip('Refresh available network addresses')
        self.refresh_addresses_button.setFixedWidth(34)
        self.refresh_addresses_button.clicked.connect(self._refresh_pairing_addresses)
        address_row.addWidget(self.refresh_addresses_button)
        qr_column.addLayout(address_row)
        self._refresh_pairing_addresses()
        self.qr_label = QLabel('Start pairing to display a QR code.')
        self.qr_label.setWordWrap(True)
        self.qr_label.setObjectName('QRPanel')
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(self.QR_DISPLAY_SIZE + self.QR_FRAME_PADDING,
                                   self.QR_DISPLAY_SIZE + self.QR_FRAME_PADDING)
        qr_column.addWidget(self.qr_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pairing_text = QLabel('Pairing codes expire after five minutes.')
        self.pairing_text.setObjectName('SubtleText')
        self.pairing_text.setWordWrap(True)
        self.pairing_text.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.pairing_text.setMinimumWidth(self.QR_DISPLAY_SIZE + 16)
        self.pairing_text.setMaximumWidth(276)
        qr_column.addWidget(self.pairing_text)
        content.addLayout(qr_column, 0)
        self.qr_column = qr_column

        phones = QVBoxLayout()
        phones.setSpacing(5)
        phones_heading = QLabel('Paired phones')
        phones_heading.setStyleSheet('font-weight: 800; font-size: 14px;')
        phones.addWidget(phones_heading)
        self.devices = QListWidget()
        self.devices.setMinimumHeight(105)
        self.devices.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.devices.itemSelectionChanged.connect(self._update_device_actions)
        phones.addWidget(self.devices, 1)
        device_actions = QHBoxLayout()
        self.rename_button = QPushButton('Rename')
        self.rename_button.clicked.connect(self._rename_selected)
        device_actions.addWidget(self.rename_button)
        self.remove_button = QPushButton('Remove Phone')
        self.remove_button.setObjectName('RemovePhone')
        self.remove_button.clicked.connect(self._revoke_selected)
        device_actions.addWidget(self.remove_button)
        phones.addLayout(device_actions)
        content.addLayout(phones, 1)
        self.phones_column = phones
        self.content_scroll.setWidget(content_body)
        outer.addWidget(self.content_scroll, 1)

        self.status = QLabel('')
        self.status.setObjectName('SubtleText')
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        actions = QHBoxLayout()
        self.cancel_pairing_button = QPushButton('Cancel pairing')
        self.cancel_pairing_button.clicked.connect(self._cancel_pairing)
        self.cancel_pairing_button.setEnabled(False)
        actions.addWidget(self.cancel_pairing_button)
        actions.addStretch(1)
        self.copy_button = QPushButton('Copy pairing code')
        self.copy_button.clicked.connect(self._copy_pairing)
        self.copy_button.setEnabled(False)
        actions.addWidget(self.copy_button)
        self.start_button = QPushButton('Start pairing')
        self.start_button.setObjectName('StartPairing')
        self.start_button.clicked.connect(self._start_pairing)
        actions.addWidget(self.start_button)
        outer.addLayout(actions)

        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        # A little more height fits the full QR and both control rows at
        # normal Windows display scaling without an unnecessary scrollbar.
        target_w, target_h = 760, 570
        if available:
            target_w = min(target_w, max(460, available.width() - 55))
            target_h = min(target_h, max(350, available.height() - 70))
        self.setMinimumSize(450, 340)
        self.resize(target_w, target_h)
        self._update_mobile_layout()

        self.server.pairingChanged.connect(self._show_pairing)
        self.server.clientCountChanged.connect(self._show_client_count)
        self.server.statusChanged.connect(self._show_server_status)
        self._refresh_devices()
        self._show_client_count(len(self.server.connected_device_ids()))
        self._connection_timer = QTimer(self)
        self._connection_timer.setInterval(1500)
        self._connection_timer.timeout.connect(self._poll_connection)
        self._connection_timer.start()
        # The dialog may be recreated while a valid code is still active.
        self._restore_pairing()

    def _update_mobile_layout(self) -> None:
        """Avoid clipped QR/instructions on small or high-DPI windows."""
        layout = getattr(self, 'content_layout', None)
        if layout is None:
            return
        # Below 690px the QR+phones layout needs more than the available
        # width: stack it and let the existing scroll area handle height.
        compact = self.width() < 690
        requested = (QBoxLayout.Direction.TopToBottom if compact
                     else QBoxLayout.Direction.LeftToRight)
        if layout.direction() != requested:
            layout.setDirection(requested)
        # In stacked mode let phone rows be tall enough to use comfortably.
        self.devices.setMinimumHeight(145 if compact else 105)
        self.content_scroll.widget().updateGeometry()
        self._schedule_qr_fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_mobile_layout()

    def eventFilter(self, watched, event):
        # When a status line wraps, Qt may resize the viewport without
        # resizing the window itself. Re-fit the QR after that layout change.
        if (watched is self.content_scroll.viewport()
                and event.type() == QEvent.Type.Resize):
            self._schedule_qr_fit()
        return super().eventFilter(watched, event)

    def _schedule_qr_fit(self) -> None:
        if self._qr_fit_scheduled:
            return
        self._qr_fit_scheduled = True
        QTimer.singleShot(0, self._fit_qr_to_viewport)

    def _fit_qr_to_viewport(self) -> None:
        """Use free vertical space for QR; avoid scrolling at normal sizes.

        The device list scrolls internally when populated. The outer middle
        pane only scrolls when the actual screen is too small to show both
        columns (for example, in the narrow stacked layout).
        """
        self._qr_fit_scheduled = False
        if not self.isVisible():
            return
        if self.width() < 690:
            # A stacked phone+QR layout really is taller than the viewport.
            new_side = self.QR_DISPLAY_SIZE + self.QR_FRAME_PADDING
        else:
            available = self.content_scroll.viewport().height()
            if available <= 0:
                return
            # The QR is the only large, fixed-height element in its column.
            # Everything else (network menu and instructions) must be reserved.
            side_now = self.qr_label.minimumHeight()
            fixed_height = max(0, self.qr_column.sizeHint().height() - side_now)
            margins = self.content_layout.contentsMargins()
            free = available - fixed_height - margins.top() - margins.bottom() - 3
            new_side = max(self.MIN_QR_FRAME_SIZE,
                           min(self.QR_DISPLAY_SIZE + self.QR_FRAME_PADDING, int(free)))
        if new_side != self.qr_label.width():
            self.qr_label.setFixedSize(new_side, new_side)
            self._update_qr_pixmap_size()
            self.content_scroll.widget().updateGeometry()

    def _update_qr_pixmap_size(self) -> None:
        if self._qr_original_pixmap is None:
            return
        image_side = max(1, self.qr_label.width() - self.QR_FRAME_PADDING)
        self.qr_label.setPixmap(self._qr_original_pixmap.scaled(
            image_side, image_side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        ))

    def _poll_connection(self) -> None:
        self._show_client_count(len(self.server.connected_device_ids()))
        # Server owns expiration. Polling refreshes the countdown while shown;
        # the server heartbeat expires hidden codes independently.
        self._refresh_pairing_timer()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.setStyleSheet(_theme_style(ui_theme.CURRENT_THEME == 'dark'))
        self._refresh_devices()
        self._show_client_count(len(self.server.connected_device_ids()))
        # Changing theme while the dialog is closed must also restyle the QR
        # placeholder. Actual QR codes stay white for reliable scanning.
        self._restore_pairing()
        self._update_mobile_layout()
        self._schedule_qr_fit()


    def _set_qr_placeholder(self, message: str) -> None:
        self._qr_original_pixmap = None
        self.qr_label.clear()
        self.qr_label.setPixmap(QPixmap())
        self.qr_label.setText(message)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dark = ui_theme.CURRENT_THEME == 'dark'
        bg = '#192b3a' if dark else '#fffaf0'
        fg = '#f6f0e4' if dark else '#6c5428'
        edge = '#b28b45' if dark else '#c79a3b'
        self.qr_label.setStyleSheet(
            f'QLabel#QRPanel {{ background: {bg}; color: {fg}; '
            f'border: 1px dashed {edge}; border-radius: 10px; padding: 12px; }}'
        )
        self._schedule_qr_fit()

    def _show_qr_pixmap(self, pixmap: QPixmap) -> None:
        self.qr_label.setText('')
        self.qr_label.setStyleSheet(
            'QLabel#QRPanel { background: white; color: #25190f; '
            'border: 1px solid #c79a3b; border-radius: 10px; padding: 2px; }'
        )
        self._qr_original_pixmap = pixmap
        self._update_qr_pixmap_size()
        self._schedule_qr_fit()

    def _refresh_pairing_addresses(self) -> None:
        """List active NICs; retain explicit user choice when still available."""
        selected = self.address_selector.currentData()
        self.address_selector.clear()
        self.address_selector.addItem('Automatic (recommended)', None)
        for label, ip in self.server.pairing_lan_addresses():
            self.address_selector.addItem(label, ip)
        if selected is not None:
            index = self.address_selector.findData(selected)
            if index >= 0:
                self.address_selector.setCurrentIndex(index)

    def _start_pairing(self) -> None:
        had_active_code = self.server.active_pairing_payload() is not None
        try:
            # begin_pairing emits pairingChanged. The previous temporary token
            # becomes invalid immediately; permanently paired phones are safe.
            self.server.begin_pairing(host_override=self.address_selector.currentData())
            self.status.setText('Previous pairing code replaced.' if had_active_code
                                else 'Temporary pairing code ready.')
        except Exception as exc:
            QMessageBox.warning(self, 'Mobile Companion', str(exc))

    def _cancel_pairing(self) -> None:
        if self.server.active_pairing_payload() is not None:
            self.server.cancel_pairing()

    def _restore_pairing(self) -> None:
        """Keep a valid QR and its copy action visible after reopening."""
        payload = self.server.active_pairing_payload()
        if payload is not None:
            # Only re-render if a new code replaced the displayed one.
            raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            if self._last_pairing_json != raw:
                self._show_pairing(payload)
            else:
                self._refresh_pairing_timer()
        elif self._last_pairing_json:
            self._show_pairing(None)
        else:
            self._set_qr_placeholder('Start pairing to display a QR code.')

    def _refresh_pairing_timer(self) -> None:
        if not self._last_pairing_json:
            return
        if self.server.active_pairing_payload() is None:
            # active_pairing_payload() emits pairingChanged(None) on expiry.
            # Do not keep an old scannable QR visible after revocation.
            if self._last_pairing_json:
                self._show_pairing(None)
            return
        left = max(0, math.ceil(self._display_expires_at - time.time()))
        self.pairing_text.setText(
            f'{self._pairing_explanation}\nCode expires in {left // 60}:{left % 60:02d}.'
        )
        self._schedule_qr_fit()

    def _show_pairing(self, payload) -> None:
        if not payload:
            self._last_pairing_json = ''
            self._pairing_explanation = ''
            self._display_expires_at = 0.0
            self._set_qr_placeholder('Start pairing to display a QR code.')
            reason = getattr(self.server, '_pairing_last_end_reason', '')
            if reason == 'expired':
                message = 'Pairing code expired. Start pairing for a new code.'
            elif reason == 'cancelled':
                message = 'Pairing cancelled. The previous code no longer works.'
            elif reason == 'completed':
                message = 'Phone paired successfully.'
            else:
                message = 'Pairing codes expire after five minutes.'
            self.pairing_text.setText(message)
            if reason:
                self.status.setText(message)
            self.copy_button.setEnabled(False)
            self.cancel_pairing_button.setEnabled(False)
            self.start_button.setText('Start pairing')
            self._show_client_count(len(self.server.connected_device_ids()))
            return

        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        self._last_pairing_json = raw
        self._display_expires_at = float(payload.get('expires_at') or 0)
        qr_data = raw
        explanation = ('Scan in Pocket DID, or copy the code and paste it there.')
        landing = os.environ.get('DID_PAIRING_LANDING_URL', '').strip() or DEFAULT_PAIRING_LANDING_URL
        if landing:
            try:
                qr_data = make_pairing_landing_url(payload, landing)
                explanation = ('Scan with the phone camera, then open Pocket DID from the page. '
                               'Manual code also works.')
            except ValueError:
                self.status.setText('Invalid DID_PAIRING_LANDING_URL; using legacy QR.')
        self.copy_button.setEnabled(True)
        self.cancel_pairing_button.setEnabled(True)
        self.start_button.setText('New pairing code')
        self._pairing_explanation = explanation
        self._refresh_pairing_timer()
        if not self._last_pairing_json:
            # The temporary token may expire while the QR is being built.
            return
        pixmap = self._qr_pixmap(qr_data)
        if pixmap is None:
            self._set_qr_placeholder('QR support unavailable.\nUse Copy pairing code.')
            return
        self._show_qr_pixmap(pixmap)

    def _copy_pairing(self) -> None:
        if not self._last_pairing_json:
            return
        if self.server.active_pairing_payload() is None:
            # A click right at expiry must neither copy nor leave the old
            # enabled controls onscreen (even if no signal was delivered).
            if self._last_pairing_json:
                self._show_pairing(None)
            return
        QGuiApplication.clipboard().setText(self._last_pairing_json)
        self.status.setText('Temporary pairing code copied. Paste it into Pocket DID.')

    def _refresh_devices(self, paired_devices=None, live=None) -> None:
        """Update device states while retaining selection and scroll position."""
        if paired_devices is None:
            paired_devices = self.server.paired_devices()
        if live is None:
            live = self.server.connected_device_ids()
        selected = self.devices.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        scroll = self.devices.verticalScrollBar()
        old_scroll = scroll.value()
        self.devices.blockSignals(True)
        try:
            self.devices.clear()
            for row in _device_rows(paired_devices, live):
                item = QListWidgetItem(f"{row['display_name']}  •  {row['status']}")
                item.setData(Qt.ItemDataRole.UserRole, row['device_id'])
                item.setData(int(Qt.ItemDataRole.UserRole) + 1, row['name'])
                if row['last_seen']:
                    try:
                        last_seen = datetime.fromtimestamp(int(row['last_seen'])).strftime('%Y-%m-%d %H:%M')
                        item.setToolTip(f'Last seen: {last_seen}')
                    except (OSError, OverflowError, TypeError, ValueError):
                        pass
                self.devices.addItem(item)
                if row['device_id'] == selected_id:
                    self.devices.setCurrentItem(item)
            scroll.setValue(old_scroll)
        finally:
            self.devices.blockSignals(False)
        self._update_device_actions()

    def _update_device_actions(self) -> None:
        selected = self.devices.currentItem()
        has_id = bool(selected and selected.data(Qt.ItemDataRole.UserRole))
        self.remove_button.setEnabled(has_id)
        self.rename_button.setEnabled(has_id)

    def _device_action_dialog(self, title: str):
        """Theme-matched action dialog: Cancel left, affirmative action right."""
        dialog = QDialog(self)
        dialog.setObjectName('PhoneManagementDialog')
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setStyleSheet(_theme_style(ui_theme.CURRENT_THEME == 'dark'))
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        return dialog, layout

    def _rename_selected(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        device_id = str(item.data(Qt.ItemDataRole.UserRole) or '')
        if not device_id:
            return
        name = str(item.data(int(Qt.ItemDataRole.UserRole) + 1) or 'Phone')
        dialog, layout = self._device_action_dialog('Rename Phone')
        layout.addWidget(QLabel('Phone name:'))
        edit = QLineEdit(name, dialog)
        edit.setMaxLength(120)
        edit.selectAll()
        layout.addWidget(edit)
        warning = QLabel('Use a name between 1 and 120 characters.')
        warning.setObjectName('ValidationWarning')
        warning.setWordWrap(True)
        layout.addWidget(warning)
        warning.hide()
        actions = QHBoxLayout()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(dialog.reject)
        actions.addWidget(cancel)
        actions.addStretch(1)
        save = QPushButton('Rename')
        actions.addWidget(save)
        save.clicked.connect(dialog.accept)
        layout.addLayout(actions)

        def valid_name(text):
            cleaned = text.strip()
            return bool(cleaned) and len(cleaned) <= 120 and all(ord(c) >= 32 for c in cleaned)

        def validate(text):
            valid = valid_name(text)
            save.setEnabled(valid)
            warning.setVisible(not valid)
        edit.textChanged.connect(validate)
        validate(name)
        save.setDefault(True)
        edit.setFocus()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            renamed = self.server.rename_device(device_id, edit.text().strip())
        except OSError:
            renamed = False
        if not renamed:
            self.status.setText('Could not rename this phone. Check the name and try again.')
        self._refresh_devices()
        self._show_client_count(len(self.server.connected_device_ids()))

    def _revoke_selected(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        device_id = str(item.data(Qt.ItemDataRole.UserRole) or '')
        if not device_id:
            return
        name = str(item.data(int(Qt.ItemDataRole.UserRole) + 1) or 'Phone')
        dialog, layout = self._device_action_dialog('Remove Phone')
        question = QLabel(f'Remove {name}?')
        question.setWordWrap(True)
        question.setStyleSheet('font-weight: bold; font-size: 14px;')
        layout.addWidget(question)
        explanation = QLabel('This phone will disconnect immediately and must pair again to reconnect.')
        explanation.setObjectName('SubtleText')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        actions = QHBoxLayout()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(dialog.reject)
        cancel.setDefault(True)  # Avoid an accidental destructive Enter press.
        actions.addWidget(cancel)
        actions.addStretch(1)
        remove = QPushButton('Remove Phone')
        remove.setObjectName('RemovePhone')
        remove.clicked.connect(dialog.accept)
        actions.addWidget(remove)
        layout.addLayout(actions)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            removed = self.server.revoke_device(device_id)
        except OSError:
            removed = False
        if not removed:
            self.status.setText('Could not remove this phone. Please try again.')
        self._refresh_devices()
        self._show_client_count(len(self.server.connected_device_ids()))

    def _show_server_status(self, message: str) -> None:
        if message and ('error' in message.lower() or 'could not' in message.lower()):
            self.status.setText(message)

    def _show_client_count(self, count: int) -> None:
        # Fetch identity snapshots instead of trusting a potentially stale
        # emitted count. Two phones can trade sessions with no count change.
        live = self.server.connected_device_ids()
        devices = self.server.paired_devices()
        actual_count = len(live)
        pending = self.server.pending_connection_count()
        paired = bool(devices)
        if actual_count:
            banner = f'● Connected — {actual_count} live phone' + ('s' if actual_count != 1 else '')
        elif pending:
            banner = '◌ Connecting — waiting for phone authentication'
        elif paired:
            banner = '○ Paired but offline — reconnect Pocket DID'
        else:
            banner = '○ Disconnected — pair a phone to begin'
        # Include device names, identities and live state. Poll refreshes now
        # catch swaps/renames even when the total number of phones is stable.
        signature = tuple(sorted((str(d.get('device_id') or ''),
                                  str(d.get('device_name') or ''),
                                  str(d.get('last_seen') or '')) for d in devices))
        state = (actual_count, pending, banner, signature, tuple(sorted(live)))
        if state != self._last_device_status:
            self._last_device_status = state
            self._displayed_count = actual_count
            self.connection_banner.setText(banner)
            self._refresh_devices(devices, live)

    @staticmethod
    def _qr_pixmap(text: str) -> Optional[QPixmap]:
        if qrcode is None:
            return None
        try:
            import io
            qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                               box_size=7, border=4)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            pixmap = QPixmap()
            return pixmap if pixmap.loadFromData(QByteArray(buf.getvalue()), 'PNG') else None
        except Exception:
            return None
