import re

from PySide6.QtGui import (
    QColor,
    QPalette,
)

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QComboBox,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

from PySide6.QtCore import (
    Qt,
    QSettings,
)

BLUE = "#c7e6f7"

# ==============================================================
# Theme palette
# ==============================================================

# Dark mode is intentionally COLOR-ONLY.  The existing Light UI remains
# the source of truth for layout, sizes, spacing, typography and behavior.
CURRENT_THEME = "light"

THEME = {
    "light": {
        "page": "#F0FFFF",
        "surface": "#ffffff",
        "input": "#f4fbff",
        "input_alt": "#eef8fc",
        "text": "#000000",
        "text_2": "#222222",
        "text_3": "#333333",
        "text_muted": "#555555",
        "important": "#000000",
        "border": "#000000",
        "blue": "#c7e6f7",
        "blue_hover": "#d8eef8",
        "blue_mid": "#9fcfe3",
        "blue_mid_hover": "#79b8d4",
        "blue_empower": "#a9d5ea",
        "blue_empower_2": "#b9dff2",
        "blue_top": "#b8d8ea",
        "blue_action": "#2f5f91",
        "positive": "#8fd694",
        "positive_hover": "#a7e7ab",
        "negative": "#f3a6a6",
        "negative_hover": "#f7bdbd",
        "warning": "#aa0000",
        "danger_pressed": "#b71c1c",
        "image_frame": "#eeeeee",
        "soft_neutral": "#f5f5f5",
        "locked": "#dddddd",
        "heart_empty": "#ffffff",
        "heart_locked": "#dddddd",
        "heart_fill": "#ff0000",
        "heart_outline": "#ff0000",
        "at_fill": "#d4af37",
        "at_fill_border": "#b8962e",
        "at_empty": "#f7efd0",
        "at_empty_border": "#d4af37",
    },
    "dark": {
        "page": "#101820",
        "surface": "#18232e",
        "input": "#1b2a37",
        "input_alt": "#182936",
        "text": "#eef3f7",
        "text_2": "#e2eaf0",
        "text_3": "#d4dee6",
        "text_muted": "#aab8c4",
        # Important neutral black becomes blue instead of generic white.
        "important": "#5f8fb8",
        "border": "#3f5f78",
        # Same DID blue family, simply darker.
        "blue": "#294e68",
        "blue_hover": "#355f7a",
        "blue_mid": "#376979",
        "blue_mid_hover": "#3f7188",
        "blue_empower": "#315b70",
        "blue_empower_2": "#335f78",
        "blue_top": "#2d5369",
        "blue_action": "#6f9fc8",
        # Same semantic colors, darker versions.
        "positive": "#3f704b",
        "positive_hover": "#4e8659",
        "negative": "#7f4147",
        "negative_hover": "#985058",
        "warning": "#c05b63",
        "danger_pressed": "#7f2429",
        "image_frame": "#17232f",
        "soft_neutral": "#1a2631",
        "locked": "#33414c",
        "heart_empty": "#18232e",
        "heart_locked": "#33414c",
        "heart_fill": "#b33a42",
        "heart_outline": "#b33a42",
        "at_fill": "#9d7d2b",
        "at_fill_border": "#80651f",
        "at_empty": "#37311f",
        "at_empty_border": "#9d7d2b",
    },
}

# The source QSS remains written in the original Light colors.  These
# exact source colors are translated to the Dark palette when applied.
LIGHT_HEX_TO_THEME_KEY = {
    "#F0FFFF": "page",
    "#f0ffff": "page",
    "#f4fbff": "input",
    "#eef8fc": "input_alt",
    "#eeeeee": "image_frame",
    "#f5f5f5": "soft_neutral",
    "#dddddd": "locked",
    "#c7e6f7": "blue",
    "#d8eef8": "blue_hover",
    "#9fcfe3": "blue_mid",
    "#79b8d4": "blue_mid_hover",
    "#a9d5ea": "blue_empower",
    "#b9dff2": "blue_empower_2",
    "#b8d8ea": "blue_top",
    "#2f5f91": "blue_action",
    "#a9d8ed": "blue_hover",
    "#8fc5df": "blue_mid",
    "#8fd694": "positive",
    "#a7e7ab": "positive_hover",
    "#f3a6a6": "negative",
    "#f7bdbd": "negative_hover",
    "#aa0000": "warning",
    "#b71c1c": "danger_pressed",
    "#222222": "text_2",
    "#333333": "text_3",
    "#555555": "text_muted",
    # Note-paper colors. They stay the same hue family.
    "#ffc078": "note_orange",
    "#ffe98a": "note_yellow",
    "#a8e6b0": "note_green",
    "#c8b6ff": "note_purple",
    "#f4b6cf": "note_pink",
}

