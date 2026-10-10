from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from campaign_privacy import normalize_privacy_preferences
from ui_theme import set_themed_stylesheet


PRIVACY_QSS = """
QDialog { background-color: #fffdf7; }
QLabel { background: transparent; border: none; color: #25190f; font-family: Georgia; }
QPushButton {
    background-color: #fffdf7; border: 1px solid #c79a3b; border-radius: 9px;
    color: #25190f; font-family: Georgia; font-size: 12px; font-weight: 800;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #fff4df; border-color: #a87824; }
QCheckBox { color: #25190f; font-family: Georgia; font-size: 12px; spacing: 7px; }
QScrollArea { background: transparent; border: 1px solid #dcc79f; border-radius: 9px; }
"""


class SharingPrivacyDialog(QDialog):
    def __init__(self, parent, character, preferences):
        super().__init__(parent)
        self.character = character
        self.preferences = normalize_privacy_preferences(preferences)
        self.saved_preferences = None
        self.inventory_boxes = {}
        self.note_boxes = {}

        self.setWindowTitle("Sharing & Privacy")
        self.resize(610, 690)
        self.setMinimumSize(520, 560)
        set_themed_stylesheet(self, PRIVACY_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("Sharing & Privacy")
        title.setStyleSheet(
            "font-family: Georgia; font-size: 21px; font-weight: 900; color:#25190f;"
        )
        root.addWidget(title)

        explanation = QLabel(
            "Choose what this character shares with the campaign DM. Core tactical "
            "data is required for campaign play. Everything else below is optional."
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        core = QCheckBox(
            "Core tactical data — identity, level, Hearts, AT, IP, abilities and defense"
        )
        core.setChecked(True)
        core.setEnabled(False)
        root.addWidget(core)

        self.improvements = QCheckBox("Improvements")
        self.improvements.setChecked(self.preferences["share_improvements"])
        root.addWidget(self.improvements)

        self.portrait = QCheckBox("Character portrait")
        self.portrait.setChecked(self.preferences["share_portrait"])
        root.addWidget(self.portrait)

        self.backstory = QCheckBox("Backstory")
        self.backstory.setChecked(self.preferences["share_backstory"])
        root.addWidget(self.backstory)

        self.inventory = QCheckBox("Selected inventory items")
        self.inventory.setChecked(self.preferences["share_inventory"])
        root.addWidget(self.inventory)
        inventory_note = QLabel(
            "Only the individual items checked below will be shared. Descriptions and quantities are included."
        )
        inventory_note.setWordWrap(True)
        inventory_note.setStyleSheet("color:#7c6a52; font-size:11px; margin-left:20px;")
        root.addWidget(inventory_note)
        inventory_scroll, inventory_layout = self._make_list_area()
        root.addWidget(inventory_scroll)
        self._populate_inventory(inventory_layout)

        self.notes = QCheckBox("Selected notes")
        self.notes.setChecked(self.preferences["share_notes"])
        root.addWidget(self.notes)
        notes_note = QLabel(
            "Notes are never shared automatically. Only the individual notes checked below are sent to the DM."
        )
        notes_note.setWordWrap(True)
        notes_note.setStyleSheet("color:#7c6a52; font-size:11px; margin-left:20px;")
        root.addWidget(notes_note)
        notes_scroll, notes_layout = self._make_list_area()
        root.addWidget(notes_scroll)
        self._populate_notes(notes_layout)

        self.inventory.toggled.connect(self._refresh_enabled_state)
        self.notes.toggled.connect(self._refresh_enabled_state)
        self._refresh_enabled_state()

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addStretch()
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _make_list_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(92)
        scroll.setMaximumHeight(145)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        scroll.setWidget(body)
        return scroll, layout

    def _populate_inventory(self, layout):
        selected = set(self.preferences["inventory_item_ids"])
        items = list(getattr(getattr(self.character, "inventory", None), "list_of_items", []) or [])
        if not items:
            label = QLabel("No inventory items on this character.")
            label.setStyleSheet("color:#7c6a52; font-style:italic;")
            layout.addWidget(label)
            return

        for item in items:
            item_id = str(getattr(item, "id", "") or "").strip()
            if not item_id:
                continue
            name = str(getattr(item, "name", "") or "Unnamed item").strip() or "Unnamed item"
            try:
                quantity = max(0, int(getattr(item, "quantity", 0) or 0))
            except Exception:
                quantity = 0
            label = f"{name}  ×{quantity}" if quantity != 1 else name
            box = QCheckBox(label)
            box.setChecked(item_id in selected)
            self.inventory_boxes[item_id] = box
            layout.addWidget(box)
        layout.addStretch()

    def _populate_notes(self, layout):
        selected = set(self.preferences["note_ids"])
        notes = list(getattr(getattr(self.character, "notes", None), "list_of_notes", []) or [])
        if not notes:
            label = QLabel("No notes on this character.")
            label.setStyleSheet("color:#7c6a52; font-style:italic;")
            layout.addWidget(label)
            return

        for note in notes:
            note_id = str(getattr(note, "id", "") or "").strip()
            if not note_id:
                continue
            title = str(getattr(note, "title", "") or "Untitled note").strip() or "Untitled note"
            box = QCheckBox(title)
            box.setChecked(note_id in selected)
            self.note_boxes[note_id] = box
            layout.addWidget(box)
        layout.addStretch()

    def _refresh_enabled_state(self):
        inventory_enabled = self.inventory.isChecked()
        for box in self.inventory_boxes.values():
            box.setEnabled(inventory_enabled)
        notes_enabled = self.notes.isChecked()
        for box in self.note_boxes.values():
            box.setEnabled(notes_enabled)

    def _save(self):
        value = {
            "share_improvements": self.improvements.isChecked(),
            "share_portrait": self.portrait.isChecked(),
            "share_backstory": self.backstory.isChecked(),
            "share_inventory": self.inventory.isChecked(),
            "inventory_item_ids": [
                item_id
                for item_id, box in self.inventory_boxes.items()
                if box.isChecked()
            ],
            "share_notes": self.notes.isChecked(),
            "note_ids": [
                note_id
                for note_id, box in self.note_boxes.items()
                if box.isChecked()
            ],
        }
        self.saved_preferences = normalize_privacy_preferences(value)
        self.accept()


def open_sharing_privacy_dialog(parent, character, preferences):
    dialog = SharingPrivacyDialog(parent, character, preferences)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.saved_preferences
