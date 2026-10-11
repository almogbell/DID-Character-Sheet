from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
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
QDialog {
    background-color: #f7f1e5;
}
QWidget {
    color: #25190f;
    font-family: Georgia;
}
QLabel {
    background: transparent;
    border: none;
    color: #25190f;
    font-family: Georgia;
    font-size: 13px;
}
QLabel#PageTitle {
    font-size: 27px;
    font-weight: 900;
}
QLabel#PageSubtitle {
    color: #765d34;
    font-size: 12px;
    font-weight: 700;
}
QLabel#StepBar {
    background-color: #fffaf0;
    border: 1px solid #d9bd82;
    border-radius: 11px;
    color: #6c5428;
    font-size: 12px;
    font-weight: 900;
    padding: 5px 12px;
}
QLabel#SectionTitle {
    font-size: 20px;
    font-weight: 900;
}
QLabel#FieldLabel {
    font-size: 13px;
}
QLabel#Hint {
    color: #765d34;
    font-size: 11px;
}
QLabel#EmptyMessage {
    color: #765d34;
    font-size: 11px;
    font-style: italic;
    padding: 5px 2px;
}
QCheckBox {
    background: transparent;
    border: none;
    color: #25190f;
    font-family: Georgia;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox:disabled {
    color: #6c5428;
}
QScrollArea#ChoiceList {
    background-color: #fffaf0;
    border: 1px solid #d9bd82;
    border-radius: 9px;
}
QScrollArea#ChoiceList QWidget {
    background-color: #fffaf0;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: #d9bd82;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background-color: #c79a3b;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
