from dataclasses import dataclass, field
from typing import Any, Dict
import json
import os
import re
from uuid import uuid4

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeySequence, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from ui_widgets import NumericEntry

from ui_theme import (
    set_themed_stylesheet,
)


# ============================================================
# CONSTANTS
# ============================================================

TEMPLATE_FILE_TYPE = "did_character_template"
TEMPLATE_FILE_VERSION = 4
TEMPLATE_EXTENSION = ".didtemplate"

try:
    from character_API import (
        ABILITY_ARRAYS,
        IMPROVEMENT_CATALOG,
    )
except ImportError:
    ABILITY_ARRAY = []
    IMPROVEMENT_CATALOG = {}

BLUE = "#d8edf7"


FANTASY_DIALOG_QSS = """
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

    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QListWidget {
        background-color: #fffaf0;
        border: 1px solid #d9bd82;
        border-radius: 9px;
        padding: 6px 8px;
        color: #25190f;
        font-family: Georgia;
        font-size: 13px;
        selection-background-color: #d8edf7;
        selection-color: #25190f;
    }

    QLineEdit:focus,
    QTextEdit:focus,
    QComboBox:focus,
    QSpinBox:focus,
    QListWidget:focus {
        background-color: #fffdf7;
        border: 1px solid #a87824;
    }

    QComboBox::drop-down {
        width: 26px;
        border: none;
        border-left: 1px solid #d9bd82;
        background-color: #d8edf7;
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
    }

    QComboBox QAbstractItemView {
        background-color: #fffdf7;
        border: 1px solid #cdaa63;
        color: #25190f;
        selection-background-color: #d8edf7;
        selection-color: #25190f;
        outline: none;
        padding: 4px;
    }

    QListWidget {
        padding: 6px;
        outline: none;
    }

    QListWidget::item {
        border: none;
        border-radius: 7px;
        padding: 7px 9px;
        margin: 1px 0px;
    }

    QListWidget::item:selected {
        background-color: #d8edf7;
        color: #25190f;
    }

    QListWidget::item:hover {
        background-color: #fff4df;
    }

    QCheckBox {
        background: transparent;
        border: none;
        color: #25190f;
        font-family: Georgia;
        font-size: 13px;
        font-weight: 700;
        spacing: 8px;
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
"""


BUTTON_PRIMARY_QSS = """
    QPushButton {
        background-color: #d8edf7;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-size: 12px;
        font-weight: 800;
        color: #25190f;
        padding: 5px 13px;
        margin: 0px;
    }

    QPushButton:hover {
        background-color: #e8f5fb;
        border-color: #a87824;
    }

    QPushButton:pressed {
        background-color: #c9e3ef;
    }

    QPushButton:disabled {
        background-color: #eee9df;
        border-color: #d8ccb5;
        color: #9b9388;
    }
"""


BUTTON_SECONDARY_QSS = """
    QPushButton {
        background-color: #fffdf7;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-size: 12px;
        font-weight: 800;
        color: #4f3b18;
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
"""


def make_positive_button(button):
    set_themed_stylesheet(
        button,
        BUTTON_PRIMARY_QSS,
    )


def make_negative_button(button):
    set_themed_stylesheet(
        button,
        BUTTON_SECONDARY_QSS,
    )


def make_normal_button(button):
    set_themed_stylesheet(
        button,
        BUTTON_SECONDARY_QSS,
    )


class TemplateRichTextEdit(QTextEdit):
    """Rich-text editor with the standard formatting shortcuts."""

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Bold):
            self._toggle_format("bold")
            event.accept()
            return

        if event.matches(QKeySequence.StandardKey.Italic):
            self._toggle_format("italic")
            event.accept()
            return

        if event.matches(QKeySequence.StandardKey.Underline):
            self._toggle_format("underline")
            event.accept()
            return

        super().keyPressEvent(event)

    def _toggle_format(self, kind):
        current = self.currentCharFormat()
        fmt = QTextCharFormat()

        if kind == "bold":
            fmt.setFontWeight(
                400 if current.fontWeight() >= 700 else 700
            )
        elif kind == "italic":
            fmt.setFontItalic(not current.fontItalic())
        elif kind == "underline":
            fmt.setFontUnderline(not current.fontUnderline())

        self.mergeCurrentCharFormat(fmt)

    def set_stored_text(self, value):
        value = str(value or "")
        lowered = value.lower()

        if any(tag in lowered for tag in (
            "<b", "<strong", "<i", "<em", "<u", "<span",
            "<p", "<br", "<div",
        )):
            self.setHtml(value)
        else:
            self.setPlainText(value)

    def stored_html(self):
        if not self.toPlainText().strip():
            return ""

        html_text = self.document().toHtml()
        match = re.search(
            r"<body[^>]*>(.*)</body>",
            html_text,
            re.IGNORECASE | re.DOTALL,
        )
        return (match.group(1) if match else html_text).strip()


class TemplateImprovementEditDialog(QDialog):
    """Edit the template-facing name, IP cost and description of an improvement."""

    def __init__(
        self,
        parent=None,
        *,
        name="",
        cost=0,
        description="",
        custom=False,
    ):
        super().__init__(parent)
        self.custom = bool(custom)
        self.result_data = None
        self.delete_requested = False

        self.setWindowTitle(
            "Edit Template Improvement"
            if not custom
            else "Template Custom Improvement"
        )
        self.setFixedSize(520, 430)
        set_themed_stylesheet(self, FANTASY_DIALOG_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)

        layout.addWidget(QLabel("Name"))
        self.name_input = QLineEdit(str(name))
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("IP Cost"))
        self.cost_input = NumericEntry()
        self.cost_input.setRange(0, 99)
        self.cost_input.setValue(max(0, int(cost)))
        self.cost_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        layout.addWidget(self.cost_input)

        layout.addWidget(QLabel("Description"))
        self.description_input = TemplateRichTextEdit()
        self.description_input.set_stored_text(description)
        self.description_input.setPlaceholderText(
            "Ctrl+B = bold   •   Ctrl+I = italic   •   Ctrl+U = underline"
        )
        layout.addWidget(self.description_input, 1)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        make_negative_button(cancel)
        make_positive_button(save)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)

        if self.custom:
            delete = QPushButton("Delete")
            make_negative_button(delete)
            delete.clicked.connect(self._delete)
            buttons.addWidget(delete)

        buttons.addStretch()
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Enter an improvement name.")
            return

        self.result_data = {
            "name": name,
            "cost": int(self.cost_input.value()),
            "description": self.description_input.stored_html(),
        }
        self.accept()

    def _delete(self):
        self.delete_requested = True
        self.accept()