# Extend the palette with note-paper colors after the main dictionaries so
# the color intent stays obvious above.
THEME["light"].update({
    "note_orange": "#ffc078",
    "note_yellow": "#ffe98a",
    "note_green": "#a8e6b0",
    "note_purple": "#c8b6ff",
    "note_pink": "#f4b6cf",
})
THEME["dark"].update({
    "note_orange": "#76502f",
    "note_yellow": "#686033",
    "note_green": "#3d6547",
    "note_purple": "#4e466d",
    "note_pink": "#704258",
})

# ==============================================================
# Shared light-fantasy dialog palette
# ==============================================================

THEME["light"].update({
    "fantasy_page": "#f7f1e5",
    "fantasy_surface": "#fffdf7",
    "fantasy_surface_alt": "#fffaf0",
    "fantasy_text": "#25190f",
    "fantasy_text_2": "#3b332a",
    "fantasy_text_gold": "#6c5428",
    "fantasy_text_muted": "#765d34",
    "fantasy_gold": "#a87824",
    "fantasy_gold_mid": "#c79a3b",
    "fantasy_border": "#cdaa63",
    "fantasy_border_soft": "#d9bd82",
    "fantasy_hover": "#fff4df",
    "fantasy_pressed": "#f5ead2",
    "fantasy_selected_2": "#fff1d6",
    "fantasy_disabled": "#eee9df",
    "fantasy_disabled_border": "#d8ccb5",
    "fantasy_disabled_text": "#9b9388",
})

THEME["dark"].update({
    "fantasy_page": "#111922",
    "fantasy_surface": "#18232e",
    "fantasy_surface_alt": "#1d2a35",
    "fantasy_text": "#f2eee7",
    "fantasy_text_2": "#d8d1c5",
    "fantasy_text_gold": "#d6b66f",
    "fantasy_text_muted": "#b7a98c",
    "fantasy_gold": "#d0aa54",
    "fantasy_gold_mid": "#b58d43",
    "fantasy_border": "#8e7446",
    "fantasy_border_soft": "#68583b",
    "fantasy_hover": "#243440",
    "fantasy_pressed": "#1e2c36",
    "fantasy_selected_2": "#2a3137",
    "fantasy_disabled": "#25313a",
    "fantasy_disabled_border": "#49483f",
    "fantasy_disabled_text": "#7e8b96",
})

LIGHT_HEX_TO_THEME_KEY.update({
    "#f7f1e5": "fantasy_page",
    "#fffdf7": "fantasy_surface",
    "#fffaf0": "fantasy_surface_alt",
    "#25190f": "fantasy_text",
    "#3b332a": "fantasy_text_2",
    "#4f3b18": "fantasy_text_gold",
    "#6c5428": "fantasy_text_gold",
    "#765d34": "fantasy_text_muted",
    "#a87824": "fantasy_gold",
    "#c79a3b": "fantasy_gold_mid",
    "#cdaa63": "fantasy_border",
    "#d9bd82": "fantasy_border_soft",
    "#fff4df": "fantasy_hover",
    "#f5ead2": "fantasy_pressed",
    "#fff1d6": "fantasy_selected_2",
    "#eee9df": "fantasy_disabled",
    "#d8ccb5": "fantasy_disabled_border",
    "#9b9388": "fantasy_disabled_text",
    "#d8edf7": "blue",
    "#e8f5fb": "blue_hover",
    "#c9e3ef": "blue_mid",
})

def theme_color(key):
    return THEME[CURRENT_THEME][key]

def set_runtime_theme(theme_name):
    global CURRENT_THEME

    if theme_name not in THEME:
        theme_name = "light"

    CURRENT_THEME = theme_name