QPushButton {
    background-color: #fffdf7;
    border: 1px solid #c79a3b;
    border-radius: 9px;
    color: #4f3b18;
    font-family: Georgia;
    font-size: 12px;
    font-weight: 800;
    padding: 5px 13px;
    margin: 0px;
}
QPushButton:hover {
    background-color: #fff4df;
    border-color: #a87824;
    color: #25190f;
}
QPushButton:pressed {
    background-color: #f5ead2;
}
QPushButton#PrimaryButton {
    background-color: #d8edf7;
    border: 1px solid #c79a3b;
    color: #25190f;
}
QPushButton#PrimaryButton:hover {
    background-color: #e8f5fb;
    border-color: #a87824;
}
QPushButton#PrimaryButton:pressed {
    background-color: #c9e3ef;
}
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
        self.resize(790, 610)
        self.setMinimumSize(720, 560)
        set_themed_stylesheet(self, PRIVACY_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(8)

        title = QLabel("Sharing & Privacy")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(title)

        subtitle = QLabel(
            "Choose what this character shares with the campaign DM. "
            "Nothing optional is shared unless you enable it."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        character_name = str(getattr(character, "name", "") or "Character").strip()
        step = QLabel(f"Character Sharing  •  {character_name}")
        step.setObjectName("StepBar")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(step)

        heading = QLabel("What the DM can see")
        heading.setObjectName("SectionTitle")
        root.addWidget(heading)

        help_text = QLabel(
            "Core campaign data is required for live play. Everything else below is optional. "
            "Archived session snapshots keep whatever was shared when the snapshot was created."
        )
        help_text.setObjectName("PageSubtitle")
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        form = QGridLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setColumnMinimumWidth(0, 165)
        form.setColumnStretch(1, 1)

        core_label = QLabel("Always Shared")
        core_label.setObjectName("FieldLabel")
        form.addWidget(core_label, 0, 0, Qt.AlignmentFlag.AlignTop)

        core = QCheckBox(
            "Core tactical data - identity, level, Hearts, AT, IP, abilities and defense"
        )
        core.setChecked(True)
        core.setEnabled(False)
        form.addWidget(core, 0, 1)

        improvements_label = QLabel("Improvements")
        improvements_label.setObjectName("FieldLabel")
        form.addWidget(improvements_label, 1, 0)
        self.improvements = QCheckBox("Share Improvements")
        self.improvements.setChecked(self.preferences["share_improvements"])
        form.addWidget(self.improvements, 1, 1)

        portrait_label = QLabel("Portrait")
        portrait_label.setObjectName("FieldLabel")
        form.addWidget(portrait_label, 2, 0)
        self.portrait = QCheckBox("Share character portrait")
        self.portrait.setChecked(self.preferences["share_portrait"])
        form.addWidget(self.portrait, 2, 1)

        backstory_label = QLabel("Backstory")
        backstory_label.setObjectName("FieldLabel")
        form.addWidget(backstory_label, 3, 0)
        self.backstory = QCheckBox("Share backstory")
        self.backstory.setChecked(self.preferences["share_backstory"])
        form.addWidget(self.backstory, 3, 1)

        inventory_label = QLabel("Inventory")
        inventory_label.setObjectName("FieldLabel")
        inventory_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        form.addWidget(inventory_label, 4, 0)

        inventory_column = QVBoxLayout()
        inventory_column.setContentsMargins(0, 0, 0, 0)
        inventory_column.setSpacing(5)
        self.inventory = QCheckBox("Share selected inventory items")
        self.inventory.setChecked(self.preferences["share_inventory"])
        inventory_column.addWidget(self.inventory)

        inventory_hint = QLabel(
            "Only checked items are shared, including their quantity and description."
        )
        inventory_hint.setObjectName("Hint")
        inventory_hint.setWordWrap(True)
        inventory_column.addWidget(inventory_hint)

        self.inventory_scroll, inventory_layout = self._make_list_area()
        self.inventory_empty = QLabel("No inventory items on this character.")
        self.inventory_empty.setObjectName("EmptyMessage")
        inventory_column.addWidget(self.inventory_scroll)
        inventory_column.addWidget(self.inventory_empty)
        self._populate_inventory(inventory_layout)
        form.addLayout(inventory_column, 4, 1)

        notes_label = QLabel("Notes")
        notes_label.setObjectName("FieldLabel")
        notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        form.addWidget(notes_label, 5, 0)

        notes_column = QVBoxLayout()
        notes_column.setContentsMargins(0, 0, 0, 0)
        notes_column.setSpacing(5)
        self.notes = QCheckBox("Share selected notes")
        self.notes.setChecked(self.preferences["share_notes"])
        notes_column.addWidget(self.notes)

        notes_hint = QLabel(
            "Notes are never shared automatically. Only checked notes are sent to the DM."
        )
        notes_hint.setObjectName("Hint")
        notes_hint.setWordWrap(True)
        notes_column.addWidget(notes_hint)

        self.notes_scroll, notes_layout = self._make_list_area()
        self.notes_empty = QLabel("No notes on this character.")
        self.notes_empty.setObjectName("EmptyMessage")
        notes_column.addWidget(self.notes_scroll)
        notes_column.addWidget(self.notes_empty)
        self._populate_notes(notes_layout)
        form.addLayout(notes_column, 5, 1)

        root.addLayout(form, 1)

        self.inventory.toggled.connect(self._refresh_enabled_state)
        self.notes.toggled.connect(self._refresh_enabled_state)
        self._refresh_enabled_state()

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("PrimaryButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)

        for button in (cancel, save):
            button.setMinimumHeight(36)
            button.adjustSize()
            button.setFixedWidth(button.sizeHint().width())

        buttons.addWidget(cancel)
        buttons.addStretch()
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _make_list_area(self):
        scroll = QScrollArea()
        scroll.setObjectName("ChoiceList")
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(82)
        scroll.setMaximumHeight(105)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)
        scroll.setWidget(body)
        return scroll, layout

    def _populate_inventory(self, layout):
        selected = set(self.preferences["inventory_item_ids"])
        items = list(
            getattr(getattr(self.character, "inventory", None), "list_of_items", []) or []
        )
        has_items = False
        for item in items:
            item_id = str(getattr(item, "id", "") or "").strip()
            if not item_id:
                continue
            has_items = True
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
        self.inventory_scroll.setVisible(has_items)
        self.inventory_empty.setVisible(not has_items)

    def _populate_notes(self, layout):
        selected = set(self.preferences["note_ids"])
        notes = list(
            getattr(getattr(self.character, "notes", None), "list_of_notes", []) or []
        )
        has_notes = False
        for note in notes:
            note_id = str(getattr(note, "id", "") or "").strip()
            if not note_id:
                continue
            has_notes = True
            title = str(getattr(note, "title", "") or "Untitled note").strip() or "Untitled note"
            linked = str(getattr(note, "linked_improvement_id", "") or "").strip()
            label = f"{title}  (linked note)" if linked else title
            box = QCheckBox(label)
            box.setChecked(note_id in selected)
            self.note_boxes[note_id] = box
            layout.addWidget(box)
        layout.addStretch()
        self.notes_scroll.setVisible(has_notes)
        self.notes_empty.setVisible(not has_notes)

    def _refresh_enabled_state(self):
        inventory_enabled = self.inventory.isChecked()
        self.inventory_scroll.setEnabled(inventory_enabled)
        for box in self.inventory_boxes.values():
            box.setEnabled(inventory_enabled)

        notes_enabled = self.notes.isChecked()
        self.notes_scroll.setEnabled(notes_enabled)
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
