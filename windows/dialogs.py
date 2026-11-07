import re
import html

from PySide6.QtCore import (
    Qt,
    QPoint,
)

from PySide6.QtGui import (
    QCursor,
)

from PySide6.QtWidgets import (
    QDialog,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QFrame,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QMessageBox,
    QMenu,
    QSizePolicy,
    QToolTip,
    QWidget,
)

from backend_2_1 import (
    STAT_NAMES,
    StatSystem,
    STAT_POINT_COSTS,
    ImprovementCatalogSystem
)

from character_API import (
    ABILITY_ARRAYS,
    ANIMAL_BUDDY_PERKS,
    animal_buddy_perk_id_from_choices,
    animal_buddy_perk_name,
)

from ui_widgets import NumericEntry

from ui_theme import (
    BLUE,
    set_themed_stylesheet,
    make_positive_button,
    make_negative_button,
    FANTASY_DIALOG_QSS,
    apply_fantasy_dialog_style,
    theme_color,
)


# ===================================
# Improvement rule glossary
# ===================================

RULE_GLOSSARY = {
    "parry": "Spend AT to reduce damage from a hit by 1 HP.",
    "advantage": "Roll a d6 and add it to your check.",
    "disadvantage": "Roll a d6 and subtract it from your check.",
    "exploding_die": (
        "When a die rolls its maximum, roll it again and add the result."
    ),
    "snap_decision": (
        "A rushed check under pressure that must be rolled."
    ),
    "melee": "Within touching distance.",
    "very_close": "About 5-10 feet away.",
    "close": "About 10-30 feet away.",
    "far": "About 30-100 feet away.",
    "very_far": "About 100-300 feet away.",
    "out_of_range": "Beyond Very Far range.",
}

RULE_GLOSSARY_TERMS = [
    (r"\bout\s+of\s+range\b", "out_of_range"),
    (r"\bvery\s+close(?:\s+range)?\b", "very_close"),
    (r"\bvery\s+far(?:\s+range)?\b", "very_far"),
    (r"\bprotect\s+action\b", "protect"),
    (r"\bparry\s+action\b", "parry"),
    (r"\bexploding\s+dice\b", "exploding_die"),
    (r"\bexploding\s+die\b", "exploding_die"),
    (r"\bsnap\s+decision\b", "snap_decision"),
    (r"\bdisadvantage\b", "disadvantage"),
    (r"\badvantage\b", "advantage"),
    (r"\bmelee(?:\s+range)?\b", "melee"),
    (r"\bclose(?:\s+range)?\b", "close"),
    (r"\bfar(?:\s+range)?\b", "far"),
    (r"\bparry\b", "parry"),
]

_RULE_GLOSSARY_REGEX = re.compile(
    "|".join(
        f"(?P<t{index}>{pattern})"
        for index, (pattern, _slug)
        in enumerate(RULE_GLOSSARY_TERMS)
    ),
    re.IGNORECASE,
)


def _rule_slug_from_match(match):
    for index, (_pattern, slug) in enumerate(
        RULE_GLOSSARY_TERMS
    ):
        if match.group(f"t{index}") is not None:
            return slug

    return None


def _plain_rule_text(text):
    plain = re.sub(
        r"<br\s*/?>",
        "\n",
        str(text or ""),
        flags=re.IGNORECASE,
    )

    plain = re.sub(
        r"<[^>]+>",
        "",
        plain,
    )

    return html.unescape(plain)


def _protect_range_from_context(source_text):
    """
    Fill the Protect definition's {range} from the Improvement text.

    If the text does not name a modified Protect range, use the base
    Very Close range.
    """
    plain = _plain_rule_text(source_text)

    match = re.search(
        (
            r"\bprotect\s+action\b"
            r"[^.!?\n]{0,140}?"
            r"\b(very\s+close|very\s+far|close|far|melee)"
            r"\s+range\b"
        ),
        plain,
        flags=re.IGNORECASE,
    )

    if match is None:
        return "Very Close"

    value = " ".join(
        match.group(1).lower().split()
    )

    return {
        "melee": "Melee",
        "very close": "Very Close",
        "close": "Close",
        "far": "Far",
        "very far": "Very Far",
    }.get(
        value,
        value.title(),
    )


def rule_glossary_definition(
    slug,
    source_text="",
):
    if slug == "protect":
        range_name = _protect_range_from_context(
            source_text
        )

        return (
            "Spend 1 AT to take an attack aimed at "
            f"an ally at {range_name} range."
        )

    return RULE_GLOSSARY.get(
        slug,
        "",
    )


def apply_rule_glossary_html(
    source_text,
    link_color=None,
):
    """
    Wrap glossary terms in invisible HTML links while preserving existing
    formatting such as <b>...</b>.
    """
    source_text = str(
        source_text or ""
    )

    if link_color is None:
        link_color = theme_color(
            "fantasy_text"
        )

    parts = re.split(
        r"(<[^>]+>)",
        source_text,
    )

    output = []

    for part in parts:
        if not part:
            continue

        if (
            part.startswith("<")
            and part.endswith(">")
        ):
            output.append(part)
            continue

        safe_text = html.escape(
            part,
            quote=False,
        )

        def replace_term(match):
            slug = _rule_slug_from_match(
                match
            )

            if not slug:
                return match.group(0)

            visible_text = match.group(0)

            return (
                f'<a href="rule:{slug}" '
                f'style="color:{link_color}; text-decoration:none;">'
                f"{visible_text}</a>"
            )

        safe_text = _RULE_GLOSSARY_REGEX.sub(
            replace_term,
            safe_text,
        )

        safe_text = safe_text.replace(
            "\n",
            "<br>",
        )

        output.append(
            safe_text
        )

    return "".join(output)


def show_rule_glossary_tooltip(
    anchor,
    source_text="",
):
    anchor = str(
        anchor or ""
    )

    if not anchor.startswith(
        "rule:"
    ):
        QToolTip.hideText()
        return False

    slug = anchor.split(
        ":",
        1,
    )[1]

    definition = rule_glossary_definition(
        slug,
        source_text,
    )

    if not definition:
        QToolTip.hideText()
        return False

    QToolTip.showText(
        QCursor.pos(),
        definition,
    )

    return True


def hide_rule_glossary_tooltip():
    QToolTip.hideText()