def translate_qss_for_theme(stylesheet):
    """Return the source stylesheet unchanged in Light mode, and with
    color values translated in Dark mode. No geometry/style structure is
    changed here.
    """
    if not stylesheet or CURRENT_THEME == "light":
        return str(stylesheet)

    result = str(stylesheet)

    for light_hex, palette_key in LIGHT_HEX_TO_THEME_KEY.items():
        result = result.replace(
            light_hex,
            theme_color(palette_key),
        )

    # White neutral surfaces -> dark neutral surface.
    result = re.sub(
        r"(?i)(background(?:-color)?\s*:\s*)white\b",
        lambda match: match.group(1) + theme_color("surface"),
        result,
    )

    # Normal black text -> off-white.
    result = re.sub(
        r"(?i)((?:selection-)?color\s*:\s*)black\b",
        lambda match: match.group(1) + theme_color("text"),
        result,
    )

    # Important black borders -> muted DID blue, not white.
    result = re.sub(
        r"(?i)(border(?:-(?:left|right|top|bottom))?\s*:[^;]*?)black\b",
        lambda match: match.group(1) + theme_color("border"),
        result,
    )

    # One named red is used for invalid ability points.
    result = re.sub(
        r"(?i)(color\s*:\s*)red\b",
        lambda match: match.group(1) + theme_color("warning"),
        result,
    )

    # Translucent white/black note-editor overlays become translucent blue-gray.
    overlay_map = {
        "rgba(255, 255, 255, 60)": "rgba(69, 93, 112, 55)",
        "rgba(255, 255, 255, 80)": "rgba(69, 93, 112, 70)",
        "rgba(255, 255, 255, 90)": "rgba(69, 93, 112, 75)",
        "rgba(255, 255, 255, 110)": "rgba(69, 93, 112, 90)",
        "rgba(255, 255, 255, 125)": "rgba(69, 93, 112, 100)",
        "rgba(255, 255, 255, 150)": "rgba(69, 93, 112, 115)",
        "rgba(0, 0, 0, 45)": "rgba(76, 107, 132, 70)",
        "rgba(0, 0, 0, 100)": "rgba(76, 107, 132, 120)",
    }

    for light_value, dark_value in overlay_map.items():
        result = result.replace(light_value, dark_value)

    return result

def set_themed_stylesheet(widget, stylesheet):
    """Apply a source Light stylesheet through the active palette.

    The raw Light QSS is cached on the widget. This is what makes
    Light -> Dark -> Light lossless and also means refresh methods can keep
    using their existing styles normally.
    """
    raw_qss = str(stylesheet)

    widget.setProperty(
        "_did_light_qss",
        raw_qss,
    )

    widget.setStyleSheet(
        translate_qss_for_theme(raw_qss)
    )

def apply_theme_to_existing_widgets(root):
    widgets = [root]

    if isinstance(root, QWidget):
        widgets.extend(
            root.findChildren(QWidget)
        )

    for widget in widgets:
        raw_qss = widget.property(
            "_did_light_qss"
        )

        if raw_qss is not None:
            widget.setStyleSheet(
                translate_qss_for_theme(
                    str(raw_qss)
                )
            )

        widget.update()

