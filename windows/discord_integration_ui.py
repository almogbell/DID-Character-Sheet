from __future__ import annotations

import webbrowser
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from discord_integration import load_config, stop_bot


DISCORD_QSS = """
QDialog { background-color: #f7f1e5; }
QWidget { font-family: Georgia; color:#25190f; }
QLabel { background: transparent; border: none; }
QLabel#Title { font-size: 27px; font-weight: 900; }
QLabel#Subtitle { color:#765d34; font-size:12px; font-weight:700; }
QLabel#SectionTitle { font-size:18px; font-weight:900; }
QLabel#Muted { color:#765d34; font-size:11px; }
QLabel#Good { color:#2f6a47; font-size:13px; font-weight:900; }
QLabel#Bad { color:#8b3932; font-size:12px; font-weight:900; }
QFrame#Card { background:#fffdf7; border:1px solid #e0c68f; border-radius:11px; }
QFrame#ConnectedCard { background:#f7fff8; border:1px solid #9fc7a9; border-radius:11px; }
QPushButton {
    min-height:34px; background:#fffdf7; border:1px solid #c79a3b;
    border-radius:9px; padding:5px 13px; font-size:12px; font-weight:800;
}
QPushButton:hover { background:#fff4df; border-color:#a87824; }
QPushButton#Primary { background:#d8edf7; }
QPushButton#Danger { color:#8b3932; border-color:#cba79d; }
QPushButton#Code {
    font-family: Consolas; font-size:21px; font-weight:900; letter-spacing:2px;
    background:#fff4df; padding:8px 22px; min-height:42px;
}
"""