class GlossaryTextEdit(QTextEdit):
    """
    Read-only Improvement description box with rule-definition hovers.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._glossary_source_text = ""
        self._glossary_hover_anchor = ""

        self.setMouseTracking(
            True
        )

        self.viewport().setMouseTracking(
            True
        )

    def _set_glossary_text(
        self,
        text,
    ):
        self._glossary_source_text = str(
            text or ""
        )

        self._glossary_hover_anchor = ""

        super().setHtml(
            apply_rule_glossary_html(
                self._glossary_source_text
            )
        )

    def setPlainText(
        self,
        text,
    ):
        self._set_glossary_text(
            text
        )

    def setHtml(
        self,
        text,
    ):
        self._set_glossary_text(
            text
        )

    def clear(self):
        self._glossary_source_text = ""
        self._glossary_hover_anchor = ""

        hide_rule_glossary_tooltip()
        super().clear()

    def mouseMoveEvent(
        self,
        event,
    ):
        anchor = self.anchorAt(
            event.position().toPoint()
        )

        if anchor.startswith(
            "rule:"
        ):
            self.viewport().setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            if anchor != self._glossary_hover_anchor:
                self._glossary_hover_anchor = anchor

                show_rule_glossary_tooltip(
                    anchor,
                    self._glossary_source_text,
                )

        else:
            self.viewport().setCursor(
                Qt.CursorShape.ArrowCursor
            )

            if self._glossary_hover_anchor:
                self._glossary_hover_anchor = ""

                hide_rule_glossary_tooltip()

        super().mouseMoveEvent(
            event
        )

    def mousePressEvent(
        self,
        event,
    ):
        anchor = self.anchorAt(
            event.position().toPoint()
        )

        if anchor.startswith(
            "rule:"
        ):
            event.accept()
            return

        super().mousePressEvent(
            event
        )

    def leaveEvent(
        self,
        event,
    ):
        self._glossary_hover_anchor = ""

        hide_rule_glossary_tooltip()

        super().leaveEvent(
            event
        )


def ask_yes_no(
    parent,
    title,
    text,
    yes_text="Yes",
    no_text="No",
    button_width=None,
    button_height=None,
    dialog_width=None,
):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)

    requested_width = (
        max(220, int(dialog_width))
        if dialog_width is not None
        else 360
    )

    dialog.setFixedWidth(requested_width)
    set_themed_stylesheet(
        dialog,
        FANTASY_DIALOG_QSS,
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(12)

    label = QLabel(text)
    label.setWordWrap(True)
    layout.addWidget(label)

    button_row = QHBoxLayout()

    no_btn = QPushButton(no_text)
    yes_btn = QPushButton(yes_text)

    no_btn.setMinimumSize(50, 34)
    yes_btn.setMinimumSize(50, 34)

    make_negative_button(no_btn)
    make_positive_button(yes_btn)

    yes_btn.setDefault(True)
    yes_btn.setAutoDefault(True)
    no_btn.setAutoDefault(False)

    no_btn.clicked.connect(dialog.reject)
    yes_btn.clicked.connect(dialog.accept)
    
    if button_width is not None:
        no_btn.setMinimumWidth(button_width)
        yes_btn.setMinimumWidth(button_width)

        if dialog_width is None:
            dialog.setFixedWidth(
                max(180, button_width * 2 + 70)
            )

    if button_height is not None:
        no_btn.setMinimumHeight(button_height)
        yes_btn.setMinimumHeight(button_height)
        
    button_row.addWidget(no_btn)
    button_row.addStretch()
    button_row.addWidget(yes_btn)


    layout.addLayout(button_row)

    return dialog.exec() == QDialog.DialogCode.Accepted

# ===================================
# Dialogs
# ===================================

class ImprovementListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.last_search_letter = ""
        self.last_search_row = -1

    def keyPressEvent(self, event):
        key = event.key()

        # Enter adds the currently selected improvement.
        if key in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            dialog = self.window()

            if (
                isinstance(dialog, ImprovementPickerDialog)
                and not dialog.browse_only
            ):
                dialog.accept_selected()

            return

        # Up and Down use the normal QListWidget navigation.
        if key in (
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_PageUp,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        ):
            self.last_search_letter = ""
            self.last_search_row = -1
            super().keyPressEvent(event)
            return

        # Typing a letter jumps to improvements beginning
        # with that letter. Repeating the letter cycles through them.
        text = event.text()

        if text and text.isalpha():
            letter = text.lower()

            if letter == self.last_search_letter:
                start_row = self.currentRow() + 1
            else:
                start_row = 0

            matching_rows = []

            for row in range(self.count()):
                item_text = self.item(row).text().strip()

                # Ignore the empowerment prefix.
                item_text = item_text.removeprefix("↳").strip()

                if item_text.lower().startswith(letter):
                    matching_rows.append(row)

            if matching_rows:
                next_row = None

                for row in matching_rows:
                    if row >= start_row:
                        next_row = row
                        break

                if next_row is None:
                    next_row = matching_rows[0]

                self.setCurrentRow(next_row)
                self.scrollToItem(self.item(next_row))

                self.last_search_letter = letter
                self.last_search_row = next_row
                return

            self.last_search_letter = ""
            self.last_search_row = -1

        # Preserve all other normal QListWidget keyboard behavior.
        super().keyPressEvent(event)
        
class CustomImprovementDialog(QDialog):
    """
    Creates or edits a custom improvement.

    When editing, the IP cost cannot be increased beyond
    the amount that was available when the dialog opened,
    plus the custom improvement's existing cost.
    """

    def __init__(
        self,
        parent=None,
        initial_name="",
        initial_description="",
        initial_cost=1,
        maximum_cost=99,
        edit_mode=False,
        initial_icon="",
        available_icons=None,
    ):
        super().__init__(parent)

        self.improvement = None
        self.edit_mode = edit_mode

        self.setWindowTitle(
            "Edit Custom Improvement"
            if edit_mode
            else "Custom Improvement"
        )

        self.setFixedSize(480, 420)

        set_themed_stylesheet(self, f"""
            QDialog {{
                background-color: #fffdf7;
            }}

            QLabel {{
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 800;
                color: #25190f;
            }}

            QLineEdit, QTextEdit, QSpinBox {{
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 10px;
                padding: 6px;
                font-size: 14px;
                font-weight: 700;
                color: #25190f;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # --------------------------------------------------------
        # Name
        # --------------------------------------------------------

        name_label = QLabel("Name")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "Custom improvement name"
        )
        self.name_input.setFixedHeight(42)
        self.name_input.setText(initial_name)

        # --------------------------------------------------------
        # IP cost
        # --------------------------------------------------------

        cost_label = QLabel("IP Cost")

        self.cost_input = NumericEntry()
        self.cost_input.setMinimum(0)
        self.cost_input.setMaximum(
            min(10, max(0, int(maximum_cost)))
        )
        self.cost_input.lineEdit().setMaxLength(2)
        
        self.cost_input.setValue(
            min(
                max(0, int(initial_cost)),
                self.cost_input.maximum(),
            )
        )
        self.cost_input.setFixedHeight(42)
        self.cost_input.setButtonSymbols(
            QSpinBox.ButtonSymbols.NoButtons
        )

        # Optional explanation while editing.
        if edit_mode:
            cost_label.setToolTip(
                (
                    "The maximum cost includes this improvement's "
                    "current cost plus the IP that was available "
                    "when editing began."
                )
            )

        # --------------------------------------------------------
        # Description
        # --------------------------------------------------------

        description_label = QLabel("Description")

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Describe what this improvement does."
        )
        self.description_input.setPlainText(
            initial_description
        )
        self.description_input.setFixedHeight(95)
        self.description_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        icon_label = QLabel("Icon")
        self.icon_input = QComboBox()
        self.icon_input.addItem("No icon", "")
        for filename in sorted(available_icons or [], key=str.casefold):
            if str(filename).lower().endswith(".svg"):
                self.icon_input.addItem(str(filename)[:-4].replace("_", " "), str(filename))
        selected_icon = self.icon_input.findData(initial_icon)
        self.icon_input.setCurrentIndex(max(0, selected_icon))

        # --------------------------------------------------------
        # Buttons
        # --------------------------------------------------------

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)

        cancel_btn = QPushButton("Cancel")
        make_negative_button(cancel_btn)
        cancel_btn.setFixedSize(90, 38)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton(
            "Save"
            if edit_mode
            else "Add"
        )
        make_positive_button(save_btn)

        save_btn.setDefault(True)
        save_btn.setAutoDefault(True)
        cancel_btn.setAutoDefault(False)

        save_btn.setFixedSize(90, 38)
        save_btn.clicked.connect(
            self.accept_improvement
        )

        button_row.addWidget(cancel_btn)
        button_row.addStretch()
        button_row.addWidget(save_btn)

        # --------------------------------------------------------
        # Layout
        # --------------------------------------------------------

        layout.addWidget(name_label)
        layout.addWidget(self.name_input)

        layout.addSpacing(4)

        layout.addWidget(cost_label)
        layout.addWidget(self.cost_input)

        layout.addSpacing(4)

        layout.addWidget(description_label)
        layout.addWidget(self.description_input)

        layout.addWidget(icon_label)
        layout.addWidget(self.icon_input)

        layout.addStretch()
        layout.addLayout(button_row)

        self.name_input.setFocus()

        if edit_mode:
            self.name_input.selectAll()

        apply_fantasy_dialog_style(self)

    def accept_improvement(self):
        name = self.name_input.text().strip()
        description = (
            self.description_input
            .toPlainText()
            .strip()
        )
        cost = int(self.cost_input.value())

        if not name:
            QMessageBox.warning(
                self,
                "Missing Name",
                "Enter a name for the custom improvement."
            )
            return

        self.improvement = {
            "kind": "custom",
            "catalog_id": "custom",
            "name": name,
            "cost": cost,
            "description": description,
            "icon": self.icon_input.currentData() or "",
            "requires_choices": [],
            "effects": [],
            "tags": ["custom"],
        }

        self.accept()
                
