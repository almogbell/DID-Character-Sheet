from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _text_label(text, muted=False, bold=False):
    label = QLabel(str(text or ""))
    label.setWordWrap(True)
    if muted:
        label.setObjectName("Muted")
    if bold:
        label.setStyleSheet("font-weight:900;")
    return label


def _card(title, body="", meta=""):
    frame = QFrame()
    frame.setObjectName("Field")
    box = QVBoxLayout(frame)
    box.setContentsMargins(12, 9, 12, 9)
    box.setSpacing(4)
    box.addWidget(_text_label(title, bold=True))
    if meta:
        box.addWidget(_text_label(meta, muted=True))
    if body:
        box.addWidget(_text_label(body))
    return frame


def _request_rows(client, table, campaign_id, select, order=None):
    query = {
        "campaign_id": f"eq.{campaign_id}",
        "select": select,
    }
    if order:
        query["order"] = order
    rows = client._request_json("GET", f"/rest/v1/{table}", query=query)
    return rows if isinstance(rows, list) else []


def _phase8_build_campaign_info_page(self):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(18, 10, 18, 4)
    outer.setSpacing(7)

    heading = QLabel("Campaign Info")
    heading.setObjectName("SectionTitle")
    outer.addWidget(heading)
    intro = QLabel(
        "Information the DM has revealed to you. Private DM notes, secrets, and hidden effects never appear here."
    )
    intro.setObjectName("SectionText")
    intro.setWordWrap(True)
    outer.addWidget(intro)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    holder = QWidget()
    holder.setStyleSheet("background: transparent;")
    self._phase8_info_layout = QVBoxLayout(holder)
    self._phase8_info_layout.setContentsMargins(0, 4, 4, 4)
    self._phase8_info_layout.setSpacing(8)
    self._phase8_info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    scroll.setWidget(holder)
    outer.addWidget(scroll, 1)
    self.pages.addWidget(page)


def _phase8_refresh_campaign_info(self):
    layout = getattr(self, "_phase8_info_layout", None)
    if layout is None:
        return
    _clear_layout(layout)

    campaign = getattr(self, "current_campaign", None)
    client = getattr(self, "client", None)
    if not campaign or client is None:
        layout.addWidget(_text_label("Select a player campaign to see information shared by its DM.", muted=True))
        return

    campaign_id = str(campaign.get("id") or "").strip()
    if not campaign_id:
        layout.addWidget(_text_label("No campaign selected.", muted=True))
        return

    try:
        npcs = _request_rows(
            client,
            "campaign_npcs",
            campaign_id,
            "id,name,status,description,portrait_url,visible_to_players",
            "name.asc",
        )
        entries = _request_rows(
            client,
            "campaign_entries",
            campaign_id,
            "id,entry_type,title,body,status,visible_to_players,updated_at",
            "updated_at.desc",
        )
        effects = _request_rows(
            client,
            "campaign_character_effects",
            campaign_id,
            "id,campaign_character_id,name,description,status,visible_to_player,updated_at",
            "updated_at.desc",
        )
    except Exception as error:
        layout.addWidget(_card("Could not load campaign information", str(error)))
        return

    if entries:
        section = QLabel("Shared Campaign Information")
        section.setStyleSheet("font-size:16px; font-weight:900;")
        layout.addWidget(section)
        for entry in entries:
            kind = str(entry.get("entry_type") or "Info").replace("_", " ").title()
            status = str(entry.get("status") or "").strip()
            meta = kind + (f" • {status}" if status else "")
            layout.addWidget(_card(entry.get("title") or "Untitled", entry.get("body") or "", meta))

    if npcs:
        section = QLabel("Revealed NPCs")
        section.setStyleSheet("font-size:16px; font-weight:900; margin-top:6px;")
        layout.addWidget(section)
        for npc in npcs:
            layout.addWidget(_card(npc.get("name") or "Unnamed NPC", npc.get("description") or "", npc.get("status") or ""))

    if effects:
        section = QLabel("Effects on My Character")
        section.setStyleSheet("font-size:16px; font-weight:900; margin-top:6px;")
        layout.addWidget(section)
        for effect in effects:
            status = str(effect.get("status") or "active")
            layout.addWidget(_card(effect.get("name") or "Effect", effect.get("description") or "", status.title()))

    if not entries and not npcs and not effects:
        layout.addWidget(_text_label("The DM has not revealed any campaign information yet.", muted=True))

    layout.addStretch()


def apply_phase8_player_ui(player_dialog_class):
    if getattr(player_dialog_class, "_phase8_campaign_info_applied", False):
        return player_dialog_class

    player_dialog_class._phase8_campaign_info_applied = True
    player_dialog_class.page_names = (
        "Campaign",
        "My Character & Sharing",
        "Creation Rules",
        "Campaign Info",
    )
    player_dialog_class._phase8_build_campaign_info_page = _phase8_build_campaign_info_page
    player_dialog_class._phase8_refresh_campaign_info = _phase8_refresh_campaign_info

    original_init = player_dialog_class.__init__
    original_campaign_changed = player_dialog_class._campaign_changed

    def phase8_init(self, window):
        original_init(self, window)
        self._phase8_build_campaign_info_page()
        self._phase8_refresh_campaign_info()

    def phase8_campaign_changed(self, index):
        original_campaign_changed(self, index)
        self._phase8_refresh_campaign_info()

    player_dialog_class.__init__ = phase8_init
    player_dialog_class._campaign_changed = phase8_campaign_changed
    return player_dialog_class