class DiscordIntegrationDialog(QDialog):
    """Simple campaign-to-Discord connection flow for ordinary DID users.

    The official DID Discord application is configured and hosted once by the
    developer. Users never see a bot token, application ID, guild ID, channel
    ID, or Discord Developer Portal controls.
    """

    def __init__(self, parent, campaign_id, campaign_name, app_dir=None, campaign_client=None):
        super().__init__(parent)
        self.campaign_id = str(campaign_id or "").strip()
        self.campaign_name = str(campaign_name or "Campaign").strip() or "Campaign"
        self.client = campaign_client
        self.service_config = {}
        self.connection = None
        self.pending_code = ""
        self.legacy_config = {}
        self.setWindowTitle("Connect Discord")
        self.resize(700, 510)
        self.setMinimumSize(620, 450)
        self.setStyleSheet(DISCORD_QSS)

        # Upgrade cleanup: a current DID desktop must never leave the old
        # development/local bot process running in the background.
        try:
            stop_bot()
        except Exception:
            pass

        self._build_ui()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(2000)
        self.poll_timer.timeout.connect(self.refresh_connection)
        self.endpoint_timer = QTimer(self)
        self.endpoint_timer.setInterval(2000)
        self.endpoint_timer.timeout.connect(self.check_endpoint_verification)
        QTimer.singleShot(0, self.refresh_all)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("Connect Discord")
        title.setObjectName("Title")
        subtitle = QLabel(f"Connect {self.campaign_name} to one Discord channel.")
        subtitle.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.status = QLabel("Checking…")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.status)
        root.addLayout(header)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_setup_page())
        self.pages.addWidget(self._build_connected_page())
        self.pages.addWidget(self._build_unavailable_page())

    def _card(self):
        frame = QFrame()
        frame.setObjectName("Card")
        return frame

    def _build_setup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        install = self._card()
        box = QVBoxLayout(install)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(7)
        title = QLabel("Add DID to your Discord server")
        title.setObjectName("SectionTitle")
        text = QLabel(
            "This is needed only once for each Discord server. If DID is already "
            "installed on that server, skip this step."
        )
        text.setObjectName("Muted")
        text.setWordWrap(True)
        self.install_btn = QPushButton("Add DID to Server")
        self.install_btn.setObjectName("Primary")
        self.install_btn.clicked.connect(self.open_install_url)
        row = QHBoxLayout()
        row.addWidget(self.install_btn)
        row.addStretch()
        box.addWidget(title)
        box.addWidget(text)
        box.addLayout(row)
        layout.addWidget(install)

        connect = self._card()
        box = QVBoxLayout(connect)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(7)
        title = QLabel("Choose this campaign's Discord channel")
        title.setObjectName("SectionTitle")
        text = QLabel(
            "In the Discord channel you want for this campaign, run /did-connect and "
            "paste the short code DID gives you below."
        )
        text.setObjectName("Muted")
        text.setWordWrap(True)
        box.addWidget(title)
        box.addWidget(text)

        self.create_code_btn = QPushButton("Get Connection Code")
        self.create_code_btn.setObjectName("Primary")
        self.create_code_btn.clicked.connect(self.create_connect_code)
        code_row = QHBoxLayout()
        code_row.addWidget(self.create_code_btn)
        code_row.addStretch()
        box.addLayout(code_row)

        self.code_area = QWidget()
        code_layout = QVBoxLayout(self.code_area)
        code_layout.setContentsMargins(0, 4, 0, 0)
        code_layout.setSpacing(5)
        self.code_btn = QPushButton("")
        self.code_btn.setObjectName("Code")
        self.code_btn.clicked.connect(self.copy_code)
        self.code_help = QLabel("")
        self.code_help.setObjectName("Muted")
        self.code_help.setWordWrap(True)
        code_layout.addWidget(self.code_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        code_layout.addWidget(self.code_help)
        self.code_area.hide()
        box.addWidget(self.code_area)
        layout.addWidget(connect)

        layout.addStretch()
        return page

    def _build_connected_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("ConnectedCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(7)
        good = QLabel("✓ Connected")
        good.setObjectName("Good")
        self.connected_title = QLabel("")
        self.connected_title.setObjectName("SectionTitle")
        self.connected_details = QLabel("")
        self.connected_details.setObjectName("Muted")
        self.connected_details.setWordWrap(True)
        box.addWidget(good)
        box.addWidget(self.connected_title)
        box.addWidget(self.connected_details)
        layout.addWidget(card)

        info = QLabel(
            "Use /did in the connected channel. Dice sharing and session notices are "
            "handled by the official DID Discord service - this computer does not run a bot."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        layout.addWidget(info)

        actions = QHBoxLayout()
        change = QPushButton("Change Channel")
        change.clicked.connect(self.show_setup)
        disconnect = QPushButton("Disconnect")
        disconnect.setObjectName("Danger")
        disconnect.clicked.connect(self.disconnect_campaign)
        actions.addWidget(change)
        actions.addStretch()
        actions.addWidget(disconnect)
        layout.addLayout(actions)
        layout.addStretch()
        return page

    def _build_unavailable_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = self._card()
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(8)
        self.unavailable_title = QLabel("Discord service setup is not finished")
        self.unavailable_title.setObjectName("SectionTitle")
        self.unavailable_text = QLabel("")
        self.unavailable_text.setObjectName("Muted")
        self.unavailable_text.setWordWrap(True)
        box.addWidget(self.unavailable_title)
        box.addWidget(self.unavailable_text)

        self.developer_credentials = QWidget()
        dev = QVBoxLayout(self.developer_credentials)
        dev.setContentsMargins(0, 8, 0, 0)
        dev.setSpacing(7)
        found = QLabel("DID found the Bot Token and Application ID from your old local setup automatically. Copy only the Public Key from Discord once.")
        found.setObjectName("Muted")
        found.setWordWrap(True)
        self.public_key_input = QLineEdit()
        self.public_key_input.setPlaceholderText("Discord Public Key")
        self.public_key_input.setMaxLength(64)
        self.public_key_input.setMinimumHeight(38)
        self.public_key_input.setStyleSheet("QLineEdit { background:#fffdf7; border:1px solid #c79a3b; border-radius:8px; padding:6px 10px; }")
        dev_buttons = QHBoxLayout()
        self.open_portal_btn = QPushButton("Open Discord Developer Portal")
        self.open_portal_btn.clicked.connect(self.open_developer_portal)
        self.save_service_btn = QPushButton("Save & Continue")
        self.save_service_btn.setObjectName("Primary")
        self.save_service_btn.clicked.connect(self.finish_developer_credentials)
        dev_buttons.addWidget(self.open_portal_btn)
        dev_buttons.addStretch()
        dev_buttons.addWidget(self.save_service_btn)
        dev.addWidget(found)
        dev.addWidget(self.public_key_input)
        dev.addLayout(dev_buttons)
        self.developer_credentials.hide()
        box.addWidget(self.developer_credentials)

        self.endpoint_setup = QWidget()
        ep = QVBoxLayout(self.endpoint_setup)
        ep.setContentsMargins(0, 8, 0, 0)
        ep.setSpacing(7)
        ep_help = QLabel("In Discord Developer Portal → General Information, paste this into Interactions Endpoint URL and save. This is the last developer-only step.")
        ep_help.setObjectName("Muted")
        ep_help.setWordWrap(True)
        self.endpoint_btn = QPushButton("")
        self.endpoint_btn.setObjectName("Code")
        self.endpoint_btn.clicked.connect(self.copy_endpoint_url)
        ep_buttons = QHBoxLayout()
        portal = QPushButton("Open Discord Developer Portal")
        portal.clicked.connect(self.open_developer_portal)
        self.endpoint_done_btn = QPushButton("Check Again")
        self.endpoint_done_btn.setObjectName("Primary")
        self.endpoint_done_btn.clicked.connect(self.check_endpoint_verification)
        ep_buttons.addWidget(portal)
        ep_buttons.addStretch()
        ep_buttons.addWidget(self.endpoint_done_btn)
        ep.addWidget(ep_help)
        ep.addWidget(self.endpoint_btn)
        ep.addLayout(ep_buttons)
        self.endpoint_setup.hide()
        box.addWidget(self.endpoint_setup)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def refresh_all(self):
        if self.client is None:
            self.show_unavailable("Campaign cloud connection is unavailable.")
            return
        try:
            self.service_config = self.client.discord_service_config()
        except Exception as error:
            self.show_unavailable(str(error))
            return

        if self.service_config.get("configured"):
            self.developer_credentials.hide()
            self.endpoint_setup.hide()
            self.install_btn.setEnabled(bool(self.service_config.get("install_url")))
            self.refresh_connection()
            return

        try:
            self.legacy_config = load_config()
        except Exception:
            self.legacy_config = {}

        if self.service_config.get("credentials_ready") and not self.service_config.get("endpoint_verified"):
            self.show_endpoint_setup()
            return

        if str(self.legacy_config.get("application_id") or "").strip() and str(self.legacy_config.get("bot_token") or "").strip():
            self.show_developer_credentials_setup()
            return

        self.show_unavailable(
            "The official DID Discord service has not been configured by the app developer yet. "
            "Ordinary users do not need Discord developer settings."
        )


    def show_developer_credentials_setup(self):
        self.poll_timer.stop()
        self.status.setText("One-time setup")
        self.status.setObjectName("Subtitle")
        self.unavailable_title.setText("Finish official Discord setup")
        self.unavailable_text.setText(
            "This is a one-time developer step on your computer. DID already found your existing "
            "Application ID and Bot Token. Open your DID application in Discord Developer Portal, "
            "copy the Public Key from General Information, and paste it below."
        )
        self.developer_credentials.show()
        self.endpoint_setup.hide()
        self.pages.setCurrentIndex(2)

    def finish_developer_credentials(self):
        application_id = str(self.legacy_config.get("application_id") or "").strip()
        bot_token = str(self.legacy_config.get("bot_token") or "").strip()
        public_key = self.public_key_input.text().strip()
        if len(public_key) != 64:
            self.unavailable_text.setText("The Discord Public Key should be exactly 64 hexadecimal characters.")
            return
        self.save_service_btn.setEnabled(False)
        self.save_service_btn.setText("Saving…")
        try:
            self.client.bootstrap_official_discord(application_id, public_key, bot_token)
            self.client.register_official_discord_commands()
            self.service_config = self.client.discord_service_config()
            self.show_endpoint_setup()
        except Exception as error:
            self.unavailable_text.setText(str(error))
        finally:
            self.save_service_btn.setEnabled(True)
            self.save_service_btn.setText("Save & Continue")

    def show_endpoint_setup(self):
        self.poll_timer.stop()
        self.status.setText("Waiting for Discord")
        self.status.setObjectName("Subtitle")
        self.unavailable_title.setText("Verify the Discord connection endpoint")
        self.unavailable_text.setText(
            "The bot credentials are ready. Discord still has to verify where DID commands are sent. "
            "Open your DID application in Discord Developer Portal → General Information, paste the URL below "
            "into Interactions Endpoint URL, and click Save. Keep this window open - DID will detect Discord's "
            "verification automatically. Do not create a campaign connection code until this step succeeds."
        )
        self.developer_credentials.hide()
        endpoint = str(self.service_config.get("endpoint_url") or "").strip()
        self.endpoint_btn.setText(endpoint or "Interactions Endpoint URL unavailable")
        self.endpoint_btn.setEnabled(bool(endpoint))
        self.endpoint_setup.show()
        self.pages.setCurrentIndex(2)
        self.endpoint_done_btn.setEnabled(True)
        self.endpoint_done_btn.setText("Check Again")
        if not self.endpoint_timer.isActive():
            self.endpoint_timer.start()

    def check_endpoint_verification(self):
        if self.client is None:
            return
        try:
            self.service_config = self.client.discord_service_config()
        except Exception as error:
            self.unavailable_text.setText(str(error))
            return
        if not self.service_config.get("endpoint_verified"):
            self.status.setText("Waiting for Discord")
            self.endpoint_done_btn.setText("Check Again")
            return
        self.endpoint_timer.stop()
        self.status.setText("Verified")
        self.status.setObjectName("Good")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.developer_credentials.hide()
        self.endpoint_setup.hide()
        self.install_btn.setEnabled(bool(self.service_config.get("install_url")))
        self.refresh_connection()

    def copy_endpoint_url(self):
        endpoint = str(self.service_config.get("endpoint_url") or "").strip()
        if endpoint:
            QApplication.clipboard().setText(endpoint)

    def open_developer_portal(self):
        application_id = str(
            self.service_config.get("application_id")
            or self.legacy_config.get("application_id")
            or ""
        ).strip()
        if application_id:
            webbrowser.open(f"https://discord.com/developers/applications/{application_id}/information")
        else:
            webbrowser.open("https://discord.com/developers/applications")

    def finish_endpoint_setup(self):
        # Kept for compatibility with older signal wiring. Endpoint readiness is
        # now proven by Discord's signed PING, never by a manual confirmation.
        self.check_endpoint_verification()

    def refresh_connection(self):
        if self.client is None:
            return
        if self.service_config.get("endpoint_verified"):
            self.endpoint_timer.stop()
        try:
            self.connection = self.client.get_discord_connection(self.campaign_id)
        except Exception as error:
            self.status.setText("Connection check failed")
            self.status.setObjectName("Bad")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return

        if self.connection:
            self.poll_timer.stop()
            self.status.setText("Connected")
            self.status.setObjectName("Good")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            guild = str(self.connection.get("guild_name") or "Discord server")
            channel_name = str(self.connection.get("channel_name") or "").strip()
            channel = f"#{channel_name}" if channel_name else "Connected channel"
            self.connected_title.setText(f"{guild}  ·  {channel}")
            self.connected_details.setText(
                "This campaign is routed automatically. No IDs, bot token, or Discord roles are required."
            )
            self.pages.setCurrentIndex(1)
        else:
            self.status.setText("Not connected")
            self.status.setObjectName("Subtitle")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            if self.pages.currentIndex() != 0:
                self.pages.setCurrentIndex(0)

    def open_install_url(self):
        url = str(self.service_config.get("install_url") or "").strip()
        if url:
            webbrowser.open(url)

    def create_connect_code(self):
        try:
            result = self.client.create_discord_connect_code(self.campaign_id)
        except Exception as error:
            self.code_area.show()
            self.code_btn.setText("Could not create code")
            self.code_btn.setEnabled(False)
            self.code_help.setText(str(error))
            return
        self.pending_code = str(result.get("code") or "").strip()
        if not self.pending_code:
            return
        self.code_btn.setEnabled(True)
        self.code_btn.setText(self.pending_code)
        expiry = str(result.get("expires_at") or "").strip()
        expiry_text = ""
        if expiry:
            try:
                dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                expiry_text = f" The code expires at {dt.astimezone().strftime('%H:%M')}."
            except Exception:
                pass
        self.code_help.setText(
            "Click the code to copy it. Then, in the Discord channel for this campaign, "
            f"run /did-connect and paste the code when Discord asks for it.{expiry_text} "
            "DID will detect the connection automatically."
        )
        self.code_area.show()
        self.poll_timer.start()

    def copy_code(self):
        if self.pending_code:
            QApplication.clipboard().setText(self.pending_code)

    def show_setup(self):
        self.pages.setCurrentIndex(0)
        self.status.setText("Change channel")

    def disconnect_campaign(self):
        if self.client is None:
            return
        try:
            self.client.disconnect_discord_campaign(self.campaign_id)
        except Exception as error:
            self.status.setText(str(error))
            return
        self.connection = None
        self.pending_code = ""
        self.code_area.hide()
        self.pages.setCurrentIndex(0)
        self.refresh_connection()

    def show_unavailable(self, message):
        self.poll_timer.stop() if hasattr(self, "poll_timer") else None
        self.status.setText("Unavailable")
        self.status.setObjectName("Bad")
        self.unavailable_title.setText("Discord service setup is not finished")
        self.unavailable_text.setText(str(message or "Discord service unavailable."))
        self.developer_credentials.hide()
        self.endpoint_setup.hide()
        self.pages.setCurrentIndex(2)