def build_application_palette(theme_name):
    palette = QPalette()

    if theme_name == "light":
        # Exact clean-file palette.
        palette.setColor(QPalette.ColorRole.Window, QColor("white"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("black"))
        palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f4fbff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("black"))
        palette.setColor(QPalette.ColorRole.Button, QColor("white"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("black"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(BLUE))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("black"))
        return palette

    colors = THEME["dark"]
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["page"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["input"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["blue"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    return palette

FANTASY_BUTTON_PRIMARY_STYLE = """
QPushButton {
    background-color: #d8edf7;
    border: 1px solid #c79a3b;
    border-radius: 9px;
    padding: 5px 12px;
    font-family: Georgia;
    font-size: 12px;
    font-weight: 800;
    color: #25190f;
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

FANTASY_BUTTON_SECONDARY_STYLE = """
QPushButton {
    background-color: #fffdf7;
    border: 1px solid #c79a3b;
    border-radius: 9px;
    padding: 5px 12px;
    font-family: Georgia;
    font-size: 12px;
    font-weight: 800;
    color: #4f3b18;
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

FANTASY_BUTTON_DANGER_STYLE = """
QPushButton {
    background-color: #fff1d6;
    border: 1px solid #c79a3b;
    border-radius: 9px;
    padding: 5px 12px;
    font-family: Georgia;
    font-size: 12px;
    font-weight: 800;
    color: #aa0000;
}
QPushButton:hover {
    background-color: #fff4df;
    border-color: #aa0000;
}
"""

FANTASY_DIALOG_QSS = """
QDialog {
    background-color: #fffdf7;
}
QLabel {
    background: transparent;
    border: none;
    color: #25190f;
    font-family: Georgia;
    font-size: 13px;
}
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background-color: #fffaf0;
    border: 1px solid #d9bd82;
    border-radius: 8px;
    padding: 5px 8px;
    color: #25190f;
    font-family: Georgia;
    font-size: 13px;
    selection-background-color: #d8edf7;
    selection-color: #25190f;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #a87824;
    background-color: #fffdf7;
}
QComboBox::drop-down {
    width: 26px;
    border: none;
    border-left: 1px solid #d9bd82;
    background-color: #d8edf7;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}
QComboBox QAbstractItemView {
    background-color: #fffdf7;
    border: 1px solid #cdaa63;
    border-radius: 8px;
    padding: 4px;
    color: #25190f;
    selection-background-color: #d8edf7;
    selection-color: #25190f;
    outline: none;
}
QListWidget {
    background-color: #fffaf0;
    border: 1px solid #cdaa63;
    border-radius: 11px;
    padding: 6px;
    color: #25190f;
    font-family: Georgia;
    font-size: 14px;
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
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""

FANTASY_MENU_QSS = """
QMenu {
    background-color: #fffdf7;
    border: 1px solid #cdaa63;
    border-radius: 9px;
    padding: 5px;
    font-family: Georgia;
    font-size: 13px;
    font-weight: 700;
    color: #25190f;
}
QMenu::item {
    background-color: transparent;
    border-radius: 6px;
    padding: 7px 24px 7px 10px;
    margin: 1px 2px;
    color: #25190f;
}
QMenu::item:selected {
    background-color: #d8edf7;
    color: #25190f;
}
QMenu::separator {
    height: 1px;
    background-color: #d9bd82;
    margin: 5px 7px;
}
"""

# Backward-compatible names now use the fantasy system.
POSITIVE_BUTTON_STYLE = FANTASY_BUTTON_PRIMARY_STYLE
NEGATIVE_BUTTON_STYLE = FANTASY_BUTTON_SECONDARY_STYLE


def make_positive_button(button):
    set_themed_stylesheet(
        button,
        FANTASY_BUTTON_PRIMARY_STYLE,
    )


def make_negative_button(button):
    set_themed_stylesheet(
        button,
        FANTASY_BUTTON_SECONDARY_STYLE,
    )


def style_fantasy_button(button):
    text = str(button.text() or "").strip().lower()

    if any(word in text for word in ("delete", "discard", "don't save", "remove")):
        style = FANTASY_BUTTON_DANGER_STYLE
    elif text in {"cancel", "no", "later", "close", "back"} or text.startswith("cancel"):
        style = FANTASY_BUTTON_SECONDARY_STYLE
    else:
        style = FANTASY_BUTTON_PRIMARY_STYLE

    set_themed_stylesheet(button, style)


def apply_fantasy_dialog_style(dialog):
    """Apply the shared fantasy presentation to a fully-built dialog."""
    set_themed_stylesheet(dialog, FANTASY_DIALOG_QSS)

    widgets = []
    for widget_type in (
        QLineEdit,
        QTextEdit,
        QSpinBox,
        QComboBox,
        QListWidget,
    ):
        widgets.extend(
            dialog.findChildren(widget_type)
        )

    for widget in widgets:
        # Reapply the dialog stylesheet to child controls which had their
        # own older local stylesheet. A tiny type-specific sheet gives the
        # child higher precedence without changing its behavior.
        if isinstance(widget, QLineEdit):
            qss = """
            QLineEdit { background-color: #fffaf0; border: 1px solid #d9bd82; border-radius: 8px; padding: 5px 8px; color: #25190f; font-family: Georgia; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #a87824; background-color: #fffdf7; }
            """
        elif isinstance(widget, QTextEdit):
            qss = """
            QTextEdit { background-color: #fffaf0; border: 1px solid #d9bd82; border-radius: 10px; padding: 8px; color: #25190f; font-family: Georgia; font-size: 13px; }
            QTextEdit:focus { border: 1px solid #a87824; background-color: #fffdf7; }
            """
        elif isinstance(widget, QSpinBox):
            qss = """
            QSpinBox { background-color: #fffaf0; border: 1px solid #d9bd82; border-radius: 8px; padding: 5px 8px; color: #25190f; font-family: Georgia; font-size: 13px; }
            QSpinBox:focus { border: 1px solid #a87824; background-color: #fffdf7; }
            """
        elif isinstance(widget, QComboBox):
            qss = """
            QComboBox { background-color: #fffaf0; border: 1px solid #d9bd82; border-radius: 8px; padding: 4px 30px 4px 8px; color: #25190f; font-family: Georgia; font-size: 13px; }
            QComboBox::drop-down { width: 25px; border: none; border-left: 1px solid #d9bd82; background-color: #d8edf7; border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
            QComboBox QAbstractItemView { background-color: #fffdf7; border: 1px solid #cdaa63; padding: 4px; color: #25190f; selection-background-color: #d8edf7; selection-color: #25190f; outline: none; }
            """
        else:
            qss = """
            QListWidget { background-color: #fffaf0; border: 1px solid #cdaa63; border-radius: 11px; padding: 6px; color: #25190f; font-family: Georgia; font-size: 14px; outline: none; }
            QListWidget::item { border: none; border-radius: 7px; padding: 7px 9px; margin: 1px 0px; }
            QListWidget::item:selected { background-color: #d8edf7; color: #25190f; }
            QListWidget::item:hover { background-color: #fff4df; }
            """

        set_themed_stylesheet(widget, qss)

    for button in dialog.findChildren(QPushButton):
        style_fantasy_button(button)


def fantasy_text_input(
    parent,
    title,
    label_text,
    text="",
    accept_text="Save",
    cancel_text="Cancel",
):
    """Theme-consistent replacement for native text-entry prompts."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(390)
    set_themed_stylesheet(dialog, FANTASY_DIALOG_QSS)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)

    title_label = QLabel(title)
    set_themed_stylesheet(
        title_label,
        """
        QLabel { background: transparent; border: none; font-family: Georgia; font-size: 20px; font-weight: 900; color: #25190f; }
        """,
    )
    layout.addWidget(title_label)

    field_label = QLabel(label_text)
    field_label.setWordWrap(True)
    layout.addWidget(field_label)

    field = QLineEdit()
    field.setText(str(text or ""))
    field.setMinimumHeight(36)
    layout.addWidget(field)

    buttons = QHBoxLayout()
    cancel_btn = QPushButton(cancel_text)
    accept_btn = QPushButton(accept_text)
    cancel_btn.setFixedSize(100, 34)
    accept_btn.setFixedSize(100, 34)
    make_negative_button(cancel_btn)
    make_positive_button(accept_btn)
    cancel_btn.clicked.connect(dialog.reject)
    accept_btn.clicked.connect(dialog.accept)
    accept_btn.setDefault(True)
    buttons.addWidget(cancel_btn)
    buttons.addStretch()
    buttons.addWidget(accept_btn)
    layout.addLayout(buttons)

    field.setFocus()
    field.selectAll()

    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    return field.text(), accepted


class ThemeMixin:

    def apply_current_theme(self):
        set_runtime_theme(
            self.current_theme
        )

        app = QApplication.instance()
        if app is not None:
            app.setPalette(
                build_application_palette(
                    self.current_theme
                )
            )

        apply_theme_to_existing_widgets(
            self
        )

        if self.current_theme == "dark":
            accent = theme_color("important")

            for stat_row in self.stat_rows.values():
                raw_qss = stat_row.bottom_label.property(
                    "_did_light_qss"
                )

                if raw_qss is not None:
                    styled = translate_qss_for_theme(
                        str(raw_qss)
                    )

                    styled = styled.replace(
                        "color: #eef3f7;",
                        f"color: {accent};",
                    )

                    stat_row.bottom_label.setStyleSheet(
                        styled
                    )

            for box in (
                self.bdv_box,
                self.dr_box,
            ):
                raw_qss = box.title_label.property(
                    "_did_light_qss"
                )

                if raw_qss is not None:
                    styled = translate_qss_for_theme(
                        str(raw_qss)
                    )

                    styled = styled.replace(
                        "color: #eef3f7;",
                        f"color: {accent};",
                    )

                    box.title_label.setStyleSheet(
                        styled
                    )

        self.hp_panel.update()
        self.at_box.update()
        self.update()

    def set_theme(self, theme_name):
        if theme_name not in THEME:
            return

        self.current_theme = theme_name

        settings = QSettings(
            "DID",
            "CharacterSheet",
        )

        settings.setValue(
            "theme",
            theme_name,
        )

        settings.sync()

        self.apply_current_theme()
        self.update_theme_toggle_button()

    def use_light_theme(self):
        self.set_theme("light")

    def use_dark_theme(self):
        self.set_theme("dark")

    def toggle_theme_from_button(self):
        if self.current_theme == "light":
            self.use_dark_theme()
        else:
            self.use_light_theme()

        self.update_theme_toggle_button()

    def update_theme_toggle_button(self):
        if not hasattr(
            self,
            "theme_toggle_btn",
        ):
            return

        if self.current_theme == "light":
            self.theme_toggle_btn.setText("☾")
            self.theme_toggle_btn.setToolTip(
                "Switch to Dark mode"
            )

        else:
            self.theme_toggle_btn.setText("☀")
            self.theme_toggle_btn.setToolTip(
                "Switch to Light mode"
            )
    # ============================================================
    # THEME
    # ============================================================

    def apply_current_theme(self):
        set_runtime_theme(
            self.current_theme
        )

        app = QApplication.instance()
        if app is not None:
            app.setPalette(
                build_application_palette(
                    self.current_theme
                )
            )

        apply_theme_to_existing_widgets(
            self
        )

        # Selected important labels become blue in Dark mode instead of
        # generic white. Everything else follows the normal palette rules.
        if self.current_theme == "dark":
            accent = theme_color("important")

            for stat_row in self.stat_rows.values():
                raw_qss = stat_row.bottom_label.property(
                    "_did_light_qss"
                )
                if raw_qss is not None:
                    styled = translate_qss_for_theme(
                        str(raw_qss)
                    )
                    styled = styled.replace(
                        "color: #eef3f7;",
                        f"color: {accent};",
                    )
                    stat_row.bottom_label.setStyleSheet(
                        styled
                    )

            for box in (self.bdv_box, self.dr_box):
                raw_qss = box.title_label.property(
                    "_did_light_qss"
                )
                if raw_qss is not None:
                    styled = translate_qss_for_theme(
                        str(raw_qss)
                    )
                    styled = styled.replace(
                        "color: #eef3f7;",
                        f"color: {accent};",
                    )
                    box.title_label.setStyleSheet(
                        styled
                    )

        self.hp_panel.update()
        self.at_box.update()
        self.update()

    def set_theme(self, theme_name):
        if theme_name not in THEME:
            return

        self.current_theme = theme_name

        settings = QSettings(
            "DID",
            "CharacterSheet",
        )
        settings.setValue(
            "theme",
            theme_name,
        )
        settings.sync()

        self.apply_current_theme()
        self.update_theme_toggle_button()

    def use_light_theme(self):
        self.set_theme("light")

    def use_dark_theme(self):
        self.set_theme("dark")

    def toggle_theme_from_button(self):
        if self.current_theme == "light":
            self.use_dark_theme()
        else:
            self.use_light_theme()

        self.update_theme_toggle_button()

    def update_theme_toggle_button(self):
        if not hasattr(
            self,
            "theme_toggle_btn",
        ):
            return

        if self.current_theme == "light":
            # Moon means: click to go to Dark mode.
            self.theme_toggle_btn.setText("☾")
            self.theme_toggle_btn.setToolTip(
                "Switch to Dark mode"
            )
        else:
            # Sun means: click to go to Light mode.
            self.theme_toggle_btn.setText("☀")
            self.theme_toggle_btn.setToolTip(
                "Switch to Light mode"
            )