class ImprovementPickerDialog(QDialog):
    """
    Popup dialog for selecting improvements or empowerments to buy.
    Includes filtering, description preview, and cost display.
    """
    def __init__(self, options, parent=None, browse_only=False):
        super().__init__(parent)

        self.all_options = sorted(
            options, key=lambda item: item["name"].lower()
        )
        
        self.options = list(self.all_options)
        self.selected_option = None
        self.browse_only = browse_only

        self.setWindowTitle(
            "Browse Improvements"
            if self.browse_only
            else "Add Improvement"
        )
        self.setFixedSize(560, 460)

        set_themed_stylesheet(self, f"""
            QDialog {{
                background-color: #fffdf7;
            }}

            QLabel {{
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: 800;
                color: #25190f;
            }}

            QComboBox {{
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 8px;
                padding: 2px 28px 2px 8px;
                font-size: 13px;
                font-weight: 700;
                min-height: 24px;
            }}

            QComboBox::drop-down {{
                width: 24px;
                border-left: 1px solid #d9bd82;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: {BLUE};
            }}

            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}

            QComboBox QAbstractItemView {{
                background-color: #fffdf7;
                border: 1px solid #d9bd82;
                selection-background-color: {BLUE};
                selection-color: #25190f;
                font-size: 13px;
                padding: 4px;
                outline: none;
            }}

            QListWidget {{
                background-color: #fffaf0;
                border: 1px solid #c79a3b;
                border-radius: 14px;
                padding: 6px;
                font-size: 15px;
            }}

            QListWidget::item {{
                padding: 7px;
                border: none;
                outline: none;
            }}

            QListWidget::item:selected {{
                background-color: #b9dff2;
                color: #25190f;
                border: none;
            }}
            
            QTextEdit {{
                background-color: #fffaf0;
                border: 1px solid #c79a3b;
                border-radius: 14px;
                padding: 8px;
                font-size: 14px;
            }}

            QPushButton#PositiveButton {{
                background-color: #d8edf7;
                border: 1px solid #c79a3b;
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 14px;
                font-weight: 800;
            }}

            QPushButton#PositiveButton:hover {{
                background-color: #e8f5fb;
            }}

            QPushButton#NegativeButton {{
                background-color: #fffdf7;
                border: 1px solid #c79a3b;
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 14px;
                font-weight: 800;
            }}

            QPushButton#NegativeButton:hover {{
                background-color: #fff4df;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        filter_label = QLabel("Filter")
        filter_label.setFixedWidth(44)

        self.filter_combo = QComboBox()
        self.filter_combo.setFixedWidth(150)
        self.filter_combo.setFixedHeight(30)
        self.filter_combo.addItem("All", None)

        has_empowerments = any(
            option.get("kind") == "empowerment"
            for option in self.all_options
        )

        if has_empowerments:
            self.filter_combo.addItem(
                "Empowerments",
                "__empowerments__",
            )
            
        self.list_widget = ImprovementListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list_widget.setSelectionRectVisible(False)

        self.list_widget.itemDoubleClicked.connect(
            lambda item: self.accept_selected()
        )
        
        for tag in ImprovementCatalogSystem.get_all_tags():
            display_name = tag.replace("_", "-").title()
            self.filter_combo.addItem(display_name, tag)

        self.filter_combo.currentIndexChanged.connect(
            self.refresh_filtered_options
        )

        top_row.addWidget(filter_label)
        top_row.addWidget(self.filter_combo)
        top_row.addStretch()

        layout.addLayout(top_row)

        self.list_widget = ImprovementListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list_widget.setSelectionRectVisible(False)
        
        layout.addWidget(self.list_widget, 1)

        self.description_box = GlossaryTextEdit()
        self.description_box.setReadOnly(True)
        self.description_box.setFixedHeight(105)
        layout.addWidget(self.description_box)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 6, 0, 0)

        self.cancel_btn = QPushButton("Cancel")
        make_negative_button(self.cancel_btn)

        self.add_btn = QPushButton("Add")
        make_positive_button(self.add_btn)

        self.cancel_btn.setFixedSize(88, 30)
        self.add_btn.setFixedSize(88, 30)

        self.add_btn.setDefault(True)
        self.add_btn.setAutoDefault(True)
        self.cancel_btn.setAutoDefault(False)

        self.cancel_btn.clicked.connect(self.reject)
        self.add_btn.clicked.connect(self.accept_selected)

        button_row.addWidget(self.cancel_btn)
        button_row.addStretch()
        button_row.addWidget(self.add_btn)

        if self.browse_only:
            self.cancel_btn.hide()
            self.add_btn.hide()

        layout.addLayout(button_row)

        self.list_widget.currentRowChanged.connect(self.update_description)

        self.refresh_filtered_options()
        self.list_widget.setFocus()

        apply_fantasy_dialog_style(self)

    def refresh_filtered_options(self):
        selected_filter = self.filter_combo.currentData()

        if selected_filter is None:
            self.options = list(self.all_options)

        elif selected_filter == "__empowerments__":
            self.options = [
                option
                for option in self.all_options
                if option.get("kind") == "empowerment"
            ]
            
        else:
            self.options = [
                option
                for option in self.all_options
                if selected_filter in option.get("tags", [])
            ]

        self.list_widget.clear()

        for option in self.options:
            kind = option.get("kind", "base")
            prefix = "↳ " if kind == "empowerment" else ""
            choice_marker = " ✎" if option.get("requires_choices") else ""

            self.list_widget.addItem(
                f"{prefix}{option['name']} ({option['cost']} IP){choice_marker}"
            )

        if self.options:
            self.list_widget.setCurrentRow(0)
            self.update_description(0)
        else:
            self.description_box.setPlainText("No options for this filter.")

    def update_description(self, index):
        if index < 0 or index >= len(self.options):
            self.description_box.clear()
            return

        option = self.options[index]
        description = str(
            option.get("description")
            or ""
        )

        if not description:
            self.description_box.setPlainText(
                "No description."
            )
            return

        # Improvement descriptions intentionally contain small HTML
        # fragments such as <b>...</b>. Force rich-text rendering when
        # those supported tags are present so the player sees emphasis
        # instead of literal angle-bracket markup.
        rich_markers = (
            "<b>", "</b>",
            "<strong>", "</strong>",
            "<i>", "</i>",
            "<em>", "</em>",
            "<u>", "</u>",
            "<br>", "<br/>", "<br />",
        )

        if any(
            marker in description.lower()
            for marker in rich_markers
        ):
            html_text = description.replace(
                "\n",
                "<br>",
            )
            self.description_box.setHtml(
                html_text
            )
        else:
            self.description_box.setPlainText(
                description
            )

    def accept_selected(self):
        index = self.list_widget.currentRow()

        if index < 0 or index >= len(self.options):
            return

        selected = self.options[index]

        if selected.get("catalog_id") == "custom":
            dlg = CustomImprovementDialog(self)

            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            self.selected_option = dlg.improvement
            self.accept()
            return

        self.selected_option = selected
        self.accept()


class BuddyPerkPickerDialog(QDialog):
    """Add-Improvement style picker for Animal Buddy Natural Perks."""

    def __init__(self, parent=None, initial_choices=None, unavailable_perk_ids=None):
        super().__init__(parent)
        self.initial_choices = dict(initial_choices or {})
        self.unavailable_perk_ids = set(unavailable_perk_ids or ())
        self.perk_choices = None
        self.options = list(ANIMAL_BUDDY_PERKS.values())

        self.setWindowTitle("Choose Natural Perk")
        self.setFixedSize(370, 365)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        set_themed_stylesheet(self, FANTASY_DIALOG_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        heading = QLabel("Choose a Natural Perk")
        set_themed_stylesheet(heading, """
            QLabel {
                background: transparent; border: none; font-family: Georgia;
                font-size: 18px; font-weight: 900; color: #25190f;
            }
        """)
        layout.addWidget(heading)

        content = QHBoxLayout()
        content.setSpacing(10)
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(125)
        self.list_widget.setSelectionRectVisible(False)
        set_themed_stylesheet(self.list_widget, """
            QListWidget { background-color:#fffaf0; border:1px solid #c79a3b;
                border-radius:12px; padding:5px; font-family:Georgia;
                font-size:14px; font-weight:800; color:#25190f; }
            QListWidget::item { padding:8px 7px; border-radius:7px; }
            QListWidget::item:selected { background-color:#d8edf7; color:#25190f; }
            QListWidget::item:disabled { color:#9b9388; }
        """)

        right = QVBoxLayout()
        right.setSpacing(7)
        self.description = GlossaryTextEdit()
        self.description.setReadOnly(True)
        self.description.setMinimumHeight(150)
        set_themed_stylesheet(self.description, """
            QTextEdit { background-color:#fffaf0; border:1px solid #c79a3b;
                border-radius:12px; padding:9px; font-family:Georgia;
                font-size:14px; color:#25190f; }
        """)

        self.custom_box = QFrame()
        self.custom_box.setObjectName("BuddyCustomPerkBox")
        set_themed_stylesheet(self.custom_box, """
            QFrame#BuddyCustomPerkBox { background:transparent; border:none; }
            QLineEdit, QTextEdit { background-color:#fffaf0; border:1px solid #d9bd82;
                border-radius:8px; padding:6px; font-family:Georgia;
                font-size:13px; color:#25190f; }
        """)
        custom_layout = QVBoxLayout(self.custom_box)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(5)
        custom_layout.addWidget(QLabel("Custom perk name"))
        self.custom_name = QLineEdit()
        self.custom_name.setPlaceholderText("Name your custom perk")
        custom_layout.addWidget(self.custom_name)
        custom_layout.addWidget(QLabel("Description"))
        self.custom_description = QTextEdit()
        self.custom_description.setPlaceholderText("Describe what the perk does.")
        self.custom_description.setFixedHeight(72)
        custom_layout.addWidget(self.custom_description)

        content.addWidget(self.list_widget)
        right.addWidget(self.description, 1)
        right.addWidget(self.custom_box, 0)
        content.addLayout(right, 1)
        layout.addLayout(content, 1)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        select = QPushButton("Select")
        make_negative_button(cancel)
        make_positive_button(select)
        cancel.setFixedSize(90, 34)
        select.setFixedSize(90, 34)
        cancel.clicked.connect(self.reject)
        select.clicked.connect(self.accept_selected)
        select.setDefault(True)
        buttons.addWidget(cancel)
        buttons.addStretch()
        buttons.addWidget(select)
        layout.addLayout(buttons)

        current_id = animal_buddy_perk_id_from_choices(self.initial_choices) or "mobile"
        raw = str(self.initial_choices.get("buddy_perk") or "").strip()
        custom_name = str(self.initial_choices.get("buddy_perk_custom_name") or "").strip()
        if current_id == "custom" and not custom_name and raw.lower() not in {"", "custom", "missing"}:
            custom_name = raw
        self.custom_name.setText(custom_name)
        self.custom_description.setPlainText(
            str(self.initial_choices.get("buddy_perk_custom_description") or "")
        )

        selected_row = 0
        for row, option in enumerate(self.options):
            perk_id = option["id"]
            label = option["name"]
            disabled = perk_id in self.unavailable_perk_ids and perk_id != current_id
            if disabled:
                label += "  — unavailable"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, perk_id)
            if disabled:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)
            self.list_widget.addItem(item)
            if perk_id == current_id:
                selected_row = row

        self.list_widget.setMouseTracking(True)
        self.list_widget.itemEntered.connect(self.preview_item)
        self.list_widget.currentRowChanged.connect(self.refresh_description)
        self.list_widget.itemClicked.connect(lambda item: self.accept_selected() if item.data(Qt.ItemDataRole.UserRole) == "custom" else None)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept_selected())
        self.list_widget.setCurrentRow(selected_row)
        self.refresh_description(selected_row)
        apply_fantasy_dialog_style(self)

    def preview_item(self, item):
        self.description.setHtml(str(ANIMAL_BUDDY_PERKS.get(item.data(Qt.ItemDataRole.UserRole), {}).get("description") or "").replace("\n", "<br>"))

    def selected_perk_id(self):
        item = self.list_widget.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""

    def refresh_description(self, _row):
        perk_id = self.selected_perk_id()
        option = ANIMAL_BUDDY_PERKS.get(perk_id, {})
        text = str(option.get("description") or "No description.")
        self.description.setHtml(text.replace("\n", "<br>"))
        self.custom_box.hide()

    def accept_selected(self):
        perk_id = self.selected_perk_id()
        option = ANIMAL_BUDDY_PERKS.get(perk_id)
        if option is None or perk_id in self.unavailable_perk_ids:
            return
        result = {"buddy_perk": perk_id}
        if option.get("custom"):
            editor = QDialog(self)
            editor.setWindowTitle("Custom Natural Perk")
            editor.setFixedSize(320, 210)
            fields = QVBoxLayout(editor)
            fields.addWidget(QLabel("Name"))
            name_field = QLineEdit(self.custom_name.text())
            fields.addWidget(name_field)
            fields.addWidget(QLabel("Description"))
            description_field = QTextEdit()
            description_field.setPlainText(self.custom_description.toPlainText())
            fields.addWidget(description_field)
            save = QPushButton("Save")
            save.clicked.connect(editor.accept)
            fields.addWidget(save)
            set_themed_stylesheet(editor, FANTASY_DIALOG_QSS)
            if editor.exec() != QDialog.DialogCode.Accepted:
                return
            name = name_field.text().strip()
            description = description_field.toPlainText().strip()
            if not name:
                QMessageBox.warning(self, "Missing Perk Name", "Enter a name for the custom perk.")
                return
            result["buddy_perk_custom_name"] = name
            result["buddy_perk_custom_description"] = description
        self.perk_choices = result
        self.accept()


def choose_buddy_perk_menu(parent, anchor, initial_choices=None, unavailable_perk_ids=None):
    """Small anchored dropdown; hover previews the API-authored perk text."""
    current = dict(initial_choices or {})
    unavailable = set(unavailable_perk_ids or ())
    current_id = animal_buddy_perk_id_from_choices(current)
    menu = QMenu(parent)
    set_themed_stylesheet(menu, """
        QMenu {background:#fffaf0; border:1px solid #c79a3b; border-radius:8px;
               padding:5px; font:13px Georgia; color:#25190f;}
        QMenu::item {padding:7px 18px; min-width:145px;}
        QMenu::item:selected {background:#d8edf7; color:#25190f;}
        QMenu::item:disabled {color:#9b9388;}
    """)
    for perk in ANIMAL_BUDDY_PERKS.values():
        action = menu.addAction(perk["name"])
        action.setData(perk["id"])
        action.setEnabled(perk["id"] not in unavailable or perk["id"] == current_id)
        action.hovered.connect(
            lambda description=perk.get("description", ""), menu=menu:
                QToolTip.showText(menu.mapToGlobal(QPoint(menu.width() + 5, 0)),
                                  re.sub(r"<[^>]+>", "", str(description)), menu)
        )
    anchor_point = anchor.mapToGlobal(QPoint(0, anchor.height()))
    chosen = menu.exec(anchor_point)
    QToolTip.hideText()
    if chosen is None:
        return None
    perk_id = str(chosen.data() or "")
    result = {"buddy_perk": perk_id}
    if perk_id == "custom":
        editor = QDialog(parent)
        editor.setWindowTitle("Custom Natural Perk")
        editor.setFixedSize(330, 220)
        fields = QVBoxLayout(editor)
        fields.addWidget(QLabel("Name"))
        name_field = QLineEdit(str(current.get("buddy_perk_custom_name") or ""))
        fields.addWidget(name_field)
        fields.addWidget(QLabel("Description"))
        description_field = QTextEdit()
        description_field.setPlainText(str(current.get("buddy_perk_custom_description") or ""))
        fields.addWidget(description_field)
        save = QPushButton("Save")
        make_positive_button(save)
        save.clicked.connect(editor.accept)
        fields.addWidget(save)
        set_themed_stylesheet(editor, FANTASY_DIALOG_QSS)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return None
        name = name_field.text().strip()
        if not name:
            QMessageBox.warning(parent, "Missing Perk Name", "Enter a name for the custom perk.")
            return None
        result.update(buddy_perk_custom_name=name,
                      buddy_perk_custom_description=description_field.toPlainText().strip())
    return result


class BuddyPerkField(QPushButton):
    """Compact field that opens the Natural Perk picker."""
    def __init__(self, parent=None, initial_choices=None, unavailable_perk_ids=None):
        super().__init__(parent)
        self.choice_data = dict(initial_choices or {})
        self.unavailable_perk_ids = set(unavailable_perk_ids or ())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clicked.connect(self.open_picker)
        set_themed_stylesheet(self, """
            QPushButton { text-align:left; background-color:#fffaf0;
                border:1px solid #d9bd82; border-radius:9px; padding:6px 9px;
                font-family:Georgia; font-size:14px; font-weight:800; color:#25190f; }
            QPushButton:hover { background-color:#fff4df; border-color:#a87824; }
        """)
        self.refresh_text()

    def refresh_text(self):
        self.setText(animal_buddy_perk_name(self.choice_data))

    def open_picker(self):
        selected = choose_buddy_perk_menu(self, self, self.choice_data,
                                          self.unavailable_perk_ids)
        if selected is not None:
            self.choice_data = selected
            self.refresh_text()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.drawText(self.rect().adjusted(0, 0, -10, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "▾")

    def choice_values(self):
        return dict(self.choice_data)

class BuddyStatCard(QFrame):
    """
    Clickable card used for choosing Animal Buddy stats.
    Cycles through die sizes when clicked.
    """
    def __init__(self, stat_name, die_size, click_callback):
        super().__init__()
        self.stat_name = stat_name
        self.die_size = die_size
        self.click_callback = click_callback

        self.setFixedSize(90, 90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # These cards use stat-specific surfaces.  The light pastel fills are
        # intentionally not passed through the generic theme translator: in
        # Dark mode that translator changes the text to light ink while leaving
        # these custom pastels bright, producing white-on-pastel cards.
        # Give the six stats explicit dark companions instead.
        light_stat_colors = {
            "agility": "#f5c5a8", "strength": "#efb2b4",
            "finesse": "#f1dda0", "instinct": "#b9dfbf",
            "presence": "#d5c6ea", "knowledge": "#b9d9ee",
        }
        dark_stat_colors = {
            "agility": "#60483b", "strength": "#603d43",
            "finesse": "#5b5132", "instinct": "#385344",
            "presence": "#4a405c", "knowledge": "#355267",
        }
        is_dark = theme_color("page").lower() == "#101820"
        stat_colors = dark_stat_colors if is_dark else light_stat_colors
        card_ink = theme_color("text") if is_dark else "#25190f"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {stat_colors.get(stat_name.lower(), theme_color("blue"))};
                border: 1px solid #c79a3b;
                border-radius: 14px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self.die_label = QLabel()
        self.die_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.die_label.setStyleSheet(f"""
            QLabel {{
                border: none;
                background: transparent;
                font-size: 28px;
                font-weight: 900;
                color: {card_ink};
            }}
        """)

        self.name_label = QLabel(stat_name.title())
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                border: none;
                background: transparent;
                font-size: 13px;
                font-weight: 900;
                color: {card_ink};
            }}
        """)

        layout.addStretch()
        layout.addWidget(self.die_label)
        layout.addStretch()
        layout.addWidget(self.name_label)

        self.refresh()

    def refresh(self):
        self.die_label.setText(f"d{self.die_size}")

    def mousePressEvent(self, event):
        self.click_callback(self.stat_name)

    
class ChoiceInputDialog(QDialog):
    """
    Dialog for entering required choices for improvements or empowerments.
    Supports text fields, combo boxes, long text, and Animal Buddy stat grids.
    """

    PRETTY_LABELS = {
        "attuned_land": "Attuned Land",
        "attuned_land_description": "Land Description",
        "tell": "Tell",
        "buddy_name": "Buddy Name",
        "buddy_stat_d6": "Buddy d6 Stat",
        "buddy_stat_d8_a": "Buddy d8 Stat",
        "buddy_stat_d8_b": "Buddy second d8 Stat",
        "buddy_stat_d10": "Buddy d10 Stat",
        "buddy_perk": "Buddy Perk",
        "buddy_training_stat": "Buddy Ability",
        "magic_school": "Magic School",
        "specific_magic_effect": "Specific Magic Effect",
        "magic_school_description": "School Description",
        "deity_name": "Deity Name",
        "deity_domain": "Deity Domain",
        "skill_name": "Skill Name",
        "skill_description": "Skill Description",
        "stat_name": "Stat Name",
        "original_stat": "Original Stat",
        "replacement_stat": "Replacement Stat",
        "artificer_item_description": "Artificer Item Description",
    }

    STAT_CHOICE_KEYS = {
        "stat_name",
        "original_stat",
        "replacement_stat",
        "buddy_stat_d6",
        "buddy_stat_d8_a",
        "buddy_stat_d8_b",
        "buddy_stat_d10",
        "buddy_training_stat",
    }
    
    LONG_TEXT_KEYS = {
        "skill_description",
        "artificer_item_description",
        "specific_magic_effect",
        "magic_school_description",
    }
    
    def __init__(
        self,
        required_choices,
        title="Choices",
        parent=None,
        initial_choices=None,
        allowed_buddy_training_stats=None,
    ):
        super().__init__(parent)
        
        self.required_choices = required_choices or []
        self.inputs = {}
        self.choices = {}
        self.initial_choices = initial_choices or {}

        self.allowed_buddy_training_stats = (
            allowed_buddy_training_stats
        )
        self.unavailable_buddy_perk_ids = self.find_unavailable_buddy_perks()
        self.buddy_stat_cards = {}
        self.buddy_stat_dice = {}

        self.setWindowTitle(title)

        is_animal_buddy = all(
            key in self.required_choices
            for key in (
                "buddy_name",
                "buddy_stat_d6",
                "buddy_stat_d8_a",
                "buddy_stat_d8_b",
                "buddy_stat_d10",
                "buddy_perk",
            )
        )

        if is_animal_buddy:
            self.setFixedSize(350, 350)
        else:
            self.setFixedSize(
                400,
                60 + 60*max(1, len(self.required_choices)),
            )        

        set_themed_stylesheet(self, f"""
            QDialog {{
                background-color: #fffdf7;
            }}

            QLabel {{
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 800;
                color: #25190f;
            }}

            QLineEdit, QComboBox, QTextEdit {{
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 10px;
                padding: 6px;
                font-size: 14px;
                font-weight: 700;
                color: #25190f;
            }}

            QComboBox::drop-down {{
                width: 24px;
                border-left: 1px solid #d9bd82;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background-color: {BLUE};
            }}

            QComboBox QAbstractItemView {{
                background-color: #fffdf7;
                border: 1px solid #d9bd82;
                selection-background-color: {BLUE};
                selection-color: #25190f;
                font-size: 13px;
                padding: 4px;
                outline: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)


        if is_animal_buddy:
            self.build_animal_buddy_choices(layout)
        else:
            self.build_generic_choices(layout)

        layout.addSpacing(4)
        layout.addLayout(self.build_buttons_row())

        apply_fantasy_dialog_style(self)

    def find_unavailable_buddy_perks(self):
        """Disable already-owned official perks and Large/Small conflicts."""
        parent = self.parent()
        character = getattr(parent, "character", None)
        if character is None:
            return set()
        buddy = next((imp for imp in character.improvements.list_of_taken_improvements
                      if imp.catalog_id == "animal_buddy"), None)
        if buddy is None:
            return set()
        current_id = animal_buddy_perk_id_from_choices(self.initial_choices)
        owned = []
        for choices in [buddy.choices] + [e.choices for e in buddy.empowerments
                                          if e.catalog_id == "gifted"]:
            perk_id = animal_buddy_perk_id_from_choices(choices)
            if perk_id and perk_id != "custom":
                owned.append(perk_id)
        if current_id in owned:
            owned.remove(current_id)
        unavailable = set(owned)
        for perk_id in owned:
            unavailable.update(ANIMAL_BUDDY_PERKS.get(perk_id, {}).get("incompatible_with", []))
        unavailable.discard("custom")
        return unavailable

    def build_generic_choices(self, layout):
        for choice_key in self.required_choices:
            row = QHBoxLayout()
            row.setSpacing(8)

            label = QLabel(
                self.PRETTY_LABELS.get(
                    choice_key,
                    choice_key.replace("_", " ").title(),
                )
            )
            label.setFixedWidth(120)
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Preferred,
            )

            field = self.create_field_for_choice(choice_key)

            row.addWidget(label)
            row.addWidget(field, 1)
            layout.addLayout(row)

            self.inputs[choice_key] = field

    def build_animal_buddy_choices(self, layout):
        name_row = QHBoxLayout()
        name_label = QLabel("Buddy Name")
        name_label.setFixedWidth(120)

        name_field = QLineEdit()
        self.apply_initial_value("buddy_name", name_field)

        name_row.addWidget(name_label)
        name_row.addWidget(name_field, 1)
        layout.addLayout(name_row)

        self.inputs["buddy_name"] = name_field

        perk_row = QHBoxLayout()
        perk_label = QLabel("Buddy Perk")
        perk_label.setFixedWidth(120)
        perk_field = BuddyPerkField(
            self, initial_choices=self.initial_choices,
            unavailable_perk_ids=self.unavailable_buddy_perk_ids,
        )
        perk_row.addWidget(perk_label)
        perk_row.addWidget(perk_field, 1)
        layout.addLayout(perk_row)
        self.inputs["buddy_perk"] = perk_field



        self.initialize_buddy_stat_dice()

        cards_grid = QGridLayout()
        cards_grid.setHorizontalSpacing(8)
        cards_grid.setVerticalSpacing(8)

        for index, stat_name in enumerate(STAT_NAMES):
            card = BuddyStatCard(
                stat_name,
                self.buddy_stat_dice[stat_name],
                self.cycle_buddy_stat_die,
            )

            self.buddy_stat_cards[stat_name] = card

            row = index // 3
            col = index % 3

            cards_grid.addWidget(card, row, col)

        layout.addLayout(cards_grid)

    def build_buttons_row(self):
        button_row = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        make_negative_button(cancel_btn)

        save_btn = QPushButton("Save")
        make_positive_button(save_btn)

        save_btn.setDefault(True)
        save_btn.setAutoDefault(True)
        cancel_btn.setAutoDefault(False)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept_choices)

        button_row.addWidget(cancel_btn)
        button_row.addStretch()
        button_row.addWidget(save_btn)

        return button_row

    def create_field_for_choice(self, choice_key):
        if choice_key == "buddy_perk":
            return BuddyPerkField(
                self, initial_choices=self.initial_choices,
                unavailable_perk_ids=self.unavailable_buddy_perk_ids,
            )
        if choice_key in self.STAT_CHOICE_KEYS:
            return self.create_stat_combo(choice_key)

        if choice_key in self.LONG_TEXT_KEYS:
            field = QTextEdit()
            field.setFixedHeight(70)
            self.apply_initial_value(choice_key, field)
            return field

        field = QLineEdit()
        if choice_key == "attuned_land_description":
            field.setMaxLength(140)
            field.setPlaceholderText("Briefly describe this land")
        self.apply_initial_value(choice_key, field)
        return field

    def create_stat_combo(self, choice_key):
        field = QComboBox()

        if (
            choice_key == "buddy_training_stat"
            and self.allowed_buddy_training_stats is not None
        ):
            stat_names = self.allowed_buddy_training_stats

        else:
            stat_names = STAT_NAMES

        for stat_name in stat_names:
            field.addItem(stat_name.title(), stat_name)

        self.apply_initial_value(choice_key, field)

        return field

    def apply_initial_value(self, choice_key, field):
        initial_value = self.initial_choices.get(choice_key)

        if initial_value in (None, "", "Missing"):
            return

        if isinstance(field, QComboBox):
            index = field.findData(initial_value)
            if index >= 0:
                field.setCurrentIndex(index)
            return

        if isinstance(field, QTextEdit):
            field.setPlainText(str(initial_value))
            return

        field.setText(str(initial_value))

    def accept_choices(self):
        choices = {}

        for choice_key, field in self.inputs.items():
            if isinstance(field, BuddyPerkField):
                perk_values = field.choice_values()
                if not perk_values.get("buddy_perk"):
                    QMessageBox.warning(self, "Missing Buddy Perk",
                                        "Choose a Natural Perk for your Animal Buddy.")
                    return
                choices.update(perk_values)
                continue
            if isinstance(field, QComboBox):
                value = field.currentData()
            elif isinstance(field, QTextEdit):
                value = field.toPlainText().strip()
                if value:
                    value = self.parent().capitalize_sentences(value)
            else:
                value = field.text().strip()

                if value:
                    value = self.parent().capitalize_sentences(value)

            if value is None or value == "":
                value = "Missing"

            choices[choice_key] = value

        if self.buddy_stat_dice:
            buddy_choices = self.buddy_card_choices()

            if buddy_choices is None:
                return

            choices.update(buddy_choices)
    
        buddy_stat_keys = [
            "buddy_stat_d6",
            "buddy_stat_d8_a",
            "buddy_stat_d8_b",
            "buddy_stat_d10",
        ]

        if all(key in choices for key in buddy_stat_keys):
            selected_buddy_stats = [
                choices[key]
                for key in buddy_stat_keys
                if choices[key] != "Missing"
            ]

            if len(selected_buddy_stats) != len(set(selected_buddy_stats)):
                QMessageBox.warning(
                    self,
                    "Duplicate Buddy Stats",
                    "Choose a different stat for each Animal Buddy die.",
                )
                return

        self.choices = choices
        self.accept()

    def initialize_buddy_stat_dice(self):
        self.buddy_stat_dice = {
            stat_name: 4
            for stat_name in STAT_NAMES
        }

        initial_map = {
            "buddy_stat_d10": 10,
            "buddy_stat_d8_a": 8,
            "buddy_stat_d8_b": 8,
            "buddy_stat_d6": 6,
        }

        for choice_key, die_size in initial_map.items():
            stat_name = self.initial_choices.get(choice_key)

            if stat_name in self.buddy_stat_dice:
                self.buddy_stat_dice[stat_name] = die_size

    def cycle_buddy_stat_die(self, stat_name):
        current = self.buddy_stat_dice.get(stat_name, 4)

        order = [4, 6, 8, 10]
        current_index = order.index(current)

        for step in range(1, len(order) + 1):
            candidate = order[(current_index + step) % len(order)]

            old_value = self.buddy_stat_dice[stat_name]
            self.buddy_stat_dice[stat_name] = candidate

            if self.buddy_dice_are_legal():
                self.refresh_buddy_stat_cards()
                return

            self.buddy_stat_dice[stat_name] = old_value

    def buddy_dice_are_legal(self):
        counts = {
            4: 0,
            6: 0,
            8: 0,
            10: 0,
        }

        for die_size in self.buddy_stat_dice.values():
            counts[die_size] += 1

        return (
            counts[10] <= 1
            and counts[8] <= 2
            and counts[6] <= 1
            and counts[4] <= 6
        )

    def refresh_buddy_stat_cards(self):
        for stat_name, card in self.buddy_stat_cards.items():
            card.die_size = self.buddy_stat_dice[stat_name]
            card.refresh()

    def buddy_card_choices(self):
        d10_stats = [
            stat_name
            for stat_name, die_size in self.buddy_stat_dice.items()
            if die_size == 10
        ]

        d8_stats = [
            stat_name
            for stat_name, die_size in self.buddy_stat_dice.items()
            if die_size == 8
        ]

        d6_stats = [
            stat_name
            for stat_name, die_size in self.buddy_stat_dice.items()
            if die_size == 6
        ]

        if len(d10_stats) != 1 or len(d8_stats) != 2 or len(d6_stats) != 1:
            QMessageBox.warning(
                self,
                "Invalid Buddy Stats",
                "Choose exactly one d10, two d8 stats, and one d6 stat."
            )
            return None

        return {
            "buddy_stat_d10": d10_stats[0],
            "buddy_stat_d8_a": d8_stats[0],
            "buddy_stat_d8_b": d8_stats[1],
            "buddy_stat_d6": d6_stats[0],
        }

        
class AbilityEditorDialog(QDialog):
    """
    Full editor for adjusting ability dice and bonuses.
    Enforces legal arrays, shows point costs, and updates the character’s stats.
    """
    CELL_SIZE = 86

    def __init__(self, character, parent=None, allowed_array_ids=None):
        super().__init__(parent)
        self.character = character
        self.allowed_array_ids = (
            set(allowed_array_ids)
            if allowed_array_ids
            else None
        )
        self.stat_inputs = {}
        self.selected_stat_name = None

        self.pretty_names = {
            "agility": "Agility",
            "strength": "Strength",
            "finesse": "Finesse",
            "instinct": "Instinct",
            "presence": "Presence",
            "knowledge": "Knowledge",
        }

        self.setWindowTitle("Edit Abilities")
        self.setFixedSize(720, 350)

        set_themed_stylesheet(self, f"""
            QDialog {{
                background-color: #fffdf7;
            }}

            QLabel {{
                color: #25190f;
                background: transparent;
                border: none;
            }}

            QFrame#StatCell {{
                background-color: {BLUE};
                border: 1px solid #c79a3b;
                border-radius: 14px;
            }}

            QFrame#StatCellSelected {{
                background-color: {BLUE};
                border: 2px solid #a87824;
                border-radius: 14px;
            }}

            QPushButton#DieButton {{
                background-color: transparent;
                border: none;
                font-size: 24px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
            }}

            QPushButton#OptionButton {{
                background-color: {BLUE};
                border: 1px solid #d9bd82;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 900;
                color: #25190f;
                padding: 4px 8px;
            }}

            QPushButton#OptionButton:hover {{
                background-color: #d8eef8;
            }}

            QPushButton#InfoButton {{
                background-color: transparent;
                border: 1px solid #c79a3b;
                border-radius: 14px;
                font-size: 20px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
            }}

            QPushButton {{
                background-color: {BLUE};
                border: 1px solid #c79a3b;
                border-radius: 14px;
                padding: 8px 18px;
                font-size: 16px;
                font-weight: 800;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self.info_btn = QPushButton("i")
        self.info_btn.setObjectName("InfoButton")
        self.info_btn.setFixedSize(32, 32)
        self.info_btn.clicked.connect(self.open_arrays_info)

        self.reset_btn = QPushButton("↻")
        self.reset_btn.setToolTip("Reset all abilities to d4")
        self.reset_btn.setFixedSize(32, 32)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_themed_stylesheet(self.reset_btn, f"""
            QPushButton {{
                background-color: {BLUE};
                border: 1px solid #d9bd82;
                border-radius: 16px;
                font-size: 21px;
                font-weight: 900;
                padding: 0px;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}
        """)

        self.reset_btn.clicked.connect(self.reset_all_abilities)

        self.points_label = QLabel()

        self.points_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        set_themed_stylesheet(self.points_label, """
            font-size: 24px;
            font-weight: 900;
            color: #25190f;
        """)
        
        top_row.addWidget(self.info_btn)
        top_row.addStretch()
        top_row.addWidget(self.points_label)
        top_row.addStretch()
        top_row.addWidget(self.reset_btn)

        layout.addLayout(top_row)

        self.stats_row = QHBoxLayout()
        self.stats_row.setContentsMargins(0, 0, 0, 0)
        self.stats_row.setSpacing(4)
        layout.addLayout(self.stats_row)

        for stat_name in STAT_NAMES:
            self.create_stat_cell(stat_name)

        self.options_bar = QFrame()
        self.options_bar.setVisible(False)
        set_themed_stylesheet(self.options_bar, f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
        """)

        self.options_layout = QVBoxLayout(self.options_bar)
        self.options_layout.setContentsMargins(0, 2, 0, 2)
        self.options_layout.setSpacing(6)

        layout.addWidget(self.options_bar)

        layout.addStretch()

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)

        self.cancel_btn = QPushButton("Cancel")
        make_negative_button(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        make_positive_button(self.save_btn)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.save)

        button_row.addWidget(self.cancel_btn)
        button_row.addStretch()
        button_row.addWidget(self.save_btn)

        layout.addLayout(button_row)

        self.refresh_all()

    def create_stat_cell(self, stat_name):
        stat = self.character.stats.get_stat(stat_name)

        cell = QFrame()
        cell.setObjectName("StatCell")
        cell.setFixedSize(self.CELL_SIZE, self.CELL_SIZE)
        cell.setCursor(Qt.CursorShape.PointingHandCursor)
        cell.mousePressEvent = (
            lambda event, s=stat_name: self.select_stat(s)
        )

        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(4, 5, 4, 5)
        cell_layout.setSpacing(2)

        die_button = QPushButton()
        die_button.setObjectName("DieButton")
        die_button.clicked.connect(
            lambda checked=False, s=stat_name: self.select_stat(s)
        )

        name_label = QLabel(self.pretty_names.get(stat_name, stat_name.title()))
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        set_themed_stylesheet(name_label, """
            font-size: 13px;
            font-weight: 900;
            color: #25190f;
        """)


        cell_layout.addStretch()
        cell_layout.addWidget(die_button, 0, Qt.AlignmentFlag.AlignHCenter)
        cell_layout.addStretch()
        cell_layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignHCenter)


        self.stats_row.addWidget(cell)

        self.stat_inputs[stat_name] = {
            "die": stat.die_size if stat else 4,
            "locked": True,
            "cell": cell,
            "button": die_button,
        }

    def used_points(self):
        total = 0

        for inputs in self.stat_inputs.values():
            if inputs["locked"]:
                total += STAT_POINT_COSTS.get(inputs["die"], 0)

        return total

    def remaining_points(self):
        return self.character.stat_point_budget - self.used_points()

    def refresh_all(self):
        self.reorder_stat_cells()
        self.refresh_points()
        self.refresh_stat_cells()


    def refresh_points(self):
        remaining = self.remaining_points()
        total = self.character.stat_point_budget

        self.points_label.setText(f"{remaining}/{total}")

        if remaining < 0:
            color = "red"
        elif remaining == 0 and self.all_stats_locked():
            color = "black"
        else:
            color = "black"

        set_themed_stylesheet(self.points_label, f"""
            font-size: 24px;
            font-weight: 900;
            color: {color};
        """)

    def refresh_stat_cells(self):
        for stat_name, inputs in self.stat_inputs.items():
            die_size = inputs["die"]
            button = inputs["button"]
            cell = inputs["cell"]

            button.setText(f"d{die_size}")

            if stat_name == self.selected_stat_name:
                cell.setObjectName("StatCellSelected")
            else:
                cell.setObjectName("StatCell")

            cell.style().unpolish(cell)
            cell.style().polish(cell)

    def select_stat(self, stat_name):
        self.selected_stat_name = stat_name
        self.refresh_stat_cells()
        self.open_dice_menu(stat_name)
        
    def clear_options_layout(self):
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh_options_bar(self):
        self.clear_options_layout()
        self.options_bar.setVisible(False)


    def open_dice_menu(self, stat_name):
        menu = QMenu(self)

        set_themed_stylesheet(menu, f"""
            QMenu {{
                background-color: #fffdf7;
                border: 1px solid #d9bd82;
                padding: 4px;
            }}

            QMenu::item {{
                background-color: {BLUE};
                color: #25190f;
                padding: 4px 14px;
                margin: 2px;
                font-size: 12px;
                font-weight: 900;
                border-radius: 8px;
            }}

            QMenu::item:selected {{
                background-color: #d8eef8;
            }}
        """)

        possible_dice = self.get_possible_dice_for_stat(stat_name)
        current_die = self.stat_inputs[stat_name]["die"]
    
        for die_size in possible_dice:
            if die_size == current_die:
                continue
            
            cost = STAT_POINT_COSTS.get(die_size, 0)
            text = f"d{die_size} ({cost})"

            action = menu.addAction(text)
            action.triggered.connect(
                lambda checked=False, s=stat_name, d=die_size: self.choose_die(s, d)
            )

        cell = self.stat_inputs[stat_name]["cell"]

        menu.exec(
            cell.mapToGlobal(QPoint(0, 78))
        )


    def get_possible_dice_for_stat(self, stat_name):
        possible = []

        for candidate_die in sorted(STAT_POINT_COSTS):
            if self.can_choose_die(stat_name, candidate_die):
                possible.append(candidate_die)

        return possible

    def can_choose_die(self, stat_name, candidate_die):
        # While editing abilities, allow temporary arrangements.
        # The final legal-array check still happens when Save is pressed.

        candidate_cost = STAT_POINT_COSTS.get(candidate_die, 0)

        used_by_other_stats = 0

        for name, inputs in self.stat_inputs.items():
            if name == stat_name:
                continue

            if inputs["locked"]:
                used_by_other_stats += STAT_POINT_COSTS.get(
                    inputs["die"],
                    0,
                )

        return (
            used_by_other_stats + candidate_cost
            <= self.character.stat_point_budget
        )

    def locked_choices_fit_array(self, locked_choices, legal_dice):
        remaining_legal = list(legal_dice)

        for die in locked_choices:
            if die not in remaining_legal:
                return False
            remaining_legal.remove(die)

        return True

    def choose_die(self, stat_name, die_size):
        self.stat_inputs[stat_name]["die"] = die_size
        self.stat_inputs[stat_name]["locked"] = True

        self.auto_fill_forced_d4s()
        
        self.selected_stat_name = None
        self.refresh_all()

    def all_stats_locked(self):
        return all(inputs["locked"] for inputs in self.stat_inputs.values())

    def final_dice_are_legal(self):
        current_dice = sorted(
            [inputs["die"] for inputs in self.stat_inputs.values()],
            reverse=True
        )

        legal_arrays = [
            sorted(
                ability_array["dice"],
                reverse=True
            )
            for ability_array
            in self.available_ability_arrays()
        ]

        return current_dice in legal_arrays

    def open_arrays_info(self):
        menu = QMenu(self)

        set_themed_stylesheet(menu, f"""
            QMenu {{
                background-color: #fffdf7;
                border: 1px solid #d9bd82;
                padding: 4px;
            }}

            QMenu::item {{
                background-color: {BLUE};
                color: #25190f;
                padding: 5px 14px;
                margin: 2px;
                font-size: 12px;
                font-weight: 900;
                border-radius: 8px;
            }}

            QMenu::item:disabled {{
                color: #25190f;
            }}
        """)

        for ability_array in self.available_ability_arrays():
            dice_text = ", ".join(f"d{die}" for die in ability_array["dice"])
            action = menu.addAction(
                f"{ability_array['name']}:\n{dice_text}"
            )
            action.setEnabled(False)

        menu.exec(
            self.mapToGlobal(
                QPoint(220, self.info_btn.height() + 110)
            )
        )

    def save(self):
        if not self.all_stats_locked():
            QMessageBox.warning(
                self,
                "Incomplete Abilities",
                "Choose a die for every ability before saving."
            )
            return

        if self.remaining_points() != 0:
            QMessageBox.warning(
                self,
                "Invalid Ability Points",
                "You must use exactly all 23 ability points."
            )
            return

        if not self.final_dice_are_legal():
            QMessageBox.warning(
                self,
                "Invalid Ability Array",
                "Your dice must match one of the legal ability arrays."
            )
            return

        for stat_name, inputs in self.stat_inputs.items():
            StatSystem.set_die_size(
                self.character,
                stat_name,
                inputs["die"]
            )

        self.character.validate()
        self.accept()

    def auto_fill_forced_d4s(self):
        if self.remaining_points() != 0:
            return

        for stat_name, inputs in self.stat_inputs.items():
            if inputs["locked"]:
                continue

            if self.can_choose_die(stat_name, 4):
                inputs["die"] = 4
                inputs["locked"] = True

    def get_sorted_stat_names(self):
        return sorted(
            STAT_NAMES,
            key=lambda stat_name: (
                -self.stat_inputs[stat_name]["die"],
                -self.character.stats.get_stat(stat_name).bonus,
                self.pretty_names.get(stat_name, stat_name).lower(),
            )
        )
    
    def reorder_stat_cells(self):
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            widget = item.widget()

            if widget is not None:
                self.stats_row.removeWidget(widget)

        for stat_name in self.get_sorted_stat_names():
            self.stats_row.addWidget(
                self.stat_inputs[stat_name]["cell"]
            )

    def reset_all_abilities(self):
        for inputs in self.stat_inputs.values():
            inputs["die"] = 4
            inputs["locked"] = False

        self.selected_stat_name = None
        self.refresh_all()

    def available_ability_arrays(self):
        if not self.allowed_array_ids:
            return list(ABILITY_ARRAYS)

        return [
            ability_array
            for ability_array in ABILITY_ARRAYS
            if ability_array.get("id")
            in self.allowed_array_ids
        ]
