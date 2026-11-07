import re
from ui_feedback import preserve_sheet_scroll
from uuid import uuid4
import json
import random
from math import ceil, pi, sin, cos, atan2, hypot
from html import escape
from character_API import (
    IMPROVEMENT_REFERENCE_NOTES,
    SPELLCASTING_EMPOWERMENT_NOTE_HTML,
    ANIMAL_BUDDY_PERKS,
    ANIMAL_BUDDY_PERK_DESCRIPTIONS,
    ANIMAL_BUDDY_NOTE_TEMPLATE,
    animal_buddy_perk_id_from_choices,
    animal_buddy_perk_name,
    animal_buddy_perk_description,
)

from PySide6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QPoint,
    QRectF,
    QSettings,
)

from PySide6.QtGui import (
    QTextDocument,
    QTextCharFormat,
    QShortcut,
    QKeySequence,
    QFont,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QBrush,
    QPolygonF,
    QPalette,
    QIcon,
    QPixmap,
    QImage,
    QIntValidator,
)

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QMenu,
    QDialog,
    QColorDialog,
    QWidgetAction,
    QSlider,
    QSizePolicy,
)

from backend_2_1 import (
    CharacterNote,
)

from dialogs import (
    ask_yes_no,
    BuddyPerkPickerDialog,
    choose_buddy_perk_menu,
)

from ui_theme import (
    BLUE,
    set_themed_stylesheet,
    FANTASY_MENU_QSS,
    FANTASY_DIALOG_QSS,
    theme_color,
)
import ui_theme as ui_theme_module

def can_link_note(character, note, target_id):
    """Three total slots; reserve the managed note slot even before sync."""
    target_id = str(target_id or "")
    if not target_id or target_id == str(getattr(note, "linked_improvement_id", "") or ""):
        return True
    if character is None:
        return False
    others = [n for n in character.notes.list_of_notes
              if str(n.id) != str(note.id)
              and str(getattr(n, "linked_improvement_id", "") or "") == target_id]
    system_title = None
    if not target_id.startswith("item:"):
        improvement = next((i for i in character.improvements.list_of_taken_improvements
                            if str(i.id) == target_id), None)
        system_title = {
            "spellcasting": "spellcasting verbs", "magic_novice": "spellcasting verbs",
            "sneak_attack": "sneak attack", "mighty": "mighty",
            "animal_buddy": "animal buddy",
        }.get(getattr(improvement, "catalog_id", ""))
    if system_title:
        player_notes = [n for n in others if str(n.title).strip().lower() != system_title]
        return len(player_notes) < 2 and len(others) < 3
    return len(others) < 3


DARK_NOTE_COLORS = {
    "red": "#5a3333", "orange": "#60452f", "yellow": "#5a4d2d",
    "green": "#304f39", "blue": "#315767", "purple": "#4a3d68",
    "pink": "#5c394b",
}
DARK_NOTE_BODY_COLORS = {
    "red": "#432829", "orange": "#493626", "yellow": "#463d26",
    "green": "#263e2f", "blue": "#294754", "purple": "#3d3454",
    "pink": "#49313d",
}

def random_note_hex_color(existing_colors=()):
    """Choose a colorful pastel HEX for a *new player note*.

    The stored value never changes with the theme. Avoid near-neutrals and the
    muddy orange/brown hue range; try not to repeat nearby recent note hues.
    Existing character notes and system-note colors are not touched.
    """
    recent_hues = []
    for value in list(existing_colors)[-10:]:
        color = QColor(str(value))
        if color.isValid() and color.hslSaturation() >= 85:
            recent_hues.append(color.hslHue())

    for _ in range(36):
        hue = random.randrange(360)
        if 18 <= hue <= 47:  # These darken toward brown in Dark mode.
            continue
        saturation = random.randint(164, 218)
        lightness = random.randint(173, 202)
        candidate = QColor.fromHsl(hue, saturation, lightness).name()
        if all(min(abs(hue - old), 360 - abs(hue - old)) >= 13
               for old in recent_hues):
            return candidate
    # With a large number of notes, accepting a nearby hue is preferable to
    # endlessly retrying. Never fall back to black/white/gray/brown.
    while True:
        hue = random.randrange(360)
        if not 18 <= hue <= 47:
            return QColor.fromHsl(hue, random.randint(164, 218),
                                  random.randint(173, 202)).name()