# ============================================================
# CHARACTER CREATION RULES
# ============================================================

@dataclass
class CharacterCreationRules:
    """
    Rules that are applied when a character is created
    from a template.

    These are creation rules only.

    They do not create an ongoing connection between
    the character and the template.
    """

    level: int = 1
    extra_ip: int = 0

    # "disabled"
    #     Species are not used.
    #
    # "required"
    #     The player must use a Species.
    #
    # We can add more modes later if needed.
    species_mode: str = "normal"

    # These are included now because they are useful template
    # concepts, but they are deliberately optional.
    #
    # None means:
    # "Use the normal character-sheet default."
    starting_hearts: int | None = None
    starting_at: int | None = None

    # Custom Improvements can be disabled by the GM.
    allow_custom_improvements: bool = True

    # Empty means all normal ability arrays are available.
    allowed_ability_array_ids: list[str] = field(default_factory=list)

    # Number of free Heightened Ability choices granted at creation.
    free_heightened_ability_slots: int = 2

    # When enabled, only die sizes used by the selected legal arrays may
    # be chosen in the ability editor.
    restrict_ability_dice_to_allowed_arrays: bool = False

    # "all", "allow_only", or "ban".
    improvement_mode: str = "all"
    improvement_ids: list[str] = field(default_factory=list)

    # Template-specific presentation/cost overrides for catalog improvements.
    # Mechanics such as effects, choices and empowerments stay attached to the
    # original catalog entry.
    improvement_overrides: dict[str, dict] = field(default_factory=dict)

    # Completely new Improvements that only exist for characters created
    # from this template.
    template_custom_improvements: list[dict] = field(default_factory=list)

    def validate(self) -> None:
        try:
            self.level = int(
                self.level
            )
        except (TypeError, ValueError):
            self.level = 1

        self.level = max(
            1,
            self.level,
        )

        try:
            self.extra_ip = int(
                self.extra_ip
            )
        except (TypeError, ValueError):
            self.extra_ip = 0

        self.extra_ip = max(
            0,
            self.extra_ip,
        )

        if self.species_mode not in {
            "normal",
            "disabled",
            "required",
        }:
            self.species_mode = "normal"

        if self.starting_hearts is not None:
            try:
                self.starting_hearts = int(
                    self.starting_hearts
                )
            except (TypeError, ValueError):
                self.starting_hearts = None

            if self.starting_hearts is not None:
                self.starting_hearts = max(
                    1,
                    self.starting_hearts,
                )

        if self.starting_at is not None:
            try:
                self.starting_at = int(
                    self.starting_at
                )
            except (TypeError, ValueError):
                self.starting_at = None

            if self.starting_at is not None:
                self.starting_at = max(
                    0,
                    self.starting_at,
                )

        self.allow_custom_improvements = bool(
            self.allow_custom_improvements
        )

        if not isinstance(self.allowed_ability_array_ids, list):
            self.allowed_ability_array_ids = []
        self.allowed_ability_array_ids = [
            str(value) for value in self.allowed_ability_array_ids
            if str(value).strip()
        ]

        try:
            self.free_heightened_ability_slots = int(
                self.free_heightened_ability_slots
            )
        except (TypeError, ValueError):
            self.free_heightened_ability_slots = 2

        self.free_heightened_ability_slots = max(
            0,
            self.free_heightened_ability_slots,
        )

        self.restrict_ability_dice_to_allowed_arrays = bool(
            self.restrict_ability_dice_to_allowed_arrays
        )

        if self.improvement_mode not in {"all", "allow_only", "ban"}:
            self.improvement_mode = "all"

        if not isinstance(self.improvement_ids, list):
            self.improvement_ids = []
        self.improvement_ids = [
            str(value) for value in self.improvement_ids
            if str(value).strip()
        ]

        if not isinstance(self.improvement_overrides, dict):
            self.improvement_overrides = {}

        clean_overrides = {}
        for catalog_id, override in self.improvement_overrides.items():
            if not isinstance(override, dict):
                continue
            catalog_id = str(catalog_id).strip()
            if not catalog_id:
                continue
            clean_overrides[catalog_id] = {
                "name": str(override.get("name", "")).strip(),
                "cost": max(0, int(override.get("cost", 0))),
                "description": str(override.get("description", "")),
            }
        self.improvement_overrides = clean_overrides

        if not isinstance(self.template_custom_improvements, list):
            self.template_custom_improvements = []

        clean_custom = []
        seen_ids = set()
        for item in self.template_custom_improvements:
            if not isinstance(item, dict):
                continue
            catalog_id = str(item.get("id", "")).strip()
            if not catalog_id or catalog_id in seen_ids:
                continue
            seen_ids.add(catalog_id)
            clean_custom.append({
                "id": catalog_id,
                "name": str(item.get("name", "Custom Improvement")).strip() or "Custom Improvement",
                "cost": max(0, int(item.get("cost", 0))),
                "description": str(item.get("description", "")),
                "purchase_rule": "single",
                "requires_choices": [],
                "effects": [],
                "tags": ["template", "custom"],
            })
        self.template_custom_improvements = clean_custom


# ============================================================
# CHARACTER TEMPLATE
# ============================================================

@dataclass
class CharacterTemplate:
    """
    Portable character-creation template made by a GM.

    A .didtemplate contains one of these.

    The template controls the INITIAL CREATION of a character.
    It does not continue controlling the character afterward.
    """

    name: str = "New Character Template"

    description: str = ""

    player_instructions: str = ""

    rules: CharacterCreationRules = field(
        default_factory=CharacterCreationRules
    )

    def validate(self) -> None:
        self.name = str(
            self.name
        ).strip()

        self.description = str(
            self.description
        ).strip()

        self.player_instructions = str(
            self.player_instructions
        ).strip()

        if not self.name:
            self.name = "Character Template"

        if not isinstance(
            self.rules,
            CharacterCreationRules,
        ):
            self.rules = CharacterCreationRules()

        self.rules.validate()


# ============================================================
# TEMPLATE STORAGE
# ============================================================