def _custom_note_colors_for_theme(hex_color, dark):
    """Project one saved HEX into readable Light/Dark note surfaces.

    Hue and the underlying saved HEX stay unchanged when switching themes,
    including for colors chosen manually in the wheel. Neutral manual choices
    remain permitted; only *random* colors exclude them.
    """
    color = QColor(hex_color)
    hue = max(0, color.hslHue())
    saturation = color.hslSaturation()
    if dark:
        outer_lightness = max(61, min(86, color.lightness() // 2))
        outer_sat = min(170, round(saturation * 0.84))
        body_lightness = max(41, outer_lightness - 16)
        body_sat = min(155, outer_sat)
    else:
        outer_lightness = max(173, min(206, color.lightness()))
        outer_sat = saturation
        body_lightness = min(232, outer_lightness + 23)
        body_sat = max(0, saturation - 12)
    outer = QColor.fromHsl(hue, outer_sat, outer_lightness).name()
    body = QColor.fromHsl(hue, body_sat, body_lightness).name()
    return outer, body


def note_colors_for_theme(key):
    dark = ui_theme_module.CURRENT_THEME == "dark"
    if key in NOTE_COLORS:
        override = palette_note_color(key)
        if override == NOTE_COLORS[key]:
            return ((DARK_NOTE_COLORS[key], DARK_NOTE_BODY_COLORS[key]) if dark
                    else (NOTE_COLORS[key], ANIMAL_BUDDY_NOTE_BODY_COLORS[key]))
        return _custom_note_colors_for_theme(override, dark)
    return _custom_note_colors_for_theme(note_paper_color(key), dark)

def note_paper_color(key):
    return palette_note_color(key) if key in NOTE_COLORS else (
        key if QColor(key).isValid() else palette_note_color("yellow"))

def palette_note_color(key):
    try:
        overrides = json.loads(QSettings("DIDCharacterSheet", "NoteColors").value("palette_overrides", "{}"))
    except (TypeError, ValueError):
        overrides = {}
    value = overrides.get(key) if isinstance(overrides, dict) else None
    return QColor(value).name() if isinstance(value, str) and QColor(value).isValid() else NOTE_COLORS[key]

def set_palette_note_color(key, value=None):
    settings = QSettings("DIDCharacterSheet", "NoteColors")
    try:
        overrides = json.loads(settings.value("palette_overrides", "{}"))
    except (TypeError, ValueError):
        overrides = {}
    if not isinstance(overrides, dict):
        overrides = {}
    if value is None:
        overrides.pop(key, None)
    else:
        overrides[key] = QColor(value).name()
    settings.setValue("palette_overrides", json.dumps(overrides))

def saved_note_colors(kind):
    settings = QSettings("DIDCharacterSheet", "NoteColors")
    try:
        colors = json.loads(settings.value(kind, "[]"))
    except (TypeError, ValueError):
        colors = []
    return [value for value in colors if isinstance(value, str)
            and (value in NOTE_COLORS or QColor(value).isValid())][:12]

def remember_note_color(value):
    colors = [value] + [item for item in saved_note_colors("recent") if item != value]
    QSettings("DIDCharacterSheet", "NoteColors").setValue(
        "recent", json.dumps(colors[:8]))

def _matching_quick_note_color(current):
    """Return the quick-palette slot represented by *current*, if any."""
    if current in NOTE_COLOR_ORDER:
        return current
    try:
        current_name = QColor(note_paper_color(current)).name()
    except Exception:
        return None
    for key in NOTE_COLOR_ORDER:
        if QColor(palette_note_color(key)).name() == current_name:
            return key
    return None


def note_menu(menu, current="yellow"):
    set_themed_stylesheet(menu, FANTASY_MENU_QSS)
    palette = QWidget(menu)
    row = QHBoxLayout(palette)
    row.setContentsMargins(6, 6, 6, 6)
    row.setSpacing(5)

    selected_quick = _matching_quick_note_color(current)
    dark = ui_theme_module.CURRENT_THEME == "dark"
    selected_ring = "#f5efe3" if dark else "#5f431c"
    hover_ring = "#ffffff" if dark else "#6f4e22"

    for key in NOTE_COLOR_ORDER:
        swatch = QPushButton(palette)
        swatch.setFixedSize(28, 28)
        swatch.setToolTip(key.title())
        color = note_colors_for_theme(key)[0]
        if key == selected_quick:
            border = f"3px solid {selected_ring}"
            radius = 10
        else:
            border = "2px solid #b89a62"
            radius = 8
        swatch.setStyleSheet(
            f"QPushButton {{background:{color}; border:{border}; border-radius:{radius}px;}} "
            f"QPushButton:hover {{border:3px solid {hover_ring}; border-radius:10px;}}"
        )
        swatch.clicked.connect(lambda checked=False, value=key: (setattr(menu, "selected_color", value), menu.close()))
        row.addWidget(swatch)

    # The + is an action, not an eighth color swatch. Keep it neutral so the
    # selected quick color is the only color that receives a selection ring.
    more = QPushButton("+", palette)
    more.setFixedSize(28, 28)
    more.setToolTip("Choose any color")
    ink = "#f3dfb1" if dark else "#6f4e22"
    more.setStyleSheet(
        f"QPushButton {{background:transparent; color:{ink}; border:2px solid #b89a62; "
        "border-radius:8px; font-size:18px; font-weight:bold;} "
        f"QPushButton:hover {{border:3px solid {hover_ring}; border-radius:10px;}}"
    )
    more.clicked.connect(lambda: (setattr(menu, "selected_color", "custom"), menu.close()))
    row.addWidget(more)
    action = QWidgetAction(menu)
    action.setDefaultWidget(palette)
    menu.addAction(action)

def selected_note_color(menu, button, current):
    menu.selected_color = None
    menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
    choice = menu.selected_color
    if choice is None:
        return None
    if choice == "custom":
        picker = NoteColorPicker(QColor(note_paper_color(current)), button)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return None
        color = picker.selected_color
        chosen = color.name() if color.isValid() else None
    else:
        chosen = choice
    if chosen:
        remember_note_color(chosen)
    return chosen

class NoteColorWheel(QWidget):
    """Continuous hue and saturation wheel for custom note colors."""
    def __init__(self, on_pick, parent=None):
        super().__init__(parent)
        self.setFixedSize(174, 174)
        self.on_pick = on_pick
        self.hue, self.saturation, self.brightness = 0, 0, 255
        self.image = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_color(self, color):
        self.hue = max(0, color.hsvHue())
        self.saturation = color.hsvSaturation()
        if self.brightness != color.value():
            self.brightness = color.value()
            self.image = None
        self.update()

    def paintEvent(self, event):
        if self.image is None:
            size = self.width()
            image = QImage(size, size, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            center, radius = (size - 1) / 2, (size - 4) / 2
            for y in range(size):
                for x in range(size):
                    distance = hypot(x - center, y - center)
                    if distance <= radius:
                        hue = round(atan2(center - y, x - center) * 180 / pi) % 360
                        saturation = round(255 * distance / radius)
                        image.setPixelColor(x, y, QColor.fromHsv(hue, saturation, self.brightness))
            self.image = image
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawImage(0, 0, self.image)
        center, radius = (self.width() - 1) / 2, (self.width() - 4) / 2
        angle = self.hue * pi / 180
        x = center + cos(angle) * radius * self.saturation / 255
        y = center - sin(angle) * radius * self.saturation / 255
        painter.setPen(QPen(QColor("#171717"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), 6, 6)
        painter.end()

    def mousePressEvent(self, event):
        self._pick(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def _pick(self, position):
        center, radius = (self.width() - 1) / 2, (self.width() - 4) / 2
        dx, dy = position.x() - center, center - position.y()
        self.on_pick(round(atan2(dy, dx) * 180 / pi) % 360,
                     round(255 * min(radius, hypot(dx, dy)) / radius))

class NoteColorPicker(QDialog):
    """Compact HSV range picker with an editable hex value."""
    def __init__(self, initial, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose note color")
        self.setFixedWidth(350)
        self.selected_color = QColor(initial)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        self.preview = QFrame(self)
        self.preview.setFixedHeight(42)
        layout.addWidget(self.preview)
        recent = saved_note_colors("recent")
        if recent:
            layout.addWidget(QLabel("Recent colors"))
            recent_row = QHBoxLayout()
            recent_row.setSpacing(5)
            for value in recent[:8]:
                recent_row.addWidget(self.color_chip(value))
            recent_row.addStretch()
            layout.addLayout(recent_row)
        self.wheel = NoteColorWheel(self.update_from_wheel, self)
        layout.addWidget(self.wheel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.sliders = []
        for title, maximum, value in (("Hue", 359, max(0, initial.hsvHue())),
                                      ("Saturation", 255, initial.hsvSaturation()),
                                      ("Brightness", 255, initial.value())):
            row = QHBoxLayout()
            label = QLabel(title)
            label.setFixedWidth(74)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, maximum)
            slider.setValue(value)
            slider.valueChanged.connect(self.update_from_sliders)
            row.addWidget(label)
            row.addWidget(slider)
            layout.addLayout(row)
            self.sliders.append(slider)
        hex_row = QHBoxLayout()
        hex_row.setSpacing(5)
        hex_row.addWidget(QLabel("Hex"))
        self.hex_edit = QLineEdit(initial.name())
        self.hex_edit.setMaxLength(7)
        self.hex_edit.setFixedWidth(84)
        self.hex_edit.editingFinished.connect(self.update_from_hex)
        hex_row.addWidget(self.hex_edit)
        hex_row.addSpacing(7)
        self.rgb_fields = []
        for name, value in zip(("R", "G", "B"), (initial.red(), initial.green(), initial.blue())):
            hex_row.addWidget(QLabel(name))
            field = QLineEdit(str(value), self)
            field.setValidator(QIntValidator(0, 255, field))
            field.setFixedWidth(39)
            field.editingFinished.connect(self.update_from_rgb)
            hex_row.addWidget(field)
            self.rgb_fields.append(field)
        layout.addLayout(hex_row)
        layout.addWidget(QLabel("Customize quick colors"))
        self.quick_row = QHBoxLayout()
        self.quick_row.setSpacing(5)
        layout.addLayout(self.quick_row)
        self.refresh_quick_palette()
        palette_buttons = QVBoxLayout()
        self.slot_selector = QComboBox(self)
        for key in NOTE_COLOR_ORDER:
            self.slot_selector.addItem(key.title(), key)
        set_slot = QPushButton("Replace selected color")
        reset_slot = QPushButton("Reset selected color")
        set_slot.clicked.connect(lambda: self.change_quick_palette(False))
        reset_slot.clicked.connect(lambda: self.change_quick_palette(True))
        palette_buttons.addWidget(self.slot_selector)
        controls = QHBoxLayout()
        controls.addWidget(set_slot)
        controls.addWidget(reset_slot)
        palette_buttons.addLayout(controls)
        layout.addLayout(palette_buttons)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        okay = QPushButton("Use color")
        cancel.clicked.connect(self.reject)
        okay.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addStretch()
        buttons.addWidget(okay)
        layout.addLayout(buttons)
        dark = ui_theme_module.CURRENT_THEME == "dark"
        bg, text, field, button_bg, hover = (
            ("#192631", "#f2eee7", "#293946", "#465c68", "#587180") if dark
            else ("#f8f3e9", "#25190f", "#ffffff", "#e8d7b6", "#f7eacb")
        )
        self.setStyleSheet(FANTASY_DIALOG_QSS + f"QDialog {{background:{bg}; color:{text};}} QLabel {{color:{text};}} QLineEdit, QComboBox {{background:{field}; color:{text}; border:1px solid #b89a62; border-radius:5px; padding:5px;}} QPushButton {{background:{button_bg}; color:{text}; border:1px solid #b08b48; border-radius:6px; padding:6px 10px; font-weight:600;}} QPushButton:hover {{background:{hover};}}")
        self.update_preview()

    def color_chip(self, value):
        chip = QPushButton(self)
        chip.setFixedSize(25, 25)
        chip.setToolTip(value)
        chip.setStyleSheet(f"QPushButton {{background:{note_colors_for_theme(value)[0]}; border:2px solid #b89a62; border-radius:12px;}}")
        chip.clicked.connect(lambda: self.use_color(note_paper_color(value)))
        return chip

    def use_color(self, value):
        self.selected_color = QColor(value)
        self.sync_fields()
        self.update_preview()

    def refresh_quick_palette(self):
        while self.quick_row.count():
            item = self.quick_row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for key in NOTE_COLOR_ORDER:
            chip = self.color_chip(key)
            chip.setToolTip(f"{key.title()}: {palette_note_color(key)}")
            chip.clicked.connect(lambda checked=False, slot=key: self.slot_selector.setCurrentIndex(NOTE_COLOR_ORDER.index(slot)))
            self.quick_row.addWidget(chip)
        self.quick_row.addStretch()

    def change_quick_palette(self, remove):
        self.update_from_hex()
        set_palette_note_color(self.slot_selector.currentData(), None if remove else self.selected_color.name())
        self.refresh_quick_palette()

    def accept(self):
        self.update_from_hex()
        super().accept()

    def update_preview(self):
        self.preview.setStyleSheet(f"background:{self.selected_color.name()}; border:1px solid #9c8255; border-radius:7px;")
        self.wheel.set_color(self.selected_color)

    def sync_fields(self):
        color = self.selected_color
        self.hex_edit.setText(color.name())
        for slider, value in zip(self.sliders, (max(0, color.hsvHue()), color.hsvSaturation(), color.value())):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        for field, value in zip(self.rgb_fields, (color.red(), color.green(), color.blue())):
            field.blockSignals(True)
            field.setText(str(value))
            field.blockSignals(False)

    def update_from_wheel(self, hue, saturation):
        for slider, value in zip(self.sliders[:2], (hue, saturation)):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.update_from_sliders()

    def update_from_sliders(self, *_):
        if len(self.sliders) != 3:
            return
        self.selected_color = QColor.fromHsv(*(slider.value() for slider in self.sliders))
        self.sync_fields()
        self.update_preview()

    def update_from_rgb(self, *_):
        if len(self.rgb_fields) != 3:
            return
        if any(not field.text() for field in self.rgb_fields):
            return
        self.selected_color = QColor.fromRgb(*(int(field.text()) for field in self.rgb_fields))
        self.sync_fields()
        self.update_preview()

    def update_from_hex(self):
        color = QColor(self.hex_edit.text())
        if not color.isValid():
            self.hex_edit.setText(self.selected_color.name())
            return
        self.selected_color = color
        self.sync_fields()
        self.update_preview()

NOTE_COLORS = {
    "red": "#f3a6a6",
    "orange": "#ffc078",
    "yellow": "#ffe98a",
    "green": "#a8e6b0",
    "blue": "#9fcfe3",
    "purple": "#c8b6ff",
    "pink": "#f4b6cf",
}

SPELLCASTING_VERBS_NOTE_TEXT = """Agility: Teleport, Speed Up, Fly
Strength: Lift, Constrict, Hold, Break, Launch
Finesse: Conceal, Dispel, Abjure
Instinct: Shape, Detect, Connect, Bless
Presence: Charm, Direct, Buff, Channel
Knowledge: Identify, Clairvoyance, Reveal, Modify"""

def spellcasting_note_html(improvement):
    """Render verbs followed by one flush-left list of all owned spell effects."""
    verbs = []
    for line in SPELLCASTING_VERBS_NOTE_TEXT.splitlines():
        name, description = line.split(":", 1)
        verbs.append(f"<b>{escape(name)}:</b>{escape(description)}")
    owned = {getattr(item, "catalog_id", "") for item in getattr(improvement, "empowerments", ())}
    effects = []
    for perk_id in ("harm_slinger", "expert_enchanter"):
        if perk_id in owned:
            source = SPELLCASTING_EMPOWERMENT_NOTE_HTML[perk_id]
            effects.extend(part.removesuffix("</li>") for part in source.split("<li>") if part)
    if not effects:
        return "<br>".join(verbs)
    # Qt gives <ul> a large implicit left and vertical margin. Render one
    # uninterrupted list with explicit bullets at the text's left edge.
    bullets = "<br>".join("&#8226; " + effect for effect in effects)
    return "<br>".join(verbs) + "<br><br>" + bullets

def format_system_note_html(value):
    """Indent ordinary lines and hang wrapped bullet text after its marker."""
    lines = str(value).replace("\n", "<br>").split("<br>")
    while lines and not lines[-1].strip():
        lines.pop()
    formatted = []
    for line in lines:
        if not line.strip():
            formatted.append('<p style="margin:0">&nbsp;</p>')
            continue
        bullet = line.lstrip().startswith(("*", "•", "&#8226;", "- "))
        heading = line.lstrip().startswith("<b>") and not bullet
        # Labeled verb rows need a hanging indent too, so a wrapped word such
        # as "Modify" lines up under the verb text instead of the far-left edge.
        labeled_row = bool(
            re.match(r"^\s*<b>[^<]+:</b>", line, flags=re.IGNORECASE)
        )
        indent = (
            "margin:0 0 0 15px; text-indent:-15px"
            if bullet or labeled_row
            else "margin:0" if heading
            else "margin:0 0 0 15px"
        )
        formatted.append(f'<p style="{indent}">{line}</p>')
    return "".join(formatted)

def format_spellcasting_system_note_html(value):
    """Use the same inline labels and hanging wraps as the sheet preview."""
    return format_system_note_html(value)


NOTE_COLOR_ORDER = [
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
]
NOTE_COLOR_SHORT_NAMES = {
    "red": "RD",
    "orange": "OR",
    "yellow": "YL",
    "green": "GN",
    "blue": "BL",
    "purple": "PR",
    "pink": "PK",
}

# Companion resource state is stored in the owned Improvement's choices, not
# in a note's free-text field. The note is a view/editor of that existing model.
BUDDY_STATS = ("Agility", "Strength", "Finesse", "Instinct", "Presence", "Knowledge")


def buddy_state(buddy, owner_bdv):
    """Calculate companion mechanics without mutating saved character data."""
    choices = buddy.choices or {}
    dice = {name: 4 for name in BUDDY_STATS}
    for key, size in (("buddy_stat_d10", 10), ("buddy_stat_d8_a", 8),
                      ("buddy_stat_d8_b", 8), ("buddy_stat_d6", 6)):
        selected = str(choices.get(key, "")).strip().lower()
        for stat in dice:
            if stat.lower() == selected:
                dice[stat] = size
                break
    training = {stat: 0 for stat in BUDDY_STATS}
    perks = []
    primary = str(choices.get("buddy_perk") or "").strip()
    if primary and primary.lower() != "missing":
        perks.append((primary, choices, "buddy_perk"))
    extra_hearts = 0
    for upgrade in buddy.empowerments:
        if upgrade.group_id == "buddy_hearts":
            extra_hearts += 1
        elif upgrade.catalog_id == "gifted":
            perk = str((upgrade.choices or {}).get("buddy_perk") or "").strip()
            if perk and perk.lower() != "missing":
                perks.append((perk, upgrade.choices, "buddy_perk"))
        elif upgrade.catalog_id == "well_trained":
            selected = str((upgrade.choices or {}).get(
                "buddy_training_stat") or "").strip().lower()
            for stat in training:
                if stat.lower() == selected:
                    training[stat] += 1
                    break
    sturdy = any(
        animal_buddy_perk_id_from_choices(destination) == "sturdy"
        for _name, destination, _key in perks
    )
    hearts = (2 if sturdy else 1) + extra_hearts
    max_hp = 4 * hearts
    try:
        damage = max(0, int(choices.get("_buddy_marked_damage", 0)))
    except (TypeError, ValueError):
        damage = 0
    return dict(dice=dice, training=training, perks=perks, hearts=hearts,
                max_hp=max_hp, current_hp=max(0, max_hp - damage),
                bdv=ceil(owner_bdv / 2))


class BuddyHeart(QWidget):
    """Actual heart artwork with four HP quarters; left damage, right heal."""
    def __init__(self, index, get_hp, change_hp, parent=None):
        super().__init__(parent)
        self.index, self.get_hp, self.change_hp = index, get_hp, change_hp
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Click a filled quarter to mark damage; click an empty quarter to heal. Right-click heals.")

    def paintEvent(self, event):
        # Match the character sheet's HeartWidget silhouette and quarter lines.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.moveTo(w * .50, h * .20)
        path.cubicTo(w * .50, h * .04, w * .78, h * .02, w * .88, h * .22)
        path.cubicTo(w * .98, h * .42, w * .88, h * .70, w * .50, h * .95)
        path.cubicTo(w * .12, h * .70, w * .02, h * .42, w * .12, h * .22)
        path.cubicTo(w * .22, h * .02, w * .50, h * .04, w * .50, h * .20)
        path.closeSubpath()
        halves = [QRectF(0, 0, w / 2, h / 2), QRectF(w / 2, 0, w / 2, h / 2),
                  QRectF(0, h / 2, w / 2, h / 2), QRectF(w / 2, h / 2, w / 2, h / 2)]
        remaining = max(0, min(4, self.get_hp() - 4 * self.index))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme_color("heart_empty"))))
        painter.drawPath(path)
        painter.setBrush(QBrush(QColor(theme_color("heart_fill"))))
        for rect in halves[:remaining]:
            piece = QPainterPath()
            piece.addRect(rect)
            painter.drawPath(path.intersected(piece))
        painter.setPen(QPen(QColor(theme_color("heart_outline")), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.drawLine(int(w * .5), int(h * .15), int(w * .5), int(h * .95))
        painter.drawLine(int(w * .12), int(h * .5), int(w * .9), int(h * .5))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Each of the four quadrants is an independently clickable HP
            # segment. Filled quarter = mark damage; empty = heal.
            position = event.position()
            segment = (2 if position.y() >= self.height() * .42 else 0) + (1 if position.x() >= self.width() / 2 else 0)
            remaining = max(0, min(4, self.get_hp() - 4 * self.index))
            self.change_hp(-1 if segment < remaining else 1)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.change_hp(1)
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.change_hp(-1)
            event.accept()
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.change_hp(1)
            event.accept()
        else:
            super().keyPressEvent(event)


class BuddyBDVBadge(QWidget):
    """Compact starburst indicator matching the character sheet's BDV emblem."""

    def __init__(self, value, parent=None):
        super().__init__(parent)
        self.value = str(value)
        self.setFixedSize(52, 63)
        self.setToolTip("Buddy base damage value")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#f2eee7" if ui_theme_module.CURRENT_THEME == "dark" else "#3b2616")))
        title_font = QFont("Georgia", 10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(0, 0, self.width(), 16, Qt.AlignmentFlag.AlignCenter, "BDV")
        cx, cy = self.width() / 2, 40
        points = []
        for n in range(24):
            angle = -pi / 2 + n * pi / 12
            radius = 24 if n % 2 == 0 else 17
            points.append(QPointF(cx + radius * cos(angle), cy + radius * sin(angle)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c82541"))
        painter.drawPolygon(QPolygonF(points))
        painter.setPen(QColor("#ffffff"))
        value_font = QFont("Georgia", 12)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.drawText(0, 19, self.width(), 43, Qt.AlignmentFlag.AlignCenter, self.value)
        painter.end()


class AnimalBuddyPanel(QFrame):
    """Interactive miniature character sheet linked to the owned companion."""

    ACCENTS = {"Agility": "#6F8F2C", "Strength": "#A8453C",
               "Finesse": "#356FA8", "Instinct": "#6B55A6",
               "Presence": "#2F8792", "Knowledge": "#B17828"}

    def __init__(self, note, character, on_change, parent=None):
        super().__init__(parent)
        self.character, self.note, self.on_change = character, note, on_change
        self.buddy = next((imp for imp in character.improvements.list_of_taken_improvements
                           if imp.catalog_id == "animal_buddy"
                           and str(imp.id) == str(note.linked_improvement_id)), None)
        self.setObjectName("AnimalBuddyPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # The NOTE is the parchment. Only ability cards retain individual panels.
        set_themed_stylesheet(self, """
            QFrame#AnimalBuddyPanel { background:transparent; border:none; }
            QLineEdit { background:transparent; color:#352414; border:none;
                        padding:0; font-family:Georgia; font-weight:700; }
            QLineEdit:focus { border-bottom:1px solid #a7752b; }
        """)
        main = QVBoxLayout(self)
        main.setContentsMargins(2, 2, 2, 3)
        main.setSpacing(2)
        if self.buddy is None:
            main.addWidget(QLabel("The linked Animal Buddy was not found."))
            return
        self.state = buddy_state(self.buddy, character.BDV)

        # ---------------------------------------------------------
        # NAME + PERKS + BDV
        # ---------------------------------------------------------
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)

        left_info = QVBoxLayout()
        left_info.setContentsMargins(0, 0, 0, 0)
        left_info.setSpacing(1)

        # -------------------------
        # Name
        # -------------------------

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(4)

        name_label = QLabel("Name:")
        name_label.setStyleSheet(
            "color:#603d1a;"
            "background:transparent;"
            "border:none;"
            "font-family:Georgia;"
            "font-size:13px;"
            "font-weight:800;"
            "padding:0;"
        )

        name_row.addWidget(
            name_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.name_edit = QLineEdit(
            str(self.buddy.choices.get("buddy_name") or "")
        )

        self.name_edit.setMaxLength(100)
        self.name_edit.setPlaceholderText("Buddy name")
        self.name_edit.setToolTip(
            "Click to edit your companion's name"
        )

        self.name_edit.setFixedHeight(24)

        self.name_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.name_edit.setStyleSheet(
            "QLineEdit {"
            "background:transparent;"
            "border:none;"
            "color:#452711;"
            "font-family:Georgia;"
            "font-size:13px;"
            "font-weight:800;"
            "padding:0;"
            "}"
            "QLineEdit:focus {"
            "border-bottom:1px solid #a7752b;"
            "}"
        )

        self.name_edit.editingFinished.connect(
            lambda field=self.name_edit:
            self.save_choice(
                self.buddy.choices,
                "buddy_name",
                field.text(),
            )
        )

        name_row.addWidget(
            self.name_edit,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )

        left_info.addLayout(name_row)

        # -------------------------
        # Perks
        # -------------------------

        perk_heading = QLabel("Perks:")
        perk_heading.setStyleSheet(
            "color:#603d1a; background:transparent; border:none;"
            "font-family:Georgia; font-size:13px; font-weight:800; padding:0;"
        )
        left_info.addWidget(perk_heading)
        if not self.state["perks"]:
            left_info.addWidget(QLabel("None selected"))
        for perk, destination, key in self.state["perks"]:
            display_name = animal_buddy_perk_name(destination)
            description = animal_buddy_perk_description(destination)
            choice = QPushButton(f"• {display_name} ▾")
            choice.setCursor(Qt.CursorShape.PointingHandCursor)
            choice.setToolTip("Choose this buddy perk")
            choice.setFixedHeight(24)
            choice.setStyleSheet(
                "QPushButton {text-align:left; color:#452711; background:transparent; "
                "border:none; padding:0; font-family:Georgia; font-size:13px; font-weight:800;} "
                "QPushButton:hover {color:#925718; text-decoration:underline;}"
            )
            left_info.addWidget(choice)
            choice.clicked.connect(
                lambda checked=False, target=destination, anchor=choice:
                self.choose_perk(target, anchor)
            )
            if description:
                detail = QLabel(description)
                detail.setWordWrap(True)
                detail.setStyleSheet(
                    "color:#452711; background:transparent; border:none;"
                    "font-family:Georgia; font-size:11px; padding:0 0 2px 12px;"
                )
                left_info.addWidget(detail)

        # Put name/perks on left and BDV on right.
        status_row.addLayout(
            left_info,
            1,
        )

        status_row.addWidget(
            BuddyBDVBadge(
                self.state["bdv"],
                self,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        main.addLayout(
            status_row
        )
        # Hearts remain grouped together at the left.
        heart_row = QHBoxLayout()
        heart_row.setContentsMargins(0, 0, 0, 0)
        heart_row.setSpacing(6)
        self.hearts = [
            BuddyHeart(i, lambda: self.state["current_hp"], self.adjust_hp, self)
            for i in range(self.state["hearts"])
        ]
        for heart in self.hearts:
            heart.setFixedSize(57, 53)
            heart_row.addWidget(heart, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        heart_row.addStretch(1)
        main.addLayout(heart_row)

        # Compact original-style colored ability cards; clicking rolls the buddy die.
        self.ability_cells = []
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        for i, stat in enumerate(BUDDY_STATS):
            accent = self.ACCENTS[stat]
            die = self.state["dice"][stat]
            bonus = self.state["training"][stat]
            value = f"d{die}" + (f" +{bonus}" if bonus else "")
            cell = QPushButton()
            cell.setObjectName("BuddyAbility")
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            cell.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            cell.setToolTip(f"Roll {stat}: {value}")
            cell.setStyleSheet(
                f"QPushButton#BuddyAbility {{background:#fffdf8; border:1px solid {accent}; "
                f"border-radius:7px; padding:0;}} "
                "QPushButton#BuddyAbility:hover {background:#fff8ec;} "
                "QPushButton#BuddyAbility:pressed {background:#f3ead7;}"
            )
            cell.setMinimumHeight(67)
            cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            v = QVBoxLayout(cell)
            v.setContentsMargins(4, 5, 4, 4)
            v.setSpacing(3)
            title = QLabel(stat)
            title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setMinimumHeight(19)
            title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            title.setStyleSheet(
                f"color:{accent}; border:none; background:transparent; font-family:Georgia; "
                "font-size:10px; font-weight:800; padding:0;"
            )
            number = QLabel(value)
            number.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setStyleSheet(
                f"color:{accent}; background:#f7f0df; border:1px solid {accent}; "
                "border-radius:4px; font-family:Georgia; font-size:13px; "
                "font-weight:900; padding:0 2px;"
            )
            self.ability_cells.append((cell, title, number, accent))
            number.setMinimumHeight(27)
            v.addWidget(title)
            v.addWidget(number)
            cell.clicked.connect(
                lambda checked=False, stat_name=stat, sides=die, flat_bonus=bonus, color=accent:
                self.roll_buddy_ability(stat_name, sides, flat_bonus, color)
            )
            grid.addWidget(cell, i // 3, i % 3)
            grid.setColumnStretch(i % 3, 1)
        main.addLayout(grid)

        # Purchased upgrades are already listed on the sheet's Improvement.

    def owned_other_perk_ids(self, target_choices):
        result = set()
        for _name, destination, _key in self.state.get("perks", []):
            if destination is target_choices:
                continue
            perk_id = animal_buddy_perk_id_from_choices(destination)
            if perk_id and perk_id != "custom":
                result.add(perk_id)
        unavailable = set(result)
        for perk_id in result:
            unavailable.update(
                ANIMAL_BUDDY_PERKS.get(perk_id, {}).get("incompatible_with", [])
            )
        unavailable.discard("custom")
        return unavailable

    def choose_perk(self, destination, anchor=None):
        if self.readonly():
            return
        selected = choose_buddy_perk_menu(
            self, anchor or self, destination,
            self.owned_other_perk_ids(destination),
        )
        if selected is None:
            return
        for key in ("buddy_perk_custom_name", "buddy_perk_custom_description"):
            destination.pop(key, None)
        destination.update(selected)
        self.persist(refresh=True)

    def roll_buddy_ability(self, stat_name, die_size, bonus, accent):
        window = self.window()
        owner = getattr(window, "_buddy_sheet_owner", None)
        if owner is not None:
            window = owner
        if not hasattr(window, "roll_dice_plan"):
            return
        if hasattr(window, "dice_roller_is_enabled") and not window.dice_roller_is_enabled():
            return
        window._pending_other_dice_count = 0
        window._pending_d100_count = 0
        window._pending_dice_stat_name = f"Animal Buddy — {stat_name}"
        window._pending_dice_stat_key = ""
        window._pending_dice_color = accent
        plan = {
            "ability_name": f"Animal Buddy — {stat_name}",
            "ability": {"label": "roll", "sides": int(die_size), "sign": 1, "explode": True},
            "flat_bonus": int(bonus),
            "extras": [],
        }
        window.roll_dice_plan(plan, accent)

    def readonly(self):
        window = self.window()
        return bool(hasattr(window, "is_readonly_character") and window.is_readonly_character())

    def persist(self, refresh=False):
        window = self.window()
        if hasattr(window, "character"):
            window.character.validate()
        if hasattr(window, "synchronize_animal_buddy_note"):
            window.synchronize_animal_buddy_note()
        if hasattr(window, "mark_dirty"):
            window.mark_dirty(auto_save=True)
        if refresh and hasattr(window, "refresh_all"):
            QTimer.singleShot(0, window.refresh_all)

    def save_choice(self, destination, key, value):
        if self.buddy is None or self.readonly():
            return
        if destination.get(key, "") == value:
            return
        destination[key] = value
        self.persist(refresh=True)

    def set_hp(self, hp):
        if self.buddy is None or self.readonly():
            return
        hp = max(0, min(self.state["max_hp"], int(hp)))
        if self.state["current_hp"] == hp:
            return
        self.state["current_hp"] = hp
        self.buddy.choices["_buddy_marked_damage"] = self.state["max_hp"] - hp
        for heart in self.hearts:
            heart.update()
        self.persist()

    def adjust_hp(self, delta):
        if self.readonly():
            return
        self.set_hp(self.state["current_hp"] + delta)



ANIMAL_BUDDY_NOTE_BODY_COLORS = {
    "red": "#f8caca", "orange": "#ffd7aa", "yellow": "#fff2b8",
    "green": "#c9efce", "blue": "#c7e5f1", "purple": "#ded5ff",
    "pink": "#f8d2e2",
}


class AnimalBuddyNoteCard(QFrame):
    """One canonical Animal Buddy card used on Notes and in sheet previews."""
    CARD_WIDTH = 300

    def __init__(self, note, character, update_callback, parent=None):
        super().__init__(parent)
        self.note = note
        self.character = character
        self.update_callback = update_callback
        self.setObjectName("AnimalBuddyNoteCard")
        self.setFixedWidth(self.CARD_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)

        color_key = note.color if note.color in NOTE_COLORS else "yellow"
        outer_color = NOTE_COLORS[color_key]
        body_color = ANIMAL_BUDDY_NOTE_BODY_COLORS.get(color_key, "#fff2b8")
        set_themed_stylesheet(self, f"""
            QFrame#AnimalBuddyNoteCard {{
                background-color: {outer_color};
                border: 1px solid #c79a3b;
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 10)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.arrow_btn = QPushButton("▾" if note.expanded else "▸")
        self.arrow_btn.setFixedSize(18, 18)
        self.arrow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow_btn.setStyleSheet("QPushButton {background:transparent; border:none; font-size:13px; font-weight:900;}")
        self.arrow_btn.clicked.connect(self.toggle_expanded)
        header.addWidget(self.arrow_btn)
        title = QLabel("Animal Buddy")
        self.title_label = title
        set_themed_stylesheet(title, """
            QLabel {background:transparent; border:none; font-family:Georgia;
                    font-size:15px; font-weight:900; color:#25190f; padding:0 2px;}
        """)
        header.addWidget(title, 1)

        # Animal Buddy is a managed/system note, but pinning is a display-order
        # preference rather than an edit to its authored content.  Give it the
        # same pin control as every other note card.
        self.pin_btn = QPushButton("✦" if getattr(note, "pinned", False) else "✧")
        self.pin_btn.setFixedSize(20, 20)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.clicked.connect(self.toggle_pinned)
        header.addWidget(self.pin_btn)

        self.color_btn = QPushButton("")
        self.color_btn.setToolTip("Change note color")
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_btn.clicked.connect(self.open_color_menu)
        header.addWidget(self.color_btn)
        layout.addLayout(header)

        body = QFrame()
        body.setObjectName("AnimalBuddyNoteBody")
        set_themed_stylesheet(body, f"""
            QFrame#AnimalBuddyNoteBody {{
                background-color: {body_color};
                border: 1px solid #c79a3b;
                border-radius: 9px;
            }}
        """)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 7, 8, 8)
        body_layout.setSpacing(0)
        self.panel = AnimalBuddyPanel(note, character, update_callback, body)
        body_layout.addWidget(self.panel)
        layout.addWidget(body)
        self.body = body
        self.set_expanded_state()
        self.update_color_style()

    def set_expanded_state(self):
        self.arrow_btn.setText("▾" if self.note.expanded else "▸")
        self.body.setVisible(self.note.expanded)
        layout = self.layout()
        if self.note.expanded:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            layout.setContentsMargins(10, 7, 10, 10)
            layout.setSpacing(6)
        else:
            # Match the collapsed height of the standard NoteCard at 100% DPI.
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(0)
            self.setFixedHeight(30)
        layout.invalidate()
        self.updateGeometry()

    def toggle_expanded(self):
        self.note.expanded = not self.note.expanded
        self.set_expanded_state()
        if self.parentWidget() is not None:
            self.parentWidget().updateGeometry()
        self.update_callback()

    def update_color_style(self):
        color_key = self.note.color if self.note.color in NOTE_COLORS else "yellow"
        outer_color, body_color = note_colors_for_theme(self.note.color)
        dark = ui_theme_module.CURRENT_THEME == "dark"
        border = "#8e7446" if dark else "#c79a3b"
        ink = "#f2eee7" if dark else "#452711"
        set_themed_stylesheet(self, f"QFrame#AnimalBuddyNoteCard {{background-color:{outer_color}; border:1px solid {border}; border-radius:12px;}}")
        set_themed_stylesheet(self.body, f"QFrame#AnimalBuddyNoteBody {{background-color:{body_color}; border:1px solid {border}; border-radius:9px;}}")
        for widget in (self.panel.findChildren(QLabel) + self.panel.findChildren(QLineEdit)
                       + self.panel.findChildren(QPushButton)):
            if isinstance(widget, QPushButton) and widget.objectName() == "BuddyAbility":
                continue
            if not hasattr(widget, "_buddy_original_css"):
                widget._buddy_original_css = widget.styleSheet()
            css = widget._buddy_original_css
            if dark:
                css = css.replace("#603d1a", ink).replace("#452711", ink)
            widget.setStyleSheet(css)
        for cell, title, number, accent in getattr(self.panel, "ability_cells", ()):
            surface = "#273642" if dark else "#fffdf8"
            inset = "#344453" if dark else "#f7f0df"
            hover = "#385166" if dark else "#fff8ec"
            accent_color = QColor(accent).lighter(160).name() if dark else accent
            cell.setStyleSheet(f"QPushButton#BuddyAbility {{background:{surface}; border:1px solid {accent_color}; border-radius:7px; padding:0; color:{accent_color};}} QPushButton#BuddyAbility:hover {{background:{hover};}}")
            title.setStyleSheet(f"color:{accent_color}; border:none; background:transparent; font-family:Georgia; font-size:10px; font-weight:800; padding:0;")
            number.setStyleSheet(f"color:{accent_color}; background:{inset}; border:1px solid {accent_color}; border-radius:4px; font-family:Georgia; font-size:13px; font-weight:900; padding:0 2px;")
        self.arrow_btn.setStyleSheet(f"QPushButton {{background:transparent; border:none; color:{ink}; font-size:13px; font-weight:900;}}")
        self.title_label.setStyleSheet(f"QLabel {{background:transparent; border:none; font-family:Georgia; font-size:15px; font-weight:900; color:{ink}; padding:0 2px;}}")
        for badge in self.panel.findChildren(BuddyBDVBadge):
            badge.update()
        for heart in self.panel.findChildren(BuddyHeart):
            heart.update()
        self.panel.update()
        self.refresh_pin_button()

        # Use the same note-control geometry and accent border as the
        # redesigned regular NoteCard.  The old generic ``black`` border was
        # translated to the Dark theme's blue UI border, which is why Animal
        # Buddy showed a blue, heavier-looking ring while other notes used the
        # muted gold note border.
        self.color_btn.setText("")
        self.color_btn.setToolTip("Change note color")
        set_themed_stylesheet(self.color_btn, f"""
            QPushButton {{
                background-color: {outer_color};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 0px;
                margin: 0px;
                font-size: 9px;
                font-weight: 900;
                color: {ink};
            }}

            QPushButton:hover {{
                background-color: {body_color};
                border-color: {border};
            }}
        """)

    def refresh_pin_button(self):
        pinned = bool(getattr(self.note, "pinned", False))
        self.pin_btn.setText("✦" if pinned else "✧")
        self.pin_btn.setToolTip("Unpin note" if pinned else "Pin note to the top")
        set_themed_stylesheet(
            self.pin_btn,
            """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 900;
                color: #8f6417;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 90);
                border-radius: 4px;
            }
            """
        )

    def toggle_pinned(self):
        window = self.window()
        if hasattr(window, "block_if_readonly") and window.block_if_readonly():
            return
        self.note.pinned = not bool(getattr(self.note, "pinned", False))
        self.refresh_pin_button()
        self.update_callback()
        if hasattr(window, "mark_dirty"):
            window.mark_dirty(auto_save=True)
        if hasattr(window, "refresh_notes"):
            QTimer.singleShot(0, window.refresh_notes)

    def open_color_menu(self):
        menu = QMenu(self)
        note_menu(menu, self.note.color)
        selected = selected_note_color(menu, self.color_btn, self.note.color)
        if selected is not None:
            self.note.color = selected
            self.update_color_style()
            self.update_callback()


class NoteCard(QFrame):
    """
    Compact sticky-note card.

    A sticky‑note style card with title, color selector, and editable text.
    Supports expand/collapse and deletion for organizing character notes.
    """

    CARD_WIDTH = 300
    SYSTEM_CARD_WIDTH = 300
    
    def __init__(
        self,
        note,
        update_callback,
        delete_callback,
        parent=None,
        character=None,
        link_callback=None,
    ):
        super().__init__(parent)

        self.note = note
        self.update_callback = update_callback
        self.delete_callback = delete_callback
        self.character = character
        self.link_callback = link_callback

        self.pending_autosave = False

        app = QApplication.instance()

        if app is not None:
            app.focusChanged.connect(
                self.on_application_focus_changed
            )

        self.is_system_note = (
            self.note.title.strip().lower()
            in {
                "spellcasting verbs",
                "sneak attack",
                "mighty",
            }
            or (self.note.title.strip().lower() == "animal buddy"
                and bool(str(self.note.linked_improvement_id or "")))
        )

        if (self.note.title.strip().lower() == "animal buddy"
                and self.is_system_note and self.character is not None):
            self.setObjectName("AnimalBuddyNoteHost")
            self.setStyleSheet("QFrame#AnimalBuddyNoteHost {background:transparent; border:none;}")
            host_layout = QVBoxLayout(self)
            host_layout.setContentsMargins(0, 0, 0, 0)
            host_layout.setSpacing(0)
            self.animal_buddy_card = AnimalBuddyNoteCard(
                self.note, self.character, self.update_callback, self
            )
            self.text_edit = self.animal_buddy_card.panel
            host_layout.addWidget(self.animal_buddy_card)
            self.setFixedWidth(self.animal_buddy_card.CARD_WIDTH)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
            return

        self.setObjectName("NoteCard")

        card_width = (
            self.SYSTEM_CARD_WIDTH
            if self.is_system_note
            else self.CARD_WIDTH
        )

        self.setFixedWidth(card_width)

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Maximum,
        )

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(8, 5, 8, 7)
        self.outer_layout.setSpacing(3)

        # ========================================================
        # Header
        # ========================================================

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.arrow_btn = QPushButton(
            "▾" if self.note.expanded else "▸"
        )

        self.arrow_btn.setFixedSize(
            18,
            18,
        )

        self.arrow_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        set_themed_stylesheet(
            self.arrow_btn,
            """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #2f5f91;
            }
            """
        )

        self.arrow_btn.clicked.connect(
            self.toggle_expanded
        )            



        # Directly editable note title
        self.title_edit = QLineEdit(self.note.title)
        self.title_edit.setMaxLength(120)
        self.title_edit.setCursorPosition(0)
        self.title_edit.setToolTip(self.note.title)
        if self.is_system_note:
            self.title_edit.setReadOnly(True)
            self.title_edit.setFocusPolicy(
                Qt.FocusPolicy.NoFocus
            )
        self.title_edit.setPlaceholderText("New Note")
        
        self.title_edit.setFrame(False)
        self.title_edit.setMinimumWidth(0)
        self.title_edit.setMaximumHeight(24)

        self.title_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(self.title_edit, """
            QLineEdit {
                background: transparent;
                border: none;
                padding: 0px 2px;
                margin: 0px;
                font-size: 15px;
                font-weight: 900;
                color: black;
                selection-background-color: rgba(255, 255, 255, 150);
            }

            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 60);
                border-radius: 4px;
            }

            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 110);
                border: 1px solid rgba(0, 0, 0, 100);
                border-radius: 4px;
                padding: 0px 3px;
            }
        """)

        self.title_edit.textEdited.connect(
            self.on_title_edited
        )
        self.title_edit.editingFinished.connect(
            self.finish_title_edit
        )

        self.link_btn = QPushButton("Link", self)
        self.link_btn.setFixedSize(52, 22)
        self.link_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.link_btn.setToolTip(
            "Attach this note to one of your Improvements"
        )
        self.link_btn.clicked.connect(
            self.open_improvement_link_menu
        )
        self.link_btn.setVisible(
            not self.is_system_note
        )

        self.color_btn = QPushButton(
            NOTE_COLOR_SHORT_NAMES.get(
                self.note.color,
                "YL",
            )
        )
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.color_btn.clicked.connect(
            self.open_color_menu
        )

        self.pin_btn = QPushButton(
            "✦" if getattr(self.note, "pinned", False) else "✧"
        )
        self.pin_btn.setFixedSize(20, 20)
        self.pin_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.pin_btn.clicked.connect(
            self.toggle_pinned
        )
        self.refresh_pin_button()

        self.refresh_improvement_link_button()

        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(18, 18)
        self.delete_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.delete_btn.clicked.connect(
            lambda checked=False: self.delete_callback(self.note)
        )

        set_themed_stylesheet(self.delete_btn, """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #aa0000;
                background-color: rgba(255, 255, 255, 90);
                border-radius: 4px;
            }
        """)

        header.addWidget(
            self.arrow_btn,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        header.addWidget(
            self.title_edit,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )
        

        header.addWidget(self.pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        if self.is_system_note:
            header.addWidget(self.color_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            self.options_btn = QPushButton("⋯", self)
            self.options_btn.setFixedSize(22, 22)
            self.options_btn.setToolTip("Connect note to an improvement or item")
            self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.options_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 20px; padding: 0; } ")
            self.options_btn.clicked.connect(self.open_note_options)
            header.addWidget(self.options_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self.link_btn.hide()
            header.addWidget(self.color_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.outer_layout.addLayout(header)

        # ========================================================
        # Note text
        # ========================================================

        if (self.note.title.strip().lower() == "animal buddy"
                and self.is_system_note and self.character is not None):
            self.text_edit = AnimalBuddyPanel(
                self.note, self.character, self.update_callback, self)
        elif self.is_system_note:
            # System notes are display-only, so use QLabel.
            # This completely prevents internal scrolling.
            self.text_edit = QLabel()

            self.text_edit.setWordWrap(True)
            self.text_edit.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
            )

            self.text_edit.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            self.text_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )

            set_themed_stylesheet(self.text_edit, """
                QLabel {
                    background: transparent;
                    border: none;
                    font-size: 13px;
                    color: black;
                    padding: 4px;
                    margin: 0px;
                }
            """)

            if self.note.title.strip().lower() in {"spellcasting verbs", "mighty", "sneak attack"}:
                if self.note.title.strip().lower() == "spellcasting verbs":
                    note_html = format_spellcasting_system_note_html(self.note.text)
                else:
                    note_html = format_system_note_html(self.note.text)

                self.text_edit.setTextFormat(
                    Qt.TextFormat.RichText
                )
                self.text_edit.setText(
                    note_html
                )

            else:
                self.text_edit.setTextFormat(
                    Qt.TextFormat.PlainText
                )
                self.text_edit.setText(
                    self.note.text
                )

        else:
            self.text_edit = QTextEdit()

            self.text_edit.setAcceptRichText(False)
            if str(self.note.text).startswith("<!--DID_RICH_NOTE-->"):
                self.text_edit.setHtml(self.note.text)
            else:
                self.text_edit.setPlainText(self.note.text)
            for key, shortcut in [("bold", "Ctrl+B"), ("italic", "Ctrl+I"), ("underline", "Ctrl+U")]:
                binding = QShortcut(QKeySequence(shortcut), self.text_edit)
                binding.setContext(Qt.ShortcutContext.WidgetShortcut)
                binding.activated.connect(lambda k=key: self.toggle_note_format(k))

            self.text_edit.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

            self.text_edit.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

            self.text_edit.setLineWrapMode(
                QTextEdit.LineWrapMode.WidgetWidth
            )

            self.text_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            set_themed_stylesheet(self.text_edit, """
                QTextEdit {
                    background-color: rgba(255, 255, 255, 80);
                    border: 1px solid rgba(0, 0, 0, 45);
                    border-radius: 6px;
                    font-size: 13px;
                    color: black;
                    padding: 4px;
                    margin: 0px;
                }

                QTextEdit:focus {
                    background-color: rgba(255, 255, 255, 125);
                    border: 1px solid rgba(0, 0, 0, 100);
                }
            """)

            self.text_edit.textChanged.connect(
                self.on_text_changed
            )

        self.outer_layout.addWidget(
            self.text_edit
        )
        self.apply_style()
        self.refresh_expanded_state()
        QTimer.singleShot(
            0,
            self.resize_text_edit,
        )
        
    def apply_style(self):
        color_key = (
            self.note.color
            if self.note.color in NOTE_COLORS
            else "blue"
        )

        color = note_paper_color(self.note.color)
        
        self.color_btn.setText("")
        self.color_btn.setToolTip("Change note color")

        set_themed_stylesheet(self, f"""
            QFrame {{
                background-color: {color};
                border: 2px solid black;
                border-radius: 11px;
            }}
        """)

        set_themed_stylesheet(self.color_btn, f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid black;
                border-radius: 10px;
                padding: 0px;
                margin: 0px;
                font-size: 9px;
                font-weight: 900;
                color: black;
            }}

            QPushButton:hover {{
                background-color: white;
                border: 3px solid black;
            }}
        """)

    def notify_note_changed(self):
        self.pending_autosave = True
        self.update_callback()


    def widget_belongs_to_this_note(self, widget):
        current = widget

        while current is not None:
            if current is self:
                return True

            if not hasattr(current, "parentWidget"):
                return False

            current = current.parentWidget()

        return False

    def on_application_focus_changed(
        self,
        old_widget,
        new_widget,
    ):
        if not self.pending_autosave:
            return

        if not self.widget_belongs_to_this_note(old_widget):
            return

        if self.widget_belongs_to_this_note(new_widget):
            return

        QTimer.singleShot(
            0,
            self.autosave_after_leaving_note,
        )


    def autosave_after_leaving_note(self):
        if not self.pending_autosave:
            return

        focused_widget = QApplication.focusWidget()

        if self.widget_belongs_to_this_note(focused_widget):
            return

        if (
            not str(self.note.title or "").strip()
            and not str(self.note.text or "").strip()
        ):
            return

        window = self.window()

        if hasattr(window, "auto_save_character"):
            reordered = False

            if hasattr(
                window,
                "sort_notes_longest_first",
            ):
                reordered = (
                    window.sort_notes_longest_first()
                )

            window.auto_save_character()

            if not window.unsaved_changes:
                self.pending_autosave = False

                if (
                    reordered
                    and hasattr(
                        window,
                        "refresh_notes",
                    )
                ):
                    # Rebuild only after this NoteCard's focus callback
                    # has returned; rebuilding it immediately would delete
                    # the widget while one of its own methods is running.
                    QTimer.singleShot(
                        0,
                        window.refresh_notes,
                    )

    def refresh_pin_button(self):
        pinned = bool(
            getattr(
                self.note,
                "pinned",
                False,
            )
        )
        self.pin_btn.setText(
            "✦" if pinned else "✧"
        )
        self.pin_btn.setToolTip(
            "Unpin note"
            if pinned
            else "Pin note to the top"
        )
        set_themed_stylesheet(
            self.pin_btn,
            """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 900;
                color: #8f6417;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 90);
                border-radius: 4px;
            }
            """
        )

    def toggle_pinned(self):
        window = self.window()

        if hasattr(
            window,
            "block_if_readonly",
        ) and window.block_if_readonly():
            return

        self.note.pinned = not bool(
            getattr(
                self.note,
                "pinned",
                False,
            )
        )
        self.refresh_pin_button()
        self.update_callback()

        if hasattr(
            window,
            "mark_dirty",
        ):
            window.mark_dirty(
                auto_save=True
            )

        # Rebuild after the button callback returns. Pinned notes are sorted
        # before all unpinned notes; size still decides the order within each
        # group.
        if hasattr(
            window,
            "refresh_notes",
        ):
            QTimer.singleShot(
                0,
                window.refresh_notes,
            )

    def refresh_expanded_state(self):
        self.arrow_btn.setText(
            "▾" if self.note.expanded else "▸"
        )

        self.text_edit.setVisible(self.note.expanded)

        if self.note.expanded:
            self.outer_layout.setContentsMargins(8, 6, 8, 8)
            self.outer_layout.setSpacing(5)

            QTimer.singleShot(0, self.resize_text_edit)
        else:
            self.outer_layout.setContentsMargins(8, 4, 8, 4)
            self.outer_layout.setSpacing(0)

        self.updateGeometry()

    def toggle_expanded(self):
        self.note.expanded = not self.note.expanded
        self.refresh_expanded_state()

    def toggle_note_format(self, key):
        current = self.text_edit.currentCharFormat()
        fmt = QTextCharFormat()
        if key == "bold":
            fmt.setFontWeight(QFont.Weight.Normal if current.fontWeight() >= QFont.Weight.Bold else QFont.Weight.Bold)
        elif key == "italic":
            fmt.setFontItalic(not current.fontItalic())
        else:
            fmt.setFontUnderline(not current.fontUnderline())
        self.text_edit.mergeCurrentCharFormat(fmt)
        self.text_edit.setFocus()

    def serialized_player_note(self):
        # Store only supported emphasis, never fixed font sizes or colors.
        # That keeps the note readable when switching themes.
        lines = []
        has_format = False
        block = self.text_edit.document().begin()
        while block.isValid():
            parts = []
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    text = escape(fragment.text())
                    fmt = fragment.charFormat()
                    for enabled, tag in [(fmt.fontWeight() >= QFont.Weight.Bold, "b"),
                                         (fmt.fontItalic(), "i"), (fmt.fontUnderline(), "u")]:
                        if enabled:
                            text = f"<{tag}>{text}</{tag}>"
                            has_format = True
                    parts.append(text)
                it += 1
            lines.append("".join(parts))
            block = block.next()
        if not has_format:
            return self.text_edit.toPlainText()
        return '<!--DID_RICH_NOTE--><span style="white-space: pre-wrap;">' + "<br>".join(lines) + "</span>"

    def on_text_changed(self):
        QTimer.singleShot(
            0,
            self.resize_text_edit,
        )

        if self.is_system_note:
            return

        self.note.text = self.serialized_player_note()

        self.notify_note_changed()
        
    def on_title_edited(self, title):
        if self.is_system_note:
            return

        self.note.title = title
        self.notify_note_changed()

    def finish_title_edit(self):
        """
        Save the note title. An empty title is displayed
        using the "New Note" placeholder.
        """
        if self.is_system_note:
            return
        title = self.title_edit.text().strip()
        window = self.window()

        if title and hasattr(window, "capitalize_first"):
            title = window.capitalize_first(title)
        self.note.title = title

        if self.title_edit.text() != title:
            self.title_edit.setText(title)

        self.title_edit.setCursorPosition(0)
        self.title_edit.setToolTip(title)
        self.notify_note_changed()

    def linked_improvement(self):
        if self.character is None:
            return None

        linked_id = str(
            getattr(
                self.note,
                "linked_improvement_id",
                "",
            )
            or ""
        )

        if not linked_id:
            return None

        for improvement in (
            self.character
            .improvements
            .list_of_taken_improvements
        ):
            if str(improvement.id) == linked_id:
                return improvement

        return None


    def refresh_improvement_link_button(self):
        if not hasattr(self, "link_btn"):
            return

        linked_id = str(self.note.linked_improvement_id or "")
        if linked_id.startswith("item:") and self.character is not None:
            item = next((item for item in self.character.inventory.list_of_items
                         if str(item.id) == linked_id[5:]), None)
            if item is not None:
                self.link_btn.setText(self.link_btn.fontMetrics().elidedText(
                    item.name, Qt.TextElideMode.ElideRight, 40))
                self.link_btn.setToolTip(f"Linked to item: {item.name}")
                return

        improvement = self.linked_improvement()

        if improvement is None:
            self.link_btn.setText("Link")
            self.link_btn.setToolTip(
                "Attach this note to an Improvement or item"
            )
            return

        full_name = str(
            improvement.name
            or "Improvement"
        )

        shown_name = (
            self.link_btn
            .fontMetrics()
            .elidedText(
                full_name,
                Qt.TextElideMode.ElideRight,
                40,
            )
        )

        self.link_btn.setText(shown_name)
        self.link_btn.setToolTip(
            f"Linked to {full_name}"
        )


    def open_note_options(self):
        menu = QMenu(self)
        set_themed_stylesheet(menu, FANTASY_MENU_QSS)
        link = menu.addAction("connect to...")
        if self.note.linked_improvement_id:
            linked_name = self.link_btn.toolTip()
            for prefix in ("Linked to item: ", "Linked to "):
                if linked_name.startswith(prefix):
                    linked_name = linked_name[len(prefix):]
                    break
            link.setText(f"linked to {linked_name}")
        selected = menu.exec(self.options_btn.mapToGlobal(self.options_btn.rect().bottomLeft()))
        if selected is link:
            self.open_improvement_link_menu()

    def open_improvement_link_menu(self):
        if self.is_system_note:
            return

        menu = QMenu(self)
        set_themed_stylesheet(
            menu,
            FANTASY_MENU_QSS + "\nQMenu::item:disabled { color: #9b9388; background: transparent; }",
        )

        current_id = str(
            getattr(
                self.note,
                "linked_improvement_id",
                "",
            )
            or ""
        )

        unlink_action = menu.addAction(
            "No link"
        )
        unlink_action.setData("")

        if not current_id:
            unlink_action.setText(
                "✓  No link"
            )

        improvements = []

        if self.character is not None:
            improvements = list(
                self.character
                .improvements
                .list_of_taken_improvements
            )

        if improvements:
            menu.addSeparator()
            improvements.sort(
                key=lambda improvement:
                    str(
                        improvement.name
                        or ""
                    ).lower()
            )

            for improvement in improvements:
                improvement_id = str(
                    improvement.id
                )

                name = str(
                    improvement.name
                    or "Improvement"
                )

                if improvement_id == current_id:
                    name = "✓  " + name

                action = menu.addAction(name)
                action.setData(improvement_id)
                action.setEnabled(can_link_note(self.character, self.note, improvement_id))
        else:
            menu.addSeparator()
            empty_action = menu.addAction(
                "No owned Improvements"
            )
            empty_action.setEnabled(False)

        items = (self.character.inventory.list_of_items
                 if self.character is not None else [])
        if items:
            menu.addSeparator()
            heading = menu.addAction("Inventory items")
            heading.setEnabled(False)
            for item in sorted(items, key=lambda value: value.name.casefold()):
                item_id = "item:" + str(item.id)
                action = menu.addAction(
                    ("✓  " if item_id == current_id else "") + item.name)
                action.setData(item_id)
                action.setEnabled(can_link_note(self.character, self.note, item_id))

        selected = menu.exec(
            getattr(self, "options_btn", self.link_btn).mapToGlobal(
                getattr(self, "options_btn", self.link_btn).rect().bottomLeft()
            )
        )

        if selected is None:
            return

        selected_id = selected.data()

        if selected_id is None:
            return

        self.set_improvement_link(
            str(selected_id or "")
        )


    def set_improvement_link(
        self,
        improvement_id,
    ):
        improvement_id = str(
            improvement_id
            or ""
        )

        if not can_link_note(self.character, self.note, improvement_id):
            return

        if callable(self.link_callback):
            self.link_callback(
                self.note,
                improvement_id,
            )
            return

        self.note.linked_improvement_id = (
            improvement_id
        )
        self.refresh_improvement_link_button()
        self.notify_note_changed()


    def open_color_menu(self):
        menu = QMenu(self)
        note_menu(menu, self.note.color)
        color_key = selected_note_color(menu, self.color_btn, self.note.color)
        if color_key is None:
            return

        self.note.color = color_key
        
        self.apply_style()
        window = self.window()
        if hasattr(window, "style_redesign_note_card"):
            window.style_redesign_note_card(self)
        self.notify_note_changed()

    def resize_text_edit(self, *_):
        if not self.note.expanded:
            return

        # System notes are QLabel-based and never scroll internally.
        # Measure the rendered text directly instead of relying on
        # QLabel.heightForWidth(), which can substantially overestimate
        # rich-text height on some DPI/font combinations.
        if isinstance(self.text_edit, AnimalBuddyPanel):
            body_width = max(100, self.width() - 16)
            self.text_edit.setFixedWidth(body_width)
            inner_layout = self.text_edit.layout()
            height = self.text_edit.sizeHint().height()
            if inner_layout is not None:
                inner_layout.activate()
                height = max(height, inner_layout.sizeHint().height())
                if inner_layout.hasHeightForWidth():
                    height = max(height, inner_layout.heightForWidth(body_width))
            # QLabel wrapping changes by a pixel or two at Windows DPI
            # scales; reserve a line rather than clipping the last sentence.
            self.text_edit.setFixedHeight(height + 8)
            self.text_edit.updateGeometry()
            self.outer_layout.invalidate()
            self.updateGeometry()
            return
        if self.is_system_note:
            body_width = max(
                1,
                self.width() - 16,
            )

            self.text_edit.setFixedWidth(
                body_width
            )

            # QLabel measures the actual rich text with its final theme padding.
            self.text_edit.ensurePolished()
            required_height = self.text_edit.heightForWidth(body_width)
            if required_height < 0:
                required_height = self.text_edit.sizeHint().height()
            self.text_edit.setFixedHeight(max(20, required_height))

            # Propagate the changed text height through the note card and
            # grid without changing its saved expanded state.
            self.text_edit.updateGeometry()
            self.outer_layout.invalidate()
            self.updateGeometry()
            return

        document = self.text_edit.document()

        available_width = max(
            1,
            self.text_edit.viewport().width(),
        )

        document.setTextWidth(
            available_width
        )

        document_height = (
            document.documentLayout()
            .documentSize()
            .height()
        )

        self.text_edit.setFixedHeight(
            max(
                40,
                int(document_height) + 20,
            )
        )

        self.text_edit.updateGeometry()
        self.updateGeometry()


class NotesMixin:

    def note_length_for_order(self, note):
        """
        Order notes by how tall their text is at the width it will actually
        have on the redesigned Notes page, rather than at the old fixed
        300 px card width.
        """

        text = str(
            getattr(
                note,
                "text",
                "",
            )
            or ""
        ).strip()

        document = QTextDocument()

        font = QFont()
        font.setPixelSize(13)

        document.setDefaultFont(
            font
        )

        # System notes are rich text; measure the markup as it is rendered.
        if "<" in text and ">" in text:
            document.setHtml(text)
        else:
            document.setPlainText(text)

        # Match the approximate usable width of the card as it is actually
        # displayed.  The redesigned Notes page stretches cards across the
        # available columns, so using NoteCard.CARD_WIDTH (300 px) here can
        # rank a heavily-wrapped note ahead of a note that is visibly taller.
        columns = max(1, self.calculate_note_columns())

        available_width = 0
        notes_frame = getattr(self, "notes_frame", None)
        if notes_frame is not None:
            available_width = notes_frame.contentsRect().width()

        if available_width <= 100:
            available_width = max(
                NoteCard.CARD_WIDTH,
                self.width() - 24,
            )

        horizontal_spacing = 8
        card_width = (
            available_width
            - horizontal_spacing * (columns - 1)
        ) / columns

        document.setTextWidth(
            max(
                80,
                card_width - 52,
            )
        )

        displayed_height = (
            document
            .documentLayout()
            .documentSize()
            .height()
        )

        title_length = len(
            str(
                getattr(
                    note,
                    "title",
                    "",
                )
                or ""
            ).strip()
        )

        return (
            displayed_height,
            len(document.toPlainText()),
            title_length,
        )
    
    def sort_notes_longest_first(self):
        """
        Reorder the model without marking the character dirty.

        Ordering is presentation-derived from note content, so it is updated
        when a note is saved rather than on every keystroke.
        """
        self.ensure_character_notes()

        notes = (
            self.character
            .notes
            .list_of_notes
        )

        old_order = [
            note.id
            for note in notes
        ]

        # Python's sort is stable. Give every pinned note the same key so
        # pinned notes keep their existing relative order, while unpinned
        # notes continue to use the normal longest-first presentation order.
        def presentation_key(note):
            if bool(getattr(note, "pinned", False)):
                return (0, 0.0, 0, 0)
            height, text_length, title_length = self.note_length_for_order(note)
            return (1, -height, -text_length, -title_length)

        notes.sort(key=presentation_key)

        new_order = [
            note.id
            for note in notes
        ]

        return old_order != new_order

    def synchronize_animal_buddy_note(self):
        """Keep only the owned buddy's data in its API-authored system note.

        Never rewrite player-created notes. Only a system note linked to the
        owned Animal Buddy is managed here.
        """
        self.character.notes.validate()
        improvements = self.character.improvements.list_of_taken_improvements
        buddy = next((imp for imp in improvements
                      if imp.catalog_id == "animal_buddy"), None)
        managed = [note for note in self.character.notes.list_of_notes
                   if note.title.strip().lower() == "animal buddy"
                   and str(note.linked_improvement_id or "")]
        if buddy is None:
            self.character.notes.list_of_notes = [note for note in
                self.character.notes.list_of_notes
                if note.title.strip().lower() != "animal buddy"]
            return

        choices = buddy.choices or {}
        data = buddy_state(buddy, self.character.BDV)
        stats_text = "\n".join(
            f"{stat}: d{data['dice'][stat]}" +
            (f"+{data['training'][stat]}" if data['training'][stat] else "")
            for stat in BUDDY_STATS)
        perk_lines = []
        for _perk, destination, _key in data["perks"]:
            title = animal_buddy_perk_name(destination)
            description = animal_buddy_perk_description(destination)
            perk_lines.append(f"{title}: {description}" if description else title)
        text = IMPROVEMENT_REFERENCE_NOTES["animal_buddy"].format(
            buddy_name=str(choices.get("buddy_name") or "Unnamed Buddy"),
            buddy_hearts=data["hearts"], buddy_hp=data["max_hp"],
            buddy_current_hp=data["current_hp"],
            buddy_bdv=data["bdv"], buddy_die=4,
            buddy_stats=stats_text,
            buddy_perks="\n".join(perk_lines) if perk_lines else "None selected",
        )
        note = next((item for item in managed
                     if item.linked_improvement_id == str(buddy.id)), None)
        if note is None:
            note = CharacterNote(
                id=str(uuid4()), title="Animal Buddy", text=text,
                color="green", expanded=True,
                linked_improvement_id=str(buddy.id),
            )
            self.character.notes.list_of_notes.append(note)
        elif note.text != text:
            note.text = text
        # Avoid duplicate old managed notes, without touching personal notes.
        self.character.notes.list_of_notes = [item for item in
            self.character.notes.list_of_notes
            if item is note or item not in managed]

    @preserve_sheet_scroll
    def refresh_notes(self):
        self.synchronize_spellcasting_note()
        self.synchronize_animal_buddy_note()
        self.synchronize_mighty_note()
        self.synchronize_sneak_attack_note()
        self.ensure_character_notes()

        # Existing characters may carry a saved copy of the old heading.
        sneak_note = self.find_note_by_title("Sneak Attack")
        if sneak_note is not None and "Base effects:" in sneak_note.text:
            sneak_note.text = sneak_note.text.replace("Base effects:", "Effects:")
            self.mark_dirty(auto_save=True)

        # refresh_notes() is not called for every keystroke. Sorting here
        # therefore gives loaded/saved notes a consistent longest-to-shortest
        # layout without making cards jump around while the player is typing.
        self.sort_notes_longest_first()

        notes = self.character.notes.list_of_notes

        if not self.notes_board_visible:
            self.notes_frame.hide()
            self.notes_reopen_row.show()
            return

        self.notes_reopen_row.hide()
        self.notes_frame.show()

        self.clear_layout(self.notes_grid_layout)

        self.no_notes_label.setVisible(not notes)

        columns = self.calculate_note_columns()
        column_layouts = []
        for col in range(columns):
            stack = QVBoxLayout()
            stack.setContentsMargins(0, 0, 0, 0)
            stack.setSpacing(10)
            stack.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.notes_grid_layout.addLayout(stack, 0, col, Qt.AlignmentFlag.AlignTop)
            column_layouts.append(stack)
        
        for index, note in enumerate(notes):
            col = index % columns

            card = NoteCard(
                note,
                self.on_note_changed,
                self.confirm_delete_note,
                self,
                character=self.character,
                link_callback=self.link_note_to_improvement,
            )

            column_layouts[col].addWidget(card, 0, Qt.AlignmentFlag.AlignTop)

        for column in range(columns):
            self.notes_grid_layout.setColumnStretch(column, 1)

        QTimer.singleShot(
            0,
            self.keep_sheet_horizontally_locked,
        )


    def build_notes_board(self, outer_layout):
        # ========================================================
        # Small reopen button shown ONLY while Notes are closed
        # ========================================================

        self.notes_reopen_row = QWidget()
        self.notes_reopen_row.setFixedHeight(30)

        reopen_layout = QHBoxLayout(
            self.notes_reopen_row
        )
        reopen_layout.setContentsMargins(
            0, 0, 6, 0
        )
        reopen_layout.setSpacing(0)

        reopen_layout.addStretch()

        self.notes_reopen_btn = QPushButton("▸")
        self.notes_reopen_btn.setFixedSize(
            30,
            26,
        )
        self.notes_reopen_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        set_themed_stylesheet(
            self.notes_reopen_btn,
            f"""
            QPushButton {{
                background-color: {BLUE};
                border: 2px solid black;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}
            """
        )

        self.notes_reopen_btn.clicked.connect(
            self.open_notes_board
        )

        reopen_layout.addWidget(
            self.notes_reopen_btn
        )

        outer_layout.addWidget(
            self.notes_reopen_row
        )

        self.notes_reopen_row.hide()

        # ========================================================
        # Actual Notes board
        # ========================================================

        self.notes_frame = QFrame()

        set_themed_stylesheet(
            self.notes_frame,
            """
            QFrame {
                background-color: white;
                border: none;
            }
            """
        )

        notes_layout = QVBoxLayout(
            self.notes_frame
        )
        notes_layout.setContentsMargins(
            6, 6, 6, 6
        )
        notes_layout.setSpacing(5)

        # ========================================================
        # Header
        # ========================================================

        header = QHBoxLayout()
        header.setContentsMargins(
            0, 0, 0, 0
        )
        header.setSpacing(5)

        title = QLabel("Notes")

        set_themed_stylesheet(
            title,
            """
            QLabel {
                border: none;
                background: transparent;
                font-size: 22px;
                font-weight: 900;
                color: black;
            }
            """
        )

        # Whole Notes board collapse button.
        self.close_notes_btn = QPushButton("▾")
        self.close_notes_btn.setFixedSize(
            30,
            26,
        )
        self.close_notes_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        set_themed_stylesheet(
            self.close_notes_btn,
            """
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 18px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #2f5f91;
            }
            """
        )

        self.close_notes_btn.clicked.connect(
            self.close_notes_board
        )

        header.addWidget(title)
        header.addStretch()
        header.addWidget(
            self.close_notes_btn
        )

        notes_layout.addLayout(header)

        # ========================================================
        # Notes grid
        # ========================================================

        self.notes_grid_layout = QGridLayout()
        self.notes_grid_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.notes_grid_layout.setHorizontalSpacing(8)
        self.notes_grid_layout.setVerticalSpacing(8)

        notes_layout.addLayout(
            self.notes_grid_layout
        )

        self.no_notes_label = QLabel(
            "No notes yet. Click + to add one."
        )

        set_themed_stylesheet(
            self.no_notes_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 800;
                color: #333333;
            }
            """
        )

        notes_layout.addWidget(
            self.no_notes_label
        )

        # ========================================================
        # Add Note button
        # ========================================================

        self.add_note_btn = QPushButton("+")
        self.add_note_btn.setFixedSize(
            30,
            26,
        )
        self.add_note_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        set_themed_stylesheet(
            self.add_note_btn,
            f"""
            QPushButton {{
                background-color: {BLUE};
                border: 2px solid black;
                border-radius: 8px;
                font-size: 18px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}
            """
        )

        self.add_note_btn.clicked.connect(
            self.add_note_from_ui
        )

        add_button_row = QHBoxLayout()
        add_button_row.setContentsMargins(
            0, 0, 0, 0
        )
        add_button_row.setSpacing(0)

        add_button_row.addStretch()
        add_button_row.addWidget(
            self.add_note_btn
        )

        notes_layout.addLayout(
            add_button_row
        )

        outer_layout.addWidget(
            self.notes_frame
        )

        self.notes_frame.hide()
    
    def calculate_note_columns(self):
        return 4

    def close_notes_board(self):
        self.notes_board_visible = False

        self.notes_frame.hide()
        self.notes_reopen_row.show()

        self.content_widget.updateGeometry()

        QTimer.singleShot(
            0,
            self.keep_sheet_horizontally_locked,
        )
    
    def toggle_notes_board(self):
        if self.notes_board_visible:
            self.close_notes_board()
        else:
            self.open_notes_board()
            
    def open_notes_board(self):
        if self.block_if_readonly():
            return
        
        self.ensure_character_notes()

        self.notes_board_visible = True

        self.notes_reopen_row.hide()
        self.notes_frame.show()

        if self.character.notes.list_of_notes:
            self.refresh_notes()
            return

        note = CharacterNote(
            id=str(uuid4()),
            title="",
            text="",
            color=random_note_hex_color(),
            expanded=True,
        )

        self.character.notes.list_of_notes.append(
            note
        )

        self.refresh_notes()
        
    @preserve_sheet_scroll
    def refresh_note_links(self):
        self.refresh_notes()
        self.refresh_inventory()
        self.refresh_improvements()

    def add_note_from_ui(self):
        if self.block_if_readonly():
            return

        self.ensure_character_notes()
        self.notes_board_visible = True
        self.notes_frame.show()

        new_color = random_note_hex_color(
            note.color for note in self.character.notes.list_of_notes
        )

        self.character.notes.list_of_notes.append(
            CharacterNote(
                id=str(uuid4()),
                title="",
                text="",
                color=new_color,
                expanded=True,
            )
        )

        self.mark_dirty()
        self.refresh_notes()

    def link_note_to_improvement(
        self,
        note,
        improvement_id,
    ):
        if self.is_readonly_character():
            return

        improvement_id = str(
            improvement_id
            or ""
        )

        valid_ids = {
            str(improvement.id)
            for improvement in (
                self.character
                .improvements
                .list_of_taken_improvements
            )
        }
        valid_ids.update("item:" + str(item.id)
                         for item in self.character.inventory.list_of_items)

        if (
            improvement_id
            and improvement_id not in valid_ids
        ):
            improvement_id = ""

        if not can_link_note(self.character, note, improvement_id):
            return

        note.linked_improvement_id = (
            improvement_id
        )

        self.character.notes.validate()
        self.mark_dirty()

        # Rebuild only after the NoteCard callback returns.
        QTimer.singleShot(
            0,
            self.refresh_note_links,
        )


    def on_note_changed(self):
        if self.is_readonly_character():
            return

        self.character.notes.validate()
        self.mark_dirty()

    def confirm_delete_note(self, note):
        managed_titles = {"spellcasting verbs", "sneak attack", "mighty"}
        title_key = str(note.title or "").strip().lower()
        if title_key in managed_titles or (title_key == "animal buddy" and note.linked_improvement_id):
            return
        if self.block_if_readonly():
            return

        self.ensure_character_notes()

        if not any(item.id == note.id for item in self.character.notes.list_of_notes):
            return

        title = str(note.title or "").strip()
        text = str(note.text or "").strip()

        # Empty note -> delete immediately.
        if not title and not text:
            self.character.notes.list_of_notes = [
                item for item in self.character.notes.list_of_notes if item.id != note.id
            ]

            self.mark_dirty(auto_save=True)
            self.refresh_note_links()
            return

        # Non-empty note -> ask.
        display_name = title if title else "Untitled Note"

        if not ask_yes_no(
            self,
            "Delete Note",
            f"Delete note '{display_name}'?",
        ):
            return

        self.character.notes.list_of_notes = [
            item for item in self.character.notes.list_of_notes if item.id != note.id
        ]

        self.mark_dirty(auto_save=True)
        self.refresh_note_links()
    
    def ensure_character_notes(self):
        self.character.notes.validate()

        valid_improvement_ids = {
            str(improvement.id)
            for improvement in (
                self.character
                .improvements
                .list_of_taken_improvements
            )
        }

        valid_improvement_ids.update(
            "item:" + str(item.id)
            for item in self.character.inventory.list_of_items
        )

        for note in (
            self.character
            .notes
            .list_of_notes
        ):
            linked_id = str(
                getattr(
                    note,
                    "linked_improvement_id",
                    "",
                )
                or ""
            )

            if (
                linked_id
                and linked_id not in valid_improvement_ids
                and note.title.strip().lower() not in {
                    "animal buddy", "mighty", "spellcasting verbs", "sneak attack"
                }
            ):
                note.linked_improvement_id = ""
        
    def cleanup_empty_notes(self):
        # Remove truly blank player notes on explicit save. Preserve linked
        # or managed notes; the displayed "New Note" is only a placeholder.
        self.ensure_character_notes()
        notes = self.character.notes.list_of_notes
        kept = [
            note for note in notes
            if (str(getattr(note, "title", "") or "").strip()
                or str(getattr(note, "text", "") or "").strip()
                or str(getattr(note, "linked_improvement_id", "") or "").strip())
        ]
        if len(kept) == len(notes):
            return False
        self.character.notes.list_of_notes = kept
        self.refresh_note_links()
        return True

    def synchronize_spellcasting_note(self):
        self.ensure_character_notes()
        spell = next((item for item in self.character.improvements.list_of_taken_improvements
                      if item.catalog_id in {"spellcasting", "magic_novice"}), None)
        if spell is None:
            self.character.notes.list_of_notes = [note for note in
                self.character.notes.list_of_notes
                if note.title.strip().lower() != "spellcasting verbs"]
            return
        self.offer_spellcasting_verbs_note(spell)

    def synchronize_mighty_note(self):
        """Create and update the owned Mighty's reference note."""
        self.ensure_character_notes()
        improvements = self.character.improvements.list_of_taken_improvements
        mighty = next((item for item in improvements
                       if item.catalog_id == "mighty"), None)
        notes = self.character.notes.list_of_notes
        existing = next((note for note in notes
                         if note.title.strip().lower() == "mighty"), None)
        if mighty is None:
            self.character.notes.list_of_notes = [note for note in notes
                if note.title.strip().lower() != "mighty"]
            return

        dice = getattr(getattr(self.character, "bonus_dice", None), "dice", {}) or {}
        die_size = dice.get("mighty_die", 4)
        note_text = IMPROVEMENT_REFERENCE_NOTES["mighty"].format(
            mighty_die=die_size)
        if existing is None:
            notes.append(CharacterNote(
                id=str(uuid4()), title="Mighty", text=note_text,
                color="orange", expanded=True,
                linked_improvement_id=str(mighty.id),
            ))
        elif existing.text != note_text:
            existing.text = note_text
            existing.linked_improvement_id = str(mighty.id)

    def synchronize_sneak_attack_note(self):
        sneak = next((item for item in self.character.improvements.list_of_taken_improvements
                      if item.catalog_id == "sneak_attack"), None)
        if sneak is None:
            self.character.notes.list_of_notes = [note for note in
                self.character.notes.list_of_notes
                if note.title.strip().lower() != "sneak attack"]
            return
        existing = self.find_note_by_title("Sneak Attack")
        if existing is None:
            self.offer_sneak_attack_note(sneak)
        else:
            existing.text = self.build_sneak_attack_note_text(sneak)
            existing.linked_improvement_id = str(sneak.id)

    def spellcasting_note_html(self, improvement):
        return spellcasting_note_html(improvement)

    def offer_spellcasting_verbs_note(self, improvement):
        self.ensure_character_notes()
        existing = self.find_note_by_title("Spellcasting Verbs")
        if existing is None:
            existing = CharacterNote(
                id=str(uuid4()), title="Spellcasting Verbs",
                text=spellcasting_note_html(improvement), color="blue", expanded=True,
                linked_improvement_id=str(improvement.id),
            )
            self.character.notes.list_of_notes.append(existing)
        else:
            existing.text = spellcasting_note_html(improvement)
            existing.linked_improvement_id = str(improvement.id)
        improvement.choices["_verbs_note_created"] = True

    def find_note_by_title(self, title):
        """
        Return the first note whose title matches, ignoring capitalization.
        """
        self.ensure_character_notes()

        target = title.strip().lower()

        for note in self.character.notes.list_of_notes:
            if note.title.strip().lower() == target:
                return note

        return None

    def build_sneak_attack_note_text(self, improvement):
        import re
        import html

        def clean_description(text):
            text = str(text or "")

            # Convert HTML line breaks to normal line breaks.
            text = re.sub(
                r"<br\s*/?>",
                "\n",
                text,
                flags=re.IGNORECASE,
            )

            # Remove any other HTML tags.
            text = re.sub(
                r"<[^>]+>",
                "",
                text,
            )

            text = html.unescape(text).strip()

            # Remove the catalog wrapper because the note
            # already IS the Sneak Attack effect list.
            text = re.sub(
                r"^Add this option to your Sneak Attack effect list:\s*",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            text = re.sub(
                r"^Add a Sneak Attack option:\s*", "", text,
                flags=re.IGNORECASE,
            ).strip()

            return text

        effects = [
            ("Disadvantage", "They have some sort of disadvantage on their next turn."),
            ("Advantage", "You create some sort of advantage you or an ally can act on."),
            ("Hide", "You slip into a hiding place immediately after the attack, with GM approval."),
            ("Extra damage", "You deal extra HP of damage to the target."),
        ]

        # Add purchased Sneak Attack effect empowerments.
        for empowerment in improvement.empowerments:
            if empowerment.group_id != "extra_effects":
                continue

            description = clean_description(
                empowerment.description
            )

            if description:
                name = re.sub(r"^Sneak Attack\s*(?:->|⇒|:)\s*", "",
                              str(empowerment.name), flags=re.IGNORECASE)
                effects.append((name, description))

        lines = [
            "<b>Effects:</b>",
        ]

        for name, effect in effects:
            lines.append(
                f"- <b>{html.escape(name)}:</b> {html.escape(effect)}"
            )

        return "\n".join(lines)
    
    def offer_sneak_attack_note(self, improvement):
        self.ensure_character_notes()
        note_text = self.build_sneak_attack_note_text(improvement)
        existing = self.find_note_by_title("Sneak Attack")
        if existing is None:
            existing = CharacterNote(
                id=str(uuid4()), title="Sneak Attack", text=note_text,
                color="red", expanded=True,
            )
            self.character.notes.list_of_notes.append(existing)
        else:
            existing.text = note_text
            existing.expanded = True
        improvement.choices["_sneak_attack_note_created"] = True