class CharacterTemplateStorage:
    """
    Save and load portable .didtemplate files.

    Unlike the old campaign system, a template is just one file.
    It does not create folders or manage character files.
    """

    @staticmethod
    def template_to_dict(
        template: CharacterTemplate,
    ) -> Dict[str, Any]:

        template.validate()

        return {
            "name": template.name,
            "description": template.description,
            "player_instructions": (
                template.player_instructions
            ),

            "rules": {
                "level": (
                    template.rules.level
                ),

                "extra_ip": (
                    template.rules.extra_ip
                ),

                "species_mode": (
                    template.rules.species_mode
                ),

                "starting_hearts": (
                    template.rules.starting_hearts
                ),

                "starting_at": (
                    template.rules.starting_at
                ),

                "allow_custom_improvements": (
                    template.rules
                    .allow_custom_improvements
                ),
                "allowed_ability_array_ids": (
                    template.rules.allowed_ability_array_ids
                ),
                "free_heightened_ability_slots": (
                    template.rules.free_heightened_ability_slots
                ),
                "restrict_ability_dice_to_allowed_arrays": (
                    template.rules.restrict_ability_dice_to_allowed_arrays
                ),
                "improvement_mode": template.rules.improvement_mode,
                "improvement_ids": template.rules.improvement_ids,
                "improvement_overrides": template.rules.improvement_overrides,
                "template_custom_improvements": (
                    template.rules.template_custom_improvements
                ),
            },
        }

    @staticmethod
    def template_from_dict(
        data: Dict[str, Any],
    ) -> CharacterTemplate:

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Invalid character template data."
            )

        rules_data = data.get(
            "rules",
            {},
        )

        if not isinstance(
            rules_data,
            dict,
        ):
            rules_data = {}

        template = CharacterTemplate(
            name=data.get(
                "name",
                "Character Template",
            ),

            description=data.get(
                "description",
                "",
            ),

            player_instructions=data.get(
                "player_instructions",
                "",
            ),

            rules=CharacterCreationRules(
                level=rules_data.get(
                    "level",
                    1,
                ),

                extra_ip=rules_data.get(
                    "extra_ip",
                    0,
                ),

                species_mode=rules_data.get(
                    "species_mode",
                    "normal",
                ),

                starting_hearts=rules_data.get(
                    "starting_hearts",
                    None,
                ),

                starting_at=rules_data.get(
                    "starting_at",
                    None,
                ),

                allow_custom_improvements=(
                    rules_data.get(
                        "allow_custom_improvements",
                        True,
                    )
                ),
                allowed_ability_array_ids=rules_data.get(
                    "allowed_ability_array_ids", []
                ),
                free_heightened_ability_slots=rules_data.get(
                    "free_heightened_ability_slots",
                    2,
                ),
                restrict_ability_dice_to_allowed_arrays=rules_data.get(
                    "restrict_ability_dice_to_allowed_arrays",
                    False,
                ),
                improvement_mode=rules_data.get(
                    "improvement_mode", "all"
                ),
                improvement_ids=rules_data.get(
                    "improvement_ids", []
                ),
                improvement_overrides=rules_data.get(
                    "improvement_overrides", {}
                ),
                template_custom_improvements=rules_data.get(
                    "template_custom_improvements", []
                ),
            ),
        )

        template.validate()

        return template

    @staticmethod
    def save_template(
        template: CharacterTemplate,
        filepath: str,
    ) -> str:

        if not isinstance(
            template,
            CharacterTemplate,
        ):
            raise TypeError(
                "Expected CharacterTemplate."
            )

        template.validate()

        if not filepath.lower().endswith(
            TEMPLATE_EXTENSION
        ):
            filepath += TEMPLATE_EXTENSION

        data = {
            "file_type": TEMPLATE_FILE_TYPE,
            "file_version": TEMPLATE_FILE_VERSION,
            "template": (
                CharacterTemplateStorage
                .template_to_dict(
                    template
                )
            ),
        }

        # Save safely through a temporary file.
        #
        # If writing fails, an existing template is not
        # destroyed halfway through.
        temp_path = (
            filepath
            + ".tmp"
        )

        try:
            with open(
                temp_path,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            os.replace(
                temp_path,
                filepath,
            )

        finally:
            if os.path.exists(
                temp_path
            ):
                try:
                    os.remove(
                        temp_path
                    )
                except OSError:
                    pass

        return filepath

    @staticmethod
    def load_template(
        filepath: str,
    ) -> CharacterTemplate:

        with open(
            filepath,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Invalid DID character template."
            )

        if data.get(
            "file_type"
        ) != TEMPLATE_FILE_TYPE:

            raise ValueError(
                "This is not a DID character template."
            )

        file_version = data.get(
            "file_version",
            1,
        )

        if file_version > TEMPLATE_FILE_VERSION:
            raise ValueError(
                "This character template was created "
                "by a newer version of the DID "
                "Character Sheet."
            )

        template_data = data.get(
            "template",
            {},
        )

        return (
            CharacterTemplateStorage
            .template_from_dict(
                template_data
            )
        )


# ============================================================
# TEMPLATE EDITOR
# ============================================================

class CharacterTemplateDialog(QDialog):
    """GM-facing step-by-step editor for .didtemplate files."""

    PAGE_TITLES = (
        "Template",
        "Starting Character",
        "Abilities",
        "Improvements",
        "Other Rules",
        "Review & Save",
    )

    def __init__(self, parent=None, template=None):
        super().__init__(parent)
        self.template = template or CharacterTemplate()
        self.saved_filepath = None

        self.setWindowTitle("Creation Rules")
        self.resize(790, 610)
        self.setMinimumSize(720, 560)

        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        self.build_ui()
        self.load_template_into_ui()
        self.show_page(0)

    def _page(self, title, help_text):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(10)

        heading = QLabel(title)
        set_themed_stylesheet(
            heading,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 20px;
                font-weight: 900;
                color: #25190f;
            }
            """,
        )
        layout.addWidget(heading)

        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        set_themed_stylesheet(
            help_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 600;
                color: #765d34;
            }
            """,
        )
        layout.addWidget(help_label)
        return page, layout

    @staticmethod
    def _row(label_text, widget):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(220)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(9)

        title = QLabel("Character Creation Template")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 24px;
                font-weight: 900;
                color: #25190f;
                padding: 1px 0px;
            }
            """,
        )
        outer.addWidget(title)

        subtitle = QLabel(
            "Set the starting rules, save the template, and send the "
            ".didtemplate file to your players."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        set_themed_stylesheet(
            subtitle,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 600;
                color: #765d34;
            }
            """,
        )
        outer.addWidget(subtitle)

        self.step_label = QLabel()
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(
            self.step_label,
            """
            QLabel {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 11px;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 900;
                color: #6c5428;
                padding: 5px 12px;
            }
            """,
        )
        outer.addWidget(self.step_label)

        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)

        self._build_template_page()
        self._build_starting_page()
        self._build_abilities_page()
        self._build_improvements_page()
        self._build_other_page()
        self._build_review_page()

        buttons = QHBoxLayout()
        self.load_button = QPushButton("Load Template")
        self.back_button = QPushButton("← Back")
        self.close_button = QPushButton("Close")
        self.next_button = QPushButton("Next →")
        self.save_button = QPushButton("Save Template")

        for button in (
            self.load_button, self.back_button, self.close_button,
            self.next_button, self.save_button
        ):
            button.setMinimumHeight(36)

        make_normal_button(self.load_button)
        make_normal_button(self.back_button)
        make_negative_button(self.close_button)
        make_positive_button(self.next_button)
        make_positive_button(self.save_button)

        self.load_button.clicked.connect(self.load_template_from_ui)
        self.back_button.clicked.connect(
            lambda: self.show_page(self.pages.currentIndex() - 1)
        )
        self.next_button.clicked.connect(self.next_page)
        self.close_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.save_template_from_ui)

        buttons.addWidget(self.load_button)
        buttons.addStretch()
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.close_button)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.save_button)
        outer.addLayout(buttons)

    def _build_template_page(self):
        page, layout = self._page(
            "Template",
            "Name this character-creation setup and add any information "
            "players should read before they begin."
        )

        layout.addWidget(QLabel("Template Name"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("For example: The University Campaign")
        self.name_input.setMinimumHeight(44)
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Description"))
        self.description_input = TemplateRichTextEdit()
        self.description_input.setPlaceholderText(
            "A short description of this game or character-creation setup."
        )
        self.description_input.setFixedHeight(74)
        layout.addWidget(self.description_input)

        layout.addWidget(QLabel("Instructions for Players"))
        self.instructions_input = TemplateRichTextEdit()
        self.instructions_input.setPlaceholderText(
            "Anything players should know before creating their characters."
        )
        self.instructions_input.setFixedHeight(82)
        layout.addWidget(self.instructions_input)
        layout.addStretch()
        self.pages.addWidget(page)

    def _build_starting_page(self):
        page, layout = self._page(
            "Starting Character",
            "Choose the basic values used when a character is created "
            "from this template."
        )

        self.level_input = NumericEntry()
        self.level_input.setRange(1, 99)
        self.level_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.level_input.setMinimumHeight(42)
        layout.addLayout(self._row("Starting Level", self.level_input))

        self.extra_ip_input = NumericEntry()
        self.extra_ip_input.setRange(0, 99)
        self.extra_ip_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.extra_ip_input.setMinimumHeight(42)
        layout.addLayout(self._row("Extra Starting IP", self.extra_ip_input))

        self.free_heightened_input = NumericEntry()
        self.free_heightened_input.setRange(0, 99)
        self.free_heightened_input.setButtonSymbols(
            QSpinBox.ButtonSymbols.NoButtons
        )
        self.free_heightened_input.setMinimumHeight(42)
        layout.addLayout(
            self._row(
                "Free Heightened Abilities",
                self.free_heightened_input,
            )
        )

        self.species_input = QComboBox()
        self.species_input.setMinimumHeight(42)
        self.species_input.addItem("Normal / Optional", "normal")
        self.species_input.addItem("Disabled", "disabled")
        self.species_input.addItem("Required", "required")
        layout.addLayout(self._row("Species", self.species_input))

        self.custom_hearts_checkbox = QCheckBox("Override normal starting Hearts")
        layout.addWidget(self.custom_hearts_checkbox)
        self.hearts_input = NumericEntry()
        self.hearts_input.setRange(1, 99)
        self.hearts_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.hearts_input.setMinimumHeight(42)
        layout.addLayout(self._row("Starting Hearts", self.hearts_input))

        self.custom_at_checkbox = QCheckBox("Override normal starting AT")
        layout.addWidget(self.custom_at_checkbox)
        self.at_input = NumericEntry()
        self.at_input.setRange(0, 99)
        self.at_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.at_input.setMinimumHeight(42)
        layout.addLayout(self._row("Starting AT", self.at_input))

        self.custom_hearts_checkbox.toggled.connect(self.update_optional_controls)
        self.custom_at_checkbox.toggled.connect(self.update_optional_controls)

        layout.addStretch()
        self.pages.addWidget(page)

    def _build_abilities_page(self):
        page, layout = self._page(
            "Abilities",
            "Check the starting ability arrays players may choose. "
            "If none are checked, all normal arrays are allowed."
        )

        self.ability_array_list = QListWidget()
        for array in ABILITY_ARRAYS:
            item = QListWidgetItem(
                array.get("name", array.get("id", "Unknown Array"))
            )
            item.setData(Qt.ItemDataRole.UserRole, array.get("id"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            dice = ", ".join(f"d{x}" for x in array.get("dice", []))
            item.setToolTip(
                (array.get("description", "") +
                 ("\nDice: " + dice if dice else "")).strip()
            )
            self.ability_array_list.addItem(item)

        layout.addWidget(self.ability_array_list, 1)

        self.restrict_array_dice_checkbox = QCheckBox(
            "Only allow die sizes that appear in the selected arrays"
        )
        self.restrict_array_dice_checkbox.setToolTip(
            "If Jack of All Trades is the only selected array, d4 and d12 "
            "will not be available in the ability editor."
        )
        layout.addWidget(self.restrict_array_dice_checkbox)

        self.pages.addWidget(page)

    def _build_improvements_page(self):
        page, layout = self._page(
            "Improvements",
            "Choose which Improvements exist for this template. Use the pen "
            "to change an available Improvement's name, IP cost or description, "
            "or add an Improvement that exists only in this template."
        )

        top_row = QHBoxLayout()

        self.improvement_mode_input = QComboBox()
        self.improvement_mode_input.setMinimumHeight(42)
        self.improvement_mode_input.addItem("Allow All Improvements", "all")
        self.improvement_mode_input.addItem(
            "Allow Only Selected Improvements", "allow_only"
        )
        self.improvement_mode_input.addItem(
            "Ban Selected Improvements", "ban"
        )
        top_row.addWidget(self.improvement_mode_input, 1)

        self.add_template_improvement_btn = QPushButton(
            "+ Custom Improvement"
        )
        self.add_template_improvement_btn.setMinimumHeight(42)
        make_positive_button(self.add_template_improvement_btn)
        self.add_template_improvement_btn.clicked.connect(
            self.add_template_custom_improvement
        )
        top_row.addWidget(self.add_template_improvement_btn)
        layout.addLayout(top_row)

        self.improvement_list = QListWidget()
        self._improvement_row_widgets = {}
        self._template_improvement_overrides = {}
        self._template_custom_improvements = []

        for improvement_id, improvement in sorted(
            IMPROVEMENT_CATALOG.items(),
            key=lambda pair: str(pair[1].get("name", pair[0])).lower(),
        ):
            if improvement_id == "custom":
                continue
            self._add_improvement_editor_row(
                improvement_id,
                improvement,
                custom=False,
            )

        layout.addWidget(self.improvement_list, 1)
        self.improvement_mode_input.currentIndexChanged.connect(
            self.update_improvement_controls
        )
        self.pages.addWidget(page)

    def _add_improvement_editor_row(
        self,
        improvement_id,
        improvement_data,
        *,
        custom=False,
    ):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, improvement_id)
        item.setFlags(
            item.flags()
            & ~Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setSizeHint(QSize(0, 54))
        item.setData(
            Qt.ItemDataRole.UserRole + 1,
            bool(custom),
        )
        self.improvement_list.addItem(item)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(8)

        check = QCheckBox()
        check.setFixedWidth(26)
        row_layout.addWidget(
            check,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        card = QFrame()
        card.setObjectName("templateImprovementCard")

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(8)

        set_themed_stylesheet(
            card,
            """
            QFrame#templateImprovementCard {
                background-color: #fffdf7;
                border: 1px solid #d9bd82;
                border-radius: 10px;
            }
            QFrame#templateImprovementCard:hover {
                background-color: #fffaf0;
                border-color: #c79a3b;
            }
            """,
        )

        emblem = QLabel("✦")
        emblem.setFixedWidth(18)
        emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(
            emblem,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 15px;
                font-weight: 900;
                color: #a87824;
                padding: 0px;
                margin: 0px;
            }
            """,
        )
        card_layout.addWidget(
            emblem,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        label = QLabel()
        label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )
        set_themed_stylesheet(
            label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 800;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """,
        )
        card_layout.addWidget(label, 1)

        pen = QPushButton("✎")
        pen.setFixedSize(24, 24)
        pen.setToolTip(
            "Edit this Improvement for this template"
        )
        pen.setCursor(Qt.CursorShape.PointingHandCursor)
        set_themed_stylesheet(
            pen,
            """
            QPushButton {
                background: transparent;
                border: none;
                font-family: "Segoe UI Symbol";
                font-size: 14px;
                font-weight: 700;
                color: #8a651f;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #fff0cf;
                border: 1px solid #d9bd82;
                border-radius: 12px;
                color: #25190f;
            }
            QPushButton:pressed {
                background-color: #f0dfb8;
            }
            """,
        )
        card_layout.addWidget(
            pen,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        cost_label = QLabel()
        cost_label.setMinimumWidth(48)
        cost_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        set_themed_stylesheet(
            cost_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """,
        )
        card_layout.addWidget(
            cost_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        row_layout.addWidget(card, 1)
        self.improvement_list.setItemWidget(item, row)

        self._improvement_row_widgets[improvement_id] = {
            "item": item,
            "row": row,
            "card": card,
            "check": check,
            "emblem": emblem,
            "label": label,
            "pen": pen,
            "cost_label": cost_label,
            "custom": bool(custom),
        }

        check.toggled.connect(
            lambda checked, iid=improvement_id:
                self._improvement_check_changed(iid, checked)
        )
        pen.clicked.connect(
            lambda _checked=False, iid=improvement_id:
                self.edit_template_improvement(iid)
        )

        self._refresh_improvement_row(improvement_id)

    def _effective_improvement_data(self, improvement_id):
        for custom in self._template_custom_improvements:
            if custom.get("id") == improvement_id:
                return dict(custom)

        base = dict(IMPROVEMENT_CATALOG.get(improvement_id, {}))
        override = self._template_improvement_overrides.get(
            improvement_id, {}
        )
        for key in ("name", "cost", "description"):
            if key in override:
                base[key] = override[key]
        return base

    def _refresh_improvement_row(self, improvement_id):
        widgets = self._improvement_row_widgets.get(improvement_id)
        if not widgets:
            return

        data = self._effective_improvement_data(improvement_id)

        widgets["label"].setText(
            str(data.get("name", improvement_id))
        )
        widgets["cost_label"].setText(
            f"({int(data.get('cost', 0))} IP)"
        )

        description = str(data.get("description", ""))
        tooltip = (
            re.sub(r"<[^>]+>", "", description)
            .replace("&nbsp;", " ")
        )
        widgets["row"].setToolTip(tooltip)
        widgets["card"].setToolTip(tooltip)

    def _improvement_check_changed(self, improvement_id, checked):
        widgets = self._improvement_row_widgets.get(improvement_id)
        if not widgets:
            return
        self.update_improvement_controls()

    def _improvement_is_available(self, improvement_id):
        widgets = self._improvement_row_widgets.get(improvement_id)
        if not widgets:
            return False
        checked = widgets["check"].isChecked()
        mode = self.improvement_mode_input.currentData()
        if mode == "all":
            return True
        if mode == "allow_only":
            return checked
        if mode == "ban":
            return not checked
        return True

    def add_template_custom_improvement(self):
        dialog = TemplateImprovementEditDialog(
            self,
            name="",
            cost=1,
            description="",
            custom=True,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not dialog.result_data:
            return

        improvement_id = "template_custom_" + uuid4().hex
        data = {
            "id": improvement_id,
            **dialog.result_data,
            "purchase_rule": "single",
            "requires_choices": [],
            "effects": [],
            "tags": ["template", "custom"],
        }
        self._template_custom_improvements.append(data)
        self._add_improvement_editor_row(
            improvement_id, data, custom=True
        )

        # In Allow Only mode a newly-created template Improvement should be
        # usable immediately; in Ban mode it begins unbanned.
        widgets = self._improvement_row_widgets[improvement_id]
        if self.improvement_mode_input.currentData() == "allow_only":
            widgets["check"].setChecked(True)
        else:
            widgets["check"].setChecked(False)
        self.update_improvement_controls()

    def edit_template_improvement(self, improvement_id):
        if not self._improvement_is_available(improvement_id):
            return

        data = self._effective_improvement_data(improvement_id)
        widgets = self._improvement_row_widgets.get(improvement_id, {})
        custom = bool(widgets.get("custom", False))

        dialog = TemplateImprovementEditDialog(
            self,
            name=data.get("name", improvement_id),
            cost=data.get("cost", 0),
            description=data.get("description", ""),
            custom=custom,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if custom and dialog.delete_requested:
            self._template_custom_improvements = [
                item for item in self._template_custom_improvements
                if item.get("id") != improvement_id
            ]
            row_info = self._improvement_row_widgets.pop(improvement_id)
            row = self.improvement_list.row(row_info["item"])
            self.improvement_list.takeItem(row)
            return

        if not dialog.result_data:
            return

        if custom:
            for item in self._template_custom_improvements:
                if item.get("id") == improvement_id:
                    item.update(dialog.result_data)
                    break
        else:
            base = IMPROVEMENT_CATALOG.get(improvement_id, {})
            override = {}
            for key in ("name", "cost", "description"):
                value = dialog.result_data[key]
                if value != base.get(key, "" if key != "cost" else 0):
                    override[key] = value
            if override:
                self._template_improvement_overrides[improvement_id] = override
            else:
                self._template_improvement_overrides.pop(improvement_id, None)

        self._refresh_improvement_row(improvement_id)

    def _build_other_page(self):
        page, layout = self._page(
            "Other Rules",
            "Set additional permissions for characters created from "
            "this template."
        )

        self.custom_improvements_checkbox = QCheckBox(
            "Allow Custom Improvements"
        )
        layout.addWidget(self.custom_improvements_checkbox)

        help_label = QLabel(
            "If this is disabled, the character-creation flow can hide "
            "the Custom Improvement option."
        )
        help_label.setWordWrap(True)
        set_themed_stylesheet(
            help_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 600;
                color: #765d34;
            }
            """,
        )
        layout.addWidget(help_label)
        layout.addStretch()
        self.pages.addWidget(page)

    def _build_review_page(self):
        page, layout = self._page(
            "Review & Save",
            "Check the template before saving it for your players."
        )

        self.review_text = QTextEdit()
        self.review_text.setReadOnly(True)
        layout.addWidget(self.review_text, 1)
        self.pages.addWidget(page)

    def show_page(self, index):
        index = max(0, min(index, self.pages.count() - 1))
        self.pages.setCurrentIndex(index)

        self.step_label.setText(
            f"Step {index + 1} of {self.pages.count()}  •  "
            f"{self.PAGE_TITLES[index]}"
        )

        self.back_button.setVisible(index > 0)
        self.next_button.setVisible(index < self.pages.count() - 1)
        self.save_button.setVisible(index == self.pages.count() - 1)

        if index == self.pages.count() - 1:
            self.refresh_review()

    def next_page(self):
        current = self.pages.currentIndex()

        if current == 0 and not self.name_input.text().strip():
            QMessageBox.warning(
                self, "Template Name Required",
                "Enter a template name before continuing."
            )
            self.name_input.setFocus()
            return

        if current == 3:
            mode = self.improvement_mode_input.currentData()
            if mode in {"allow_only", "ban"}:
                selected = any(
                    widgets["check"].isChecked()
                    for widgets in self._improvement_row_widgets.values()
                )
                if not selected:
                    QMessageBox.warning(
                        self, "Select Improvements",
                        "This mode requires at least one selected improvement."
                    )
                    return

        self.show_page(current + 1)

    def update_optional_controls(self):
        self.hearts_input.setEnabled(self.custom_hearts_checkbox.isChecked())
        self.at_input.setEnabled(self.custom_at_checkbox.isChecked())

    def update_improvement_controls(self):
        mode = self.improvement_mode_input.currentData()
        self.improvement_list.setEnabled(True)

        for improvement_id, widgets in self._improvement_row_widgets.items():
            widgets["check"].setEnabled(mode != "all")
            widgets["pen"].setVisible(
                self._improvement_is_available(improvement_id)
            )

    def load_template_into_ui(self):
        self.template.validate()
        self.name_input.setText(self.template.name)
        self.description_input.set_stored_text(self.template.description)
        self.instructions_input.set_stored_text(
            self.template.player_instructions
        )

        rules = self.template.rules
        self.level_input.setValue(rules.level)
        self.extra_ip_input.setValue(rules.extra_ip)
        self.free_heightened_input.setValue(
            rules.free_heightened_ability_slots
        )
        self.restrict_array_dice_checkbox.setChecked(
            rules.restrict_ability_dice_to_allowed_arrays
        )

        index = self.species_input.findData(rules.species_mode)
        if index >= 0:
            self.species_input.setCurrentIndex(index)

        self.custom_hearts_checkbox.setChecked(rules.starting_hearts is not None)
        self.hearts_input.setValue(
            rules.starting_hearts if rules.starting_hearts is not None else 2
        )

        self.custom_at_checkbox.setChecked(rules.starting_at is not None)
        self.at_input.setValue(
            rules.starting_at if rules.starting_at is not None else 0
        )

        self.custom_improvements_checkbox.setChecked(
            rules.allow_custom_improvements
        )

        allowed_arrays = set(rules.allowed_ability_array_ids)
        for i in range(self.ability_array_list.count()):
            item = self.ability_array_list.item(i)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in allowed_arrays
                else Qt.CheckState.Unchecked
            )

        index = self.improvement_mode_input.findData(rules.improvement_mode)
        if index >= 0:
            self.improvement_mode_input.setCurrentIndex(index)

        self._template_improvement_overrides = dict(
            rules.improvement_overrides
        )
        self._template_custom_improvements = [
            dict(item) for item in rules.template_custom_improvements
        ]

        for custom in self._template_custom_improvements:
            improvement_id = custom.get("id")
            if (
                improvement_id
                and improvement_id not in self._improvement_row_widgets
            ):
                self._add_improvement_editor_row(
                    improvement_id, custom, custom=True
                )

        selected = set(rules.improvement_ids)
        for improvement_id, widgets in self._improvement_row_widgets.items():
            widgets["check"].blockSignals(True)
            widgets["check"].setChecked(improvement_id in selected)
            widgets["check"].blockSignals(False)
            self._refresh_improvement_row(improvement_id)

        self.update_optional_controls()
        self.update_improvement_controls()

    def read_template_from_ui(self):
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Enter a template name.")

        allowed_arrays = [
            self.ability_array_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.ability_array_list.count())
            if self.ability_array_list.item(i).checkState()
            == Qt.CheckState.Checked
        ]

        improvement_ids = [
            improvement_id
            for improvement_id, widgets in self._improvement_row_widgets.items()
            if widgets["check"].isChecked()
        ]

        template = CharacterTemplate(
            name=name,
            description=self.description_input.stored_html(),
            player_instructions=self.instructions_input.stored_html(),
            rules=CharacterCreationRules(
                level=self.level_input.value(),
                extra_ip=self.extra_ip_input.value(),
                free_heightened_ability_slots=(
                    self.free_heightened_input.value()
                ),
                restrict_ability_dice_to_allowed_arrays=(
                    self.restrict_array_dice_checkbox.isChecked()
                ),
                species_mode=self.species_input.currentData(),
                starting_hearts=(
                    self.hearts_input.value()
                    if self.custom_hearts_checkbox.isChecked() else None
                ),
                starting_at=(
                    self.at_input.value()
                    if self.custom_at_checkbox.isChecked() else None
                ),
                allow_custom_improvements=(
                    self.custom_improvements_checkbox.isChecked()
                ),
                allowed_ability_array_ids=allowed_arrays,
                improvement_mode=self.improvement_mode_input.currentData(),
                improvement_ids=improvement_ids,
                improvement_overrides=dict(
                    self._template_improvement_overrides
                ),
                template_custom_improvements=[
                    dict(item)
                    for item in self._template_custom_improvements
                ],
            ),
        )
        template.validate()
        return template

    def refresh_review(self):
        try:
            template = self.read_template_from_ui()
        except Exception as error:
            self.review_text.setPlainText(str(error))
            return

        rules = template.rules

        selected_arrays = set(rules.allowed_ability_array_ids)
        array_names = [
            array.get("name", array.get("id", "Unknown"))
            for array in ABILITY_ARRAYS
            if array.get("id") in selected_arrays
        ]

        selected_improvements = set(rules.improvement_ids)
        improvement_names = []
        for improvement_id in selected_improvements:
            if improvement_id in IMPROVEMENT_CATALOG:
                data = dict(IMPROVEMENT_CATALOG[improvement_id])
                data.update(rules.improvement_overrides.get(improvement_id, {}))
                improvement_names.append(data.get("name", improvement_id))
                continue
            custom = next(
                (
                    item for item in rules.template_custom_improvements
                    if item.get("id") == improvement_id
                ),
                None,
            )
            if custom:
                improvement_names.append(custom.get("name", improvement_id))

        mode_text = {
            "all": "All normal improvements",
            "allow_only": "Only selected improvements",
            "ban": "All except selected/banned improvements",
        }.get(rules.improvement_mode, rules.improvement_mode)

        lines = [
            f"Template: {template.name}",
            "",
            f"Starting Level: {rules.level}",
            f"Extra Starting IP: {rules.extra_ip}",
            f"Free Heightened Abilities: {rules.free_heightened_ability_slots}",
            f"Species: {self.species_input.currentText()}",
            (
                f"Starting Hearts: {rules.starting_hearts}"
                if rules.starting_hearts is not None
                else "Starting Hearts: Normal default"
            ),
            (
                f"Starting AT: {rules.starting_at}"
                if rules.starting_at is not None
                else "Starting AT: Normal default"
            ),
            "",
            "Ability Arrays:",
            ", ".join(array_names) if array_names else "All normal arrays",
            (
                "Restrict die choices to selected arrays: "
                + (
                    "Yes"
                    if rules.restrict_ability_dice_to_allowed_arrays
                    else "No"
                )
            ),
            "",
            "Improvements:",
            mode_text,
        ]

        if rules.improvement_mode != "all":
            lines.append(
                ", ".join(sorted(improvement_names))
                if improvement_names else "None selected"
            )

        lines.extend([
            "",
            "Custom Improvements: "
            + ("Allowed" if rules.allow_custom_improvements else "Disabled"),
        ])

        if template.description:
            lines.extend([
                "",
                "Description:",
                re.sub(r"<[^>]+>", "", template.description),
            ])
        if template.player_instructions:
            lines.extend([
                "",
                "Instructions for Players:",
                re.sub(r"<[^>]+>", "", template.player_instructions),
            ])

        self.review_text.setPlainText("\n".join(lines))

    def save_template_from_ui(self):
        try:
            template = self.read_template_from_ui()
        except Exception as error:
            QMessageBox.warning(self, "Invalid Template", str(error))
            return

        if (
            template.rules.improvement_mode in {"allow_only", "ban"}
            and not template.rules.improvement_ids
        ):
            QMessageBox.warning(
                self, "Invalid Improvement Rules",
                "Select at least one improvement for this restriction mode."
            )
            self.show_page(3)
            return

        if self.saved_filepath:
            filepath = self.saved_filepath
        else:
            suggested_name = (
                self.safe_filename(template.name) + TEMPLATE_EXTENSION
            )
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Save Character Template",
                suggested_name,
                "DID Character Templates (*.didtemplate)",
            )
            if not filepath:
                return

        try:
            saved_path = CharacterTemplateStorage.save_template(
                template, filepath
            )
        except Exception as error:
            QMessageBox.critical(
                self, "Save Template Failed",
                "Could not save the character template.\n\n"
                f"{error}"
            )
            return

        self.template = template
        self.saved_filepath = saved_path
        QMessageBox.information(
            self, "Template Saved",
            "Character template saved successfully.\n\n"
            f"{saved_path}"
        )

        # Saving finishes the Creation Rules workflow.
        self.accept()

    def load_template_from_ui(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Character Template",
            "",
            "DID Character Templates (*.didtemplate)",
        )
        if not filepath:
            return

        try:
            template = CharacterTemplateStorage.load_template(filepath)
        except Exception as error:
            QMessageBox.critical(
                self, "Open Template Failed",
                "Could not open the character template.\n\n"
                f"{error}"
            )
            return

        self.template = template
        self.saved_filepath = filepath
        self.load_template_into_ui()
        self.show_page(0)

    @staticmethod
    def safe_filename(name):
        invalid = '<>:"/\\|?*'
        clean = "".join("_" if char in invalid else char for char in name)
        clean = clean.strip(" .")
        return clean or "character_template"


# ============================================================
# TEMPLATE APPLICATION
# ============================================================

def apply_template_to_character(
    character,
    template: CharacterTemplate,
):
    """
    Apply a Creation Rules template to a new character.

    The template file is not needed after creation. The rules that must
    continue to be enforced are copied into the character and saved in
    its .didchar file.
    """
    if character is None:
        raise ValueError("No character was provided.")

    if not isinstance(template, CharacterTemplate):
        raise TypeError("Expected CharacterTemplate.")

    template.validate()
    rules = template.rules

    character.set_level(rules.level)

    if rules.extra_ip > 0:
        character.progression.current_IP += int(rules.extra_ip)

    if rules.starting_hearts is not None:
        character.HP.max_hearts = int(rules.starting_hearts)
        character.HP.max_HP = character.HP.max_hearts * 4
        character.HP.current_HP = character.HP.max_HP

    if rules.starting_at is not None:
        character.adversity.max_AT = int(rules.starting_at)
        character.adversity.current_AT = 0

    character.creation_rules_active = True
    character.creation_template_name = template.name
    character.creation_species_mode = rules.species_mode
    character.creation_allow_custom_improvements = (
        rules.allow_custom_improvements
    )
    character.creation_allowed_ability_array_ids = list(
        rules.allowed_ability_array_ids
    )
    character.free_heightened_ability_slots = int(
        rules.free_heightened_ability_slots
    )
    character.creation_restrict_ability_dice_to_allowed_arrays = bool(
        rules.restrict_ability_dice_to_allowed_arrays
    )
    character.creation_improvement_mode = rules.improvement_mode
    character.creation_improvement_ids = list(rules.improvement_ids)
    character.creation_improvement_overrides = dict(
        rules.improvement_overrides
    )
    character.creation_template_custom_improvements = [
        dict(item)
        for item in rules.template_custom_improvements
    ]

    character.validate()
    return character


def _template_html_fragment(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if "<" in value and ">" in value:
        return value
    import html as _html
    return _html.escape(value).replace("\n", "<br>")


def confirm_create_character_from_template(parent, template):
    """Scrollable, rich-text confirmation shown before character creation."""
    rules = template.rules

    species_text = {
        "required": "Required",
        "disabled": "Disabled",
    }.get(rules.species_mode, "Normal / Optional")

    hearts_text = (
        str(rules.starting_hearts)
        if rules.starting_hearts is not None
        else "Normal"
    )
    at_text = (
        str(rules.starting_at)
        if rules.starting_at is not None
        else "Normal"
    )

    dialog = QDialog(parent)
    dialog.setWindowTitle("Create Character From Template")
    dialog.resize(620, 650)
    dialog.setMinimumSize(520, 480)
    set_themed_stylesheet(dialog, FANTASY_DIALOG_QSS)

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(20, 16, 20, 16)
    outer.setSpacing(10)

    title = QLabel("Create Character From Template")
    set_themed_stylesheet(
        title,
        "QLabel { font-family: Georgia; font-size: 22px; "
        "font-weight: 900; color: #25190f; border: none; }",
    )
    outer.addWidget(title)

    browser = QTextEdit()
    browser.setReadOnly(True)
    browser.setAcceptRichText(True)

    browser.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )

    browser.setMinimumHeight(0)

    pieces = [
        f"<b>Template:</b> {_template_html_fragment(template.name)}<br><br>",
        f"<b>Starting Level:</b> {rules.level}<br>",
        f"<b>Extra Starting IP:</b> {rules.extra_ip}<br>",
        f"<b>Species:</b> {species_text}<br>",
        f"<b>Starting Hearts:</b> {hearts_text}<br>",
        f"<b>Starting AT:</b> {at_text}<br>",
    ]

    if template.description:
        pieces.extend([
            "<br>",
            _template_html_fragment(template.description),
        ])

    if template.player_instructions:
        pieces.extend([
            "<br><br><b>GM Instructions:</b><br>",
            _template_html_fragment(template.player_instructions),
        ])

    browser.setHtml("".join(pieces))
    outer.addWidget(browser, 1)

    buttons = QHBoxLayout()
    cancel = QPushButton("Cancel")
    create = QPushButton("Create")
    cancel.setFixedSize(120, 42)
    create.setFixedSize(120, 42)
    make_negative_button(cancel)
    make_positive_button(create)
    cancel.clicked.connect(dialog.reject)
    create.clicked.connect(dialog.accept)
    buttons.addWidget(cancel)
    buttons.addStretch()
    buttons.addWidget(create)
    outer.addLayout(buttons)

    return dialog.exec() == QDialog.DialogCode.Accepted


# ============================================================
# CONVENIENCE FUNCTIONS FOR THE FRONTEND
# ============================================================

def create_template_from_ui(
    parent=None,
):
    """
    Open the GM template editor with a fresh template.
    """

    dialog = CharacterTemplateDialog(
        parent=parent,
        template=CharacterTemplate(),
    )

    dialog.exec()

    return dialog.template


def edit_template_from_ui(
    template,
    parent=None,
):
    """
    Open the editor for an existing CharacterTemplate.
    """

    dialog = CharacterTemplateDialog(
        parent=parent,
        template=template,
    )

    dialog.exec()

    return dialog.template


def load_template_from_file(
    parent=None,
):
    """
    Ask the user for a .didtemplate and return it.

    Returns None if the user cancels.
    """

    filepath, _ = QFileDialog.getOpenFileName(
        parent,
        "Open Character Template",
        "",
        (
            "DID Character Templates "
            "(*.didtemplate)"
        ),
    )

    if not filepath:
        return None

    try:
        return (
            CharacterTemplateStorage
            .load_template(
                filepath
            )
        )

    except Exception as error:
        QMessageBox.critical(
            parent,
            "Open Template Failed",
            (
                "Could not open the character "
                "template.\n\n"
                f"{error}"
            ),
        )

        return None
