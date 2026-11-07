from ui_feedback import run_loading_task, BusyNotice, LoadingRing, preserve_sheet_scroll
import sys
import os
import traceback
import json
import hashlib
import tempfile
import subprocess
import shutil
import copy
import base64
import random
from math import pi, sin, cos

from collections import Counter, deque
from datetime import datetime

if sys.platform == "win32":
    try:
        import ctypes

        user32 = ctypes.windll.user32

        user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4)
        )

    except Exception:
        pass

    
from PySide6.QtCore import (
    Qt, QTimer, QSettings, QObject, QEvent,
    QPoint, QPointF, QRect, QRectF, QSize, QUrl, Slot, Signal,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QFrame, QPushButton,
    QSizePolicy, QDialog, QListWidget, QTextEdit, QTextBrowser,
    QScrollArea, QMessageBox, QComboBox, QLineEdit, QSpinBox,
    QFileDialog, QMenu, QGridLayout, QLayout, QToolTip, QCheckBox,
    QProgressBar, QWidgetAction, QListWidgetItem, QListView,
)
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply,
)
from PySide6.QtGui import (
    QKeySequence, QShortcut,
    QPainter, QPainterPath, QPen, QBrush,
    QColor, QPolygonF, QTextDocument, QIcon, QFontMetrics, QPixmap, QImage, QCursor,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEngineSettings
except ImportError:
    QWebEngineView = None
    QWebChannel = None
    QWebEngineSettings = None

try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None
from backend_2_1 import (
    Character,
    ImprovementSystem,
    CharacterStorageSystem,
    InventorySystem,
    ImageSystem,
    STAT_NAMES,
    STAT_POINT_COSTS,
)

from guided_tutorial import build_did_tutorial

from character_template import (
    create_template_from_ui,
    load_template_from_file,
    apply_template_to_character,
    confirm_create_character_from_template,
)

from ui_theme import (
    FANTASY_MENU_QSS,
    BLUE,
    CURRENT_THEME,
    THEME,
    theme_color,
    set_runtime_theme,
    translate_qss_for_theme,
    set_themed_stylesheet,
    apply_theme_to_existing_widgets,
    build_application_palette,
    make_positive_button,
    make_negative_button,
    fantasy_text_input,
    ThemeMixin
)

from ui_widgets import (
    SmallTopBox,
    NumericEntry,
    EmbeddedArrowRow,
    BigPlusButton,
    IPLabel,
    AutoWrapLabel,
)

from inventory_ui import (
    InventoryRow,
    AutoGrowTextDialog,
    InventoryEditDialog,
    InventoryItemDialog,
    InventoryMixin
)

from notes_ui import (
    NoteCard,
    AnimalBuddyNoteCard,
    NotesMixin,
    NOTE_COLORS,
    note_colors_for_theme,
    format_system_note_html,
    NOTE_COLOR_ORDER,
    NOTE_COLOR_SHORT_NAMES,
    SPELLCASTING_VERBS_NOTE_TEXT,
)

from improvements_ui import (
    ImprovementRow,
    EmpowermentRow,
    SkilledAtGroupRow,
    HeightenedAbilityRow,
    MERGED_EMPOWERMENTS,
    ImprovementsMixin,
)

from dialogs import (
    ImprovementListWidget,
    CustomImprovementDialog,
    ImprovementPickerDialog,
    BuddyStatCard,
    ChoiceInputDialog,
    AbilityEditorDialog,
    GlossaryTextEdit,
    ask_yes_no,
)

from character_display_ui import (
    StatCol,
    HeartWidget,
    HeartsPanel,
    ATWidget,
    ImageMixin,
    CharacterDisplayMixin,
    fit_image_to_frame,
    REGULAR_SHEET_HEIGHT,
    CENTER_TOP_HEIGHT,
    PICTURE_BOX_HEIGHT,
)
from character_API import IMPROVEMENT_CATALOG, ABILITY_ARRAYS
from improvement_editor import open_improvement_editor
from uuid import uuid4
from campaign_shared import build_shared_character_state, build_shared_roll_event
from campaign_runtime import (
    initialize_campaign_runtime,
    schedule_campaign_state_sync,
    restore_campaign_connection,
)
from campaign_ui import open_campaign_manager
from campaign_role_ui import open_campaigns
from campaign_dashboard_bridge import install_presence_heartbeat
from dice_asset_server import start_dice_asset_server
from species_ui_policy import is_species_required, species_tool_visible, species_field_visible

# Module aliases are used only for runtime UI overrides.
# No external source file is edited.
import ui_theme as ui_theme_module
import dialogs as dialogs_module
import improvements_ui as improvements_ui_module
import inventory_ui as inventory_ui_module
import notes_ui as notes_ui_module
import character_display_ui as character_display_ui_module

PANEL_BG = "white"


FANTASY_FONT_FAMILY = "Cinzel"


APP_VERSION = "1.0.14"
GITHUB_REPOSITORY = "almogbell/DID-Character-Sheet"
GITHUB_LATEST_RELEASE_API = (
    f"https://api.github.com/repos/"
    f"{GITHUB_REPOSITORY}/releases/latest"
)


def did_version_key(version_text):
    """
    Convert versions such as v1.0.12 into a tuple that compares correctly.
    The project's public release tags are expected to use numeric versions.
    """
    cleaned = str(version_text or "").strip().lstrip("vV")
    pieces = cleaned.split(".")
    numbers = []

    for piece in pieces:
        digits = ""

        for character in piece:
            if character.isdigit():
                digits += character
            else:
                break

        numbers.append(
            int(digits)
            if digits
            else 0
        )

    while len(numbers) < 3:
        numbers.append(0)

    return tuple(numbers[:4])




# ============================================================
# LIGHT-FANTASY THEME EXTENSION
# ============================================================
# ui_theme.py already translates the original frontend colors.
# The redesign introduced parchment/gold colors which were not part
# of that old palette. Add those translations at runtime so the
# redesign can switch cleanly between Light and Dark without editing
# ui_theme.py.

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
    "fantasy_border_faint": "#e2cfaa",
    "fantasy_hover": "#fff4df",
    "fantasy_pressed": "#f5ead2",
    "fantasy_selected": "#fff6df",
    "fantasy_selected_2": "#fff1d6",
    "fantasy_disabled": "#eee9df",
    "fantasy_disabled_2": "#f5f1e9",
    "fantasy_disabled_border": "#d8ccb5",
    "fantasy_disabled_text": "#9b9388",
})

THEME["dark"].update({
    # Deep navy/charcoal, with warm parchment-gold accents.
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
    "fantasy_border_faint": "#433c31",
    "fantasy_hover": "#243440",
    "fantasy_pressed": "#1e2c36",
    "fantasy_selected": "#2b3540",
    "fantasy_selected_2": "#2a3137",
    "fantasy_disabled": "#25313a",
    "fantasy_disabled_2": "#222d35",
    "fantasy_disabled_border": "#49483f",
    "fantasy_disabled_text": "#7e8b96",
})

ui_theme_module.LIGHT_HEX_TO_THEME_KEY.update({
    "#f7f1e5": "fantasy_page",
    "#fffdf7": "fantasy_surface",
    "#fffaf0": "fantasy_surface_alt",
    "#25190f": "fantasy_text",
    "#3b332a": "fantasy_text_2",
    "#4f3b18": "fantasy_text_gold",
    "#6c5428": "fantasy_text_gold",
    "#765d34": "fantasy_text_muted",
    "#8b6724": "fantasy_gold",
    "#a87824": "fantasy_gold",
    "#c6a15d": "fantasy_gold_mid",
    "#c79a3b": "fantasy_gold_mid",
    "#cdaa63": "fantasy_border",
    "#d9bd82": "fantasy_border_soft",
    "#e2cfaa": "fantasy_border_faint",
    "#fff4df": "fantasy_hover",
    "#f5ead2": "fantasy_pressed",
    "#fff6df": "fantasy_selected",
    "#fff1d6": "fantasy_selected_2",
    "#eee9df": "fantasy_disabled",
    "#f5f1e9": "fantasy_disabled_2",
    "#d8ccb5": "fantasy_disabled_border",
    "#9b9388": "fantasy_disabled_text",

    # Additional pale blues used by the redesign button system.
    "#d8edf7": "blue",
    "#e8f5fb": "blue_hover",
    "#c9e3ef": "blue_mid",
})


FANTASY_DIRECT_DARK_COLORS = {
    "#fffdf7": "#18232e",
    "#fffaf0": "#1d2a35",
    "#25190f": "#f2eee7",
    "#3b332a": "#d8d1c5",
    "#6c5428": "#d6b66f",
    "#765d34": "#b7a98c",
}


def fantasy_runtime_color(light_color):
    """Theme-aware color for custom QPainter widgets."""
    if ui_theme_module.CURRENT_THEME != "dark":
        return light_color

    return FANTASY_DIRECT_DARK_COLORS.get(
        str(light_color).lower(),
        light_color,
    )



def _is_near_white_portrait_pixel(color):
    """
    Treat white and light neutral gray pixels as removable portrait
    background, while avoiding colored/light character details.
    """
    red = color.red()
    green = color.green()
    blue = color.blue()

    brightest = max(
        red,
        green,
        blue,
    )

    darkest = min(
        red,
        green,
        blue,
    )

    return (
        red >= 215
        and green >= 215
        and blue >= 215
        and (
            brightest
            - darkest
        )
        <= 20
    )


def _remove_edge_connected_white_background(
    pixmap,
):
    """
    Make only the near-white background connected to the OUTSIDE EDGE
    transparent.

    This deliberately does not erase every white pixel. White/very-light
    details surrounded by the character remain untouched.
    """
    if (
        pixmap is None
        or pixmap.isNull()
    ):
        return pixmap

    image = (
        pixmap
        .toImage()
        .convertToFormat(
            QImage.Format.Format_ARGB32
        )
    )

    width = image.width()
    height = image.height()

    if (
        width <= 1
        or height <= 1
    ):
        return pixmap

    # Only treat the image as a white-canvas portrait when most of its
    # outside edge is actually near-white. This avoids deleting bright
    # photographic backgrounds merely because one edge contains sky/wall.
    edge_points = []

    for x in range(width):
        edge_points.append(
            (x, 0)
        )

        if height > 1:
            edge_points.append(
                (x, height - 1)
            )

    for y in range(
        1,
        max(
            1,
            height - 1,
        ),
    ):
        edge_points.append(
            (0, y)
        )

        if width > 1:
            edge_points.append(
                (width - 1, y)
            )

    white_edge_count = sum(
        1
        for x, y in edge_points
        if _is_near_white_portrait_pixel(
            image.pixelColor(
                x,
                y,
            )
        )
    )

    if not edge_points:
        return pixmap

    white_edge_ratio = (
        white_edge_count
        / len(
            edge_points
        )
    )

    if white_edge_ratio < 0.40:
        return pixmap

    visited = bytearray(
        width
        * height
    )

    queue = deque()

    def try_queue(
        x,
        y,
    ):
        index = (
            y
            * width
            + x
        )

        if visited[index]:
            return

        visited[index] = 1

        color = image.pixelColor(
            x,
            y,
        )

        if not _is_near_white_portrait_pixel(
            color
        ):
            return

        queue.append(
            (
                x,
                y,
            )
        )

    for x, y in edge_points:
        try_queue(
            x,
            y,
        )

    while queue:
        x, y = queue.popleft()

        color = image.pixelColor(
            x,
            y,
        )

        color.setAlpha(
            0
        )

        image.setPixelColor(
            x,
            y,
            color,
        )

        if x > 0:
            try_queue(
                x - 1,
                y,
            )

        if x + 1 < width:
            try_queue(
                x + 1,
                y,
            )

        if y > 0:
            try_queue(
                x,
                y - 1,
            )

        if y + 1 < height:
            try_queue(
                x,
                y + 1,
            )

    return QPixmap.fromImage(
        image
    )


def portrait_pixmap_for_current_theme(
    pixmap,
):
    """Preserve source pixels, including white details and existing alpha."""
    return pixmap


def qt_lifecycle_safe(method):
    """
    Protect short delayed UI callbacks from normal Qt destruction timing.

    QTimer.singleShot() callbacks may run just after their window or one of
    its child widgets has been deleted. PySide then raises errors such as:

        Internal C++ object (...) already deleted

    A callback targeting a widget which no longer exists has nothing left
    to do, so that specific lifecycle error is safely ignored. Other
    RuntimeErrors still propagate normally.
    """

    def wrapped(*args, **kwargs):
        try:
            return method(
                *args,
                **kwargs,
            )

        except (
            RuntimeError,
            ReferenceError,
        ) as error:
            message = str(
                error
            ).lower()

            deleted_object_error = (
                "already deleted" in message
                or "internal c++ object" in message
                or "wrapped c/c++ object" in message
                or "c++ object" in message
                and "deleted" in message
            )

            if deleted_object_error:
                return None

            raise

    wrapped.__name__ = getattr(
        method,
        "__name__",
        "qt_lifecycle_safe_callback",
    )

    wrapped.__doc__ = getattr(
        method,
        "__doc__",
        None,
    )

    return wrapped



def global_exception_handler(exc_type, exc_value, exc_traceback):
    with open("crash_log.txt", "a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        traceback.print_exception(
            exc_type,
            exc_value,
            exc_traceback,
            file=f,
        )
        f.write("\n")

    traceback.print_exception(
        exc_type,
        exc_value,
        exc_traceback,
    )

sys.excepthook = global_exception_handler

def create_character() -> Character:
    return Character.create_new_character()


# ============================================================
# 3D DICE BRIDGE (JavaScript <-> Python)
# ============================================================

OTHER_DICE_SIZES = (4, 6, 8, 10, 12, 20, 100)


def build_other_dice_plan(counts):
    """Build a DiceBox plan without an ability or exploding dice."""
    if not isinstance(counts, dict):
        raise ValueError("Dice quantities must be a dictionary")
    if any(size not in OTHER_DICE_SIZES for size in counts):
        raise ValueError("Unsupported die size")
    clean_counts = {}
    for size in OTHER_DICE_SIZES:
        amount = counts.get(size, 0)
        maximum = 2 if size == 100 else 20
        if isinstance(amount, bool) or not isinstance(amount, int) or not 0 <= amount <= maximum:
            raise ValueError(f"d{size} quantity must be between 0 and {maximum}")
        clean_counts[size] = amount
    total_count = sum(clean_counts.values())
    if not 1 <= total_count <= 30:
        raise ValueError("Choose between 1 and 30 dice in total")
    dice = [
        {
            "label": f"d{size}", "kind": "other_die", "sides": size,
            "sign": 1, "explode": False,
        }
        for size in OTHER_DICE_SIZES for _ in range(clean_counts[size])
    ]
    first, *extras = dice
    return {
        "roll_type": "other_dice", "ability_name": "Other Dice",
        "ability": first, "extras": extras, "flat_bonus": 0,
    }


def format_session_roll_entry(summary):
    """Format one completed DiceBox summary for character roll history."""
    if not isinstance(summary, dict):
        raise ValueError("Dice roll summary must be an object")

    terms = summary.get("terms")
    if not isinstance(terms, list) or not terms or not isinstance(terms[0], dict):
        raise ValueError("Dice roll summary has no ability die")

    if summary.get("roll_type") == "other_dice":
        if int(summary.get("flat_bonus", 0)) != 0:
            raise ValueError("Other Dice rolls cannot carry an ability bonus")
        counts = {}
        values_by_die = {}
        for term in terms:
            if not isinstance(term, dict) or int(term.get("sign", 1)) != 1:
                raise ValueError("Invalid Other Dice entry")
            sides = int(term["sides"])
            if sides not in OTHER_DICE_SIZES:
                raise ValueError("Unsupported Other Dice size")
            faces = [int(face) for face in term["values"]]
            if len(faces) != 1 or not 1 <= faces[0] <= sides:
                raise ValueError("Invalid Other Dice result")
            counts[sides] = counts.get(sides, 0) + 1
            values_by_die.setdefault(sides, []).extend(faces)
        selection = ", ".join(
            f"{counts[sides]}d{sides}" for sides in OTHER_DICE_SIZES if counts.get(sides)
        )
        details = "\n".join(
            f"d{int(term['sides'])}: {int(term['values'][0])}"
            for term in terms
        )
        return f"Other Dice ({selection})\n{details}"

    ability = terms[0]
    name = str(summary.get("ability_name") or "Ability").strip() or "Ability"
    base_sides = int(ability["sides"])
    flat_bonus = int(summary.get("flat_bonus", 0))
    bonus_text = f"{flat_bonus:+d}"
    parts = [f"{name} (d{base_sides}{bonus_text})"]
    breakdown = []

    for index, term in enumerate(terms):
        if not isinstance(term, dict):
            raise ValueError("Invalid die entry in roll summary")
        sides = int(term["sides"])
        values = term.get("values", [])
        if not isinstance(values, list) or not values:
            raise ValueError("Die entry has no rolled values")
        faces = [int(value) for value in values]
        sign = -1 if int(term.get("sign", 1)) < 0 else 1

        if index:
            kind = str(term.get("kind") or "").strip().lower()
            label = str(term.get("label") or "").strip()
            if kind == "advantage":
                label = "Advantage"
            elif kind == "disadvantage":
                label = "Disadvantage"
            elif not label or label.lower() in {"die", "extra", "roll"}:
                label = "Improvement die"
            parts.append(f"{'+' if sign > 0 else '−'} {label} (d{sides})")

        roll_values = "+".join(str(face) for face in faces)
        if index:
            breakdown.append(f"{'+' if sign > 0 else '−'} d{sides} [{roll_values}]")
        else:
            breakdown.append(f"d{sides} [{roll_values}]")

    if flat_bonus:
        breakdown.append(f"{flat_bonus:+d}")

    total = int(summary["total"])
    calculated_total = sum(
        (-1 if int(term.get("sign", 1)) < 0 else 1)
        * sum(int(value) for value in term["values"])
        for term in terms
    ) + flat_bonus
    if calculated_total != total:
        raise ValueError("Roll summary total does not match the dice")

    headline = " ".join(parts) + f": {total}"
    detail = "Rolls: " + " ".join(breakdown) + f" = {total}"
    if summary.get("deed_success") is True:
        detail += "  |  ✓ DEED SUCCESSFUL"
    return headline + "\n" + detail


class DiceBridge(QObject):
    def __init__(
        self,
        callback,
        status_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.callback = callback
        self.status_callback = status_callback

    @Slot(int)
    def receive_roll(
        self,
        total,
    ):
        if callable(self.callback):
            self.callback(int(total))

    @Slot(str)
    def receive_status(
        self,
        message,
    ):
        if callable(self.status_callback):
            self.status_callback(str(message))

    @Slot(int, int, int)
    def receive_roll_details(
        self,
        die_result,
        bonus,
        total,
    ):
        owner = self.parent()

        if owner is not None and hasattr(
            owner,
            "handle_dice_details",
        ):
            owner.handle_dice_details(
                int(die_result),
                int(bonus),
                int(total),
            )

    @Slot(str)
    def receive_roll_summary(
        self,
        summary_json,
    ):
        owner = self.parent()

        if owner is not None and hasattr(
            owner,
            "handle_dice_summary",
        ):
            owner.handle_dice_summary(
                str(summary_json)
            )

    @Slot(int, int, int, int, int, int, int)
    def receive_roll_visual(
        self,
        die_result,
        bonus,
        total,
        die_x,
        die_y,
        die_width,
        die_height,
    ):
        owner = self.parent()

        if owner is not None and hasattr(
            owner,
            "handle_dice_visual",
        ):
            owner.handle_dice_visual(
                int(die_result),
                int(bonus),
                int(total),
                QRect(
                    int(die_x),
                    int(die_y),
                    max(
                        1,
                        int(die_width),
                    ),
                    max(
                        1,
                        int(die_height),
                    ),
                ),
            )


class SpeciesSelectionField(QLineEdit):
    """An accessible Species chooser styled like the existing name field."""

    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Click or press Enter to choose or edit your Species")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            # Defer the modal picker until the mouse event has finished.
            QTimer.singleShot(0, self.activated.emit)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            QTimer.singleShot(0, self.activated.emit)
            event.accept()
            return
        super().keyPressEvent(event)


class BaseMainWindow(
    ThemeMixin,
    ImageMixin,
    InventoryMixin,
    NotesMixin,
    ImprovementsMixin,
    CharacterDisplayMixin,
    QWidget
):
    """
    The main character sheet window that builds and manages all UI sections.
    Handles saving, loading, refreshing, and coordinating all character systems.
    """
    def __init__(self):
        super().__init__()

        self.character = create_character()
        self.current_character_filepath = None
        self.saved_character_name = None
        self.character_access_mode = "editable"  # "editable" or "readonly"

        settings = QSettings(
            "DID",
            "CharacterSheet",
        )

        self._dice_roller_enabled = settings.value(
            "dice_roller_enabled",
            True,
            type=bool,
        )

        self.current_theme = settings.value(
            "theme",
            CURRENT_THEME,
            type=str,
        )

        if self.current_theme not in THEME:
            self.current_theme = "light"

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

        self.character.validate()
        self.unsaved_changes = False
        self.setWindowModified(False)
        self.supress_dirty = False
        self.notes_board_visible = False

        # Internal silent-recovery state.
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._auto_save_in_progress = False
        self._history_restore_pending = False

        # Undo / Redo state.
        self._undo_stack = []
        self._redo_stack = []
        self._undo_limit = 50
        self._undo_last_snapshot = None
        self._saved_character_snapshot = None
        self._restoring_undo_redo = False

        self._recovery_write_timer = QTimer(self)
        self._recovery_write_timer.setSingleShot(True)
        self._recovery_write_timer.setInterval(750)
        self._recovery_write_timer.timeout.connect(
            self.write_recovery_snapshot
        )
        # Persist all actual edits to existing .didchar files, but coalesce
        # repeated typing, HP clicks and AT clicks into one disk write.
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(1100)
        self._auto_save_timer.timeout.connect(self.auto_save_character)
        # Independent one-minute idle retry: the quick save normally wins,
        # but a transient failure or an interrupted save remains recoverable.
        self._idle_save_timer = QTimer(self)
        self._idle_save_timer.setSingleShot(True)
        self._idle_save_timer.setInterval(60_000)
        self._idle_save_timer.timeout.connect(self.auto_save_character)
        self.setWindowTitle(f"DID Character Sheet {APP_VERSION}[*]")
        self.resize(1600, 950)
        self._note_escape = QShortcut(QKeySequence("Escape"), self)
        self._note_escape.activated.connect(self.close_improvement_note_preview)


        # ------------------------------------------------------------
        # 3D dice engine
        # ------------------------------------------------------------
        #
        # dice.html is expected beside frontend_2_8.py.
        # Keep this optional so a missing Qt WebEngine installation or
        # missing dice.html does not prevent the character sheet opening.
        self.dice_view = None
        self.dice_channel = None
        self.dice_bridge = None
        self._dice_html_available = False
        self._dice_asset_server = None

        self._dice_result_popup = None
        self._dice_result_popup_token = 0
        # Roll history is session-only. Keep a per-character in-memory cache so
        # switching characters during this app session preserves each history,
        # while closing the app clears everything.
        self._session_roll_histories = {}
        self._roll_history_owner = None
        self._session_roll_history_dialog = None
        self._pending_dice_stat_name = ""
        self._pending_dice_stat_key = ""
        self._pending_other_dice_count = 0
        self._pending_d100_count = 0
        self._pending_dice_color = "#a87824"
        self._dice_final_rect = QRect()
        self._dice_move_animation = None

        # Phase 1 campaign sharing: structured roll events stay in memory
        # until a later Supabase transport layer consumes them.
        self._shared_roll_events = deque(maxlen=200)
        self._shared_roll_event_callback = None

        # Phase 3: Campaign owns its Creation Rules and live sync.
        initialize_campaign_runtime(self)
        install_presence_heartbeat(self)

        if (
            QWebEngineView is not None
            and QWebChannel is not None
        ):
            html_path = os.path.abspath(
                os.path.join(
                    APP_DIR,
                    "dice.html",
                )
            )

            if os.path.isfile(
                html_path
            ):
                try:
                    self.dice_view = QWebEngineView(
                        self
                    )

                    # Floating overlay: never participates in any sheet layout.
                    # It sits over the character sheet only while dice are rolling.
                    self.dice_view.setAttribute(
                        Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                        True,
                    )

                    self.dice_view.setStyleSheet(
                        "background: transparent; border: none;"
                    )

                    # Keep the WebEngine alive and composited from startup.
                    # Hiding QWebEngineView entirely can make the first visible
                    # roll miss its animation. Instead it stays visible off-screen.
                    self.dice_view.setGeometry(
                        0,
                        0,
                        max(1, self.width()),
                        max(1, self.height()),
                    )
                    self.dice_view.show()
                    self.dice_view.raise_()

                    # Keep Qt WebEngine itself transparent. dice.html is also
                    # restyled after loading so its page/canvas does not appear
                    # as a large black rectangle inside the fantasy sheet.
                    try:
                        self.dice_view.page().setBackgroundColor(
                            QColor(
                                0,
                                0,
                                0,
                                0,
                            )
                        )
                    except Exception:
                        pass

                    self.dice_channel = QWebChannel(
                        self
                    )

                    self.dice_bridge = DiceBridge(
                        self.handle_dice_result,
                        self.handle_dice_status,
                        self,
                    )

                    self.dice_channel.registerObject(
                        "pyBridge",
                        self.dice_bridge,
                    )

                    self.dice_view.page().setWebChannel(
                        self.dice_channel
                    )

                    # dice.html is a local file, but DiceBox and its 3D
                    # assets currently come from unpkg.com. Qt WebEngine
                    # blocks local-file -> remote URL access unless this
                    # permission is enabled explicitly.
                    if QWebEngineSettings is not None:
                        page_settings = self.dice_view.settings()
                        page_settings.setAttribute(
                            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                            True,
                        )

                    # Qt WebEngine may refuse file:// ES module/worker
                    # imports without raising an exception in Python. A
                    # restricted localhost origin makes the 3D assets load
                    # reliably and serves NO character or configuration data.
                    self._dice_asset_server, dice_url = start_dice_asset_server(APP_DIR)
                    app = QApplication.instance()
                    if app is not None:
                        app.aboutToQuit.connect(self._dice_asset_server.shutdown)
                    self.dice_view.loadFinished.connect(
                        self._prepare_dice_page_appearance
                    )
                    self.dice_view.load(QUrl(dice_url))

                    self._dice_html_available = True

                except Exception:
                    traceback.print_exc()
                    if self._dice_asset_server is not None:
                        self._dice_asset_server.shutdown()
                        self._dice_asset_server.server_close()
                        self._dice_asset_server = None

                    if self.dice_view is not None:
                        self.dice_view.deleteLater()

                    self.dice_view = None
                    self.dice_channel = None
                    self.dice_bridge = None

        set_themed_stylesheet(self, """
            QWidget {{
                background-color: #F0FFFF;
            }}
            
            QPushButton#PositiveButton {{
                background-color: #d8edf7;
                border: 1px solid #c79a3b;
                border-radius: 9px;
                color: #25190f;
                font-family: Georgia;
                font-weight: 800;
            }}

            QPushButton#PositiveButton:hover {{
                background-color: #e8f5fb;
                border-color: #a87824;
            }}

            QPushButton#NegativeButton {{
                background-color: #fffdf7;
                border: 1px solid #c79a3b;
                border-radius: 9px;
                color: #4f3b18;
                font-family: Georgia;
                font-weight: 800;
            }}

            QPushButton#NegativeButton:hover {{
                background-color: #fff4df;
                border-color: #a87824;
            }}
        """)

        outer_layout = QVBoxLayout(self)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        # Keep the outer vertical scrollbar permanently reserved.
        # Opening Notes makes the sheet taller; if the scrollbar appears
        # only then, Qt removes scrollbar-width from the viewport and the
        # whole top row shifts sideways ("dances").
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )

        # The horizontal scrollbar being hidden is not enough:
        # QScrollArea can still move horizontally automatically when a
        # child widget (for example a NoteCard) is shown or receives focus.
        # Lock the sheet permanently to horizontal position 0.
        self.scroll.horizontalScrollBar().valueChanged.connect(
            self.keep_sheet_horizontally_locked
        )
        self.scroll.verticalScrollBar().valueChanged.connect(
            self.keep_sheet_vertically_locked
        )

        self.scroll.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.scroll.horizontalScrollBar().setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.scroll.verticalScrollBar().setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.scroll.installEventFilter(self)
        self.scroll.viewport().installEventFilter(self)

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.build_top_bar(content_layout)

        main_layout = QHBoxLayout()
        self.main_layout = main_layout
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.addLayout(main_layout, 1)

        self.build_stats_column(main_layout)
        self.build_center_column(main_layout)
        self.build_inventory_column(main_layout)
        self.build_improvements_column(main_layout)

        self.build_notes_board(content_layout)

        self.scroll.setWidget(self.content_widget)
        self.content_widget.installEventFilter(self)

        # Capture the normal full-screen widths after Qt has completed
        # the first real layout pass. Inventory and Improvements will then
        # keep those widths when the window is narrowed instead of being
        # compressed.
        self._main_column_widths_locked = False
        QTimer.singleShot(
            100,
            self.lock_normal_inventory_improvement_widths,
        )

        outer_layout.addWidget(self.scroll)

        QTimer.singleShot(
            300,
            self.check_for_recovery_on_startup
        )

        # Discord is configured once, then should behave like infrastructure.
        # If a valid Discord setup already exists, make sure its bot process is
        # running whenever DID starts instead of requiring the user to revisit
        # Discord Settings after every app restart.
        QTimer.singleShot(
            700,
            self.ensure_discord_bot_running,
        )

        self.setup_keyboard_shortcuts()

        self.refresh_all()
        self.reset_undo_history(
            treat_current_as_clean=True
        )


        # Android mobile companion - install only after the normal 1.0.11
        # startup sequence is fully initialized. Mobile support must never
        # prevent the desktop character sheet itself from opening.
        self._mobile_companion_startup_error = None
        try:
            from mobile_companion_controller import install_mobile_companion
            install_mobile_companion(
                self,
                CharacterStorageSystem,
                APP_VERSION,
            )
        except Exception:
            self._mobile_companion_startup_error = traceback.format_exc()
            traceback.print_exc()
        

    def ensure_discord_bot_running(self):
        """Best-effort Discord bot startup after one-time configuration.

        Normal users should not have to reopen Discord Settings after the
        initial integration.  Missing/incomplete configuration is intentionally
        silent; the setup screen remains the place to fix configuration errors.
        """
        try:
            from discord_integration import (
                bot_status,
                launch_bot,
                load_config,
                validate_config_for_start,
            )

            if bot_status().get("running"):
                return

            # Do not turn an unconfigured installation into a startup error.
            # Validation also ensures we do not spawn a bot with partial data.
            try:
                validate_config_for_start(load_config())
            except Exception:
                return

            app_dir = os.path.dirname(os.path.abspath(__file__))
            launch_bot(app_dir)
        except Exception:
            # Discord is optional infrastructure.  A bot startup problem must
            # never prevent the character sheet itself from opening.
            try:
                traceback.print_exc()
            except Exception:
                pass


    # ============================================================
    # 3D DICE
    # ============================================================

    def _prepare_dice_page_appearance(
        self,
        loaded=True,
    ):
        """Make the embedded dice page blend into the character sheet."""
        if (
            not loaded
            or self.dice_view is None
        ):
            return

        # The HTML may define its own black body/canvas background. Override
        # the page shell after load so only the actual dice remain visible.
        javascript = r"""
            try {
                document.documentElement.style.background = 'transparent';
                document.body.style.background = 'transparent';
                document.body.style.margin = '0';
                document.body.style.overflow = 'hidden';

                const canvases = document.querySelectorAll('canvas');
                canvases.forEach((canvas) => {
                    canvas.style.background = 'transparent';
                    canvas.style.position = 'absolute';
                    canvas.style.left = '0';
                    canvas.style.top = '0';
                    canvas.style.width = '100%';
                    canvas.style.height = '100%';
                });

                const containers = document.querySelectorAll(
                    '#canvas, #dice-box, #dice-container, .dice-box, .dice-container'
                );

                containers.forEach((element) => {
                    element.style.background = 'transparent';
                });
            } catch (error) {
                console.log(error);
            }
        """

        self.dice_view.page().runJavaScript(
            javascript
        )


    def _dice_overlay_size(
        self,
    ):
        # The WebEngine itself stays full-window and never moves.
        # Only the small HTML dice stage moves inside it.
        other_count = int(getattr(self, "_pending_other_dice_count", 0))
        if getattr(self, "_pending_d100_count", 0):
            # Physical single-piece d100 is a real 3D mesh with 100 fixed
            # labels. Give its overhead camera enough pixels to show them.
            width = min(max(220, self.width() - 24), max(320, 180 + 55 * other_count))
            height = min(max(220, self.height() - 110), 350)
            return width, height
        if other_count > 1:
            width = min(max(170, self.width() - 24), max(280, 170 + 65 * other_count))
            height = min(max(190, self.height() - 110), 320)
            return width, height
        return (170, 190)


    def _dice_start_point(
        self,
    ):
        stage_width, stage_height = self._dice_overlay_size()

        source_widget = None
        stat_key = str(
            getattr(
                self,
                "_pending_dice_stat_key",
                "",
            )
            or ""
        )

        if stat_key:
            source_widget = getattr(
                self,
                "stat_rows",
                {},
            ).get(
                stat_key
            )

        if source_widget is not None:
            try:
                source_top_left = source_widget.mapTo(
                    self,
                    QPoint(
                        0,
                        0,
                    ),
                )

                start_y = (
                    source_top_left.y()
                    + source_widget.height() // 2
                    - stage_height // 2
                )
            except Exception:
                start_y = int(
                    self.height() * 0.45
                )
        else:
            start_y = int(
                self.height() * 0.45
            )

        start_x = 8

        start_y = max(
            70,
            min(
                start_y,
                max(
                    70,
                    self.height() - stage_height - 12,
                ),
            ),
        )

        return QPoint(
            start_x,
            start_y,
        )


    def _random_dice_final_point(
        self,
    ):
        stage_width, stage_height = self._dice_overlay_size()

        min_x = int(
            self.width() * 0.46
        )

        max_x = int(
            self.width() * 0.70
        )

        min_y = int(
            self.height() * 0.30
        )

        max_y = int(
            self.height() * 0.70
        )

        x = random.randint(
            min(
                min_x,
                max_x,
            ),
            max(
                min_x,
                max_x,
            ),
        )

        y = random.randint(
            min(
                min_y,
                max_y,
            ),
            max(
                min_y,
                max_y,
            ),
        )

        x = max(
            8,
            min(
                x,
                max(
                    8,
                    self.width() - stage_width - 8,
                ),
            ),
        )

        y = max(
            75,
            min(
                y,
                max(
                    75,
                    self.height() - stage_height - 12,
                ),
            ),
        )

        return QPoint(
            x,
            y,
        )


    def show_dice_tray(
        self,
    ):
        if self.dice_view is None:
            return

        # A new roll removes the entire previous result immediately.
        old_popup = getattr(
            self,
            "_dice_result_popup",
            None,
        )

        if old_popup is not None:
            try:
                old_popup.hide()
                old_popup.deleteLater()
            except (RuntimeError, ReferenceError):
                pass

            self._dice_result_popup = None
            self._dice_result_popup_token += 1

        if self.dice_view is not None:
            try:
                self.dice_view.page().runJavaScript(
                    "hideDiceResult();"
                )
            except Exception:
                pass

        self._dice_hide_token = (
            getattr(
                self,
                "_dice_hide_token",
                0,
            )
            + 1
        )

        stage_width, stage_height = self._dice_overlay_size()
        start_point = self._dice_start_point()
        final_point = self._random_dice_final_point()

        self._dice_start_point_current = QPoint(
            start_point
        )

        self._dice_final_point_current = QPoint(
            final_point
        )

        self._dice_final_rect = QRect(
            final_point.x(),
            final_point.y(),
            stage_width,
            stage_height,
        )

        # Keep the WebEngine perfectly stationary. Moving QWebEngineView while
        # WebGL is rendering caused the flicker/disappear/reappear behavior.
        self.dice_view.setGeometry(
            0,
            0,
            max(
                1,
                self.width(),
            ),
            max(
                1,
                self.height(),
            ),
        )

        self.dice_view.show()
        self.dice_view.raise_()

        self._prepare_dice_page_appearance(
            True
        )


    def hide_dice_tray_later(
        self,
        delay_ms=2400,
    ):
        if self.dice_view is None:
            return

        token = getattr(
            self,
            "_dice_hide_token",
            0,
        )

        def clear_if_still_current():
            if (
                token
                != getattr(
                    self,
                    "_dice_hide_token",
                    0,
                )
            ):
                return

            self.dice_view.page().runJavaScript(
                "clearDiceDisplay(); hideDiceResult();"
            )

        QTimer.singleShot(
            int(delay_ms),
            clear_if_still_current,
        )


    def dice_roller_is_enabled(
        self,
    ):
        return bool(
            getattr(
                self,
                "_dice_roller_enabled",
                True,
            )
        )


    def toggle_dice_roller_from_ui(
        self,
    ):
        self._dice_roller_enabled = not self.dice_roller_is_enabled()

        settings = QSettings(
            "DID",
            "CharacterSheet",
        )
        settings.setValue(
            "dice_roller_enabled",
            self._dice_roller_enabled,
        )
        settings.sync()

        if not self._dice_roller_enabled:
            try:
                if self.dice_view is not None:
                    self.dice_view.page().runJavaScript(
                        "clearDiceDisplay(); hideDiceResult();"
                    )
            except Exception:
                traceback.print_exc()

            old_popup = getattr(
                self,
                "_dice_result_popup",
                None,
            )

            if old_popup is not None:
                try:
                    old_popup.hide()
                    old_popup.deleteLater()
                except (RuntimeError, ReferenceError):
                    pass

                self._dice_result_popup = None

            self._set_ability_roll_active(
                None
            )


    def _owned_improvement_ids(
        self,
    ):
        result = set()

        for improvement in getattr(
            self.character.improvements,
            "list_of_taken_improvements",
            [],
        ):
            catalog_id = str(
                getattr(
                    improvement,
                    "catalog_id",
                    "",
                )
                or ""
            ).strip()

            if catalog_id:
                result.add(catalog_id)

        return result


    def _available_roll_modifier_options(
        self,
        stat_key=None,
    ):
        options = []
        owned = self._owned_improvement_ids()

        bonus_dice = dict(
            getattr(
                getattr(
                    self.character,
                    "bonus_dice",
                    None,
                ),
                "dice",
                {},
            )
            or {}
        )

        definitions = (
            (
                "martial_die",
                "martial_feats",
                "Martial Die",
                "martial",
            ),
            (
                "magic_die",
                "spellcasting",
                "Magic Die",
                "magic",
            ),
            (
                "magic_novice_die",
                "magic_novice",
                "Magic Die",
                "magic",
            ),
            (
                "mighty_die",
                "mighty",
                "Mighty Die",
                "mighty",
            ),
        )

        for key, required_id, display_name, short_label in definitions:
            die_size = bonus_dice.get(key)

            if (
                required_id not in owned
                or die_size is None
            ):
                continue

            options.append(
                {
                    "kind": "bonus_die",
                    "label": f"{display_name} (d{int(die_size)})",
                    "short_label": short_label,
                    "sides": int(die_size),
                    "sign": 1,
                    # These named bonus dice explicitly do not explode.
                    "explode": False,
                }
            )

        # Born of Soil's Wild Die is only valid for the abilities declared
        # by the API. Keep that rules metadata in character_API.py rather than
        # duplicating the allowed-stat list here.
        wild_die = bonus_dice.get("wild_die")
        born_of_soil = IMPROVEMENT_CATALOG.get("born_of_soil", {})
        wild_meta = (
            born_of_soil.get("scaling_empowerments", {})
            .get("wild_die", {})
        )
        wild_stats = {
            str(name).strip().lower()
            for name in wild_meta.get("applies_to_stats", [])
        }
        if (
            "born_of_soil" in owned
            and wild_die is not None
            and (stat_key is None or str(stat_key).lower() in wild_stats)
        ):
            options.append(
                {
                    "kind": "bonus_die",
                    "label": f"Wild Die (d{int(wild_die)})",
                    "short_label": "wild",
                    "sides": int(wild_die),
                    "sign": 1,
                    "explode": False,
                }
            )

        # Animal Buddy's helper die is a character bonus die, separate from
        # clicking one of the buddy's own six ability cards for an independent
        # buddy roll.
        buddy_die = bonus_dice.get("buddy_die")
        if "animal_buddy" in owned and buddy_die is not None:
            options.append(
                {
                    "kind": "bonus_die",
                    "label": f"Buddy Die (d{int(buddy_die)})",
                    "short_label": "buddy",
                    "sides": int(buddy_die),
                    "sign": 1,
                    "explode": True,
                }
            )

        if "reckless_attack" in owned:
            options.append(
                {
                    "kind": "advantage",
                    "label": "Reckless Attack — Advantage (+d6)",
                    "short_label": "reckless",
                    "sides": 6,
                    "sign": 1,
                    "explode": False,
                }
            )

        if "torturer" in owned:
            options.append(
                {
                    "kind": "advantage",
                    "label": "Torturer — Advantage (+d6)",
                    "short_label": "torturer",
                    "sides": 6,
                    "sign": 1,
                    "explode": False,
                }
            )

        return options


    @staticmethod
    def _cancel_opposing_roll_dice(extras):
        """Remove advantage/disadvantage pairs, preserving all other dice."""
        kept = []
        for item in extras:
            kind = item.get("kind")
            if kind not in ("advantage", "disadvantage"):
                kept.append(item)
                continue
            opposite = (
                "disadvantage" if kind == "advantage" else "advantage"
            )
            opposite_index = next(
                (index for index, other in enumerate(kept)
                 if other.get("kind") == opposite),
                None,
            )
            if opposite_index is None:
                kept.append(item)
            else:
                kept.pop(opposite_index)
        return kept


    def open_dice_options_for_stat(
        self,
        stat_key,
        global_position=None,
    ):
        if not self.dice_roller_is_enabled():
            return

        stat = self.character.stats.get_stat(
            stat_key
        )

        if stat is None:
            return

        row = getattr(
            self,
            "stat_rows",
            {},
        ).get(
            stat_key
        )

        if row is not None:
            row.hide_ability_popup()

        dialog = FantasyDiceOptionsDialog(
            str(stat_key).title(),
            self._available_roll_modifier_options(stat_key),
            self,
        )

        # Always place the roll options inside the sheet. The right-click
        # position may be near a monitor edge (or even outside the window),
        # which previously opened the dialog with its title/buttons clipped.
        # Centering after Qt calculates its final size avoids DPI offsets.
        dialog.adjustSize()
        dialog.position_inside_sheet()
        QTimer.singleShot(0, dialog.position_inside_sheet)

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        extras = []

        advantage_count, disadvantage_count = dialog.selected_roll_counts()
        for _ in range(advantage_count):
            extras.append(
                {
                    "label": "adv.",
                    "kind": "advantage",
                    "sides": 6,
                    "sign": 1,
                    "explode": False,
                }
            )
        for _ in range(disadvantage_count):
            extras.append(
                {
                    "label": "dis.",
                    "kind": "disadvantage",
                    "sides": 6,
                    "sign": -1,
                    "explode": False,
                }
            )

        for option in dialog.selected_modifiers():
            extras.append(
                {
                    "label": str(
                        option.get(
                            "short_label",
                            "die",
                        )
                    ),
                    "sides": int(
                        option.get(
                            "sides",
                            6,
                        )
                    ),
                    "sign": (
                        1
                        if int(
                            option.get(
                                "sign",
                                1,
                            )
                        ) > 0
                        else -1
                    ),
                    # Only the main ability die explodes; selected modifiers do not.
                    "explode": False,
                    "kind": (
                        str(option.get("short_label"))
                        if option.get("short_label") in {"martial", "magic", "mighty"}
                        else str(option.get("kind", "bonus_die"))
                    ),
                }
            )

        self.roll_stat_from_ui(
            stat_key,
            extra_dice=extras,
        )


    def _set_ability_roll_active(
        self,
        stat_key,
    ):
        for key, row in getattr(
            self,
            "stat_rows",
            {},
        ).items():
            try:
                row.set_dice_rolling(
                    bool(
                        stat_key
                        and key == stat_key
                    )
                )
            except Exception:
                pass


    def roll_dice_plan(
        self,
        plan,
        color=None,
    ):
        if not self.dice_roller_is_enabled():
            return

        if (
            self.dice_view is None
            or not self._dice_html_available
        ):
            return

        self._roll_history_owner = self.character
        self.show_dice_tray()

        javascript_plan = json.dumps(plan)
        javascript_color = json.dumps(
            str(color or "#a87824")
        )

        start_point = getattr(
            self,
            "_dice_start_point_current",
            QPoint(8, 120),
        )

        final_point = getattr(
            self,
            "_dice_final_point_current",
            QPoint(
                int(self.width() * 0.55),
                int(self.height() * 0.45),
            ),
        )

        stage_width, stage_height = self._dice_overlay_size()

        def start_visible_roll():
            if self.dice_view is None:
                return

            self.dice_view.page().runJavaScript(
                "rollDicePlan("
                f"{javascript_plan}, "
                f"{javascript_color}, "
                f"{int(start_point.x())}, "
                f"{int(start_point.y())}, "
                f"{int(final_point.x())}, "
                f"{int(final_point.y())}, "
                f"{int(stage_width)}, "
                f"{int(stage_height)}"
                ");"
            )

        QTimer.singleShot(
            90,
            start_visible_roll,
        )

        self.hide_dice_tray_later(
            60000 if getattr(self, "_pending_d100_count", 0) else 30000
        )


    def roll_stat_from_ui(
        self,
        stat_key,
        extra_dice=None,
    ):
        if not self.dice_roller_is_enabled():
            return

        stat = self.character.stats.get_stat(
            stat_key
        )

        if stat is None:
            return

        die_size = int(
            getattr(
                stat,
                "die_size",
                4,
            )
        )

        bonus = int(
            getattr(
                stat,
                "bonus",
                0,
            )
        )

        self._pending_other_dice_count = 0
        self._pending_d100_count = 0
        self._pending_dice_stat_name = str(
            stat_key
        ).strip().title()

        self._pending_dice_stat_key = str(
            stat_key
        ).strip().lower()

        self._pending_dice_color = ABILITY_ACCENTS.get(
            stat_key,
            "#a87824",
        )

        self._set_ability_roll_active(
            stat_key
        )

        extras = []

        for item in extra_dice or []:
            try:
                sides = int(
                    item.get(
                        "sides",
                        0,
                    )
                )
                sign = int(
                    item.get(
                        "sign",
                        1,
                    )
                )
            except Exception:
                continue

            if sides < 2 or sign == 0:
                continue

            extras.append(
                {
                    "label": str(
                        item.get(
                            "label",
                            "die",
                        )
                    ),
                    "sides": sides,
                    "sign": (
                        1
                        if sign > 0
                        else -1
                    ),
                    # Never allow advantage, magic, martial, or other extra
                    # dice to explode, even if a caller supplied that flag.
                    "explode": False,
                    "kind": str(item.get("kind", "extra")),
                }
            )

        # Cancel manual and improvement-granted opposing dice before any
        # DiceBox request. For example 3 advantages - 1 disadvantage = 2d6.
        extras = self._cancel_opposing_roll_dice(extras)

        plan = {
            "ability_name": self._pending_dice_stat_name,
            "ability": {
                "label": "roll",
                "sides": die_size,
                "sign": 1,
                "explode": True,
            },
            "flat_bonus": bonus,
            "extras": extras,
        }

        self.roll_dice_plan(
            plan,
            self._pending_dice_color,
        )


    def resizeEvent(
        self,
        event,
    ):
        super().resizeEvent(
            event
        )

        if getattr(
            self,
            "dice_view",
            None,
        ) is not None:
            self.dice_view.setGeometry(
                0,
                0,
                max(
                    1,
                    self.width(),
                ),
                max(
                    1,
                    self.height(),
                ),
            )


    def handle_dice_status(
        self,
        message,
    ):
        message = str(message or "").strip()

        if not message:
            return

        # Normal bridge/ready/rolling messages are intentionally silent.
        # Preserve actionable errors in IDLE rather than hiding failures.
        if "error" in message.casefold() or "failed" in message.casefold():
            print(f"[Dice Roller] {message}", file=sys.stderr)

        # If the HTML reports an error, do not leave an empty overlay up.
        if message.lower().startswith("dice error"):
            self.hide_dice_tray_later(
                2500
            )




    def show_dice_result_popup(
        self,
        die_result,
        bonus,
        total,
        die_rect=None,
    ):
        """Show the result directly above the actual rendered die."""
        old_popup = getattr(
            self,
            "_dice_result_popup",
            None,
        )

        if old_popup is not None:
            try:
                old_popup.hide()
                old_popup.deleteLater()
            except (RuntimeError, ReferenceError):
                pass

        popup = QFrame(
            self
        )

        popup.setObjectName(
            "DiceResultPopup"
        )

        popup.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        dice_color = str(
            getattr(
                self,
                "_pending_dice_color",
                "#a87824",
            )
            or "#a87824"
        )

        popup_text_color = "#ffffff"

        try:
            parsed_color = QColor(
                dice_color
            )

            luminance = (
                0.299 * parsed_color.red()
                + 0.587 * parsed_color.green()
                + 0.114 * parsed_color.blue()
            )

            if luminance > 165:
                popup_text_color = "#25190f"
        except Exception:
            popup_text_color = "#ffffff"

        set_themed_stylesheet(
            popup,
            f"""
            QFrame#DiceResultPopup {{
                background-color: {dice_color};
                border: 2px solid {dice_color};
                border-radius: 13px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {popup_text_color};
                font-family: Georgia;
            }}
            """,
        )

        outer = QVBoxLayout(
            popup
        )

        outer.setContentsMargins(
            8,
            7,
            8,
            8,
        )

        outer.setSpacing(
            2
        )

        stat_name = str(
            getattr(
                self,
                "_pending_dice_stat_name",
                "",
            )
            or "Roll"
        )

        buddy_roll = stat_name.startswith("Animal Buddy — ")
        if not buddy_roll:
            title = QLabel(
                stat_name
            )
            title.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            set_themed_stylesheet(
                title,
                f"""
                QLabel {{
                    font-size: 12px;
                    font-weight: 900;
                    color: {popup_text_color};
                }}
                """,
            )

            outer.addWidget(
                title
            )

        if bonus == 0:
            popup.setFixedWidth(
                116
            )

            number = QLabel(
                str(die_result)
            )
            number.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            caption = QLabel(
                "roll"
            )
            caption.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            set_themed_stylesheet(
                number,
                f"""
                QLabel {{
                    font-size: 23px;
                    font-weight: 900;
                    color: {popup_text_color};
                }}
                """,
            )

            set_themed_stylesheet(
                caption,
                f"""
                QLabel {{
                    font-size: 9px;
                    font-weight: 700;
                    color: {popup_text_color};
                }}
                """,
            )

            outer.addWidget(
                number
            )
            outer.addWidget(
                caption
            )

        else:
            # Compact five-column layout:
            # [roll] [+/-] [bonus] [=] [total]
            popup.setFixedWidth(
                146
            )

            row = QHBoxLayout()
            row.setContentsMargins(
                0,
                0,
                0,
                0,
            )
            row.setSpacing(
                0
            )

            def value_column(
                number_text,
                caption_text,
            ):
                host = QWidget()
                host.setFixedWidth(
                    32
                )

                layout = QVBoxLayout(
                    host
                )
                layout.setContentsMargins(
                    0,
                    0,
                    0,
                    0,
                )
                layout.setSpacing(
                    0
                )

                number_label = QLabel(
                    str(number_text)
                )
                number_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                caption_label = QLabel(
                    str(caption_text)
                )
                caption_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                set_themed_stylesheet(
                    number_label,
                    f"""
                    QLabel {{
                        font-size: 22px;
                        font-weight: 900;
                        color: {popup_text_color};
                    }}
                    """,
                )

                set_themed_stylesheet(
                    caption_label,
                    f"""
                    QLabel {{
                        font-size: 8px;
                        font-weight: 700;
                        color: {popup_text_color};
                    }}
                    """,
                )

                layout.addWidget(
                    number_label
                )
                layout.addWidget(
                    caption_label
                )

                return host

            def operator_label(
                text,
            ):
                label = QLabel(
                    text
                )
                label.setFixedWidth(
                    12
                )
                label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                set_themed_stylesheet(
                    label,
                    f"""
                    QLabel {{
                        font-size: 18px;
                        font-weight: 900;
                        color: {popup_text_color};
                    }}
                    """,
                )

                return label

            row.addWidget(
                value_column(
                    die_result,
                    "roll",
                )
            )

            row.addWidget(
                operator_label(
                    "+"
                    if bonus > 0
                    else "−"
                )
            )

            row.addWidget(
                value_column(
                    abs(
                        bonus
                    ),
                    "bonus",
                )
            )

            row.addWidget(
                operator_label(
                    "="
                )
            )

            row.addWidget(
                value_column(
                    total,
                    "total",
                )
            )

            outer.addLayout(
                row
            )

        if buddy_roll:
            marker = QLabel("Animal Buddy")
            marker.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            marker.setToolTip(stat_name)
            set_themed_stylesheet(marker, f"QLabel {{font-size:9px; color:{popup_text_color}; padding:0;}}")
            outer.addWidget(marker)

        popup.adjustSize()

        if (
            isinstance(
                die_rect,
                QRect,
            )
            and die_rect.isValid()
        ):
            # Exact horizontal centering on the actual rendered die.
            x = (
                die_rect.center().x()
                - popup.width() // 2
            )

            # Small consistent gap immediately above the die.
            y = (
                die_rect.top()
                - popup.height()
                - 5
            )

        else:
            final_rect = getattr(
                self,
                "_dice_final_rect",
                QRect(),
            )

            if (
                isinstance(
                    final_rect,
                    QRect,
                )
                and final_rect.isValid()
            ):
                x = (
                    final_rect.center().x()
                    - popup.width() // 2
                )

                y = (
                    final_rect.top()
                    - popup.height()
                    - 5
                )
            else:
                x = (
                    self.width()
                    - popup.width()
                ) // 2
                y = 96

        x = max(
            8,
            min(
                x,
                self.width() - popup.width() - 8,
            ),
        )

        y = max(
            45,
            min(
                y,
                self.height() - popup.height() - 8,
            ),
        )

        popup.move(
            x,
            y,
        )

        popup.show()
        popup.raise_()

        self._dice_result_popup = popup
        self._dice_result_popup_token += 1


    def _detect_rendered_die_rect(
        self,
    ):
        """
        Detect the settled die from the final dice-stage image.

        This intentionally does NOT depend on matching the exact Ability color:
        DiceBox lighting changes the face colors substantially. Instead we find
        the compact non-background rendered object inside the final stage.
        """
        if self.dice_view is None:
            return None

        search_rect = getattr(
            self,
            "_dice_final_rect",
            QRect(),
        )

        if (
            not isinstance(
                search_rect,
                QRect,
            )
            or not search_rect.isValid()
        ):
            return None

        try:
            pixmap = self.dice_view.grab(
                search_rect
            )

            if pixmap.isNull():
                return None

            image = pixmap.toImage().convertToFormat(
                QImage.Format.Format_ARGB32
            )

            width = image.width()
            height = image.height()

            points = []

            for y in range(height):
                for x in range(width):
                    color = image.pixelColor(
                        x,
                        y,
                    )

                    alpha = color.alpha()

                    # Transparent page background: ignore it.
                    if alpha < 35:
                        continue

                    r = color.red()
                    g = color.green()
                    b = color.blue()

                    brightest = max(
                        r,
                        g,
                        b,
                    )
                    darkest = min(
                        r,
                        g,
                        b,
                    )

                    saturation = (
                        brightest
                        - darkest
                    )

                    # Ignore very pale/neutral pixels. The die/shadow remain.
                    if (
                        brightest > 235
                        and saturation < 22
                    ):
                        continue

                    points.append(
                        (
                            x,
                            y,
                        )
                    )

            if not points:
                return None

            min_x = min(
                p[0]
                for p in points
            )
            max_x = max(
                p[0]
                for p in points
            )
            min_y = min(
                p[1]
                for p in points
            )
            max_y = max(
                p[1]
                for p in points
            )

            detected_width = (
                max_x
                - min_x
                + 1
            )

            detected_height = (
                max_y
                - min_y
                + 1
            )

            # Reject a detection that is effectively the whole HTML stage.
            if (
                detected_width > width * 0.90
                or detected_height > height * 0.90
            ):
                return None

            # Small padding includes the shadow without moving the center much.
            padding = 3

            left = max(
                0,
                min_x - padding,
            )
            top = max(
                0,
                min_y - padding,
            )
            right = min(
                width - 1,
                max_x + padding,
            )
            bottom = min(
                height - 1,
                max_y + padding,
            )

            return QRect(
                search_rect.x() + left,
                search_rect.y() + top,
                right - left + 1,
                bottom - top + 1,
            )

        except Exception:
            traceback.print_exc()
            return None


    def show_dice_summary_popup(
        self,
        summary,
    ):
        old_popup = getattr(
            self,
            "_dice_result_popup",
            None,
        )

        if old_popup is not None:
            try:
                old_popup.hide()
                old_popup.deleteLater()
            except (RuntimeError, ReferenceError):
                pass

        terms = list(
            summary.get(
                "terms",
                [],
            )
            or []
        )

        total = int(
            summary.get(
                "total",
                0,
            )
        )

        flat_bonus = int(
            summary.get(
                "flat_bonus",
                0,
            )
        )

        simple_roll = (
            len(terms) == 1
            and len(
                list(
                    terms[0].get(
                        "values",
                        [],
                    )
                    or []
                )
            ) == 1
            and flat_bonus == 0
        )

        popup = QFrame(
            self
        )
        popup.setObjectName(
            "DiceResultPopup"
        )
        popup.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        dice_color = str(
            getattr(
                self,
                "_pending_dice_color",
                "#a87824",
            )
            or "#a87824"
        )

        popup_text_color = "#ffffff"

        try:
            parsed_color = QColor(
                dice_color
            )

            luminance = (
                0.299 * parsed_color.red()
                + 0.587 * parsed_color.green()
                + 0.114 * parsed_color.blue()
            )

            if luminance > 165:
                popup_text_color = "#25190f"
        except Exception:
            pass

        set_themed_stylesheet(
            popup,
            f"""
            QFrame#DiceResultPopup {{
                background-color: {dice_color};
                border: 2px solid {dice_color};
                border-radius: 13px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {popup_text_color};
                font-family: Georgia;
            }}
            """,
        )

        root = QVBoxLayout(
            popup
        )
        root.setContentsMargins(
            7,
            6,
            7,
            7,
        )
        root.setSpacing(
            0
        )

        summary_title = str(getattr(self, "_pending_dice_stat_name", "Roll"))
        if summary_title.startswith("Animal Buddy — "):
            summary_title = summary_title.split(" — ", 1)[1]
        title = QLabel(summary_title)
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        set_themed_stylesheet(
            title,
            f"""
            QLabel {{
                font-size: 11px;
                font-weight: 900;
                color: {popup_text_color};
            }}
            """,
        )

        root.addWidget(
            title
        )

        if simple_roll:
            # Compact, nearly square result card.
            popup.setFixedSize(
                92,
                88,
            )

            number = QLabel(
                str(total)
            )
            number.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            caption = QLabel(
                "total"
            )
            caption.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            set_themed_stylesheet(
                number,
                f"""
                QLabel {{
                    font-size: 24px;
                    font-weight: 900;
                    color: {popup_text_color};
                }}
                """,
            )

            set_themed_stylesheet(
                caption,
                f"""
                QLabel {{
                    font-size: 8px;
                    font-weight: 700;
                    color: {popup_text_color};
                }}
                """,
            )

            root.addWidget(
                number,
                1,
            )
            root.addWidget(
                caption
            )

        else:
            row = QHBoxLayout()
            row.setContentsMargins(
                0,
                0,
                0,
                0,
            )
            row.setSpacing(
                0
            )

            def add_operator(
                symbol,
            ):
                label = QLabel(
                    symbol
                )
                label.setFixedWidth(
                    9
                )
                label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                set_themed_stylesheet(
                    label,
                    f"""
                    QLabel {{
                        font-size: 16px;
                        font-weight: 900;
                        color: {popup_text_color};
                    }}
                    """,
                )

                row.addWidget(
                    label
                )

            def add_value(
                value,
                caption,
            ):
                # Slightly wider only for "explode", so the word never clips.
                width = (
                    40
                    if str(caption) == "explode"
                    else 31
                )

                host = QWidget()
                host.setFixedWidth(
                    width
                )

                layout = QVBoxLayout(
                    host
                )
                layout.setContentsMargins(
                    0,
                    0,
                    0,
                    0,
                )
                layout.setSpacing(
                    0
                )

                number = QLabel(
                    str(value)
                )
                number.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                caption_label = QLabel(
                    str(caption)
                )
                caption_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                set_themed_stylesheet(
                    number,
                    f"""
                    QLabel {{
                        font-size: 20px;
                        font-weight: 900;
                        color: {popup_text_color};
                    }}
                    """,
                )

                set_themed_stylesheet(
                    caption_label,
                    f"""
                    QLabel {{
                        font-size: 7px;
                        font-weight: 700;
                        color: {popup_text_color};
                    }}
                    """,
                )

                layout.addWidget(
                    number
                )
                layout.addWidget(
                    caption_label
                )

                row.addWidget(
                    host
                )

            first = True

            for term in terms:
                sign = int(
                    term.get(
                        "sign",
                        1,
                    )
                )

                values = list(
                    term.get(
                        "values",
                        [],
                    )
                    or []
                )

                caption = str(
                    term.get(
                        "label",
                        "die",
                    )
                )

                for index, value in enumerate(values):
                    if not first:
                        add_operator(
                            "+"
                            if sign > 0
                            else "−"
                        )

                    add_value(
                        value,
                        (
                            caption
                            if index == 0
                            else "explode"
                        ),
                    )

                    first = False

            if flat_bonus != 0:
                add_operator(
                    "+"
                    if flat_bonus > 0
                    else "−"
                )
                add_value(
                    abs(
                        flat_bonus
                    ),
                    "bonus",
                )

            add_operator(
                "="
            )
            add_value(
                total,
                "total",
            )

            root.addLayout(
                row
            )

            popup.adjustSize()

        # Position from the final DiceBox stage itself.
        #
        # DiceBox consistently settles the die in the lower half of this
        # compact stage. Using the stage center is more stable than trying
        # to infer the die from a grabbed WebEngine frame, which has proven
        # unreliable with transparent WebGL.
        final_rect = getattr(
            self,
            "_dice_final_rect",
            QRect(),
        )

        if (
            isinstance(
                final_rect,
                QRect,
            )
            and final_rect.isValid()
        ):
            # Calibrated to DiceBox's actual settled-die lane inside our
            # 170x190 stage. The die consistently lands in the lower-left
            # part of the WebGL canvas, not at the stage centre.
            die_center_x = (
                final_rect.left()
                + int(
                    final_rect.width()
                    * 0.24
                )
            )

            estimated_die_top = (
                final_rect.top()
                + int(
                    final_rect.height()
                    * 0.64
                )
            )

            # Popup horizontal centre == die horizontal centre.
            x = (
                die_center_x
                - popup.width() // 2
            )

            # Small gap directly above the die.
            y = (
                estimated_die_top
                - popup.height()
                - 5
            )

        else:
            x = (
                self.width()
                - popup.width()
            ) // 2

            y = 20

        x = max(
            8,
            min(
                x,
                self.width()
                - popup.width()
                - 8,
            ),
        )

        # Do not force the popup down to y=45. That old clamp is exactly
        # what caused the die to sit inside the popup near the top of the app.
        y = max(
            6,
            min(
                y,
                self.height()
                - popup.height()
                - 8,
            ),
        )

        popup.move(
            x,
            y,
        )
        popup.show()
        popup.raise_()

        self._dice_result_popup = popup
        self._dice_result_popup_token += 1


    def handle_dice_summary(
        self,
        summary_json,
    ):
        try:
            summary = json.loads(
                summary_json
            )
        except Exception:
            traceback.print_exc()
            self._set_ability_roll_active(
                None
            )
            return

        self._set_ability_roll_active(
            None
        )

        # The summary arrives once per completed roll (unlike receive_roll,
        # which duplicates the total). Roll history is deliberately session-only:
        # do not mark the character dirty or autosave because of a dice roll.
        owner = self._roll_history_owner or self.character

        try:
            entry = format_session_roll_entry(summary)
            owner.roll_history.append(entry)
            self._remember_session_roll_history(owner)
            self._refresh_session_roll_history_dialog()
        except (ValueError, TypeError, KeyError, OverflowError):
            traceback.print_exc()

        # Phase 1 campaign sharing. This only records a structured in-memory
        # event; it performs no network request and does not affect the roll.
        try:
            self._record_shared_roll_event(
                summary,
                owner,
            )
        except (ValueError, TypeError, KeyError, OverflowError):
            traceback.print_exc()

        # Render the result inside dice.html, in the SAME coordinate system
        # as the die. This guarantees the card stays centered above the die
        # stage and avoids Qt/WebEngine coordinate mismatch.
        if self.dice_view is not None:
            javascript_summary = json.dumps(
                summary
            )

            display_title = str(getattr(self, "_pending_dice_stat_name", "Roll"))
            if display_title.startswith("Animal Buddy — "):
                display_title = display_title.split(" — ", 1)[1]
            javascript_title = json.dumps(display_title)

            javascript_color = json.dumps(
                str(
                    getattr(
                        self,
                        "_pending_dice_color",
                        "#a87824",
                    )
                )
            )

            self.dice_view.page().runJavaScript(
                "showDiceResult("
                f"{javascript_summary}, "
                f"{javascript_title}, "
                f"{javascript_color}"
                ");"
            )

        self.hide_dice_and_result_together_later(
            4000
        )


    def hide_dice_and_result_together_later(
        self,
        delay_ms=4000,
    ):
        """
        Remove the settled die and its popup together.

        The timer starts after the physical roll has finished, so the result
        remains visible for the full delay. A newer roll invalidates the old
        timer so it cannot remove the newer die/popup.
        """
        dice_token = getattr(
            self,
            "_dice_hide_token",
            0,
        )

        popup_token = getattr(
            self,
            "_dice_result_popup_token",
            0,
        )

        popup = getattr(
            self,
            "_dice_result_popup",
            None,
        )

        def cleanup():
            # If another roll started, this timer belongs to the old roll.
            if (
                dice_token
                != getattr(
                    self,
                    "_dice_hide_token",
                    0,
                )
            ):
                return

            if self.dice_view is not None:
                try:
                    self.dice_view.page().runJavaScript(
                        "clearDiceDisplay(); hideDiceResult();"
                    )
                except Exception:
                    traceback.print_exc()

            if (
                popup is not None
                and popup_token
                == getattr(
                    self,
                    "_dice_result_popup_token",
                    0,
                )
                and popup
                is getattr(
                    self,
                    "_dice_result_popup",
                    None,
                )
            ):
                try:
                    popup.hide()
                    popup.deleteLater()
                except (RuntimeError, ReferenceError):
                    pass

                self._dice_result_popup = None

        QTimer.singleShot(
            int(delay_ms),
            cleanup,
        )


    def handle_dice_visual(
        self,
        die_result,
        bonus,
        total,
        die_rect,
    ):
        self.show_dice_result_popup(
            int(die_result),
            int(bonus),
            int(total),
            die_rect=die_rect,
        )

        self._set_ability_roll_active(
            None
        )

        self.hide_dice_and_result_together_later(
            4000
        )

    def handle_dice_details(
        self,
        die_result,
        bonus,
        total,
    ):
        # Fallback for older dice.html files that do not send visual bounds.
        self.show_dice_result_popup(
            int(die_result),
            int(bonus),
            int(total),
        )

        self._set_ability_roll_active(
            None
        )

        self.hide_dice_and_result_together_later(
            4000
        )


    def handle_dice_result(
        self,
        total,
    ):
        """Called by dice.html through QWebChannel when the roll ends."""
        total = int(
            total
        )

        # A matching structured summary already recorded this roll.
        # Routine outcomes belong in session history, not the IDLE console.
        # Preserve the normal Saved/Unsaved indicator in the top bar.

        # The die and popup are removed together by
        # hide_dice_and_result_together_later(), 7 seconds after landing.


    # ============================================================
    # UI BUILDERS
    # ============================================================

    def build_top_bar(self, outer_layout):
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.tools_toggle_btn = QPushButton("⚙")
        self.tools_toggle_btn.setFixedSize(38, 32)
        set_themed_stylesheet(self.tools_toggle_btn, f"""
            QPushButton {{
                background-color: {BLUE};
                border: 2px solid black;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 900;
                color: black;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}
        """)
        self.tools_toggle_btn.clicked.connect(self.toggle_tools_menu)

        self.character_name_label = QLineEdit()
        self.character_name_label.setPlaceholderText("Unnamed Character")
        self.character_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(self.character_name_label, """
            QLineEdit {
                background: transparent;
                border: none;
                font-size: 20px;
                font-weight: 900;
                color: black;
                padding: 2px;
            }

            QLineEdit:focus {
                background-color: transparent;
                padding: 2px;
            }
        """)
        self.character_name_label.editingFinished.connect(
            self.update_character_name_from_ui
        )

        self.species_label = SpeciesSelectionField()
        self.species_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.species_label.setPlaceholderText("Choose Species")

        set_themed_stylesheet(self.species_label, """
            QLineEdit {
                background: transparent;
                border: none;
                font-size: 18px;
                font-weight: 800;
                color: black;
            }

            QLineEdit:focus {
                background-color: transparent;
                padding: 2px;
            }
        """)

        self.species_label.activated.connect(self.choose_species_from_sheet)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(100) # space between name and specie

        name_row.addWidget(self.character_name_label)
        name_row.addWidget(self.species_label)

        name_widget = QWidget()
        name_widget.setLayout(name_row)
        
        self.save_status_label = QLabel("Saved")
        self.save_status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignCenter
        )
        set_themed_stylesheet(self.save_status_label, """
            QLabel {
                background: transparent;
                border: none;
                font-size: 12px;
                font-weight: 700;
                color: #555555;
                padding: 0px 8px;
            }
        """)


        # Live Android connection status. The companion controller owns the
        # text and hides this label when no phone socket is actually alive.
        self.phone_connection_label = QLabel("")
        self.phone_connection_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignCenter
        )
        set_themed_stylesheet(
            self.phone_connection_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 900;
                color: #159447;
                padding: 0px 8px;
            }
            """,
        )
        self.phone_connection_label.setVisible(False)


        self.theme_toggle_btn = QPushButton()

        self.theme_toggle_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        set_themed_stylesheet(
            self.theme_toggle_btn,
                """
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                    font-size: 19px;
                    font-weight: 900;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    background-color: #c7e6f7;
                }
                """
            )
        self.theme_toggle_btn.clicked.connect(
            self.toggle_theme_from_button
        )
        self.theme_toggle_btn.clicked.connect(
            lambda: QTimer.singleShot(0, self.refresh_notes)
        )
        self.theme_toggle_btn.clicked.connect(
            lambda: QTimer.singleShot(0, self.refresh_improvements)
        )

        self.update_theme_toggle_button()
        
        top_bar.addWidget(
            self.tools_toggle_btn,
            0,
            Qt.AlignmentFlag.AlignLeft
        )

        # Change this number to move the name/species block left/right
        top_bar.addSpacing(250)

        top_bar.addWidget(name_widget)
        top_bar.addStretch()
        top_bar.addWidget(self.save_status_label)
        top_bar.addWidget(self.phone_connection_label)
        top_bar.addWidget(self.theme_toggle_btn)

        outer_layout.addLayout(top_bar)

    def show_welcome_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Welcome")
        dialog.setFixedWidth(500)
        set_themed_stylesheet(
            dialog,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        label = QLabel(
            "Welcome to the DID Character Sheet.\n\n"
            "If this is your first time using the program, open "
            "'How to Use' from the Tools menu.\n\n"
            "The Tools menu is the gear icon in the top-left corner of the screen."
        )

        label.setWordWrap(True)
        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 15px;
                font-weight: 700;
                color: #25190f;
            }
            """,
        )

        layout.addWidget(label)

        dont_show_checkbox = QCheckBox(
            "Don't show this again"
        )

        set_themed_stylesheet(
            dont_show_checkbox,
            """
            QCheckBox {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 700;
                color: #25190f;
                spacing: 8px;
            }
            """,
        )

        layout.addWidget(
            dont_show_checkbox,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        ok_btn = QPushButton("OK")
        _style_fantasy_button(ok_btn)
        ok_btn.setFixedSize(100, 36)

        def accept_welcome():
            if dont_show_checkbox.isChecked():
                settings = QSettings(
                    "DID",
                    "CharacterSheet",
                )

                settings.setValue(
                    "welcome_disabled",
                    True,
                )

                settings.sync()

            dialog.accept()

        ok_btn.clicked.connect(
            accept_welcome
        )

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(ok_btn)
        button_row.addStretch()

        layout.addLayout(button_row)

        dialog.exec()

    def show_welcome_dialog_if_needed(self):
        settings = QSettings(
            "DID",
            "CharacterSheet",
        )

        welcome_disabled = settings.value(
            "welcome_disabled",
            False,
            type=bool,
        )

        if welcome_disabled:
            return

        self.show_welcome_dialog()

    def show_release_notes_dialog(
        self,
        version,
        release_notes,
    ):
        """Show the GitHub Release description once after an update.

        The body comes directly from the matching GitHub Release, so the
        release description written while publishing a version becomes the
        in-app "What's new" message for that version.
        """
        notes_text = str(release_notes or "").strip()
        if not notes_text:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("What's New")
        dialog.setFixedWidth(560)
        set_themed_stylesheet(
            dialog,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel(
            f"What's new in DID Character Sheet {version}"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 18px;
                font-weight: 900;
                color: #25190f;
                padding: 2px;
            }
            """,
        )
        layout.addWidget(title)

        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMinimumHeight(180)
        notes.setMaximumHeight(360)
        notes.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_themed_stylesheet(
            notes,
            """
            QTextBrowser {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 9px;
                padding: 10px 12px;
                color: #25190f;
                font-family: Georgia;
                font-size: 13px;
            }
            """,
        )

        try:
            notes.setMarkdown(notes_text)
        except Exception:
            notes.setPlainText(notes_text)

        layout.addWidget(notes)

        ok_btn = QPushButton("OK")
        _style_fantasy_button(ok_btn)
        ok_btn.setFixedSize(100, 36)
        ok_btn.clicked.connect(dialog.accept)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(ok_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        dialog.exec()

    def show_release_notes_if_needed(
        self,
        version,
        release_notes,
    ):
        version = str(version or "").strip()
        notes_text = str(release_notes or "").strip()

        if not version or not notes_text:
            return

        settings = QSettings(
            "DID",
            "CharacterSheet",
        )
        seen_version = settings.value(
            "release_notes_seen_version",
            "",
            type=str,
        )

        if seen_version == version:
            return

        self.show_release_notes_dialog(
            version,
            notes_text,
        )
        settings.setValue(
            "release_notes_seen_version",
            version,
        )
        settings.sync()

    def is_blank_default_character(
        self,
        character,
    ):
        try:
            recovered_data = (
                CharacterStorageSystem
                .character_to_dict(
                    character
                )
            )

            fresh_character = (
                Character.create_new_character()
            )

            fresh_data = (
                CharacterStorageSystem
                .character_to_dict(
                    fresh_character
                )
            )

            # Every new character has a different UUID.
            # The ID itself does not mean the player changed anything.
            recovered_data.pop(
                "id",
                None,
            )

            fresh_data.pop(
                "id",
                None,
            )

            return (
                recovered_data
                == fresh_data
            )

        except Exception:
            traceback.print_exc()
            return False

    def recent_character_paths(self):
        """Return up to five recently opened character files, newest first."""
        settings = QSettings(
            "DID",
            "CharacterSheet",
        )

        raw = settings.value(
            "recent_character_filepaths",
            [],
        )

        if isinstance(raw, str):
            raw = [raw]

        clean = []

        for filepath in raw or []:
            filepath = str(
                filepath or ""
            ).strip()

            if not filepath:
                continue

            filepath = os.path.abspath(
                filepath
            )

            normalized = os.path.normcase(
                filepath
            )

            if any(
                os.path.normcase(existing)
                == normalized
                for existing in clean
            ):
                continue

            if os.path.isfile(filepath):
                clean.append(
                    filepath
                )

        return clean[:50]


    def remember_last_opened_character(
        self,
        filepath=None,
    ):
        filepath = (
            filepath
            or self.current_character_filepath
        )

        if not filepath:
            return

        filepath = os.path.abspath(
            filepath
        )

        settings = QSettings(
            "DID",
            "CharacterSheet",
        )

        settings.setValue(
            "last_character_filepath",
            filepath,
        )

        recent = [
            path
            for path in self.recent_character_paths()
            if os.path.normcase(
                os.path.abspath(path)
            )
            != os.path.normcase(filepath)
        ]

        recent.insert(
            0,
            filepath,
        )

        settings.setValue(
            "recent_character_filepaths",
            recent[:50],
        )

        settings.sync()


    def clear_last_opened_character(
        self,
        filepath=None,
    ):
        settings = QSettings(
            "DID",
            "CharacterSheet",
        )

        remembered = str(
            settings.value(
                "last_character_filepath",
                "",
                type=str,
            )
            or ""
        ).strip()

        if filepath:
            filepath = os.path.abspath(
                filepath
            )

            try:
                same_file = (
                    os.path.normcase(
                        os.path.abspath(
                            remembered
                        )
                    )
                    == os.path.normcase(
                        filepath
                    )
                )
            except Exception:
                same_file = False

            if same_file:
                settings.remove(
                    "last_character_filepath"
                )

            recent = [
                path
                for path in self.recent_character_paths()
                if os.path.normcase(
                    os.path.abspath(path)
                )
                != os.path.normcase(
                    filepath
                )
            ]

            settings.setValue(
                "recent_character_filepaths",
                recent,
            )

        else:
            settings.remove(
                "last_character_filepath"
            )

        settings.sync()



    def load_last_opened_character_on_startup(self):
        """Load the last saved character when recovery has nothing newer."""
        settings = QSettings("DID", "CharacterSheet")
        filepath = str(settings.value(
            "last_character_filepath", "", type=str
        ) or "").strip()

        if not filepath:
            return False

        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            self.clear_last_opened_character(filepath)
            return False

        try:
            if not CharacterStorageSystem.looks_like_character_file(filepath):
                self.clear_last_opened_character(filepath)
                return False
            character = CharacterStorageSystem.import_character_file(filepath)
        except Exception:
            traceback.print_exc()
            self.clear_last_opened_character(filepath)
            return False

        self.character = character
        self.open_notes_for_session()
        self.current_character_filepath = filepath
        self.saved_character_name = self.character.name
        self.character_access_mode = "editable"

        self.supress_dirty = True
        try:
            self.reconnect_character_references()
            self.refresh_all()
        finally:
            self.supress_dirty = False

        self.unsaved_changes = False
        self.setWindowModified(False)
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False

        self.reset_undo_history(
            saved_character=self.character
        )

        if hasattr(self, "save_status_label"):
            self.save_status_label.setText("Saved")
        if hasattr(self, "update_history_button_state"):
            self.update_history_button_state()
        return True

    def check_for_recovery_on_startup(self):
        try:
            candidates = (
                CharacterStorageSystem
                .get_recovery_candidates()
            )

        except Exception:
            traceback.print_exc()
            candidates = []

        candidate = None

        # ------------------------------------------------------------
        # Ignore meaningless blank recovery files.
        # ------------------------------------------------------------

        for possible_candidate in candidates:
            recovery_character = (
                possible_candidate[
                    "character"
                ]
            )

            normal_filepath = (
                possible_candidate[
                    "normal_filepath"
                ]
            )

            recovery_filepath = (
                possible_candidate[
                    "recovery_filepath"
                ]
            )

            # A never-saved character which is still exactly the default
            # blank sheet contains nothing worth recovering.
            if (
                normal_filepath is None
                and self.is_blank_default_character(
                    recovery_character
                )
            ):
                try:
                    os.remove(
                        recovery_filepath
                    )

                except OSError:
                    pass

                continue

            candidate = (
                possible_candidate
            )

            break

        # Nothing meaningful to recover.
        if candidate is None:
            self.load_last_opened_character_on_startup()
            self.show_welcome_dialog_if_needed()
            return

        # ------------------------------------------------------------
        # Silently recover real unsaved work.
        # ------------------------------------------------------------

        recovery_character = (
            candidate[
                "character"
            ]
        )

        normal_filepath = (
            candidate[
                "normal_filepath"
            ]
        )

        self.character = (
            recovery_character
        )

        self.open_notes_for_session()

        self.current_character_filepath = (
            normal_filepath
        )

        if normal_filepath:
            self.remember_last_opened_character(normal_filepath)

        self.saved_character_name = (
            self.character.name
        )

        self.character_access_mode = (
            "editable"
        )

        self.supress_dirty = True

        try:
            self.reconnect_character_references()
            self.refresh_all()

        finally:
            self.supress_dirty = False

        # Keep the recovered work protected, but remember that the player
        # has not actually edited it during THIS session yet.
        self._silently_recovered = True
        self._recovered_state_edited = False
        self.unsaved_changes = True
        self.setWindowModified(True)

        saved_character = None

        if normal_filepath:
            try:
                saved_character = (
                    CharacterStorageSystem
                    .import_character_file(
                        normal_filepath
                    )
                )
            except Exception:
                saved_character = None

        self.reset_undo_history(
            saved_character=saved_character
        )

        if hasattr(
            self,
            "save_status_label",
        ):
            self.save_status_label.setText(
                "Unsaved"
            )

        self.show_welcome_dialog_if_needed()
    
    # ============================================================
    # REFRESH METHODS
    # ============================================================

    @preserve_sheet_scroll
    def refresh_all(self):
        self.character.validate()
        self.refresh_stats()
        self.hp_panel.rebuild_hearts()
        self.refresh_top_boxes()
        self.refresh_inventory()
        self.refresh_improvements()
        self.refresh_identity()
        self.refresh_notes()
        self.refresh_character_image()

    @preserve_sheet_scroll
    def refresh_after_improvement_change(self):
        """
        Refresh only the parts of the sheet that improvements can affect.

        Avoid rebuilding unrelated inventory and image widgets after
        every improvement or empowerment purchase.
        """
        self.character.validate()

        self.setUpdatesEnabled(False)

        try:
            self.refresh_stats()
            self.hp_panel.rebuild_hearts()
            self.refresh_top_boxes()
            self.refresh_improvements()
            self.refresh_identity()

            self.refresh_notes()

        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def refresh_outer_sheet_geometry(self):
        self.notes_frame.layout().activate()
        self.notes_frame.updateGeometry()

        self.content_widget.layout().activate()
        self.content_widget.updateGeometry()

        self.scroll.widget().updateGeometry()

        QApplication.processEvents()

    def is_character_sheet_anchor_locked(self):
        return getattr(self, "current_redesign_page", "character") != "notes"


    @qt_lifecycle_safe
    def lock_character_sheet_anchor(self):
        """Force the redesigned character sheet to remain at top-left.

        The character page has its own internal scrolling regions (Inventory,
        Improvements, Notes previews, etc.). The outer QScrollArea should not
        wander because a child widget gained focus, changed size, or Qt tried
        to keep something visible after a layout pass.
        """
        if not hasattr(self, "scroll"):
            return
        if not self.is_character_sheet_anchor_locked():
            return

        hbar = self.scroll.horizontalScrollBar()
        vbar = self.scroll.verticalScrollBar()

        if hbar.value() != 0:
            hbar.blockSignals(True)
            hbar.setValue(0)
            hbar.blockSignals(False)

        if vbar.value() != 0:
            vbar.blockSignals(True)
            vbar.setValue(0)
            vbar.blockSignals(False)


    # ============================================================
    # HORIZONTAL SHEET LOCK
    # ============================================================

    @qt_lifecycle_safe
    def keep_sheet_horizontally_locked(self, value=0):
        """
        Never allow the outer character sheet to move horizontally.

        QScrollArea may change its hidden horizontal scroll position when
        Notes are shown or a child editor receives focus, even when the
        horizontal scrollbar policy is ScrollBarAlwaysOff.
        """
        if not self.is_character_sheet_anchor_locked():
            return

        bar = self.scroll.horizontalScrollBar()

        if bar.value() == 0:
            return

        bar.blockSignals(True)
        bar.setValue(0)
        bar.blockSignals(False)


    @qt_lifecycle_safe
    def keep_sheet_vertically_locked(self, value=0):
        """Keep the outer character-sheet page pinned to the top.

        Inventory, Improvements and other inner sections have their own
        scrollers. When the normal character page is active, the outer
        application scroll area should not drift vertically because of focus
        changes or wheel events. Notes remain free to use the outer scroll.
        """
        if not self.is_character_sheet_anchor_locked():
            return

        bar = self.scroll.verticalScrollBar()
        if bar.value() == 0:
            return
        bar.blockSignals(True)
        bar.setValue(0)
        bar.blockSignals(False)


    def eventFilter(self, watched, event):
        scroll = getattr(self, "scroll", None)
        event_type = event.type()

        if scroll is not None and watched in {scroll, scroll.viewport(), getattr(self, "content_widget", None)}:
            if self.is_character_sheet_anchor_locked():
                if event_type in {
                    QEvent.Type.Wheel,
                    QEvent.Type.NativeGesture,
                }:
                    # Keep wheel/gesture scrolling inside the dedicated
                    # Inventory/Improvements scrollers. When the pointer is
                    # over ordinary sheet content or blank space, suppress
                    # outer-sheet scrolling completely.
                    return True

                if event_type == QEvent.Type.KeyPress:
                    try:
                        key = event.key()
                    except RuntimeError:
                        key = None
                    if key in {
                        Qt.Key.Key_Up,
                        Qt.Key.Key_Down,
                        Qt.Key.Key_Left,
                        Qt.Key.Key_Right,
                        Qt.Key.Key_PageUp,
                        Qt.Key.Key_PageDown,
                        Qt.Key.Key_Home,
                        Qt.Key.Key_End,
                        Qt.Key.Key_Space,
                    }:
                        return True

                if event_type in {
                    QEvent.Type.Resize,
                    QEvent.Type.Show,
                    QEvent.Type.LayoutRequest,
                }:
                    QTimer.singleShot(
                        0,
                        self.lock_character_sheet_anchor,
                    )

        return super().eventFilter(watched, event)


    # ============================================================
    # RESPONSIVE MAIN-SHEET WIDTH
    # ============================================================

    @qt_lifecycle_safe
    def lock_normal_inventory_improvement_widths(self):
        """
        Preserve the actual normal/maximized widths of Inventory and
        Improvements.

        When the app is narrowed (for example to half-screen), Qt may
        otherwise compress these two columns because the center section has
        large minimum-size children.  By capturing the widths after the
        initial maximized layout, the normal appearance is preserved and the
        outer QScrollArea scrolls horizontally when necessary.

        This deliberately does NOT use guessed pixel widths.
        """
        if self._main_column_widths_locked:
            return

        if not (
            hasattr(self, "inventory_frame")
            and hasattr(self, "improvements_frame")
            and hasattr(self, "content_widget")
        ):
            return

        inventory_width = self.inventory_frame.width()
        improvements_width = self.improvements_frame.width()

        # If Qt has not completed the first layout yet, try again shortly.
        if inventory_width <= 1 or improvements_width <= 1:
            QTimer.singleShot(
                100,
                self.lock_normal_inventory_improvement_widths,
            )
            return

        self._main_column_widths_locked = True

        self.inventory_frame.setMinimumWidth(inventory_width)
        self.improvements_frame.setMinimumWidth(improvements_width)

        # Keep the columns flexible on larger screens, but never let them
        # become narrower than their real normal widths.
        self.inventory_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.improvements_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # Let the content widget's layout-derived minimum width force the
        # outer scroll area to scroll instead of crushing these columns.
        self.content_widget.updateGeometry()
        self.scroll.widget().updateGeometry()


    # ============================================================
    # GENERAL HELPERS
    # ============================================================

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue

            child_layout = item.layout()
            if child_layout is not None:
                self.clear_layout(child_layout)

    # ============================================================
    # UNDO / REDO
    # ============================================================

    def _character_snapshot(
        self,
        character=None,
    ):
        character = (
            character
            if character is not None
            else self.character
        )

        return copy.deepcopy(
            CharacterStorageSystem
            .character_to_dict(
                character
            )
        )


    def update_undo_redo_button_state(self):
        undo_button = getattr(
            self,
            "undo_btn",
            None,
        )

        redo_button = getattr(
            self,
            "redo_btn",
            None,
        )

        if undo_button is not None:
            undo_button.setEnabled(
                bool(
                    getattr(
                        self,
                        "_undo_stack",
                        [],
                    )
                )
            )

        if redo_button is not None:
            redo_button.setEnabled(
                bool(
                    getattr(
                        self,
                        "_redo_stack",
                        [],
                    )
                )
            )


    def reset_undo_history(
        self,
        saved_character=None,
        treat_current_as_clean=False,
    ):
        """
        Start a fresh undo chain for the active character.

        Undo never crosses from one loaded character into another.
        """
        self._undo_stack = []
        self._redo_stack = []

        self._undo_last_snapshot = (
            self._character_snapshot()
        )

        if saved_character is not None:
            self._saved_character_snapshot = (
                self._character_snapshot(
                    saved_character
                )
            )
        elif treat_current_as_clean:
            self._saved_character_snapshot = (
                self._character_snapshot()
            )
        else:
            self._saved_character_snapshot = None

        self.update_undo_redo_button_state()


    def _record_undo_state(self):
        if getattr(
            self,
            "_restoring_undo_redo",
            False,
        ):
            return

        current_snapshot = (
            self._character_snapshot()
        )

        previous_snapshot = getattr(
            self,
            "_undo_last_snapshot",
            None,
        )

        if previous_snapshot is None:
            self._undo_last_snapshot = (
                current_snapshot
            )
            return

        if current_snapshot == previous_snapshot:
            return

        self._undo_stack.append(
            copy.deepcopy(
                previous_snapshot
            )
        )

        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack = (
                self._undo_stack[
                    -self._undo_limit:
                ]
            )

        self._redo_stack.clear()

        self._undo_last_snapshot = (
            current_snapshot
        )

        self.update_undo_redo_button_state()


    def _sync_saved_state_after_history_move(self):
        current_snapshot = (
            self._character_snapshot()
        )

        self._undo_last_snapshot = (
            copy.deepcopy(
                current_snapshot
            )
        )

        matches_saved = (
            self._saved_character_snapshot
            is not None
            and current_snapshot
            == self._saved_character_snapshot
        )

        self.unsaved_changes = (
            not matches_saved
        )

        if matches_saved:
            if hasattr(
                self,
                "_recovery_write_timer",
            ):
                self._recovery_write_timer.stop()
            if hasattr(self, "_auto_save_timer"):
                self._auto_save_timer.stop()
            if hasattr(self, "_idle_save_timer"):
                self._idle_save_timer.stop()

            try:
                CharacterStorageSystem.delete_recovery_file(
                    self.character
                )
            except Exception:
                traceback.print_exc()

            if hasattr(
                self,
                "save_status_label",
            ):
                self.save_status_label.setText(
                    "Saved"
                    if self.current_character_filepath
                    else "New"
                )

        else:
            if getattr(
                self,
                "_silently_recovered",
                False,
            ):
                self._recovered_state_edited = True

            if hasattr(
                self,
                "save_status_label",
            ):
                self.save_status_label.setText(
                    "Unsaved"
                )

            self.schedule_recovery_write()
            self.schedule_auto_save()


    def _restore_undo_snapshot(
        self,
        snapshot,
    ):
        self._restoring_undo_redo = True
        self.supress_dirty = True

        try:
            self.character = (
                CharacterStorageSystem
                .character_from_dict(
                    copy.deepcopy(
                        snapshot
                    )
                )
            )

            self.reconnect_character_references()
            self.refresh_all()

        finally:
            self.supress_dirty = False
            self._restoring_undo_redo = False

        self._sync_saved_state_after_history_move()
        self.update_undo_redo_button_state()


    def _history_transition_summary(
        self,
        before_snapshot,
        after_snapshot,
    ):
        """Return one compact human-readable description of a state change."""
        try:
            before_character = (
                CharacterStorageSystem
                .character_from_dict(
                    copy.deepcopy(
                        before_snapshot
                    )
                )
            )

            after_character = (
                CharacterStorageSystem
                .character_from_dict(
                    copy.deepcopy(
                        after_snapshot
                    )
                )
            )

            changes = (
                self.describe_restore_differences(
                    before_character,
                    after_character,
                )
            )

        except Exception:
            traceback.print_exc()
            return "Character change"

        meaningful = [
            str(change).strip()
            for change in (changes or [])
            if str(change).strip()
            and str(change).strip()
            != "No meaningful differences."
        ]

        if not meaningful:
            return "Character change"

        first = meaningful[0]

        if len(meaningful) > 1:
            first += (
                f" (+{len(meaningful) - 1} more)"
            )

        return first


    def show_recent_change_indicator(
        self,
        text,
    ):
        """Show a tiny temporary Undo/Redo result beside the top controls."""
        host = (
            self.centralWidget()
            if (
                hasattr(self, "centralWidget")
                and self.centralWidget() is not None
            )
            else self
        )

        old_indicator = getattr(
            self,
            "_recent_change_indicator",
            None,
        )

        if old_indicator is not None:
            try:
                old_indicator.hide()
                old_indicator.deleteLater()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

        indicator = QLabel(
            str(text),
            host,
        )

        indicator.setObjectName(
            "RecentChangeIndicator"
        )

        indicator.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        set_themed_stylesheet(
            indicator,
            """
            QLabel#RecentChangeIndicator {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 8px;
                color: #25190f;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 700;
                padding: 5px 9px;
            }
            """,
        )

        indicator.adjustSize()

        anchor_widget = getattr(
            self,
            "undo_redo_frame",
            None,
        )

        if anchor_widget is not None:
            try:
                anchor_pos = anchor_widget.mapTo(
                    host,
                    QPoint(
                        0,
                        anchor_widget.height() + 5,
                    ),
                )

                x = anchor_pos.x()
                y = anchor_pos.y()

            except Exception:
                x = max(
                    8,
                    host.width()
                    - indicator.width()
                    - 130,
                )
                y = 52
        else:
            x = max(
                8,
                host.width()
                - indicator.width()
                - 130,
            )
            y = 52

        x = max(
            8,
            min(
                x,
                host.width()
                - indicator.width()
                - 8,
            ),
        )

        y = max(
            8,
            min(
                y,
                host.height()
                - indicator.height()
                - 8,
            ),
        )

        indicator.move(
            x,
            y,
        )

        indicator.show()
        indicator.raise_()

        self._recent_change_indicator = (
            indicator
        )

        def hide_if_current():
            if (
                getattr(
                    self,
                    "_recent_change_indicator",
                    None,
                )
                is not indicator
            ):
                return

            try:
                indicator.hide()
                indicator.deleteLater()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

            self._recent_change_indicator = None

        QTimer.singleShot(
            1800,
            hide_if_current,
        )


    def undo_character_change(self):
        if self.block_if_readonly():
            return

        if not self._undo_stack:
            return

        current_snapshot = (
            self._character_snapshot()
        )

        target_snapshot = (
            self._undo_stack.pop()
        )

        self._redo_stack.append(
            copy.deepcopy(
                current_snapshot
            )
        )

        if len(self._redo_stack) > self._undo_limit:
            self._redo_stack = (
                self._redo_stack[
                    -self._undo_limit:
                ]
            )

        change_summary = (
            self._history_transition_summary(
                current_snapshot,
                target_snapshot,
            )
        )

        self._restore_undo_snapshot(
            target_snapshot
        )

        self.show_recent_change_indicator(
            f"Undid: {change_summary}"
        )


    def redo_character_change(self):
        if self.block_if_readonly():
            return

        if not self._redo_stack:
            return

        current_snapshot = (
            self._character_snapshot()
        )

        target_snapshot = (
            self._redo_stack.pop()
        )

        self._undo_stack.append(
            copy.deepcopy(
                current_snapshot
            )
        )

        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack = (
                self._undo_stack[
                    -self._undo_limit:
                ]
            )

        change_summary = (
            self._history_transition_summary(
                current_snapshot,
                target_snapshot,
            )
        )

        self._restore_undo_snapshot(
            target_snapshot
        )

        self.show_recent_change_indicator(
            f"Redid: {change_summary}"
        )


    def schedule_recovery_write(self):
        if getattr(
            self,
            "supress_dirty",
            False,
        ):
            return

        if self.is_readonly_character():
            return

        if not self.unsaved_changes:
            return

        self._recovery_write_timer.start()


    def write_recovery_snapshot(self):
        if getattr(
            self,
            "supress_dirty",
            False,
        ):
            return

        if self.is_readonly_character():
            return

        if not self.unsaved_changes:
            return

        try:
            CharacterStorageSystem.write_recovery_file(
                self.character
            )

        except Exception:
            traceback.print_exc()


    def discard_current_recovery(self):
        if hasattr(
            self,
            "_recovery_write_timer",
        ):
            self._recovery_write_timer.stop()

        try:
            CharacterStorageSystem.delete_recovery_file(
                self.character
            )

        except Exception:
            traceback.print_exc()

 
    def mark_dirty(self, auto_save=False):
        if getattr(
            self,
            "supress_dirty",
            False,
        ):
            return

        self._record_undo_state()

        if getattr(
            self,
            "_silently_recovered",
            False,
        ):
            self._recovered_state_edited = True

        self.unsaved_changes = True
        self.setWindowModified(True)

        if hasattr(
            self,
            "save_status_label",
        ):
            self.save_status_label.setText(
                "Unsaved"
            )
            self.save_status_label.setToolTip(
                "Changes pending automatic save"
                if self.current_character_filepath
                else "Save this new character once to enable autosave"
            )

        self.schedule_recovery_write()

        # Campaign characters send one debounced safe-state snapshot.
        schedule_campaign_state_sync(self)

        # The old auto_save=True callers are included, but no longer force
        # a synchronous disk write for every click/keystroke.
        self.schedule_auto_save()

    def schedule_auto_save(self):
        """Quietly persist a saved character after the last edit settles.

        New characters need their initial manual Save to choose a name/path.
        A restored historical version is deliberately *not* overwritten
        automatically; the user must commit it with Save.
        """
        if (getattr(self, "supress_dirty", False)
                or getattr(self, "_restoring_undo_redo", False)
                or getattr(self, "_history_restore_pending", False)
                or self.is_readonly_character()
                or not self.unsaved_changes
                or not self.current_character_filepath):
            return
        timer = getattr(self, "_auto_save_timer", None)
        if timer is not None:
            timer.start()
        idle_timer = getattr(self, "_idle_save_timer", None)
        if idle_timer is not None:
            idle_timer.start()  # reset after each edit; fires after 60 seconds idle

    def auto_save_character(self):
        """
        Automatically save changes only after the character
        has already been manually saved at least once.

        Autosave must never interrupt the user with setup questions.
        If the character cannot be saved yet, simply leave it marked
        as Unsaved until a later autosave or manual save.
        """
        if self.is_readonly_character():
            return

        if not self.unsaved_changes:
            return

        if not self.current_character_filepath:
            return

        if getattr(self, "_history_restore_pending", False):
            return

        # Do not launch prompts or interrupt in-progress character creation.
        if not self.character.name.strip():
            return
        if getattr(self, "_auto_save_in_progress", False):
            self.schedule_auto_save()
            return

        self._auto_save_in_progress = True
        try:
            self.save_character_from_ui(quiet=True)
        except Exception as error:
            # A background timer must never open a modal dialog or cause
            # a traceback to disrupt the running character sheet.
            traceback.print_exc()
            if hasattr(self, "save_status_label"):
                self.save_status_label.setText("Unsaved")
                self.save_status_label.setToolTip(f"Automatic save failed: {error}")
        finally:
            self._auto_save_in_progress = False

    def open_notes_for_session(self):
        """Start loaded notes expanded; collapsing is session-only."""
        notes_data = getattr(self.character, "notes", None)
        if notes_data is None:
            return

        for note in getattr(notes_data, "list_of_notes", []):
            note.expanded = True


    def _session_roll_history_key(self, character=None):
        """Stable in-memory key for one character during this app session."""
        character = character or self.character
        character_id = str(getattr(character, "id", "") or "").strip()
        if character_id:
            return character_id
        return f"runtime:{id(character)}"


    def _remember_session_roll_history(self, character=None):
        """Mirror the character's current roll history into session memory."""
        character = character or self.character
        key = self._session_roll_history_key(character)
        self._session_roll_histories[key] = list(
            getattr(character, "roll_history", []) or []
        )


    def _restore_session_roll_history(self, character=None):
        """Restore only rolls made during this running app session."""
        character = character or self.character
        key = self._session_roll_history_key(character)
        character.roll_history = list(
            self._session_roll_histories.get(key, [])
        )


    def build_dm_shared_character_state(self):
        """Return the deliberately whitelisted character state safe for DM sync."""
        return build_shared_character_state(
            self.character
        )


    def recent_shared_roll_events(self):
        """Return structured rolls captured during this running app session."""
        return copy.deepcopy(
            list(
                getattr(
                    self,
                    "_shared_roll_events",
                    [],
                )
            )
        )


    def take_shared_roll_events(self):
        """Return and clear pending structured roll events for a future sync layer."""
        events = self.recent_shared_roll_events()
        queue = getattr(
            self,
            "_shared_roll_events",
            None,
        )
        if queue is not None:
            queue.clear()
        return events


    def set_shared_roll_event_callback(self, callback=None):
        """Install an optional transport callback without coupling dice to networking."""
        self._shared_roll_event_callback = (
            callback
            if callable(callback)
            else None
        )


    def _record_shared_roll_event(
        self,
        summary,
        character=None,
    ):
        """Convert one completed roll into the future DM-dashboard event format."""
        character = character or self.character
        event = build_shared_roll_event(
            character,
            summary,
        )

        queue = getattr(
            self,
            "_shared_roll_events",
            None,
        )
        if queue is None:
            self._shared_roll_events = deque(maxlen=200)
            queue = self._shared_roll_events

        queue.append(event)

        callback = getattr(
            self,
            "_shared_roll_event_callback",
            None,
        )
        if callable(callback):
            callback(
                copy.deepcopy(event)
            )

        return event


    def reconnect_character_references(self):
        self._restore_session_roll_history(self.character)
        self._refresh_session_roll_history_dialog()
        for row in self.stat_rows.values():
            row.character = self.character

        self.hp_panel.character = self.character

        self.at_box.character = self.character

        # Switching/new/loading a character also switches its campaign link.
        restore_campaign_connection(self)


    def capitalize_first(self, text):
        if not text:
            return text

        return text[0].upper() + text[1:]


    def capitalize_sentences(self, text):
        if not text:
            return text

        result = ""
        capitalize_next = True

        for char in text:
            if capitalize_next and char.isalpha():
                result += char.upper()
                capitalize_next = False
            else:
                result += char

            if char in ".!?":
                capitalize_next = True

        return result

    def setup_keyboard_shortcuts(self):
        # save
        self.save_shortcut = QShortcut(
            QKeySequence.StandardKey.Save,
            self,
        )

        self.save_shortcut.activated.connect(
            self.save_current_character
        )

        # New character
        self.new_shortcut = QShortcut(
            QKeySequence.StandardKey.New,
            self,
        )
        self.new_shortcut.activated.connect(
            self.new_character_from_ui
        )


        # Open/Load character
        self.open_shortcut = QShortcut(
            QKeySequence.StandardKey.Open,
            self,
        )
        self.open_shortcut.activated.connect(
            self.load_character_from_ui
        )

        # Edit abilities
        self.abilities_shortcut = QShortcut(
            QKeySequence("Ctrl+E"),
            self,
        )
        self.abilities_shortcut.activated.connect(
            self.open_ability_editor
        )

        # Undo / Redo
        self.undo_shortcut = QShortcut(
            QKeySequence.StandardKey.Undo,
            self,
        )
        self.undo_shortcut.activated.connect(
            self.undo_character_change
        )

        self.redo_shortcut = QShortcut(
            QKeySequence("Ctrl+Y"),
            self,
        )
        self.redo_shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )
        self.redo_shortcut.activated.connect(
            self.redo_character_change
        )

        self.redo_alt_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+Z"),
            self,
        )
        self.redo_alt_shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )
        self.redo_alt_shortcut.activated.connect(
            self.redo_character_change
        )

        self.undo_shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )

        # Ctrl+O already loads a character. Ctrl+L is an extra alias.
        self.load_alt_shortcut = QShortcut(
            QKeySequence("Ctrl+L"),
            self,
        )
        self.load_alt_shortcut.activated.connect(
            self.load_character_from_ui
        )

    def save_current_character(self):
        self.save_character_from_ui()
        


    # ============================================================
    # CHARACTER CREATION / SAVE / LOAD
    # ============================================================

    def new_character_from_template_from_ui(self):
        discard_old_recovery = False
        
        if (
            self.unsaved_changes
            and getattr(
                self,
                "_silently_recovered",
                False,
            )
            and not getattr(
                self,
                "_recovered_state_edited",
                False,
            )
        ):

            discard_old_recovery = True

        elif self.unsaved_changes:
            if ask_yes_no(
                self,
                "New Character From Template",
                (
                    "Creating a new character from a template "
                    "will replace the current character.\n"
                    "Save current character first?"
                ),
                yes_text="Save",
                no_text="Don't Save",
            ):
                self.save_current_character()

                if self.unsaved_changes:
                    return
            else:
                discard_old_recovery = True

        template = load_template_from_file(
            parent=self
        )

        if template is None:
            return

        rules = template.rules

        if not confirm_create_character_from_template(
            self,
            template,
        ):
            return

        # --------------------------------------------------------
        # Create the new sheet and apply the template BEFORE the
        # guided creation begins.
        # --------------------------------------------------------
        character = (
            Character.create_new_character()
        )

        try:
            apply_template_to_character(
                character,
                template,
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Template Error",
                (
                    "Could not create the character "
                    "from this template.\n\n"
                    f"{error}"
                ),
            )
            return

        character.validate()

        if discard_old_recovery:
            self.discard_current_recovery()

        self.character = character

        self.current_character_filepath = None
        self.saved_character_name = None
        self.character_access_mode = "editable"

        # Remember which template is being used during creation.
        self.active_character_template = template

        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False

        self.reconnect_character_references()
        self.refresh_all()

        self.reset_undo_history()
        self.mark_dirty()

        if hasattr(
            self,
            "save_status_label",
        ):
            self.save_status_label.setText(
                "Unsaved"
            )

        QTimer.singleShot(
            0,
            self.start_guided_tutorial,
        )        

        # --------------------------------------------------------
        # Replace current sheet
        # --------------------------------------------------------

        if discard_old_recovery:
            self.discard_current_recovery()
        self.character = character

        self.current_character_filepath = None
        self.saved_character_name = None
        self.character_access_mode = "editable"
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False

        self.reconnect_character_references()
        self.refresh_all()
        self.reset_undo_history()
        self.mark_dirty()

        if hasattr(self, "save_status_label"):
            self.save_status_label.setText("Unsaved")
        
    def new_character_wizard_from_ui(self):
        """Choose standalone or campaign rules before starting character creation."""
        from campaign_creation_wizard import CampaignCreationWizard
        CampaignCreationWizard(self).exec()

    def new_character_from_ui(self):
        discard_old_recovery = False
        
        if (
            self.unsaved_changes
            and getattr(
                self,
                "_silently_recovered",
                False,
            )
            and not getattr(
                self,
                "_recovered_state_edited",
                False,
            )
        ):
            discard_old_recovery = True

        elif self.unsaved_changes:
            if ask_yes_no(
                self,
                "New Character",
                (
                    "Create a new character?\n"
                    "Save current character first?"
                ),
                yes_text="Save",
                no_text="Don't Save",
            ):
                self.save_current_character()

                if self.unsaved_changes:
                    return

            else:
                discard_old_recovery = True

        new_character = (
            Character.create_new_character()
        )

        if discard_old_recovery:
            self.discard_current_recovery()

        self.character = new_character
        
        self.current_character_filepath = None
        self.saved_character_name = None
        self.character_access_mode = "editable"
        
        self.active_character_template = None
        
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False

        self.reconnect_character_references()
        self.refresh_all()
        
        # Merely opening a blank New Character is not itself an edit.
        self.reset_undo_history(
            treat_current_as_clean=True
        )
        self.unsaved_changes = False
        self.setWindowModified(False)

        if hasattr(
            self,
            "save_status_label",
        ):
            self.save_status_label.setText(
                "New"
            )

    def save_character_from_ui(self, quiet=False):
        # Background autosaves must never open a modal warning dialog.
        if quiet and self.is_readonly_character():
            return
        if not quiet and self.block_if_readonly():
            return

        # ------------------------------------------------------------
        # Creation-rule validation
        # ------------------------------------------------------------
        if (
            getattr(
                self.character,
                "creation_rules_active",
                False,
            )
            and getattr(
                self.character,
                "creation_species_mode",
                "normal",
            ) == "required"
            and not self.character.improvements.has_species_improvement()
        ):
            if not quiet:
                QMessageBox.warning(
                    self,
                    "Species Required",
                    (
                        "This character's Creation Rules "
                        "require a Species.\n\n"
                        "Add a Species before saving "
                        "the character."
                    ),
                )
            return

        # Explicit saves prune blank notes. Background autosaves must not
        # delete a newly created note before the player starts typing.
        if not quiet:
            self.cleanup_empty_notes()

        notes_reordered = False

        if hasattr(
            self,
            "sort_notes_longest_first",
        ):
            notes_reordered = (
                self.sort_notes_longest_first()
            )

        # ------------------------------------------------------------
        # Character must have a name
        # ------------------------------------------------------------

        if not self.character.name.strip():
            if quiet:
                return
            name, ok = fantasy_text_input(
                self,
                "Save Character",
                "Character name:",
                accept_text="Save",
            )

            if not ok or not name.strip():
                return

            self.character.name = name.strip()

        CharacterStorageSystem.ensure_save_dir()

        old_filepath = self.current_character_filepath

        # ------------------------------------------------------------
        # Helper for comparing Windows paths safely
        # ------------------------------------------------------------

        def same_path(path_a, path_b):
            if not path_a or not path_b:
                return False

            return (
                os.path.normcase(os.path.abspath(path_a))
                == os.path.normcase(os.path.abspath(path_b))
            )

        # ------------------------------------------------------------
        # The filename should ALWAYS match the current character name
        # ------------------------------------------------------------

        base_filename = CharacterStorageSystem.save_filename(
            self.character.name
        )

        if old_filepath:
            save_folder = os.path.dirname(old_filepath)
        else:
            save_folder = CharacterStorageSystem.SAVE_DIR

        desired_filepath = os.path.join(
            save_folder,
            base_filename + ".didchar",
        )

        # ------------------------------------------------------------
        # If the desired filename is already THIS character's file,
        # simply overwrite it.
        # ------------------------------------------------------------

        if same_path(
            desired_filepath,
            old_filepath,
        ):
            filepath = old_filepath

        else:
            filepath = desired_filepath

            # --------------------------------------------------------
            # Do not overwrite a DIFFERENT character that already
            # has the desired filename.
            # --------------------------------------------------------

            if os.path.exists(filepath):
                number = 2

                while True:
                    candidate = os.path.join(
                        save_folder,
                        f"{base_filename}_{number}.didchar",
                    )

                    # Existing old file is allowed because it belongs
                    # to the character currently being saved.
                    if (
                        not os.path.exists(candidate)
                        or same_path(
                            candidate,
                            old_filepath,
                        )
                    ):
                        filepath = candidate
                        break

                    number += 1

        # ------------------------------------------------------------
        # Save the new/current file
        # ------------------------------------------------------------

        if hasattr(self, "save_status_label"):
            self.save_status_label.setText("Saving...")
            QApplication.processEvents()

        try:
            CharacterStorageSystem.export_character_file(
                self.character,
                filepath,
            )

        except Exception as error:
            if quiet:
                traceback.print_exc()
            else:
                QMessageBox.critical(
                    self,
                    "Save Failed",
                    f"Could not save character:\n\n{error}",
                )

            if hasattr(self, "save_status_label"):
                self.save_status_label.setText("Unsaved")
                if quiet:
                    self.save_status_label.setToolTip(f"Automatic save failed: {error}")
            return

        if (
            old_filepath
            and old_filepath != filepath
        ):
            try:
                CharacterStorageSystem.migrate_character_history(
                    old_filepath,
                    filepath,
                )
            except Exception:
                pass
        # ------------------------------------------------------------
        # Store the successfully saved version in character history.
        # History failure must never prevent or undo the real save.
        # ------------------------------------------------------------

        try:
            CharacterStorageSystem.backup_character_file(
                self.character,
                filepath,
                preserve_reversion=getattr(
                    self,
                    "_history_restore_pending",
                    False,
                ),
            )

        except Exception:
            # History is an internal safety layer. The normal character save
            # already succeeded, so do not interrupt the player.
            traceback.print_exc()
        # ------------------------------------------------------------
        # If the filename changed, delete the old file only AFTER
        # the new file was successfully written.
        # ------------------------------------------------------------

        if (
            old_filepath
            and not same_path(
                old_filepath,
                filepath,
            )
            and os.path.exists(old_filepath)
        ):
            try:
                os.remove(old_filepath)

            except Exception as error:
                if quiet:
                    traceback.print_exc()
                else:
                    QMessageBox.warning(
                        self,
                        "Old File Not Removed",
                        (
                            "The character was saved successfully under "
                            "the correct filename, but the old character "
                            "file could not be removed.\n\n"
                            f"{error}"
                        ),
                    )

        # ------------------------------------------------------------
        # Successful save
        # ------------------------------------------------------------

        self.current_character_filepath = filepath
        self.remember_last_opened_character(filepath)

        current_saved_snapshot = (
            self._character_snapshot()
        )

        self._saved_character_snapshot = (
            copy.deepcopy(
                current_saved_snapshot
            )
        )

        self._undo_last_snapshot = (
            copy.deepcopy(
                current_saved_snapshot
            )
        )

        self.unsaved_changes = False
        self.setWindowModified(False)
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False

        if notes_reordered:
            QTimer.singleShot(
                0,
                self.refresh_notes,
            )

        if hasattr(self, "_recovery_write_timer",):
            self._recovery_write_timer.stop()
        if hasattr(self, "_auto_save_timer"):
            self._auto_save_timer.stop()
        if hasattr(self, "_idle_save_timer"):
            self._idle_save_timer.stop()

        try:
            CharacterStorageSystem.delete_recovery_file(self.character)
        except Exception:
            traceback.print_exc()

        if hasattr(self, "save_status_label"):
            # A fixed short label avoids shifting the phone indicator next
            # to Saved every time an automatic write completes.
            self.save_status_label.setText("Saved")
            self.save_status_label.setToolTip("All changes saved to disk")

        if hasattr(
            self,
            "update_history_button_state",
        ):
            self.update_history_button_state()

        if getattr(self, "_pending_campaign_character", None):
            self._link_pending_wizard_character_after_save()
        
            
    def _link_pending_wizard_character_after_save(self):
        """A successful local Save is the commit point for a wizard campaign link."""
        pending = getattr(self, '_pending_campaign_character', None)
        if not isinstance(pending, dict) or not self.current_character_filepath or self.unsaved_changes:
            return
        if str(pending.get('character_id')) != str(getattr(self.character, 'id', '')):
            return
        # The quick autosave may write the empty starter before the player has
        # supplied a name. Never submit an unnamed character to the DM.
        character_name = str(getattr(self.character, 'name', '') or '').strip()
        if not character_name or character_name.casefold() == 'unnamed character':
            return
        try:
            from campaign_runtime import (campaign_client, restore_campaign_connection,
                schedule_campaign_state_sync, sync_current_character_now)
            from campaign_privacy import build_window_shared_state
            from campaign_party import build_window_party_state, upload_party_state
            client = campaign_client(self)
            if client is None:
                raise RuntimeError('Campaign service is not configured.')
            campaign_id = pending['campaign_id']
            from campaign_template import CampaignTemplateService
            from campaign_admission import admit_character
            campaign = CampaignTemplateService(client).get_campaign(campaign_id)
            invite_code = str(pending.get('invite_code') or '').strip()
            if invite_code:
                # Membership was created before character selection. Use the
                # saved character's name once it is known, without rejoining a
                # different campaign or exposing additional permissions.
                CampaignTemplateService(client).join_campaign(
                    invite_code, str(getattr(self.character, 'name', '') or 'Player')
                )
            admission = admit_character(
                self, campaign, client,
                build_window_shared_state(self, campaign_id=campaign_id),
            )
            if admission.status == 'approval_pending':
                del self._pending_campaign_character
                from types import SimpleNamespace
                from campaign_role_ui import _show_campaign_approval_notice
                _show_campaign_approval_notice(self, SimpleNamespace(
                    character_name=str(getattr(self.character, 'name', 'Character') or 'Character'),
                    mismatches=admission.mismatches,
                ))
                return
            if admission.status == 'linked_elsewhere':
                raise RuntimeError('This character is already linked to another campaign.')
            upload_party_state(client, campaign_id, admission.record_id,
                build_window_party_state(self, campaign_id=campaign_id))
            restore_campaign_connection(self)
            schedule_campaign_state_sync(self)
            sync_current_character_now(self)
        except Exception as error:
            QMessageBox.warning(self, 'Campaign Link Pending',
                'The character was saved locally, but campaign linking failed. '
                'Save again to retry.\n\n' + str(error))
            return
        del self._pending_campaign_character
        QMessageBox.information(self, 'Character Linked',
            'The character was saved and linked to ' + pending.get('campaign_name', 'the campaign') + '.')

    def load_character_from_ui(self):
        discard_old_recovery = False
        if (
            self.unsaved_changes
            and getattr(
                self,
                "_silently_recovered",
                False,
            )
            and not getattr(
                self,
                "_recovered_state_edited",
                False,
            )
        ):
            # The program restored this state automatically. The player has
            # not changed it in this session, so choosing another character
            # is enough intent to move away from it. The recovery itself is
            # deleted only after the replacement succeeds.
            discard_old_recovery = True

        elif self.unsaved_changes:
            if ask_yes_no(
                self,
                "Unsaved Changes",
                (
                    "Loading another character will replace the current character.\n"
                    "Save current character first?"
                ),
                yes_text="Save",
                no_text="Don't Save",
            ):
                self.save_current_character()

                if self.unsaved_changes:
                    return
            else:
                discard_old_recovery = True

        CharacterStorageSystem.ensure_save_dir()
        save_dir = os.path.abspath(CharacterStorageSystem.SAVE_DIR)

        def read_character_records():
            paths = []
            for root, dirs, files in os.walk(save_dir):
                dirs[:] = [folder for folder in dirs if folder != "_history"]
                for name in files:
                    if name.lower().endswith(".didchar"):
                        path = os.path.join(root, name)
                        try:
                            paths.append((os.path.getmtime(path), path))
                        except OSError:
                            continue
            records = []
            for _, path in sorted(paths, reverse=True):
                try:
                    if not CharacterStorageSystem.looks_like_character_file(path):
                        continue
                    character = CharacterStorageSystem.import_character_file(path)
                    entry = character.image.current_image()
                    portrait = (entry.get("display") or entry.get("original")) if isinstance(entry, dict) else entry
                    records.append({"filepath": path,
                        "name": str(character.name or os.path.splitext(os.path.basename(path))[0].replace("_", " ")).strip(),
                        "species": str(getattr(character, "species_name", "") or "").strip(),
                        "used_ip": int(character.progression.used_IP),
                        "total_ip": int(character.progression.current_IP),
                        "portrait": portrait})
                except Exception:
                    continue
            return records

        character_records = run_loading_task(self, "Loading characters…", read_character_records)
        if not character_records:
            QMessageBox.information(self, "No Characters Found",
                                    f"No readable saved characters were found.\n\nCharacter folder:\n{save_dir}")
            return

        recent_paths = (
            self.recent_character_paths()
        )

        records_by_path = {
            os.path.normcase(
                os.path.abspath(
                    record["filepath"]
                )
            ): record
            for record in character_records
        }

        ordered_records = []
        used_paths = set()

        # Characters with recorded opening history come first,
        # newest opening first.
        for filepath in recent_paths:
            normalized = os.path.normcase(
                os.path.abspath(
                    filepath
                )
            )

            record = records_by_path.get(
                normalized
            )

            if (
                record is not None
                and normalized not in used_paths
            ):
                ordered_records.append(
                    record
                )

                used_paths.add(
                    normalized
                )

        # Characters that have never been opened since Recent Characters
        # was introduced follow in the save-file order already calculated
        # above. Once opened, they move into the true recent order.
        for record in character_records:
            normalized = os.path.normcase(
                os.path.abspath(
                    record["filepath"]
                )
            )

            if normalized in used_paths:
                continue

            ordered_records.append(
                record
            )

            used_paths.add(
                normalized
            )

        # ============================================================
        # FANTASY PICKER
        # ============================================================

        dialog = FantasyLoadCharacterDialog(
            ordered_records,
            self,
            initial_visible_count=5,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        filepath = dialog.selected_filepath()

        if not filepath:
            return

        return self.load_character_from_path(
            filepath, skip_unsaved_prompt=True,
            discard_old_recovery=discard_old_recovery,
        )

    def load_character_from_path(self, filepath, *, skip_unsaved_prompt=False,
                                 discard_old_recovery=False):
        """Open one explicitly chosen saved character, respecting unsaved edits.

        The campaign character chooser uses this same state-transition path as
        the regular Load Character dialog. Never publish another open sheet.
        """
        if not filepath or not os.path.isfile(filepath):
            QMessageBox.warning(self, "Character Unavailable", "The selected character file was not found.")
            return False
        if not CharacterStorageSystem.looks_like_character_file(filepath):
            QMessageBox.warning(self, "Invalid Character", "The selected file is not a DID character.")
            return False
        if not skip_unsaved_prompt and getattr(self, "unsaved_changes", False):
            decision = QMessageBox.question(
                self, "Save Current Character?",
                "Save your current character before opening the selected campaign character?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                return False
            if decision == QMessageBox.StandardButton.Save:
                self.save_current_character()
                if self.unsaved_changes:
                    return False
            else:
                discard_old_recovery = True
        # ============================================================
        # LOAD
        # ============================================================

        try:
            character = run_loading_task(self, "Opening character…",
                lambda: CharacterStorageSystem.import_character_file(filepath))

        except Exception as error:
            QMessageBox.critical(
                self,
                "Load Failed",
                (
                    "Could not load character:\n\n"
                    f"{error}"
                ),
            )
            return

        if discard_old_recovery:
            self.discard_current_recovery()
        self.character = character
        self.open_notes_for_session()

        self.current_character_filepath = filepath
        self.remember_last_opened_character(filepath)
        self.saved_character_name = self.character.name

        self.supress_dirty = True

        try:
            self.reconnect_character_references()
            self.refresh_all()
        finally:
            self.supress_dirty = False
            
        self.unsaved_changes = False
        self.setWindowModified(False)
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False

        self.reset_undo_history(
            saved_character=self.character
        )

        if hasattr(self, "save_status_label"):
            self.save_status_label.setText("Saved")

        if hasattr(
            self,
            "update_history_button_state",
        ):
            self.update_history_button_state()
        return True

    def describe_restore_differences(
        self,
        current_character,
        target_character,
    ):
        """Describe what would change if the target version were restored."""
        current = (
            CharacterStorageSystem
            .meaningful_history_state(
                current_character
            )
        )

        target = (
            CharacterStorageSystem
            .meaningful_history_state(
                target_character
            )
        )

        changes = []

        def add_change(
            label,
            before,
            after,
        ):
            if before == after:
                return

            before_text = (
                str(before)
                if before not in (
                    None,
                    "",
                )
                else "—"
            )

            after_text = (
                str(after)
                if after not in (
                    None,
                    "",
                )
                else "—"
            )

            changes.append(
                f"{label}: "
                f"{before_text} → {after_text}"
            )

        add_change(
            "Name",
            current.get("name", ""),
            target.get("name", ""),
        )

        add_change(
            "Species",
            current.get(
                "species_name",
                "",
            ),
            target.get(
                "species_name",
                "",
            ),
        )

        current_progression = current.get(
            "progression",
            {},
        )
        target_progression = target.get(
            "progression",
            {},
        )

        add_change(
            "Level",
            current_progression.get(
                "level",
                1,
            ),
            target_progression.get(
                "level",
                1,
            ),
        )

        add_change(
            "IP",
            current_progression.get(
                "current_IP",
                0,
            ),
            target_progression.get(
                "current_IP",
                0,
            ),
        )

        current_hp = current.get(
            "HP",
            {},
        )
        target_hp = target.get(
            "HP",
            {},
        )

        add_change(
            "Hearts",
            current_hp.get(
                "max_hearts",
                0,
            ),
            target_hp.get(
                "max_hearts",
                0,
            ),
        )

        add_change(
            "HP",
            current_hp.get(
                "current_HP",
                0,
            ),
            target_hp.get(
                "current_HP",
                0,
            ),
        )

        current_at = current.get(
            "Adversity",
            {},
        )
        target_at = target.get(
            "Adversity",
            {},
        )

        if current_at != target_at:
            changes.append(
                "AT: "
                f"{current_at.get('current_AT', 0)}/"
                f"{current_at.get('max_AT', 0)}"
                " → "
                f"{target_at.get('current_AT', 0)}/"
                f"{target_at.get('max_AT', 0)}"
            )

        current_stats = current.get(
            "stats",
            {},
        )
        target_stats = target.get(
            "stats",
            {},
        )

        for stat_name in STAT_NAMES:
            before = current_stats.get(
                stat_name,
                {},
            )
            after = target_stats.get(
                stat_name,
                {},
            )

            if before == after:
                continue

            before_die = int(
                before.get(
                    "die_size",
                    4,
                )
            )
            after_die = int(
                after.get(
                    "die_size",
                    4,
                )
            )
            before_bonus = int(
                before.get(
                    "bonus",
                    0,
                )
            )
            after_bonus = int(
                after.get(
                    "bonus",
                    0,
                )
            )

            before_text = f"d{before_die}"
            after_text = f"d{after_die}"

            if before_bonus:
                before_text += f"+{before_bonus}"

            if after_bonus:
                after_text += f"+{after_bonus}"

            changes.append(
                f"{stat_name.title()}: "
                f"{before_text} → {after_text}"
            )

        def improvement_counter(state):
            counter = Counter()

            for improvement in state.get(
                "improvements",
                [],
            ):
                catalog_id = str(
                    improvement.get(
                        "catalog_id",
                        "",
                    )
                )

                if catalog_id == "custom":
                    name = str(
                        improvement.get(
                            "name",
                            "Custom Improvement",
                        )
                    )
                else:
                    option = (
                        IMPROVEMENT_CATALOG.get(
                            catalog_id,
                            {},
                        )
                    )

                    name = str(
                        option.get(
                            "name",
                            catalog_id
                            .replace("_", " ")
                            .title(),
                        )
                    )

                counter[name] += max(
                    1,
                    int(
                        improvement.get(
                            "times_taken",
                            1,
                        )
                    ),
                )

            return counter

        current_improvements = (
            improvement_counter(
                current
            )
        )
        target_improvements = (
            improvement_counter(
                target
            )
        )

        for name in sorted(
            set(current_improvements)
            | set(target_improvements),
            key=str.lower,
        ):
            before = current_improvements[
                name
            ]
            after = target_improvements[
                name
            ]

            if before == after:
                continue

            if before == 0:
                changes.append(
                    f"Add Improvement: {name}"
                )
            elif after == 0:
                changes.append(
                    f"Remove Improvement: {name}"
                )
            else:
                changes.append(
                    f"{name}: {before} → {after}"
                )

        def inventory_quantities(state):
            result = Counter()

            for item in state.get(
                "inventory",
                [],
            ):
                name = str(
                    item.get(
                        "name",
                        "Item",
                    )
                    or "Item"
                )

                result[name] += int(
                    item.get(
                        "quantity",
                        0,
                    )
                )

            return result

        current_inventory = (
            inventory_quantities(
                current
            )
        )
        target_inventory = (
            inventory_quantities(
                target
            )
        )

        for name in sorted(
            set(current_inventory)
            | set(target_inventory),
            key=str.lower,
        ):
            before = current_inventory[
                name
            ]
            after = target_inventory[
                name
            ]

            if before == after:
                continue

            if before == 0:
                changes.append(
                    f"Add Item: {name} ×{after}"
                )
            elif after == 0:
                changes.append(
                    f"Remove Item: {name}"
                )
            else:
                changes.append(
                    f"{name}: {before} → {after}"
                )

        def note_map(state):
            return {
                str(
                    note.get(
                        "title",
                        "Untitled Note",
                    )
                    or "Untitled Note"
                ): (
                    str(
                        note.get(
                            "text",
                            "",
                        )
                    ),
                    str(
                        note.get(
                            "color",
                            "",
                        )
                    ),
                )
                for note in state.get(
                    "notes",
                    [],
                )
            }

        current_notes = note_map(
            current
        )
        target_notes = note_map(
            target
        )

        for title in sorted(
            set(current_notes)
            | set(target_notes),
            key=str.lower,
        ):
            if title not in current_notes:
                changes.append(
                    f"Add Note: {title}"
                )
            elif title not in target_notes:
                changes.append(
                    f"Remove Note: {title}"
                )
            elif (
                current_notes[title]
                != target_notes[title]
            ):
                changes.append(
                    f'Edit Note: "{title}"'
                )

        if (
            current.get("image")
            != target.get("image")
        ):
            changes.append(
                "Portraits changed"
            )

        if (
            current.get(
                "selected_defense_stat_name"
            )
            != target.get(
                "selected_defense_stat_name"
            )
        ):
            changes.append(
                "Defense ability changed"
            )

        if (
            current.get(
                "creation_rules"
            )
            != target.get(
                "creation_rules"
            )
        ):
            changes.append(
                "Creation Rules changed"
            )

        if (
            current.get(
                "backstory"
            )
            != target.get(
                "backstory"
            )
        ):
            changes.append(
                "Backstory changed"
            )

        if not changes:
            return [
                "No meaningful differences."
            ]

        max_lines = 12

        if len(changes) > max_lines:
            hidden = (
                len(changes)
                - max_lines
            )

            changes = (
                changes[:max_lines]
                + [
                    f"...and {hidden} more change"
                    + (
                        "s"
                        if hidden != 1
                        else ""
                    )
                ]
            )

        return changes


    def restore_previous_version_from_ui(self):
        if self.block_if_readonly():
            return

        if not self.current_character_filepath:
            QMessageBox.information(
                self,
                "Earlier Versions",
                (
                    "Earlier versions will become available "
                    "after this character has been saved."
                ),
            )
            return

        # Quietly protect the current state before browsing history.
        if self.unsaved_changes:
            self.save_current_character()

            if self.unsaved_changes:
                return

        history_files = (
            CharacterStorageSystem
            .get_meaningful_character_history(
                self.current_character_filepath
            )
        )

        # The newest history file mirrors the current saved version.
        if len(history_files) <= 1:
            QMessageBox.information(
                self,
                "Earlier Versions",
                (
                    "There are no earlier versions yet.\n\n"
                    "Earlier versions are kept automatically "
                    "as you continue saving this character."
                ),
            )
            return

        versions = []

        for history_index, filepath in enumerate(
            history_files[1:],
            start=1,
        ):
            filename = os.path.basename(
                filepath
            )
            timestamp_text = os.path.splitext(
                filename
            )[0]

            try:
                timestamp = datetime.strptime(
                    timestamp_text,
                    "%Y-%m-%d_%H-%M-%S_%f",
                )
                date_text = timestamp.strftime(
                    "%d %B %Y  ·  %H:%M"
                )
            except ValueError:
                date_text = timestamp_text.replace(
                    "_",
                    " ",
                )

            details = []

            try:
                version_character = (
                    CharacterStorageSystem
                    .import_character_file(
                        filepath
                    )
                )

                previous_index = (
                    history_index + 1
                )

                if previous_index < len(
                    history_files
                ):
                    previous_character = (
                        CharacterStorageSystem
                        .import_character_file(
                            history_files[
                                previous_index
                            ]
                        )
                    )

                    changed_categories = (
                        CharacterStorageSystem
                        .describe_meaningful_changes(
                            previous_character,
                            version_character,
                        )
                    )

                    if changed_categories:
                        details.append(
                            "Changed: "
                            + " · ".join(
                                changed_categories
                            )
                        )
                    else:
                        # Old history created by earlier app versions may
                        # contain duplicate saves. Do not clutter the picker
                        # with entries that have no real sheet difference.
                        continue

                else:
                    details.append(
                        "First saved version"
                    )

            except Exception:
                details.append(
                    "Earlier saved version"
                )

            display = date_text

            if details:
                display += (
                    "\n"
                    + "   •   ".join(
                        details
                    )
                )

            restore_changes = (
                self.describe_restore_differences(
                    self.character,
                    version_character,
                )
            )

            versions.append(
                {
                    "filepath": filepath,
                    "display": display,
                    "changes": restore_changes,
                }
            )

        if not versions:
            QMessageBox.information(
                self,
                "Earlier Versions",
                (
                    "There are no earlier versions with "
                    "meaningful sheet changes yet."
                ),
            )
            return

        dialog = FantasyVersionHistoryDialog(
            versions,
            self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        selected = dialog.selected_version()

        if not selected:
            return

        backup_filepath = selected[
            "filepath"
        ]

        try:
            restored_character = (
                CharacterStorageSystem
                .import_character_file(
                    backup_filepath
                )
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Could Not Restore Version",
                (
                    "This version could not be opened.\n\n"
                    f"{error}"
                ),
            )
            return

        normal_filepath = (
            self.current_character_filepath
        )

        self.character = restored_character
        self.open_notes_for_session()
        self.current_character_filepath = (
            normal_filepath
        )
        self.saved_character_name = (
            self.character.name
        )
        self.character_access_mode = (
            "editable"
        )

        self.supress_dirty = True

        try:
            self.reconnect_character_references()
            self.refresh_all()
        finally:
            self.supress_dirty = False

        # Do not immediately overwrite the current save. Remember that
        # this state came from Earlier Versions so saving it must never prune
        # the newer history entries merely because it matches an old snapshot.
        self._history_restore_pending = True
        self.mark_dirty()

    def show_how_to_use_from_ui(self):
        self.start_guided_tutorial()
        return
    
        dialog = QDialog(self)
        dialog.setWindowTitle("How to Use")
        dialog.setFixedSize(500, 500)

        set_themed_stylesheet(
            dialog,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        text = QLabel("""• Open <b>Tools → Level Up</b> to increase your character's level.<br><br>
• Open <b>Tools → Edit Abilities</b> to change your ability dice.<br><br>
• Click the <b>hearts</b> to set your current HP.<br><br>
• Click the <b>AT diamonds</b> to set your current AT.<br><br>
• Double-click the <b>IP box</b> to grant extra IP.<br><br>
• Press the <b>+</b> button under Improvements to buy improvements or empowerments.<br><br>
• Double-click an <b>Improvement Name</b> to edit its choices.<br><br>
• Double-click an <b>Inventory Item</b> to edit its name, description, and quantity together.<br><br>
• Open <b>Tools → Adjust Resources</b> to change maximum Hearts, total IP, or maximum AT directly.<br><br>
• Click <b>Free Heightened Ability</b> to add +1 to an ability. The same ability can be increased to +2, but the second increase costs <b>1 IP</b>.<br><br>
• Open <b>Tools → Add Notes</b> to create note panels beneath the character sheet. Notes can be used for backstories, spellbooks, reminders, game information, and anything else you want to keep with the character.""")

        text.setWordWrap(True)
        set_themed_stylesheet(
            text,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 600;
                color: #25190f;
            }
            """,
        )

        ok_btn = QPushButton("OK")
        set_themed_stylesheet(
            ok_btn,
            BUTTON_PRIMARY_QSS,
        )
        ok_btn.setFixedSize(100, 38)
        ok_btn.clicked.connect(dialog.accept)

        layout.addWidget(text)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(ok_btn)
        button_row.addStretch()

        layout.addLayout(button_row)

        dialog.exec()

    def create_character_template_from_ui(self):
        create_template_from_ui(parent=self)

    def start_guided_tutorial(self):        
        if hasattr(self, "guided_tutorial"):
            self.guided_tutorial.stop()

        self.guided_tutorial = build_did_tutorial(self)

        self.guided_tutorial.start()

    def open_ability_editor_for_tutorial(self):
        self._tutorial_ability_saved = False

        allowed_array_ids = None

        if getattr(
            self.character,
            "creation_rules_active",
            False,
        ):
            allowed_array_ids = getattr(
                self.character,
                "creation_allowed_ability_array_ids",
                None,
            )

        self.tutorial_dialog = FantasyAbilityEditorDialog(
            self.character,
            self,
            allowed_array_ids=allowed_array_ids,
        )

        def ability_editor_saved():
            self._tutorial_ability_saved = True

            self.mark_dirty(auto_save=True)
            self.refresh_all()

        def ability_editor_cancelled():
            if getattr(
                self,
                "_tutorial_closing_dialog_programmatically",
                False,
            ):
                return

            if hasattr(
                self,
                "guided_tutorial",
            ):
                self.guided_tutorial.stop()

        self.tutorial_dialog.accepted.connect(
            ability_editor_saved
        )

        self.tutorial_dialog.rejected.connect(
            ability_editor_cancelled
        )

        self.tutorial_dialog.setModal(False)
        self.tutorial_dialog.show()
        self.tutorial_dialog.raise_()

        return self.tutorial_dialog
    
    def tutorial_ability_editor_saved(self):
        return getattr(
            self,
            "_tutorial_ability_saved",
            False,
        )
    
    def open_improvement_picker_for_tutorial(self):
        original_current_ip = (
            self.character.progression.current_IP
        )

        try:
            self.character.progression.current_IP = (
                self.character.progression.used_IP
                + 999999
            )

            options = (
                ImprovementSystem
                .get_available_purchases(
                    self.character
                )
            )

        finally:
            self.character.progression.current_IP = (
                original_current_ip
            )

        options = [
            option
            for option in options
            if isinstance(option, dict)
            and option.get("source") != "species"
            and "species"
            not in option.get("tags", [])
        ]

        self.tutorial_dialog = ImprovementPickerDialog(
            options,
            self,
            browse_only=True,
        )

        self.tutorial_dialog.setModal(False)
        self.tutorial_dialog.show()
        self.tutorial_dialog.raise_()

        return self.tutorial_dialog

    def prepare_inventory_add_button_for_tutorial(self):
        self._tutorial_inventory_dialog_opened = False

        if getattr(
            self,
            "_tutorial_inventory_add_hijacked",
            False,
        ):
            return

        try:
            self.add_item_btn.clicked.disconnect()
        except (
            RuntimeError,
            TypeError,
        ):
            pass

        self.add_item_btn.clicked.connect(
            self.open_inventory_dialog_for_tutorial
        )

        self._tutorial_inventory_add_hijacked = True


    def restore_inventory_add_button_after_tutorial(self):
        if not getattr(
            self,
            "_tutorial_inventory_add_hijacked",
            False,
        ):
            return

        try:
            self.add_item_btn.clicked.disconnect()
        except (
            RuntimeError,
            TypeError,
        ):
            pass

        self.add_item_btn.clicked.connect(
            self.add_inventory_item_from_ui
        )

        self._tutorial_inventory_add_hijacked = False

    def tutorial_inventory_dialog_opened(self):
        return bool(
            getattr(
                self,
                "_tutorial_inventory_dialog_opened",
                False,
            )
        )

    def open_inventory_dialog_for_tutorial(self):
        # Restore the normal Add Item button immediately after this
        # demonstration dialog has been opened.
        self.restore_inventory_add_button_after_tutorial()

        self.tutorial_dialog = InventoryItemDialog(
            self
        )

        self._tutorial_inventory_dialog_opened = True

        # Enter in the Name field is reserved for the tutorial step.
        self.tutorial_dialog.add_btn.setDefault(
            False
        )
        self.tutorial_dialog.add_btn.setAutoDefault(
            False
        )
        self.tutorial_dialog.add_btn.setEnabled(
            False
        )

        self.tutorial_dialog.cancel_btn.setDefault(
            False
        )
        self.tutorial_dialog.cancel_btn.setAutoDefault(
            False
        )

        self.tutorial_dialog.setModal(
            False
        )

        self.tutorial_dialog.show()
        self.tutorial_dialog.raise_()
        self.tutorial_dialog.name_input.setFocus()

        return self.tutorial_dialog


    def close_tutorial_dialog(self):
        dialog = getattr(
            self,
            "tutorial_dialog",
            None,
        )

        # Clear the public reference first. Any signal emitted while close()
        # is running must not make the tutorial reuse a dialog which is in
        # the process of being destroyed.
        self.tutorial_dialog = None

        # Returning Back from the Inventory dialog to the Inventory + step
        # must require the + button again instead of instantly auto-advancing
        # because an old demo-dialog flag was left True.
        self._tutorial_inventory_dialog_opened = False

        if dialog is None:
            return

        self._tutorial_closing_dialog_programmatically = True

        try:
            dialog.close()
            dialog.deleteLater()
        except (
            RuntimeError,
            ReferenceError,
        ):
            pass
        finally:
            self._tutorial_closing_dialog_programmatically = False

    def show_notes_for_tutorial(self):
        # Remember the page the player was on before the tutorial moves
        # them into the dedicated Notes page.
        if getattr(
            self,
            "_tutorial_page_before_notes",
            None,
        ) is None:
            self._tutorial_page_before_notes = getattr(
                self,
                "current_redesign_page",
                "character",
            )

            self._tutorial_notes_were_visible = bool(
                self.notes_board_visible
            )

        self.show_notes_page()

        return self.notes_frame

    def restore_notes_after_tutorial(self):
        previous_page = getattr(
            self,
            "_tutorial_page_before_notes",
            None,
        )

        if previous_page is None:
            return

        if previous_page == "notes":
            self.show_notes_page()
        else:
            self.show_character_page()

        self._tutorial_page_before_notes = None
        self._tutorial_notes_were_visible = False
    

    def prepare_note_add_for_tutorial(
        self,
    ):
        self.show_notes_for_tutorial()

        self._tutorial_note_count = len(
            self.character
            .notes
            .list_of_notes
        )


    def tutorial_note_was_added(
        self,
    ):
        return (
            len(
                self.character
                .notes
                .list_of_notes
            )
            > getattr(
                self,
                "_tutorial_note_count",
                0,
            )
        )
    
    def prepare_inventory_add_for_tutorial(self):
        self.prepare_inventory_add_button_for_tutorial()


    def open_inventory_from_tutorial_button(self):
        self.open_inventory_dialog_for_tutorial()


    def tutorial_inventory_dialog_open(self):
        return self.tutorial_inventory_dialog_opened()



    # ============================================================
    # TOOLS MENU / CLOSE EVENT
    # ============================================================

    def adjust_resources_from_ui(self):
        if self.is_campaign_character_for_tools():
            return
        if self.block_if_readonly():
            return

        dialog = FantasyResourceAdjustDialog(
            self.character,
            self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        values = dialog.values()

        old_values = (
            int(
                self.character.HP.max_hearts
            ),
            int(
                self.character.progression.current_IP
            ),
            int(
                self.character.adversity.max_AT
            ),
        )

        new_values = (
            values["max_hearts"],
            values["current_IP"],
            values["max_AT"],
        )

        if new_values == old_values:
            return

        self.character.HP.max_hearts = (
            values["max_hearts"]
        )

        self.character.progression.current_IP = (
            values["current_IP"]
        )

        self.character.adversity.max_AT = (
            values["max_AT"]
        )

        # validate() recalculates max HP (including Hearty), clamps current
        # HP/AT if a maximum was lowered, and leaves Level untouched.
        self.character.validate()

        self.mark_dirty(
            auto_save=True
        )
        self.refresh_all()

    def delete_current_character_from_ui(self):
        if self.block_if_readonly():
            return

        display_name = str(self.character.name or "").strip() or "this character"

        if not ask_yes_no(
            self,
            "Delete Character",
            (
                f"Delete {display_name}?\n\n"
                "This removes the saved character and its stored earlier versions."
            ),
            yes_text="Delete",
            no_text="Cancel",
            button_width=95,
        ):
            return

        old_filepath = self.current_character_filepath

        if hasattr(self, "_recovery_write_timer"):
            self._recovery_write_timer.stop()

        self.discard_current_recovery()

        if old_filepath and os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except OSError as error:
                QMessageBox.warning(
                    self,
                    "Delete Failed",
                    f"The character file could not be deleted.\n\n{error}",
                )
                return

            history_folder = os.path.join(
                os.path.dirname(os.path.abspath(old_filepath)),
                "_history",
                os.path.splitext(os.path.basename(old_filepath))[0],
            )
            if os.path.isdir(history_folder):
                shutil.rmtree(history_folder, ignore_errors=True)

        # Persist desktop deletions regardless of whether Mobile Companion is
        # running. Broadcast only if a live controller is available.
        deleted_id = str(getattr(self.character, "id", "") or "").strip()
        if deleted_id and old_filepath:
            try:
                from mobile_sync_frontend_adapter import DesktopSyncAdapter
                DesktopSyncAdapter.record_desktop_deletion(
                    CharacterStorageSystem, deleted_id
                )
            except Exception as error:
                QMessageBox.warning(
                    self, "Mobile Sync Warning",
                    "Character deleted locally, but the deletion could not be "
                    f"recorded for offline phones:\n\n{error}",
                )
            else:
                companion = getattr(self, "mobile_companion", None)
                if companion is not None:
                    try:
                        companion._capture_and_broadcast(force_character_event=True)
                    except Exception:
                        # Persisted tombstone remains available on reconnect.
                        pass

        self.clear_last_opened_character(old_filepath)

        self.character = Character.create_new_character()
        self.current_character_filepath = None
        self.saved_character_name = None
        self.character_access_mode = "editable"
        self.active_character_template = None
        self._silently_recovered = False
        self._recovered_state_edited = False
        self._history_restore_pending = False
        self.unsaved_changes = False
        self.setWindowModified(False)

        self.supress_dirty = True
        try:
            self.reconnect_character_references()
            self.refresh_all()
        finally:
            self.supress_dirty = False

        if hasattr(self, "save_status_label"):
            self.save_status_label.setText("Saved")
        if hasattr(self, "update_history_button_state"):
            self.update_history_button_state()


    def open_improvement_editor_from_ui(self):
        """Open the embedded Improvement / Empowerment catalog editor."""
        if self.is_campaign_character_for_tools():
            return
        existing = getattr(
            self,
            "_improvement_editor_window",
            None,
        )

        if existing is not None:
            try:
                existing.show()
                existing.raise_()
                existing.activateWindow()
                return
            except RuntimeError:
                self._improvement_editor_window = None

        self._improvement_editor_window = open_improvement_editor(
            self,
            owner_mode=True,
        )

    def roll_other_dice_from_ui(self):
        """Roll chosen standard dice using the existing 3D engine and history."""
        if not self.dice_roller_is_enabled():
            return
        dialog = FantasyOtherDiceDialog(self)
        dialog.adjustSize()
        dialog.position_inside_sheet()
        QTimer.singleShot(0, dialog.position_inside_sheet)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            plan = build_other_dice_plan(dialog.selected_counts())
        except ValueError as error:
            QMessageBox.warning(self, "Invalid Dice Selection", str(error))
            return
        self._pending_other_dice_count = (
            1 + len(plan["extras"])
        )
        self._pending_d100_count = sum(
            1 for die in [plan["ability"], *plan["extras"]]
            if die["sides"] == 100
        )
        self._pending_dice_stat_name = "Other Dice"
        self._pending_dice_stat_key = ""
        self._pending_dice_color = "#a87824"
        self.roll_dice_plan(plan, self._pending_dice_color)


    def _refresh_session_roll_history_dialog(self):
        """Update an open history window without creating another window."""
        viewer = getattr(self, "_session_roll_history_text", None)
        if viewer is None:
            return
        try:
            entries = self.character.roll_history
            viewer.setPlainText(
                "\n\n".join(
                    f"{len(entries) - index}. {entry}"
                    for index, entry in enumerate(reversed(entries))
                ) if entries else "No rolls yet for this character."
            )
            viewer.verticalScrollBar().setValue(0)
        except (RuntimeError, ReferenceError):
            self._session_roll_history_text = None

    def show_session_roll_history_from_ui(self):
        """Show rolls made for the current character in this app session."""
        dialog = getattr(self, "_session_roll_history_dialog", None)
        if dialog is not None:
            try:
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                return
            except (RuntimeError, ReferenceError):
                self._session_roll_history_dialog = None

        dialog = QDialog(self)
        dialog.setWindowTitle("Previous Rolls — This Session")
        dialog.setMinimumSize(620, 380)
        dialog.resize(750, 480)
        set_themed_stylesheet(
            dialog,
            """
            QDialog { background-color: #fffdf7; color: #25190f; }
            QLabel { background: transparent; color: #25190f;
                     font-family: Georgia; font-size: 15px; font-weight: 800; }
            QTextEdit { background-color: #fffaf0; color: #25190f;
                        border: 1px solid #c79a3b; border-radius: 8px;
                        padding: 10px; font-family: Georgia; font-size: 13px; }
            QPushButton { background-color: #d8edf7; color: #25190f;
                          border: 1px solid #c79a3b; border-radius: 8px;
                          padding: 6px 17px; font-family: Georgia; font-weight: 800; }
            """,
        )
        layout = QVBoxLayout(dialog)
        heading = QLabel("Previous Rolls · This Session")
        layout.addWidget(heading)
        viewer = QTextEdit(dialog)
        viewer.setReadOnly(True)
        viewer.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(viewer, 1)
        close_button = QPushButton("Close", dialog)
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)

        self._session_roll_history_dialog = dialog
        self._session_roll_history_text = viewer
        self._refresh_session_roll_history_dialog()
        dialog.show()
        dialog.raise_()


    def toggle_tools_menu(self):
        menu = QMenu(self)

        set_themed_stylesheet(
            menu,
            """
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
                padding: 7px 28px 7px 11px;
                margin: 1px 2px;
                color: #25190f;
            }

            QMenu::item:selected {
                background-color: #d8edf7;
                color: #25190f;
            }

            QMenu::item:disabled {
                color: #9b9388;
            }

            QMenu::separator {
                height: 1px;
                background-color: #d8bd82;
                margin: 4px 7px;
            }

            QMenu::right-arrow {
                width: 8px;
                height: 8px;
                margin-right: 7px;
            }
            """,
        )

        def add_normal_action(
            label,
            callback,
        ):
            action = menu.addAction(
                label
            )
            action.triggered.connect(
                callback
            )
            return action

        add_normal_action(
            "New Character",
            self.new_character_wizard_from_ui,
        )

        add_normal_action(
            "Save Character",
            self.save_character_from_ui,
        )

        add_normal_action(
            "Load Character",
            self.load_character_from_ui,
        )

        add_normal_action(
            "Delete Character",
            self.delete_current_character_from_ui,
        )

        history_action = add_normal_action(
            "Earlier Versions",
            self.restore_previous_version_from_ui,
        )

        history_action.setEnabled(
            bool(
                getattr(
                    self,
                    "_has_earlier_versions",
                    False,
                )
            )
        )

        add_normal_action(
            "Edit Abilities",
            self.open_ability_editor,
        )

        # Android Mobile Companion. Keep this explicit so the action stays
        # visible even if the compatibility QMenu event filter is unavailable.
        def open_mobile_companion_from_tools():
            companion = getattr(self, "mobile_companion", None)
            if companion is not None:
                companion.show_dialog()
                return

            detail = getattr(
                self,
                "_mobile_companion_startup_error",
                None,
            )
            message = "Mobile Companion did not initialize."
            if detail:
                message += "\n\n" + str(detail)
            QMessageBox.warning(
                self,
                "Mobile Companion",
                message,
            )

        add_normal_action(
            "Mobile Companion",
            open_mobile_companion_from_tools,
        )

        # Keep dice-related actions together, matching the existing
        # Creation Rules fly-out rather than cluttering the Tools menu.
        dice_menu = menu.addMenu("Dice Roller")
        dice_enabled_action = dice_menu.addAction("Enabled")
        dice_enabled_action.setCheckable(True)
        dice_enabled_action.setChecked(self.dice_roller_is_enabled())
        dice_enabled_action.triggered.connect(
            lambda _checked: self.toggle_dice_roller_from_ui()
        )

        other_dice_action = dice_menu.addAction("Roll Other Dice...")
        other_dice_action.setEnabled(self.dice_roller_is_enabled())
        other_dice_action.triggered.connect(self.roll_other_dice_from_ui)

        previous_rolls_action = dice_menu.addAction(
            "Previous Rolls (This Session)"
        )
        previous_rolls_action.triggered.connect(
            self.show_session_roll_history_from_ui
        )

        # There is NO ordinary "Check for Updates" command anymore.
        # The startup background check adds this row only after confirming
        # that a newer installer-backed release actually exists.
        update_info = getattr(
            self,
            "_available_update_release",
            None,
        )

        if update_info:
            update_action = QWidgetAction(
                menu
            )

            update_action.setText(
                "Update Available"
            )

            version = str(
                update_info.get(
                    "version",
                    "",
                )
                or ""
            ).strip()

            button_text = (
                f"Update Available — {version}"
                if version
                else "Update Available"
            )

            update_btn = QPushButton(
                button_text
            )

            update_btn.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            update_btn.setFocusPolicy(
                Qt.FocusPolicy.NoFocus
            )

            set_themed_stylesheet(
                update_btn,
                """
                QPushButton {
                    background-color: #ff2f3f;
                    border: 2px solid #a90012;
                    border-radius: 7px;
                    color: white;
                    font-family: Georgia;
                    font-size: 13px;
                    font-weight: 900;
                    text-align: left;
                    padding: 7px 11px;
                    margin: 1px 2px;
                }

                QPushButton:hover {
                    background-color: #ff5260;
                    border-color: #76000d;
                }

                QPushButton:pressed {
                    background-color: #d91427;
                }
                """,
            )

            def open_available_update():
                menu.close()

                QTimer.singleShot(
                    0,
                    self.check_for_updates_from_ui,
                )

            update_btn.clicked.connect(
                open_available_update
            )

            update_action.setDefaultWidget(
                update_btn
            )

            menu.addAction(
                update_action
            )

        add_normal_action(
            "How to Use",
            self.show_how_to_use_from_ui,
        )

        campaign_locked = self.is_campaign_character_for_tools()
        if not campaign_locked:
            add_normal_action(
                "Level Up",
                self.level_up_from_ui,
            )

        if species_tool_visible(self.character):
            add_normal_action(
                "Add Species",
                self.add_species_from_ui,
            )

        menu.addSeparator()

        # Character progression is controlled by the campaign rules and DM.
        # These tools remain available for standalone characters only.
        if not campaign_locked:
            add_normal_action(
                "Adjust Resources",
                self.adjust_resources_from_ui,
            )
            add_normal_action(
                "Improvement Editor",
                self.open_improvement_editor_from_ui,
            )

        campaign_menu = menu.addMenu(
            "Campaign & Templates"
        )

        campaign_action = campaign_menu.addAction(
            "Campaigns..."
        )
        campaign_action.triggered.connect(
            lambda _checked=False: open_campaigns(self)
        )

        campaign_menu.addSeparator()

        create_template_action = (
            campaign_menu.addAction(
                "Create Standalone Template"
            )
        )

        create_template_action.triggered.connect(
            self.create_character_template_from_ui
        )

        new_from_template_action = (
            campaign_menu.addAction(
                "New Character From Standalone Template"
            )
        )

        new_from_template_action.triggered.connect(
            self.new_character_from_template_from_ui
        )

        menu.exec(
            self.tools_toggle_btn.mapToGlobal(
                self.tools_toggle_btn
                .rect()
                .bottomLeft()
            )
        )

    def closeEvent(self, event):
        settings = QSettings("DID", "CharacterSheet")
        settings.setValue("window_geometry", self.saveGeometry())
        settings.setValue("window_maximized", self.isMaximized())
        if self.cleanup_empty_notes():
            self.mark_dirty()
            self.refresh_all()

        if not self.unsaved_changes:
            event.accept()
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Unsaved Changes")
        msg.setText("You have unsaved changes.\nSave before closing?")

        save_btn = msg.addButton(
            "Save",
            QMessageBox.ButtonRole.AcceptRole,
        )

        dont_save_btn = msg.addButton(
            "Don't Save",
            QMessageBox.ButtonRole.DestructiveRole,
        )

        cancel_btn = msg.addButton(
            "Cancel",
            QMessageBox.ButtonRole.RejectRole,
        )

        _style_fantasy_button(save_btn)
        _style_fantasy_button(dont_save_btn)
        _style_fantasy_button(cancel_btn)

        save_btn.setFixedSize(120, 36)
        dont_save_btn.setFixedSize(120, 36)
        cancel_btn.setFixedSize(120, 36)

        msg.exec()

        clicked = msg.clickedButton()

        if clicked == cancel_btn:
            event.ignore()
            return

        if clicked == dont_save_btn:
            self.discard_current_recovery()
            
            event.accept()
            return


        self.save_current_character()

        if self.unsaved_changes:
            event.ignore()
            return

        event.accept()

    def is_campaign_character_for_tools(self):
        from campaign_tools_policy import window_campaign_tools_locked
        return window_campaign_tools_locked(self)

    def is_readonly_character(self):
        return self.character_access_mode == "readonly"

    def block_if_readonly(self):
        if not self.is_readonly_character():
            return False

        QMessageBox.warning(
            self,
            "Read Only",
            "This character is open in read-only mode."
        )
        return True
    
        

# =====================================================================
# CONNECTED LIGHT-FANTASY CHARACTER SHEET UI
# =====================================================================
# BaseMainWindow above retains the existing save/load, character,
# inventory, improvements, notes, recovery, shortcuts and backend logic.
# MainWindow below replaces only the presentation/layout and selected
# UI dialogs, so this file is now the normal frontend entry point.
# =====================================================================

ABILITY_ACCENTS = {
    "agility": "#6F8F2C",
    "finesse": "#356FA8",
    "instinct": "#6B55A6",
    "knowledge": "#B17828",
    "presence": "#2F8792",
    "strength": "#A8453C",
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))

ICONS_DIR = os.path.join(APP_DIR, "icons")
HEADER_ICON_DIR = os.path.join(ICONS_DIR, "headers")
IMPROVEMENT_ICON_DIR = os.path.join(ICONS_DIR, "improvements")
DEFENSE_ICON_DIR = os.path.join(ICONS_DIR, "defenses")
RELATED_NOTE_ICON_DIR = os.path.join(ICONS_DIR, "notes")


def find_note_icon_path(preferred_path=None):
    """Return the first valid note SVG, preserving dedicated icons first.

    Generic note icons share one fallback chain so the Notes heading and
    linked-note fallback cannot drift apart again.
    """
    candidates = []
    if preferred_path:
        candidates.append(preferred_path)
    candidates.extend((
        os.path.join(RELATED_NOTE_ICON_DIR, "custom.svg"),
        os.path.join(HEADER_ICON_DIR, "notes.svg"),
        os.path.join(ICONS_DIR, "notes.svg"),
    ))

    seen = set()
    for path in candidates:
        if not path:
            continue
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        if not os.path.isfile(path):
            continue
        if QSvgRenderer is None:
            return path
        renderer = QSvgRenderer(path)
        if renderer.isValid():
            return path

    return None

ABILITY_ICON_FILES = {
    "agility": "agility.svg",
    "finesse": "finesse.svg",
    "instinct": "instinct.svg",
    "knowledge": "knowledge.svg",
    "presence": "presence.svg",
    "strength": "strength.svg",
}

# Ability emblems are loaded from SVG files in the local icons folder.
# The older QPainter drawings remain below as a fallback if an SVG is missing.

ABILITY_DESCRIPTIONS = {
    "agility": (
        "Controls speed and quick movement.\n"
        "Use it to run fast, jump gaps, or dodge danger."
    ),
    "strength": (
        "Measures muscle power and toughness.\n"
        "Use it to break barriers, lift heavy objects, or fight foes."
    ),
    "finesse": (
        "Controls careful and steady movement.\n"
        "Use it to fix tools, hide, or aim accurately."
    ),
    "instinct": (
        "Controls awareness and gut feelings.\n"
        "Use it to spot danger, find your way, or read people."
    ),
    "presence": (
        "Measures personality and social power.\n"
        "Use it to charm friends, trick others, or scare enemies."
    ),
    "knowledge": (
        "Tracks memory and smart thinking.\n"
        "Use it to study clues, remember facts, or solve puzzles."
    ),
}


# ============================================================
# REDESIGN BUTTON SYSTEM
# ============================================================
# All normal action buttons use the same visual language.
# Large actions differ only by emphasis (primary/secondary), while
# compact icon buttons use the same colors, borders and hover states.

BUTTON_PRIMARY_QSS = """
    QPushButton {
        background-color: #d8edf7;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-size: 12px;
        font-weight: 800;
        color: #25190f;
        padding: 3px 12px;
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
    QPushButton:focus {
        border: 1px solid #25190f;
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
        padding: 3px 12px;
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
    QPushButton:disabled {
        background-color: #f5f1e9;
        border-color: #d8ccb5;
        color: #9b9388;
    }
    QPushButton:focus {
        border: 1px solid #25190f;
    }
"""

BUTTON_ICON_QSS = """
    QPushButton {
        background-color: #fffdf7;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-weight: 900;
        color: #6c5428;
        padding: 0px;
        margin: 0px;
    }
    QPushButton:hover {
        background-color: #e8f5fb;
        border-color: #a87824;
        color: #25190f;
    }
    QPushButton:pressed {
        background-color: #c9e3ef;
    }
"""

NAV_ACTIVE_QSS = """
    QPushButton {
        background-color: #d8edf7;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-size: 14px;
        font-weight: 900;
        color: #25190f;
        padding: 3px 16px;
        margin: 0px;
    }
    QPushButton:hover {
        background-color: #e8f5fb;
        border-color: #a87824;
    }
    QPushButton:pressed {
        background-color: #c9e3ef;
    }
"""

NAV_INACTIVE_QSS = """
    QPushButton {
        background-color: #fffdf7;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-size: 14px;
        font-weight: 900;
        color: #4f3b18;
        padding: 3px 16px;
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



# ============================================================
# REDESIGNED DIALOG SYSTEM
# ============================================================

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

    QLineEdit,
    QTextEdit,
    QSpinBox,
    QComboBox {
        background-color: #fffaf0;
        border: 1px solid #d9bd82;
        border-radius: 8px;
        padding: 5px 8px;
        color: #25190f;
        font-size: 13px;
        selection-background-color: #d8edf7;
        selection-color: #25190f;
    }

    QLineEdit:focus,
    QTextEdit:focus,
    QSpinBox:focus,
    QComboBox:focus {
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

    QTextEdit {
        background-color: #fffaf0;
        border: 1px solid #d9bd82;
        border-radius: 10px;
        padding: 8px;
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
        background-color: #c6a15d;
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


BUTTON_DANGER_QSS = """
    QPushButton {
        background-color: #fff1d6;
        border: 1px solid #c79a3b;
        border-radius: 9px;
        font-family: Georgia;
        font-size: 12px;
        font-weight: 800;
        color: #aa0000;
        padding: 3px 12px;
        margin: 0px;
    }

    QPushButton:hover {
        background-color: #fff4df;
        border-color: #aa0000;
    }

    QPushButton:pressed {
        background-color: #f5ead2;
    }

    QPushButton:focus {
        border: 1px solid #25190f;
    }
"""


FANTASY_TOOLTIP_QSS = """
    QToolTip {
        background-color: #fffaf0;
        color: #25190f;
        border: 1px solid #cdaa63;
        border-radius: 8px;
        padding: 8px 10px;
        font-family: Georgia;
        font-size: 12px;
    }
"""


def apply_fantasy_application_style():
    """Only applies app-level styling that cannot live on a normal widget."""
    app = QApplication.instance()

    if app is None:
        return

    app.setStyleSheet(
        translate_qss_for_theme(
            FANTASY_TOOLTIP_QSS
        )
    )


def _style_fantasy_button(button):
    text = button.text().strip().lower()

    danger_words = (
        "delete",
        "discard",
        "don't save",
        "remove",
    )

    secondary_words = (
        "cancel",
        "no",
        "later",
        "close",
        "back",
    )

    if any(word in text for word in danger_words):
        style = BUTTON_DANGER_QSS
    elif (
        text in secondary_words
        or text.startswith("cancel")
        or text.startswith("no")
    ):
        style = BUTTON_SECONDARY_QSS
    else:
        style = BUTTON_PRIMARY_QSS

    set_themed_stylesheet(
        button,
        style,
    )


def apply_fantasy_dialog_style(dialog):
    """
    Restyle an existing dialog AFTER its original constructor has created
    all controls. This keeps every original rule and signal intact.
    """

    set_themed_stylesheet(
        dialog,
        FANTASY_DIALOG_QSS,
    )

    for widget in dialog.findChildren(
        QLineEdit
    ):
        set_themed_stylesheet(
            widget,
            """
            QLineEdit {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 8px;
                padding: 5px 8px;
                color: #25190f;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #a87824;
                background-color: #fffdf7;
            }
            """,
        )

    for widget in dialog.findChildren(
        QSpinBox
    ):
        set_themed_stylesheet(
            widget,
            """
            QSpinBox {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 8px;
                padding: 5px 8px;
                color: #25190f;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 1px solid #a87824;
                background-color: #fffdf7;
            }
            """,
        )

    for widget in dialog.findChildren(
        QComboBox
    ):
        set_themed_stylesheet(
            widget,
            """
            QComboBox {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 8px;
                padding: 4px 30px 4px 8px;
                color: #25190f;
                font-size: 13px;
            }

            QComboBox:focus {
                border: 1px solid #a87824;
            }

            QComboBox::drop-down {
                width: 25px;
                border: none;
                border-left: 1px solid #d9bd82;
                background-color: #d8edf7;
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
            }

            QComboBox QAbstractItemView {
                background-color: #fffdf7;
                border: 1px solid #cdaa63;
                padding: 4px;
                color: #25190f;
                selection-background-color: #d8edf7;
                selection-color: #25190f;
                outline: none;
            }
            """,
        )

    for widget in dialog.findChildren(
        QListWidget
    ):
        set_themed_stylesheet(
            widget,
            """
            QListWidget {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 11px;
                padding: 6px;
                color: #25190f;
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
            """,
        )

    for widget in dialog.findChildren(
        QTextEdit
    ):
        set_themed_stylesheet(
            widget,
            """
            QTextEdit {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 10px;
                padding: 8px;
                color: #25190f;
                font-size: 13px;
            }

            QTextEdit:focus {
                border: 1px solid #a87824;
                background-color: #fffdf7;
            }
            """,
        )

    for button in dialog.findChildren(
        QPushButton
    ):
        _style_fantasy_button(
            button
        )


_OriginalImprovementPickerDialog = (
    ImprovementPickerDialog
)
_OriginalInventoryItemDialog = (
    InventoryItemDialog
)
_OriginalInventoryEditDialog = (
    InventoryEditDialog
)
_OriginalChoiceInputDialog = (
    ChoiceInputDialog
)
_OriginalCustomImprovementDialog = (
    CustomImprovementDialog
)


def find_improvement_option_icon_path(
    option,
):
    """
    Find the same Improvement SVG used by owned Improvements on the sheet.

    Empowerments also try the parent Improvement name so they inherit the
    same visual family when they do not have their own SVG.
    """
    candidates = [
        option.get(
            "catalog_id",
            "",
        ),
        option.get(
            "improvement_id",
            "",
        ),
        option.get(
            "name",
            "",
        ),
    ]

    name = str(
        option.get(
            "name",
            "",
        )
        or ""
    )

    if "->" in name:
        candidates.append(
            name.split(
                "->",
                1,
            )[0].strip()
        )

    if not os.path.isdir(
        IMPROVEMENT_ICON_DIR
    ):
        return None

    wanted = {
        normalize_improvement_icon_key(
            candidate
        )
        for candidate in candidates
        if str(
            candidate
            or ""
        ).strip()
    }

    if not wanted:
        return None

    try:
        filenames = os.listdir(
            IMPROVEMENT_ICON_DIR
        )
    except OSError:
        return None

    for filename in filenames:
        if not filename.lower().endswith(
            ".svg"
        ):
            continue

        stem = os.path.splitext(
            filename
        )[0]

        if (
            normalize_improvement_icon_key(
                stem
            )
            in wanted
        ):
            return os.path.join(
                IMPROVEMENT_ICON_DIR,
                filename,
            )

    return None


class ImprovementPickerCard(QPushButton):
    """
    Clickable Improvement card used by the Add/Browse Improvement grid.

    This is a real grid card rather than a QListWidget item. Using a
    QGridLayout guarantees exactly two columns instead of relying on
    QListWidget/IconMode wrapping, which was behaving as one column on
    the user's Windows/DPI setup.
    """

    def __init__(
        self,
        option,
        select_callback,
        activate_callback=None,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.option = option
        self.select_callback = (
            select_callback
        )
        self.activate_callback = (
            activate_callback
        )

        self.setCheckable(
            True
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setMinimumHeight(
            48
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            10,
            5,
            7,
            5,
        )

        layout.setSpacing(
            4
        )

        name = str(
            option.get(
                "name",
                "Improvement",
            )
        )

        cost = int(
            option.get(
                "cost",
                0,
            )
        )

        kind = option.get(
            "kind",
            "base",
        )

        if kind == "empowerment":
            self.empowerment_arrow = QLabel(
                "↪"
            )

            self.empowerment_arrow.setFixedWidth(
                10
            )

            self.empowerment_arrow.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            self.empowerment_arrow.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

            set_themed_stylesheet(
                self.empowerment_arrow,
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

            layout.addWidget(
                self.empowerment_arrow,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        display_name = (
            name.replace(
                " -> ",
                " → ",
            )
            .replace(
                "->",
                "→",
            )
        )

        icon_path = (
            find_improvement_option_icon_path(
                option
            )
        )

        if icon_path:
            icon = ExternalSvgIcon(
                icon_path,
                size=30,
                parent=self,
            )

            icon.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

            layout.addWidget(
                icon,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        self.name_label = QLabel(
            display_name
        )

        self.name_label.setWordWrap(
            True
        )
        self.name_label.setMaximumHeight(36)

        self.name_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

        set_themed_stylesheet(
            self.name_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 700;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        layout.addWidget(
            self.name_label,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )

        # Keep cost separate from the name. Long Empowerment names may be
        # clipped, but the IP cost must always remain visible.
        self.cost_label = QLabel(
            f"({cost} IP)"
        )

        self.cost_label.setFixedWidth(
            42
        )

        self.cost_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.cost_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        set_themed_stylesheet(
            self.cost_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 700;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        if option.get(
            "requires_choices"
        ):
            self.choice_marker = QLabel(
                "✎"
            )

            self.choice_marker.setFixedSize(
                18,
                22,
            )

            self.choice_marker.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            self.choice_marker.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

            set_themed_stylesheet(
                self.choice_marker,
                """
                QLabel {
                    background: transparent;
                    border: none;
                    font-family: Georgia;
                    font-size: 12px;
                    font-weight: 900;
                    color: #765d34;
                    padding: 0px;
                    margin: 0px;
                }
                """,
            )

            layout.addWidget(
                self.choice_marker,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        layout.addWidget(
            self.cost_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )


        set_themed_stylesheet(
            self,
            """
            QPushButton {
                background-color: #fffdf7;
                border: 1px solid #e2cfaa;
                border-radius: 8px;
                padding: 0px;
                margin: 0px;
                text-align: left;
            }

            QPushButton:hover {
                background-color: #fff4df;
                border: 1px solid #d9bd82;
            }

            QPushButton:checked {
                background-color: #d8edf7;
                border: 1px solid #a87824;
            }
            """,
        )

        self.clicked.connect(
            self._selected
        )


    def _selected(self):
        if callable(
            self.select_callback
        ):
            self.select_callback(
                self
            )


    def mouseDoubleClickEvent(
        self,
        event,
    ):
        if callable(
            self.activate_callback
        ):
            self.activate_callback(
                self
            )

            event.accept()
            return

        super().mouseDoubleClickEvent(
            event
        )


class FantasyImprovementPickerDialog(
    _OriginalImprovementPickerDialog
):
    """
    Compact two-column Improvement picker.

    The two columns are now a real QGridLayout inside a scroll area, so
    Windows scaling/DPI cannot collapse the layout back into one column.
    """

    def __init__(
        self,
        options,
        parent=None,
        browse_only=False,
    ):
        # Do not build the original QListWidget UI. We use the same dialog
        # contract (selected_option + Accepted/Rejected), but construct a
        # deterministic two-column layout ourselves.
        QDialog.__init__(
            self,
            parent,
        )

        self.browse_only = bool(
            browse_only
        )

        self.selected_option = None
        self.selected_card = None
        self.cards = []

        self.custom_allowed = any(
            (
                option.get(
                    "kind"
                )
                == "custom"
                or option.get(
                    "catalog_id"
                )
                == "custom"
            )
            for option in options
            if isinstance(
                option,
                dict,
            )
        )

        self.all_options = sorted(
            [
                option
                for option in options
                if (
                    option.get(
                        "kind"
                    )
                    != "custom"
                    and option.get(
                        "catalog_id"
                    )
                    != "custom"
                )
            ],
            key=lambda item:
                str(
                    item.get(
                        "name",
                        "",
                    )
                ).lower(),
        )

        self.options = list(
            self.all_options
        )

        self.setWindowTitle(
            "Browse Improvements"
            if self.browse_only
            else "Add Improvement"
        )

        self.setFixedSize(
            650,
            520,
        )

        apply_fantasy_dialog_style(
            self
        )

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        root.setSpacing(
            8
        )

        # --------------------------------------------------------
        # Filter row
        # --------------------------------------------------------

        top_row = QHBoxLayout()
        top_row.setSpacing(
            8
        )

        filter_label = QLabel(
            "Filter"
        )

        filter_label.setFixedWidth(
            44
        )

        self.filter_combo = QComboBox()

        self.filter_combo.setFixedSize(
            150,
            30,
        )

        self.filter_combo.addItem(
            "All",
            None,
        )

        if any(
            option.get(
                "kind"
            )
            == "empowerment"
            for option in self.all_options
        ):
            self.filter_combo.addItem(
                "Empowerments",
                "__empowerments__",
            )

        tags = sorted(
            {
                str(tag)
                for option in self.all_options
                for tag in option.get(
                    "tags",
                    [],
                )
                if str(tag).strip()
            },
            key=str.lower,
        )

        for tag in tags:
            self.filter_combo.addItem(
                tag.replace(
                    "_",
                    "-",
                ).title(),
                tag,
            )

        top_row.addWidget(
            filter_label
        )

        top_row.addWidget(
            self.filter_combo
        )

        # Search works together with the existing tag/empowerment filter.
        # Keep it in the header rather than reducing the two-column grid.
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("improvement_search_input")
        self.search_input.setPlaceholderText("Search improvements...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(125)
        self.search_input.setFixedHeight(30)
        self.search_input.setToolTip(
            "Search improvement names, descriptions, and tags"
        )
        set_themed_stylesheet(
            self.search_input,
            """
            QLineEdit {
                background-color: #fffdf7;
                border: 1px solid #c79a3b;
                border-radius: 8px;
                padding: 3px 8px;
                color: #25190f;
                font-family: Georgia;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #a87824;
            }
            """,
        )
        top_row.addWidget(self.search_input, 1)

        if (
            not self.browse_only
            and self.custom_allowed
        ):
            self.custom_improvement_btn = QPushButton(
                "+  Add custom improvement"
            )

            self.custom_improvement_btn.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            set_themed_stylesheet(
                self.custom_improvement_btn,
                BUTTON_SECONDARY_QSS,
            )

            # Size this from the rendered text instead of using a hard-coded
            # width. On Windows/DPI scaling, 155px clipped the beginning/end
            # of "+ Add custom improvement".
            self.custom_improvement_btn.setFixedHeight(
                30
            )

            self.custom_improvement_btn.setMinimumWidth(
                max(
                    190,
                    self.custom_improvement_btn
                    .sizeHint()
                    .width()
                    + 18,
                )
            )

            self.custom_improvement_btn.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )

            self.custom_improvement_btn.clicked.connect(
                self.open_custom_improvement
            )

            top_row.addWidget(
                self.custom_improvement_btn
            )

        root.addLayout(
            top_row
        )

        # --------------------------------------------------------
        # GUARANTEED two-column grid
        # --------------------------------------------------------

        self.grid_scroll = QScrollArea()

        self.grid_scroll.setWidgetResizable(
            True
        )

        self.grid_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        set_themed_stylesheet(
            self.grid_scroll,
            """
            QScrollArea {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 11px;
            }
            """
        )

        self.grid_host = QWidget()

        self.grid_layout = QGridLayout(
            self.grid_host
        )

        self.grid_layout.setContentsMargins(
            6,
            6,
            6,
            6,
        )

        self.grid_layout.setHorizontalSpacing(
            6
        )

        self.grid_layout.setVerticalSpacing(
            6
        )

        self.grid_layout.setColumnStretch(
            0,
            1,
        )

        self.grid_layout.setColumnStretch(
            1,
            1,
        )

        self.grid_scroll.setWidget(
            self.grid_host
        )

        root.addWidget(
            self.grid_scroll,
            1,
        )

        # --------------------------------------------------------
        # Description
        # --------------------------------------------------------

        self.description_box = GlossaryTextEdit()

        self.description_box.setReadOnly(
            True
        )

        self.description_box.setFixedHeight(
            112
        )

        set_themed_stylesheet(
            self.description_box,
            """
            QTextEdit {
                background-color: #fffaf0;
                border: 1px solid #c79a3b;
                border-radius: 11px;
                padding: 8px;
                font-family: Georgia;
                font-size: 12px;
                color: #25190f;
            }
            """,
        )

        root.addWidget(
            self.description_box
        )

        # --------------------------------------------------------
        # Buttons
        # --------------------------------------------------------

        button_row = QHBoxLayout()

        self.cancel_btn = QPushButton(
            "Close"
            if self.browse_only
            else "Cancel"
        )

        self.add_btn = QPushButton(
            "Add"
        )

        self.cancel_btn.setFixedSize(
            105,
            34,
        )

        self.add_btn.setFixedSize(
            105,
            34,
        )

        set_themed_stylesheet(
            self.cancel_btn,
            BUTTON_SECONDARY_QSS,
        )

        set_themed_stylesheet(
            self.add_btn,
            BUTTON_PRIMARY_QSS,
        )

        self.cancel_btn.clicked.connect(
            self.reject
        )

        self.add_btn.clicked.connect(
            self.accept_selected
        )

        button_row.addWidget(
            self.cancel_btn
        )

        button_row.addStretch()

        if not self.browse_only:
            button_row.addWidget(
                self.add_btn
            )

        root.addLayout(
            button_row
        )

        self.filter_combo.currentIndexChanged.connect(
            self.refresh_filtered_options
        )
        self.search_input.textChanged.connect(
            self.refresh_filtered_options
        )

        self.refresh_filtered_options()


    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(
                0
            )

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self.cards = []
        self.selected_card = None


    def refresh_filtered_options(self):
        selected_filter = (
            self.filter_combo.currentData()
        )

        if selected_filter is None:
            self.options = list(
                self.all_options
            )

        elif (
            selected_filter
            == "__empowerments__"
        ):
            self.options = [
                option
                for option in self.all_options
                if option.get(
                    "kind"
                )
                == "empowerment"
            ]

        else:
            self.options = [
                option
                for option in self.all_options
                if selected_filter
                in option.get(
                    "tags",
                    [],
                )
            ]

        # Search is case-insensitive and combines with the dropdown filter.
        # Separate words can match different parts of the same improvement.
        query_words = self.search_input.text().casefold().split()
        if query_words:
            self.options = [
                option
                for option in self.options
                if all(
                    word in " ".join(
                        (
                            str(option.get("name") or ""),
                            str(option.get("description") or ""),
                            " ".join(str(tag) for tag in (option.get("tags") or [])),
                        )
                    ).casefold()
                    for word in query_words
                )
            ]

        self.clear_grid()

        for index, option in enumerate(
            self.options
        ):
            card = ImprovementPickerCard(
                option,
                select_callback=self.select_card,
                activate_callback=self.activate_card,
                parent=self.grid_host,
            )

            self.cards.append(
                card
            )

            # Hard two-column placement:
            # 0 1
            # 2 3
            # 4 5
            row = index // 2
            column = index % 2

            self.grid_layout.addWidget(
                card,
                row,
                column,
            )

        # Keep both columns equal even when the final row contains one card.
        self.grid_layout.setColumnStretch(
            0,
            1,
        )

        self.grid_layout.setColumnStretch(
            1,
            1,
        )

        # Push short filtered lists to the top.
        self.grid_layout.setRowStretch(
            (len(self.options) + 1) // 2,
            1,
        )

        if self.cards:
            self.select_card(
                self.cards[0]
            )
        else:
            self.selected_option = None
            self.description_box.setPlainText(
                "No matching improvements."
            )

        self.add_btn.setEnabled(bool(self.cards) and not self.browse_only)


    def select_card(
        self,
        card,
    ):
        if card not in self.cards:
            return

        for other in self.cards:
            other.setChecked(
                other is card
            )

        self.selected_card = card
        self.selected_option = (
            card.option
        )

        self.update_description(
            self.selected_option
        )


    def activate_card(
        self,
        card,
    ):
        self.select_card(
            card
        )

        if not self.browse_only:
            self.accept_selected()


    def update_description(
        self,
        option,
    ):
        if not option:
            self.description_box.clear()
            return

        description = str(
            option.get(
                "description",
                "",
            )
            or ""
        ).strip()

        if not description:
            self.description_box.setPlainText(
                "No description."
            )
            return

        rich_markers = (
            "<b>",
            "</b>",
            "<strong>",
            "</strong>",
            "<i>",
            "</i>",
            "<em>",
            "</em>",
            "<u>",
            "</u>",
            "<br>",
            "<br/>",
            "<br />",
        )

        if any(
            marker in description.lower()
            for marker in rich_markers
        ):
            self.description_box.setHtml(
                description.replace(
                    "\n",
                    "<br>",
                )
            )
        else:
            self.description_box.setPlainText(
                description
            )


    def accept_selected(self):
        if (
            self.browse_only
            or self.selected_option
            is None
        ):
            return

        self.accept()


    def open_custom_improvement(self):
        dialog = FantasyCustomImprovementDialog(
            parent=self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        improvement = getattr(
            dialog,
            "improvement",
            None,
        )

        if not improvement:
            return

        self.selected_option = (
            improvement
        )

        self.accept()




class FantasyInventoryItemDialog(
    _OriginalInventoryItemDialog
):
    def __init__(
        self,
        parent=None,
        item=None,
    ):
        super().__init__(
            parent=parent,
            item=item,
        )

        self.setFixedSize(
            500,
            330,
        )

        apply_fantasy_dialog_style(
            self
        )

        self.cancel_btn.setFixedSize(
            105,
            34,
        )

        self.add_btn.setFixedSize(
            105,
            34,
        )


class FantasyInventoryEditDialog(
    _OriginalInventoryEditDialog
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        apply_fantasy_dialog_style(
            self
        )


class FantasyChoiceInputDialog(
    _OriginalChoiceInputDialog
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        apply_fantasy_dialog_style(
            self
        )


class FantasyCustomImprovementDialog(
    _OriginalCustomImprovementDialog
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        kwargs.setdefault(
            "available_icons",
            os.listdir(IMPROVEMENT_ICON_DIR)
            if os.path.isdir(IMPROVEMENT_ICON_DIR) else [],
        )
        super().__init__(
            *args,
            **kwargs,
        )

        for index in range(1, self.icon_input.count()):
            filename = self.icon_input.itemData(index)
            self.icon_input.setItemIcon(
                index, QIcon(os.path.join(IMPROVEMENT_ICON_DIR, filename))
            )

        apply_fantasy_dialog_style(
            self
        )


class FantasyConfirmDialog(QDialog):
    """Consistent replacement for the old thick black Yes/No dialog."""

    def __init__(
        self,
        parent,
        title,
        text,
        yes_text="Yes",
        no_text="No",
        button_width=None,
        button_height=None,
        dialog_width=None,
    ):
        super().__init__(
            parent
        )

        self.setWindowTitle(
            title
        )

        self.setModal(
            True
        )

        requested_dialog_width = (
            max(220, int(dialog_width))
            if dialog_width is not None
            else 360
        )

        if dialog_width is not None:
            self.setFixedWidth(requested_dialog_width)
        else:
            self.setMinimumWidth(requested_dialog_width)

        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )

        layout.setSpacing(
            14
        )

        title_label = QLabel(
            title
        )

        set_themed_stylesheet(
            title_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 20px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        body = QLabel(
            text
        )

        body.setWordWrap(
            True
        )

        body.setMinimumWidth(
            max(160, requested_dialog_width - 45)
        )

        set_themed_stylesheet(
            body,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                color: #3b332a;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        button_row = QHBoxLayout()
        button_row.setSpacing(
            10
        )

        self.no_btn = QPushButton(
            no_text
        )

        self.yes_btn = QPushButton(
            yes_text
        )

        # Default size
        width = (
            int(button_width)
            if button_width is not None
            else 100
        )

        height = (
            int(button_height)
            if button_height is not None
            else 34
        )

        self.no_btn.setFixedSize(
            width,
            height,
        )

        self.yes_btn.setFixedSize(
            width,
            height,
        )

        _style_fantasy_button(
            self.no_btn
        )

        _style_fantasy_button(
            self.yes_btn
        )

        self.no_btn.setAutoDefault(False)
        self.yes_btn.setAutoDefault(False)

        self.no_btn.setDefault(False)
        self.yes_btn.setDefault(False)

        self.no_btn.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.yes_btn.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.no_btn.clicked.connect(
            self.reject
        )

        self.yes_btn.clicked.connect(
            self.accept
        )
        
        self.no_btn.setAutoDefault(
            False
        )

        button_row.addWidget(
            self.no_btn
        )

        button_row.addStretch()

        button_row.addWidget(
            self.yes_btn
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            body
        )

        layout.addLayout(
            button_row
        )

        if button_width is not None and dialog_width is None:
            self.setMinimumWidth(
                max(
                    360,
                    (width * 2) + 70,
                )
            )

        self.adjustSize()



class FantasyOtherDiceDialog(QDialog):
    """Select quantities of all seven DiceBox dice without character rules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Roll Other Dice")
        self.setModal(True)
        self.setMinimumWidth(370)
        set_themed_stylesheet(self, FANTASY_DIALOG_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(8)

        heading = QLabel("Roll Other Dice")
        set_themed_stylesheet(heading, """
            QLabel { font-family: Georgia; font-size: 18px;
                     font-weight: 900; color: #25190f; }
        """)
        root.addWidget(heading)
        hint = QLabel("Select how many of each die to roll together (up to 30 total; maximum 2 d100).")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.dice_counts = {}
        for sides in OTHER_DICE_SIZES:
            line = QHBoxLayout()
            label = QLabel(f"d{sides}")
            counter = NumericEntry(self)
            counter.setObjectName(f"other_dice_d{sides}_count")
            counter.setRange(0, 2 if sides == 100 else 20)
            counter.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
            counter.setFixedSize(86, 32)
            set_themed_stylesheet(counter, """
                QSpinBox { background-color: #fffdf7;
                           color: #25190f; border: 1px solid #c79a3b;
                           border-radius: 7px; font-size: 13px;
                           font-weight: 800; padding: 2px 6px; }
            """)
            counter.valueChanged.connect(self._update_selection)
            counter.installEventFilter(self)
            self.dice_counts[sides] = counter
            line.addWidget(label)
            line.addStretch()
            line.addWidget(counter)
            root.addLayout(line)

        self.selection_label = QLabel()
        self.selection_label.setWordWrap(True)
        root.addWidget(self.selection_label)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        self.roll_button = QPushButton("Roll")
        for button, style in (
            (cancel, BUTTON_SECONDARY_QSS),
            (self.roll_button, BUTTON_PRIMARY_QSS),
        ):
            button.setFixedSize(95, 34)
            set_themed_stylesheet(button, style)
            buttons.addWidget(button)
        # Enter should roll, never dismiss the dialog without rolling.
        cancel.setAutoDefault(False)
        cancel.setDefault(False)
        self.roll_button.setAutoDefault(True)
        self.roll_button.setDefault(True)
        cancel.clicked.connect(self.reject)
        self.roll_button.clicked.connect(self._submit_roll)
        root.addLayout(buttons)
        self._update_selection()

    def _submit_roll(self):
        """Submit only a valid choice; otherwise keep the dialog open."""
        if self.roll_button.isEnabled():
            self.accept()
        else:
            self._update_selection()

    def accept(self):
        # Also guard Qt's implicit Enter/default-button acceptance path.
        if not self.roll_button.isEnabled():
            self._update_selection()
            return
        super().accept()

    def eventFilter(self, watched, event):
        # NumericEntry is a QLineEdit and consumes Return before the parent
        # dialog can handle it. Capture it at the source instead.
        if (
            watched in self.dice_counts.values()
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self._submit_roll()
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        # Also allow Enter when focus is on a label or the dialog itself.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit_roll()
            event.accept()
            return
        super().keyPressEvent(event)

    def selected_counts(self):
        return {size: widget.value() for size, widget in self.dice_counts.items()}

    def _update_selection(self, *_):
        total = sum(self.selected_counts().values())
        self.roll_button.setEnabled(1 <= total <= 30)
        self.selection_label.setText(
            f"{total} dice selected" if total <= 30
            else f"{total} selected — maximum 30 dice per roll"
        )

    def position_inside_sheet(self):
        sheet = self.parentWidget()
        if sheet is None:
            return
        rect = QRect(sheet.mapToGlobal(QPoint(0, 0)), sheet.size())
        screen = QApplication.screenAt(rect.center()) or sheet.screen()
        if screen is not None:
            visible = rect.intersected(screen.availableGeometry())
            if visible.isEmpty():
                visible = screen.availableGeometry()
        else:
            visible = rect
        width, height = self.frameGeometry().width(), self.frameGeometry().height()
        x = visible.left() + (visible.width() - width) // 2
        y = visible.top() + (visible.height() - height) // 2
        self.move(
            max(visible.left(), min(x, visible.right() - width + 1)),
            max(visible.top(), min(y, visible.bottom() - height + 1)),
        )


class FantasyDiceOptionsDialog(QDialog):
    def __init__(
        self,
        stat_name,
        modifier_options,
        parent=None,
    ):
        super().__init__(parent)

        self.setWindowTitle(
            f"{stat_name} Roll"
        )
        self.setModal(True)
        self.setFixedWidth(330)

        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(
            16,
            14,
            16,
            14,
        )
        root.setSpacing(
            10
        )

        title = QLabel(
            f"{stat_name} Roll Options"
        )
        set_themed_stylesheet(
            title,
            """
            QLabel {
                font-family: Georgia;
                font-size: 17px;
                font-weight: 900;
                color: #25190f;
            }
            """,
        )
        root.addWidget(title)

        # Each spinner is a stack of d6s. Increasing one spinner cancels
        # already-selected opposite dice immediately, one for one.
        self.advantage_count = NumericEntry(self)
        self.disadvantage_count = NumericEntry(self)
        for counter in (self.advantage_count, self.disadvantage_count):
            counter.setRange(0, 99)
            counter.setValue(0)
            counter.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            counter.setFixedSize(74, 30)
            counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
            counter.setToolTip(
                "Each advantage cancels one disadvantage before rolling."
            )
            counter.installEventFilter(self)
            if counter.lineEdit() is not None:
                counter.lineEdit().installEventFilter(self)
            set_themed_stylesheet(
                counter,
                """
                QSpinBox {
                    background-color: #fffdf7;
                    border: 1px solid #c79a3b;
                    border-radius: 7px;
                    color: #25190f;
                    font-size: 13px;
                    font-weight: 800;
                    padding: 2px 5px;
                }
                """,
            )
        self._previous_advantage_count = 0
        self._previous_disadvantage_count = 0

        for title_text, counter in (
            ("Advantage (+d6 each)", self.advantage_count),
            ("Disadvantage (−d6 each)", self.disadvantage_count),
        ):
            count_row = QHBoxLayout()
            count_row.addWidget(QLabel(title_text))
            count_row.addStretch()
            count_row.addWidget(counter)
            root.addLayout(count_row)

        self.advantage_count.valueChanged.connect(
            lambda value: self._change_opposed_count(True, value)
        )
        self.disadvantage_count.valueChanged.connect(
            lambda value: self._change_opposed_count(False, value)
        )

        self.modifier_checks = []
        # A checked improvement can be consumed by an opposing die. Keep
        # its checkmark (the user selected the improvement) but never roll
        # its canceled die, and mark the checkbox visibly as canceled.
        self._cancelled_modifier_checks = set()

        if modifier_options:
            heading = QLabel(
                "Optional Improvement / Empowerment Dice"
            )
            set_themed_stylesheet(
                heading,
                """
                QLabel {
                    font-family: Georgia;
                    font-size: 12px;
                    font-weight: 900;
                    color: #765d34;
                }
                """,
            )
            root.addWidget(heading)

            for option in modifier_options:
                checkbox = QCheckBox(
                    option["label"]
                )
                checkbox.setProperty(
                    "dice_modifier",
                    option,
                )
                root.addWidget(checkbox)
                self.modifier_checks.append(
                    checkbox
                )
                checkbox.toggled.connect(
                    lambda checked, box=checkbox:
                        self._change_modifier_selection(box, checked)
                )

        buttons = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        roll_btn = QPushButton("Roll")

        cancel_btn.setFixedSize(95, 34)
        roll_btn.setFixedSize(95, 34)

        set_themed_stylesheet(
            cancel_btn,
            BUTTON_SECONDARY_QSS,
        )
        set_themed_stylesheet(
            roll_btn,
            BUTTON_PRIMARY_QSS,
        )

        cancel_btn.clicked.connect(
            self.reject
        )
        roll_btn.clicked.connect(
            self.accept
        )

        # Keep Cancel on the left and make Enter/Numpad Enter submit Roll.
        cancel_btn.setAutoDefault(False)
        cancel_btn.setDefault(False)
        roll_btn.setAutoDefault(True)
        roll_btn.setDefault(True)
        self.advantage_count.editingFinished.connect(lambda: None)
        buttons.addWidget(cancel_btn)
        buttons.addStretch(1)
        buttons.addWidget(roll_btn)
        root.addLayout(buttons)

    def eventFilter(self, watched, event):
        counters = (self.advantage_count, self.disadvantage_count)
        if (event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and any(watched is counter or watched is counter.lineEdit()
                        for counter in counters)):
            # Commit the typed text before submitting (the spinbox's value
            # may still be the previous number while its editor has focus).
            for counter in counters:
                if callable(getattr(counter, "interpretText", None)):
                    counter.interpretText()
            self.accept()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            event.accept()
            return
        super().keyPressEvent(event)

    def position_inside_sheet(self):
        """Center the modal inside its parent sheet, within the visible screen."""
        sheet = self.parentWidget()
        if sheet is None:
            return

        sheet_rect = QRect(sheet.mapToGlobal(QPoint(0, 0)), sheet.size())
        screen = QApplication.screenAt(sheet_rect.center())
        if screen is None:
            screen = sheet.screen()
        if screen is not None:
            visible = sheet_rect.intersected(screen.availableGeometry())
            if visible.isEmpty():
                visible = screen.availableGeometry()
        else:
            visible = sheet_rect

        width = self.frameGeometry().width()
        height = self.frameGeometry().height()
        x = visible.left() + (visible.width() - width) // 2
        y = visible.top() + (visible.height() - height) // 2
        x = max(visible.left(), min(x, visible.right() - width + 1))
        y = max(visible.top(), min(y, visible.bottom() - height + 1))
        self.move(x, y)

    def _modifier_kind(self, checkbox):
        option = checkbox.property("dice_modifier")
        if not isinstance(option, dict):
            return None
        kind = str(option.get("kind", "")).lower()
        if kind in ("advantage", "disadvantage"):
            return kind
        return None

    def _mark_modifier_cancelled(self, checkbox):
        self._cancelled_modifier_checks.add(checkbox)
        option = checkbox.property("dice_modifier") or {}
        checkbox.setText(str(option.get("label", "Improvement")) + " (canceled)")
        checkbox.setToolTip("Canceled by an opposing advantage/disadvantage; no die will roll.")

    def _change_modifier_selection(self, checkbox, checked):
        """Cancel improvement advantage/disadvantage immediately in the UI."""
        if not checked:
            self._cancelled_modifier_checks.discard(checkbox)
            option = checkbox.property("dice_modifier") or {}
            checkbox.setText(str(option.get("label", "Improvement")))
            checkbox.setToolTip("")
            return

        kind = self._modifier_kind(checkbox)
        if kind not in ("advantage", "disadvantage"):
            return

        opposite = (
            self.disadvantage_count if kind == "advantage"
            else self.advantage_count
        )
        if opposite.value() > 0:
            opposite.blockSignals(True)
            try:
                opposite.setValue(opposite.value() - 1)
            finally:
                opposite.blockSignals(False)
            self._previous_advantage_count = self.advantage_count.value()
            self._previous_disadvantage_count = self.disadvantage_count.value()
            self._mark_modifier_cancelled(checkbox)

    def _change_opposed_count(self, advantage, value):
        """Cancel manual dice first, then active improvement-granted dice."""
        current = self.advantage_count if advantage else self.disadvantage_count
        opposite = self.disadvantage_count if advantage else self.advantage_count
        previous = (
            self._previous_advantage_count
            if advantage else self._previous_disadvantage_count
        )
        increment = max(0, int(value) - previous)
        canceled_manual = min(increment, opposite.value())
        remaining = increment - canceled_manual

        if canceled_manual:
            opposite.blockSignals(True)
            try:
                opposite.setValue(opposite.value() - canceled_manual)
            finally:
                opposite.blockSignals(False)

        canceled_improvements = 0
        if remaining:
            opposite_kind = "disadvantage" if advantage else "advantage"
            for checkbox in self.modifier_checks:
                if canceled_improvements >= remaining:
                    break
                if (
                    checkbox.isChecked()
                    and checkbox not in self._cancelled_modifier_checks
                    and self._modifier_kind(checkbox) == opposite_kind
                ):
                    self._mark_modifier_cancelled(checkbox)
                    canceled_improvements += 1

        canceled_total = canceled_manual + canceled_improvements
        if canceled_total:
            current.blockSignals(True)
            try:
                current.setValue(int(value) - canceled_total)
            finally:
                current.blockSignals(False)

        self._previous_advantage_count = self.advantage_count.value()
        self._previous_disadvantage_count = self.disadvantage_count.value()

    def selected_roll_counts(self):
        return self.advantage_count.value(), self.disadvantage_count.value()

    def selected_roll_type(self):
        """Compatibility with older callers that only understand a sign."""
        advantage, disadvantage = self.selected_roll_counts()
        return (advantage > 0) - (disadvantage > 0)

    def selected_modifiers(self):
        selected = []

        for checkbox in self.modifier_checks:
            if (
                not checkbox.isChecked()
                or checkbox in self._cancelled_modifier_checks
            ):
                continue

            option = checkbox.property(
                "dice_modifier"
            )

            if isinstance(option, dict):
                selected.append(
                    dict(option)
                )

        return selected


class FantasyResourceAdjustDialog(QDialog):
    """
    Tools -> Adjust Resources.

    This changes the character's maximum Hearts, total granted IP, and
    maximum AT without changing Level. Current HP/AT are clamped only when
    a new maximum is lower than the amount currently filled.
    """

    def __init__(
        self,
        character,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.character = character

        self.setWindowTitle(
            "Adjust Resources"
        )
        self.setModal(
            True
        )
        self.setFixedWidth(
            430
        )

        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            20,
            18,
            20,
            18,
        )
        root.setSpacing(
            12
        )

        title = QLabel(
            "Adjust Resources"
        )
        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 21px;
                font-weight: 900;
                color: #25190f;
            }
            """,
        )

        explanation = QLabel(
            "Change the character's resource limits directly. "
            "This does not change the character's Level."
        )
        explanation.setWordWrap(
            True
        )

        root.addWidget(
            title
        )
        root.addWidget(
            explanation
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(
            12
        )
        grid.setVerticalSpacing(
            9
        )

        self.hearts_spin = NumericEntry()
        self.hearts_spin.setRange(
            0,
            999,
        )
        self.hearts_spin.setValue(
            int(
                character.HP.max_hearts
            )
        )

        self.ip_spin = NumericEntry()

        spent_ip = max(
            0,
            int(
                character.progression.used_IP
            ),
        )

        self.ip_spin.setRange(
            spent_ip,
            9999,
        )
        self.ip_spin.setValue(
            max(
                spent_ip,
                int(
                    character.progression.current_IP
                ),
            )
        )

        self.at_spin = NumericEntry()
        self.at_spin.setRange(
            0,
            999,
        )
        self.at_spin.setValue(
            int(
                character.adversity.max_AT
            )
        )

        for spin_box in (
            self.hearts_spin,
            self.ip_spin,
            self.at_spin,
        ):
            spin_box.setButtonSymbols(
                QSpinBox.ButtonSymbols.NoButtons
            )

        fields = (
            (
                "Maximum Hearts",
                self.hearts_spin,
            ),
            (
                "Total IP",
                self.ip_spin,
            ),
            (
                "Maximum AT",
                self.at_spin,
            ),
        )

        for row_index, (
            label_text,
            spin_box,
        ) in enumerate(fields):
            label = QLabel(
                label_text
            )
            label.setMinimumWidth(
                125
            )

            spin_box.setFixedHeight(
                34
            )

            grid.addWidget(
                label,
                row_index,
                0,
            )
            grid.addWidget(
                spin_box,
                row_index,
                1,
            )

        root.addLayout(
            grid
        )

        if spent_ip > 0:
            ip_note = QLabel(
                f"{spent_ip} IP is already spent, so Total IP "
                "cannot be reduced below that amount."
            )
            ip_note.setWordWrap(
                True
            )
            set_themed_stylesheet(
                ip_note,
                """
                QLabel {
                    background: transparent;
                    border: none;
                    color: #765d34;
                    font-size: 11px;
                }
                """,
            )
            root.addWidget(
                ip_note
            )

        button_row = QHBoxLayout()

        cancel_btn = QPushButton(
            "Cancel"
        )
        save_btn = QPushButton(
            "Save"
        )

        cancel_btn.setFixedSize(
            105,
            34,
        )
        save_btn.setFixedSize(
            105,
            34,
        )

        set_themed_stylesheet(
            cancel_btn,
            BUTTON_SECONDARY_QSS,
        )
        set_themed_stylesheet(
            save_btn,
            BUTTON_PRIMARY_QSS,
        )

        cancel_btn.clicked.connect(
            self.reject
        )
        save_btn.clicked.connect(
            self.accept
        )

        save_btn.setDefault(
            True
        )

        button_row.addWidget(
            cancel_btn
        )
        button_row.addStretch()
        button_row.addWidget(
            save_btn
        )

        root.addLayout(
            button_row
        )

    def values(self):
        return {
            "max_hearts": int(
                self.hearts_spin.value()
            ),
            "current_IP": int(
                self.ip_spin.value()
            ),
            "max_AT": int(
                self.at_spin.value()
            ),
        }


def fantasy_ask_yes_no(
    parent,
    title,
    text,
    yes_text="Yes",
    no_text="No",
    button_width=None,
    button_height=None,
    dialog_width=None,
):
    dialog = FantasyConfirmDialog(
        parent,
        title,
        text,
        yes_text=yes_text,
        no_text=no_text,
        button_width=button_width,
        button_height=button_height,
        dialog_width=dialog_width,
    )

    return (
        dialog.exec()
        == QDialog.DialogCode.Accepted
    )



def show_compact_information_dialog(
    parent,
    title,
    text,
    width=360,
):
    """Compact fantasy information popup for short messages."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setFixedWidth(max(280, int(width)))
    set_themed_stylesheet(dialog, FANTASY_DIALOG_QSS)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(14)

    body = QLabel(text)
    body.setWordWrap(True)
    body.setAlignment(Qt.AlignmentFlag.AlignCenter)
    set_themed_stylesheet(body, """
        QLabel {
            background: transparent;
            border: none;
            font-family: Georgia;
            font-size: 13px;
            color: #25190f;
            padding: 0px;
            margin: 0px;
        }
    """)

    ok_btn = QPushButton("OK")
    ok_btn.setFixedSize(82, 34)
    _style_fantasy_button(ok_btn)
    ok_btn.setDefault(True)
    ok_btn.clicked.connect(dialog.accept)

    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(ok_btn)
    row.addStretch()

    layout.addWidget(body)
    layout.addLayout(row)
    dialog.adjustSize()
    return dialog.exec()

def style_fantasy_message_box(message_box):
    """Restyle ordinary warning/info/error QMessageBoxes on show."""

    set_themed_stylesheet(
        message_box,
        """
        QMessageBox {
            background-color: #fffdf7;
        }

        QMessageBox QLabel {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 13px;
            min-width: 260px;
        }
        """,
    )

    for button in message_box.findChildren(
        QPushButton
    ):
        button.setMinimumHeight(
            32
        )

        _style_fantasy_button(
            button
        )


class FantasyMessageBoxEventFilter(QObject):
    def eventFilter(
        self,
        obj,
        event,
    ):
        """
        This filter is installed application-wide, so Qt can call it while
        widgets are in the middle of being destroyed.

        PySide may still have a Python wrapper after the underlying C++
        QLabel/QWidget has disappeared. That lifecycle timing is harmless
        and must not escape as a RuntimeError.
        """

        try:
            if (
                event.type()
                == QEvent.Type.Show
                and isinstance(
                    obj,
                    QMessageBox,
                )
            ):
                style_fantasy_message_box(
                    obj
                )

        except (
            RuntimeError,
            ReferenceError,
        ):
            return False

        return False



def install_fantasy_runtime_ui():
    """
    Install runtime-only styling hooks.
    Safe to call more than once.
    """

    app = QApplication.instance()

    if app is None:
        return

    apply_fantasy_application_style()

    if not hasattr(
        app,
        "_did_fantasy_message_filter",
    ):
        event_filter = (
            FantasyMessageBoxEventFilter(
                app
            )
        )

        app.installEventFilter(
            event_filter
        )

        app._did_fantasy_message_filter = (
            event_filter
        )


# Rebind dialog classes/functions at runtime.
# Existing mixins keep all their original logic, but instantiate the
# redesigned presentation classes from now on.

ImprovementPickerDialog = (
    FantasyImprovementPickerDialog
)
InventoryItemDialog = (
    FantasyInventoryItemDialog
)
InventoryEditDialog = (
    FantasyInventoryEditDialog
)
ChoiceInputDialog = (
    FantasyChoiceInputDialog
)
CustomImprovementDialog = (
    FantasyCustomImprovementDialog
)
ask_yes_no = fantasy_ask_yes_no

dialogs_module.ImprovementPickerDialog = (
    FantasyImprovementPickerDialog
)
dialogs_module.ChoiceInputDialog = (
    FantasyChoiceInputDialog
)
dialogs_module.CustomImprovementDialog = (
    FantasyCustomImprovementDialog
)
dialogs_module.ask_yes_no = (
    fantasy_ask_yes_no
)

improvements_ui_module.ImprovementPickerDialog = (
    FantasyImprovementPickerDialog
)
improvements_ui_module.ChoiceInputDialog = (
    FantasyChoiceInputDialog
)
improvements_ui_module.CustomImprovementDialog = (
    FantasyCustomImprovementDialog
)
improvements_ui_module.ask_yes_no = (
    fantasy_ask_yes_no
)

inventory_ui_module.InventoryItemDialog = (
    FantasyInventoryItemDialog
)
inventory_ui_module.InventoryEditDialog = (
    FantasyInventoryEditDialog
)
inventory_ui_module.ask_yes_no = (
    fantasy_ask_yes_no
)

notes_ui_module.ask_yes_no = (
    fantasy_ask_yes_no
)
character_display_ui_module.ask_yes_no = (
    fantasy_ask_yes_no
)
character_display_ui_module.ImprovementPickerDialog = (
    FantasyImprovementPickerDialog
)
character_display_ui_module.ChoiceInputDialog = (
    FantasyChoiceInputDialog
)


class DIDUpdateManager(QObject):
    """
    Small asynchronous GitHub updater.

    Startup checks are silent when the computer is offline.
    A newer GitHub Release prompts the player before anything is downloaded.
    """

    def __init__(
        self,
        main_window,
    ):
        super().__init__(
            main_window
        )

        self.main_window = main_window
        self.network = QNetworkAccessManager(
            self
        )

        self._release_reply = None
        self._release_check_silent = True

        # None when this build is current. When a newer installer-backed
        # release is found, this holds everything needed to offer it later
        # from the Tools menu.
        self.available_update = None

        self._download_reply = None
        self._download_file = None
        self._download_path = None
        self._download_dialog = None
        self._download_progress = None
        self._download_cancelled = False
        self._download_version = None
        self._download_digest = None

    # ============================================================
    # RELEASE CHECK
    # ============================================================

    def check_for_updates(
        self,
        silent=True,
    ):
        if self._release_reply is not None:
            # A quiet startup check may still be running when the player
            # manually chooses Tools -> Check for Updates. Do not start a
            # duplicate request and do not show an unnecessary
            # "already in progress" message. Instead, promote the existing
            # request to a manual check so its eventual result is shown.
            if not silent:
                self._release_check_silent = False
                if getattr(self, "_check_notice", None) is None:
                    self._check_notice = BusyNotice(self.main_window, "Checking for updates…")

            return

        self._release_check_silent = bool(
            silent
        )

        if not silent:
            self._check_notice = BusyNotice(self.main_window, "Checking for updates…")
        request = QNetworkRequest(
            QUrl(
                GITHUB_LATEST_RELEASE_API
            )
        )

        request.setRawHeader(
            b"Accept",
            b"application/vnd.github+json",
        )
        request.setRawHeader(
            b"X-GitHub-Api-Version",
            b"2022-11-28",
        )
        request.setRawHeader(
            b"User-Agent",
            (
                f"DID-Character-Sheet/"
                f"{APP_VERSION}"
            ).encode(
                "ascii",
                errors="ignore",
            ),
        )

        request.setTransferTimeout(30000)
        reply = self.network.get(
            request
        )

        self._release_reply = reply

        reply.finished.connect(
            lambda:
                self._finish_release_check(
                    reply
                )
        )

    def _finish_release_check(
        self,
        reply,
    ):
        if reply is not self._release_reply:
            reply.deleteLater()
            return

        self._release_reply = None
        notice = getattr(self, "_check_notice", None)
        if notice is not None:
            notice.finish()
            self._check_notice = None

        network_error = (
            reply.error()
            != QNetworkReply.NetworkError.NoError
        )

        if network_error:
            error_text = (
                reply.errorString()
            )
            reply.deleteLater()

            # Opening the character sheet should never be interrupted merely
            # because GitHub or the Internet is unavailable.
            if not self._release_check_silent:
                QMessageBox.warning(
                    self.main_window,
                    "Update Check Failed",
                    (
                        "DID Character Sheet could not check "
                        "for updates right now.\n\n"
                        f"{error_text}"
                    ),
                )
            return

        try:
            payload = json.loads(
                bytes(
                    reply.readAll()
                ).decode(
                    "utf-8"
                )
            )
        except Exception:
            reply.deleteLater()

            if not self._release_check_silent:
                QMessageBox.warning(
                    self.main_window,
                    "Update Check Failed",
                    (
                        "GitHub returned an update response "
                        "that could not be read."
                    ),
                )
            return

        reply.deleteLater()

        latest_tag = str(
            payload.get(
                "tag_name",
                "",
            )
        ).strip()

        latest_version = (
            latest_tag.lstrip(
                "vV"
            )
        )
        release_notes = str(
            payload.get(
                "body",
                "",
            )
            or ""
        ).strip()

        if not latest_version:
            if not self._release_check_silent:
                QMessageBox.warning(
                    self.main_window,
                    "Update Check Failed",
                    (
                        "The latest GitHub release does not "
                        "contain a version tag."
                    ),
                )
            return

        if (
            did_version_key(
                latest_version
            )
            <= did_version_key(
                APP_VERSION
            )
        ):
            self._publish_available_update(
                None
            )

            # On the first launch of a newly installed release, reuse the
            # GitHub Release description as an in-app "What's new" message.
            # Show it once per exact app version; offline startup simply
            # postpones it until a later successful background check.
            if (
                self._release_check_silent
                and did_version_key(latest_version)
                == did_version_key(APP_VERSION)
                and release_notes
            ):
                QTimer.singleShot(
                    0,
                    lambda version=latest_version, notes=release_notes:
                        self.main_window.show_release_notes_if_needed(
                            version,
                            notes,
                        )
                )

            if not self._release_check_silent:
                show_compact_information_dialog(
                    self.main_window,
                    "No Updates",
                    (
                        "DID Character Sheet is up to date.\n\n"
                        f"Current version: {APP_VERSION}"
                    ),
                    width=360,
                )
            return

        asset = self._find_installer_asset(
            payload
        )

        if asset is None:
            self._publish_available_update(
                None
            )

            if not self._release_check_silent:
                QMessageBox.warning(
                    self.main_window,
                    "Update Not Available",
                    (
                        f"Version {latest_version} exists, "
                        "but its Windows installer could not "
                        "be found in the GitHub release."
                    ),
                )
            return

        download_url = str(
            asset.get(
                "browser_download_url",
                "",
            )
        ).strip()

        asset_name = str(
            asset.get(
                "name",
                (
                    "DID_Character_Sheet_"
                    f"Setup_{latest_version}.exe"
                ),
            )
        ).strip()

        digest = str(
            asset.get(
                "digest",
                "",
            )
            or ""
        ).strip()

        if not download_url:
            self._publish_available_update(
                None
            )
            return

        release_info = {
            "version": latest_version,
            "download_url": download_url,
            "asset_name": asset_name,
            "digest": digest,
            "release_notes": release_notes,
        }

        self._publish_available_update(
            release_info
        )

        # Startup checks are genuinely silent now. Their only visible effect
        # is that Tools gains a bright-red Update Available row.
        if self._release_check_silent:
            return

        self.offer_available_update()

    def _publish_available_update(
        self,
        release_info,
    ):
        self.available_update = (
            release_info
        )

        self.main_window._available_update_release = (
            release_info
        )


    def offer_available_update(
        self,
    ):
        release_info = (
            self.available_update
            or getattr(
                self.main_window,
                "_available_update_release",
                None,
            )
        )

        if not release_info:
            return

        self._offer_update(
            release_info["version"],
            release_info["download_url"],
            release_info["asset_name"],
            release_info.get(
                "digest",
                "",
            ),
        )


    def _find_installer_asset(
        self,
        release_payload,
    ):
        assets = release_payload.get(
            "assets",
            [],
        )

        preferred = None

        for asset in assets:
            name = str(
                asset.get(
                    "name",
                    "",
                )
            )

            lower_name = name.lower()

            if not lower_name.endswith(
                ".exe"
            ):
                continue

            if (
                lower_name.startswith(
                    "did_character_sheet_setup_"
                )
            ):
                return asset

            if preferred is None:
                preferred = asset

        return preferred

    def _offer_update(
        self,
        latest_version,
        download_url,
        asset_name,
        digest,
    ):
        dialog = FantasyConfirmDialog(
            self.main_window,
            "Update Available",
            (
                "A newer version of DID Character Sheet "
                "is available.\n\n"
                f"Current version: {APP_VERSION}\n"
                f"New version: {latest_version}\n\n"
                "Download the update now?"
            ),
            yes_text="Download Update",
            no_text="Later",
            button_width=135,
        )

        result = dialog.exec()

        # Explicitly remove the first prompt before showing download/update
        # UI so it cannot remain visible behind the next dialog.
        dialog.close()
        dialog.deleteLater()

        if (
            result
            != QDialog.DialogCode.Accepted
        ):
            return

        self.download_update(
            latest_version,
            download_url,
            asset_name,
            digest,
        )

    # ============================================================
    # DOWNLOAD
    # ============================================================

    def download_update(
        self,
        latest_version,
        download_url,
        asset_name,
        digest="",
    ):
        if self._download_reply is not None:
            return

        safe_name = os.path.basename(
            asset_name
        )

        if not safe_name.lower().endswith(
            ".exe"
        ):
            safe_name = (
                "DID_Character_Sheet_"
                f"Setup_{latest_version}.exe"
            )

        download_path = os.path.join(
            tempfile.gettempdir(),
            safe_name,
        )

        try:
            download_file = open(
                download_path,
                "wb",
            )
        except OSError as error:
            QMessageBox.critical(
                self.main_window,
                "Update Download Failed",
                (
                    "The update installer could not be "
                    "created on this computer.\n\n"
                    f"{error}"
                ),
            )
            return

        request = QNetworkRequest(
            QUrl(
                download_url
            )
        )

        request.setRawHeader(
            b"User-Agent",
            (
                f"DID-Character-Sheet/"
                f"{APP_VERSION}"
            ).encode(
                "ascii",
                errors="ignore",
            ),
        )

        reply = self.network.get(
            request
        )

        self._download_reply = reply
        self._download_file = download_file
        self._download_path = download_path
        self._download_cancelled = False
        self._download_version = latest_version
        self._download_digest = digest

        self._build_download_dialog(
            latest_version
        )

        reply.readyRead.connect(
            lambda:
                self._write_download_data(
                    reply
                )
        )

        reply.downloadProgress.connect(
            self._update_download_progress
        )

        reply.finished.connect(
            lambda:
                self._finish_download(
                    reply
                )
        )

    def _build_download_dialog(
        self,
        latest_version,
    ):
        dialog = QDialog(
            self.main_window
        )
        dialog.setWindowTitle(
            "Downloading Update"
        )
        dialog.setModal(
            False
        )
        dialog.setFixedWidth(
            430
        )

        set_themed_stylesheet(
            dialog,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(
            dialog
        )
        layout.setContentsMargins(
            20, 18, 20, 18
        )
        layout.setSpacing(
            12
        )

        title = QLabel(
            f"Downloading version {latest_version}"
        )
        title.setWordWrap(
            True
        )

        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 17px;
                font-weight: 900;
                color: #25190f;
            }
            """,
        )

        status = QLabel(
            "You can keep using the character sheet while the update downloads."
        )
        status.setWordWrap(
            True
        )

        progress = QProgressBar()
        progress.setRange(
            0,
            0,
        )
        progress.setTextVisible(
            True
        )

        set_themed_stylesheet(
            progress,
            """
            QProgressBar {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 8px;
                text-align: center;
                color: #25190f;
                min-height: 22px;
            }

            QProgressBar::chunk {
                background-color: #d8edf7;
                border-radius: 7px;
            }
            """,
        )

        cancel_btn = QPushButton(
            "Cancel"
        )
        cancel_btn.setFixedSize(
            105,
            34,
        )
        set_themed_stylesheet(
            cancel_btn,
            BUTTON_SECONDARY_QSS,
        )

        cancel_btn.clicked.connect(
            self.cancel_download
        )

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(
            cancel_btn
        )

        title_row = QHBoxLayout()
        title_row.addWidget(LoadingRing(dialog))
        title_row.addWidget(title, 1)
        layout.addLayout(title_row)
        layout.addWidget(
            status
        )
        layout.addWidget(
            progress
        )
        layout.addLayout(
            button_row
        )

        self._download_dialog = dialog
        self._download_progress = progress

        dialog.show()
        dialog.raise_()

    def _write_download_data(
        self,
        reply,
    ):
        if (
            reply is not self._download_reply
            or self._download_file is None
        ):
            return

        try:
            data = bytes(
                reply.readAll()
            )

            if data:
                self._download_file.write(
                    data
                )

        except Exception:
            self.cancel_download()

    def _update_download_progress(
        self,
        received,
        total,
    ):
        progress = self._download_progress

        if progress is None:
            return

        if total <= 0:
            progress.setRange(
                0,
                0,
            )
            return

        progress.setRange(
            0,
            100,
        )

        percent = int(
            (received * 100)
            / total
        )

        progress.setValue(
            max(
                0,
                min(
                    100,
                    percent,
                ),
            )
        )

    def cancel_download(
        self,
    ):
        self._download_cancelled = True

        reply = self._download_reply

        if reply is not None:
            reply.abort()

        dialog = self._download_dialog

        if dialog is not None:
            dialog.close()

    def _finish_download(
        self,
        reply,
    ):
        if reply is not self._download_reply:
            reply.deleteLater()
            return

        # Pick up any bytes delivered just before finished().
        self._write_download_data(
            reply
        )

        network_error = (
            reply.error()
            != QNetworkReply.NetworkError.NoError
        )

        error_text = (
            reply.errorString()
        )

        reply.deleteLater()

        download_file = (
            self._download_file
        )
        download_path = (
            self._download_path
        )
        latest_version = (
            self._download_version
        )
        expected_digest = (
            self._download_digest
        )

        self._download_reply = None
        self._download_file = None
        self._download_path = None
        self._download_version = None
        self._download_digest = None

        if download_file is not None:
            try:
                download_file.flush()
                download_file.close()
            except Exception:
                pass

        dialog = self._download_dialog

        self._download_dialog = None
        self._download_progress = None

        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

        if self._download_cancelled:
            self._download_cancelled = False
            self._delete_file_quietly(
                download_path
            )
            return

        if network_error:
            self._delete_file_quietly(
                download_path
            )

            QMessageBox.warning(
                self.main_window,
                "Update Download Failed",
                (
                    "The update could not be downloaded.\n\n"
                    f"{error_text}"
                ),
            )
            return

        if (
            not download_path
            or not os.path.isfile(
                download_path
            )
            or os.path.getsize(
                download_path
            ) <= 0
        ):
            self._delete_file_quietly(
                download_path
            )

            QMessageBox.warning(
                self.main_window,
                "Update Download Failed",
                "The downloaded installer was empty.",
            )
            return

        if not self._verify_download_digest(
            download_path,
            expected_digest,
        ):
            self._delete_file_quietly(
                download_path
            )

            QMessageBox.critical(
                self.main_window,
                "Update Verification Failed",
                (
                    "The downloaded installer did not match "
                    "GitHub's checksum and will not be opened."
                ),
            )
            return

        self._offer_install(
            latest_version,
            download_path,
        )

    def _verify_download_digest(
        self,
        filepath,
        expected_digest,
    ):
        digest_text = str(
            expected_digest or ""
        ).strip()

        # GitHub may omit the digest on some release assets. In that case
        # HTTPS is still used, but there is no release-side checksum to test.
        if not digest_text:
            return True

        if ":" not in digest_text:
            return True

        algorithm, expected = (
            digest_text.split(
                ":",
                1,
            )
        )

        if algorithm.lower() != "sha256":
            return True

        expected = expected.strip().lower()

        sha256 = hashlib.sha256()

        try:
            with open(
                filepath,
                "rb",
            ) as handle:
                while True:
                    chunk = handle.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    sha256.update(
                        chunk
                    )
        except OSError:
            return False

        return (
            sha256.hexdigest().lower()
            == expected
        )

    def _offer_install(
        self,
        latest_version,
        installer_path,
    ):
        dialog = FantasyConfirmDialog(
            self.main_window,
            "Update Ready",
            (
                f"Version {latest_version} has finished downloading.\n\n"
                "Install it now?\n\n"
                "DID Character Sheet will close first. "
                "The installer will then open automatically."
            ),
            yes_text="Install Now",
            no_text="Later",
            button_width=125,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            self._delete_file_quietly(
                installer_path
            )
            return

        self.main_window._pending_update_installer_path = (
            installer_path
        )

        # close() returns False if the user's normal unsaved-changes dialog
        # cancels the close. In that case the update must NOT unexpectedly
        # launch later.
        closed = self.main_window.close()

        if not closed:
            self.main_window._pending_update_installer_path = None

    @staticmethod
    def _delete_file_quietly(
        filepath,
    ):
        if not filepath:
            return

        try:
            if os.path.exists(
                filepath
            ):
                os.remove(
                    filepath
                )
        except OSError:
            pass



def _load_character_portrait_pixmap(
    image_data,
):
    """Convert the stored data:image/... portrait into a QPixmap."""
    if not image_data:
        return QPixmap()

    try:
        image_data = str(
            image_data
        )

        if (
            image_data.startswith(
                "data:image/"
            )
            and "," in image_data
        ):
            payload = image_data.split(
                ",",
                1,
            )[1]

            raw = base64.b64decode(
                payload
            )

            pixmap = QPixmap()
            pixmap.loadFromData(
                raw
            )

            return pixmap

        if os.path.isfile(
            image_data
        ):
            return QPixmap(
                image_data
            )

    except Exception:
        pass

    return QPixmap()


class CharacterLoadCard(QWidget):
    """Visual saved-character row used by Load Character."""

    def __init__(
        self,
        record,
        parent=None,
    ):
        super().__init__(parent)

        self.record = dict(
            record
        )

        # Let the QListWidget receive the click/selection.
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            8,
            6,
            10,
            6,
        )

        layout.setSpacing(
            12
        )

        portrait = QLabel()
        portrait.setFixedSize(
            70,
            70,
        )

        portrait.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            portrait,
            """
            QLabel {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 8px;
                color: #a87824;
                font-family: Georgia;
                font-size: 20px;
                font-weight: 900;
            }
            """,
        )

        pixmap = (
            _load_character_portrait_pixmap(
                self.record.get(
                    "portrait"
                )
            )
        )

        if not pixmap.isNull():
            scaled = pixmap.scaled(
                68,
                68,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )

            x = max(
                0,
                (
                    scaled.width()
                    - 68
                )
                // 2,
            )

            y = max(
                0,
                (
                    scaled.height()
                    - 68
                )
                // 2,
            )

            thumbnail = scaled.copy(
                x,
                y,
                68,
                68,
            )

            portrait.setPixmap(
                portrait_pixmap_for_current_theme(
                    thumbnail
                )
            )

        else:
            portrait.setText(
                "✦"
            )

        info = QVBoxLayout()
        info.setContentsMargins(
            0,
            2,
            0,
            2,
        )
        info.setSpacing(
            3
        )

        name_label = QLabel(
            self.record.get(
                "name",
                "Unnamed Character",
            )
        )

        set_themed_stylesheet(
            name_label,
            """
            QLabel {
                background: transparent;
                border: none;
                color: #25190f;
                font-family: Georgia;
                font-size: 16px;
                font-weight: 900;
            }
            """,
        )

        species = str(
            self.record.get(
                "species",
                "",
            )
            or ""
        ).strip()

        species_label = QLabel(
            species
            if species
            else "No Species"
        )

        set_themed_stylesheet(
            species_label,
            """
            QLabel {
                background: transparent;
                border: none;
                color: #765d34;
                font-family: Georgia;
                font-size: 12px;
                font-style: italic;
            }
            """,
        )

        used_ip = int(
            self.record.get(
                "used_ip",
                0,
            )
        )

        total_ip = int(
            self.record.get(
                "total_ip",
                0,
            )
        )

        ip_label = QLabel(
            f"IP: {used_ip} / {total_ip}"
        )

        set_themed_stylesheet(
            ip_label,
            """
            QLabel {
                background: transparent;
                border: none;
                color: #3b332a;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 700;
            }
            """,
        )

        info.addWidget(
            name_label
        )
        info.addWidget(
            species_label
        )
        info.addWidget(
            ip_label
        )
        info.addStretch()

        layout.addWidget(
            portrait
        )
        layout.addLayout(
            info,
            1,
        )


class FantasyLoadCharacterDialog(QDialog):
    """
    Compact saved-character picker.

    The first five characters are shown in last-opened order. "Rest" adds
    every remaining character to the same list, preserving that order.
    """

    def __init__(
        self,
        character_records,
        parent=None,
        initial_visible_count=5,
    ):
        super().__init__(
            parent
        )

        self.character_records = [
            dict(
                record
            )
            for record in (
                character_records
                or []
            )
        ]

        self.initial_visible_count = max(
            1,
            int(
                initial_visible_count
            ),
        )

        self.visible_count = min(
            self.initial_visible_count,
            len(
                self.character_records
            ),
        )

        self.setWindowTitle(
            "Load Character"
        )

        self.setModal(
            True
        )

        # Much smaller than the previous Recent + All window.
        self.setFixedSize(
            650,
            565,
        )

        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            22,
            18,
            22,
            18,
        )

        root.setSpacing(
            10
        )

        title = QLabel(
            "Load Character"
        )

        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 22px;
                font-weight: 900;
                color: #25190f;
            }
            """,
        )

        subtitle = QLabel(
            "Choose a saved character to open."
        )

        set_themed_stylesheet(
            subtitle,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                color: #3b332a;
            }
            """,
        )

        root.addWidget(
            title
        )

        root.addWidget(
            subtitle
        )

        heading_row = QHBoxLayout()
        heading_row.setContentsMargins(
            2,
            0,
            2,
            0,
        )

        heading_row.setSpacing(
            8
        )

        recent_title = QLabel(
            "Recent Characters"
        )

        set_themed_stylesheet(
            recent_title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 900;
                color: #765d34;
            }
            """,
        )

        self.rest_btn = QPushButton(
            "Rest"
        )

        self.rest_btn.setFixedSize(
            72,
            28,
        )

        self.rest_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.rest_btn.setToolTip(
            "Show the rest of your saved characters"
        )

        set_themed_stylesheet(
            self.rest_btn,
            BUTTON_SECONDARY_QSS,
        )

        self.rest_btn.clicked.connect(
            self.show_rest
        )

        heading_row.addWidget(
            recent_title
        )

        heading_row.addStretch()

        heading_row.addWidget(
            self.rest_btn
        )

        root.addLayout(
            heading_row
        )

        self.character_list = QListWidget()

        set_themed_stylesheet(
            self.character_list,
            """
            QListWidget {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 11px;
                padding: 5px;
                outline: none;
            }

            QListWidget::item {
                border: none;
                border-radius: 9px;
                padding: 0px;
                margin: 2px 0px;
            }

            QListWidget::item:selected {
                background-color: #d8edf7;
            }

            QListWidget::item:hover {
                background-color: #fff4df;
            }
            """,
        )

        self.character_list.itemDoubleClicked.connect(
            lambda _item:
                self.accept()
        )

        self.character_list.itemActivated.connect(
            lambda _item:
                self.accept()
        )

        root.addWidget(
            self.character_list,
            1,
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(
            10
        )

        self.cancel_btn = QPushButton(
            "Cancel"
        )

        self.load_btn = QPushButton(
            "Load Character"
        )

        self.cancel_btn.setFixedSize(
            110,
            34,
        )

        self.load_btn.setFixedSize(
            135,
            34,
        )

        set_themed_stylesheet(
            self.cancel_btn,
            BUTTON_SECONDARY_QSS,
        )

        set_themed_stylesheet(
            self.load_btn,
            BUTTON_PRIMARY_QSS,
        )

        self.cancel_btn.clicked.connect(
            self.reject
        )

        self.load_btn.clicked.connect(
            self.accept
        )

        self.load_btn.setDefault(
            True
        )

        self.load_btn.setAutoDefault(
            True
        )

        buttons.addWidget(
            self.cancel_btn
        )

        buttons.addStretch()

        buttons.addWidget(
            self.load_btn
        )

        root.addLayout(
            buttons
        )

        self._append_records(
            self.character_records[
                :self.visible_count
            ]
        )

        self._refresh_rest_button()

        if self.character_list.count():
            self.character_list.setCurrentRow(
                0
            )

            self.character_list.setFocus()


    def _append_records(
        self,
        records,
    ):
        for record in records:
            item = QListWidgetItem()

            item.setData(
                Qt.ItemDataRole.UserRole,
                record.get(
                    "filepath"
                ),
            )

            item.setSizeHint(
                QSize(
                    0,
                    86,
                )
            )

            self.character_list.addItem(
                item
            )

            self.character_list.setItemWidget(
                item,
                CharacterLoadCard(
                    record,
                    self.character_list,
                ),
            )


    def _refresh_rest_button(self):
        has_rest = (
            self.visible_count
            < len(
                self.character_records
            )
        )

        self.rest_btn.setVisible(
            has_rest
        )

        self.rest_btn.setEnabled(
            has_rest
        )


    def show_rest(self):
        if (
            self.visible_count
            >= len(
                self.character_records
            )
        ):
            return

        remaining = (
            self.character_records[
                self.visible_count:
            ]
        )

        self._append_records(
            remaining
        )

        self.visible_count = len(
            self.character_records
        )

        self._refresh_rest_button()


    def selected_filepath(self):
        item = (
            self.character_list
            .currentItem()
        )

        if item is None:
            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )

class FantasyVersionHistoryDialog(QDialog):
    """Friendly, player-facing history picker."""

    def __init__(
        self,
        versions,
        parent=None,
    ):
        super().__init__(parent)

        self.versions = list(versions)

        self.setWindowTitle(
            "Earlier Versions"
        )
        self.setModal(True)
        self.setFixedSize(
            640,
            600,
        )

        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(
            22, 18, 22, 18
        )
        root.setSpacing(12)

        title = QLabel(
            "Earlier Versions"
        )
        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 22px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        explanation = QLabel(
            "Choose an earlier saved version of this character."
        )
        explanation.setWordWrap(True)
        set_themed_stylesheet(
            explanation,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 13px;
                color: #3b332a;
                padding: 0px 0px 4px 0px;
            }
            """,
        )

        self.version_list = QListWidget()
        set_themed_stylesheet(
            self.version_list,
            """
            QListWidget {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 11px;
                padding: 6px;
                color: #25190f;
                font-family: Georgia;
                font-size: 13px;
                outline: none;
            }

            QListWidget::item {
                border: none;
                border-radius: 8px;
                padding: 10px 10px;
                margin: 2px 0px;
            }

            QListWidget::item:selected {
                background-color: #d8edf7;
                color: #25190f;
            }

            QListWidget::item:hover {
                background-color: #fff4df;
            }
            """,
        )

        for version in self.versions:
            self.version_list.addItem(
                version["display"]
            )

        preview_title = QLabel(
            "Restoring this version will change:"
        )

        set_themed_stylesheet(
            preview_title,
            '''
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 900;
                color: #765d34;
                padding: 2px 1px 0px 1px;
            }
            ''',
        )

        self.change_preview = QTextEdit()
        self.change_preview.setReadOnly(True)
        self.change_preview.setFixedHeight(118)

        set_themed_stylesheet(
            self.change_preview,
            '''
            QTextEdit {
                background-color: #fffaf0;
                border: 1px solid #d8bd82;
                border-radius: 9px;
                color: #25190f;
                font-family: Georgia;
                font-size: 12px;
                padding: 7px;
            }
            ''',
        )

        self.version_list.currentRowChanged.connect(
            self.refresh_change_preview
        )

        if self.versions:
            self.version_list.setCurrentRow(0)
            self.refresh_change_preview(0)

        reassurance = QLabel(
            "Restoring a version does not erase the newer versions."
        )
        reassurance.setWordWrap(True)
        set_themed_stylesheet(
            reassurance,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                color: #765d34;
                padding: 2px 0px;
            }
            """,
        )

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        cancel_btn = QPushButton(
            "Cancel"
        )
        self.restore_btn = QPushButton(
            "Restore Version"
        )

        cancel_btn.setFixedSize(
            110,
            34,
        )
        self.restore_btn.setFixedSize(
            140,
            34,
        )

        set_themed_stylesheet(
            cancel_btn,
            BUTTON_SECONDARY_QSS,
        )
        set_themed_stylesheet(
            self.restore_btn,
            BUTTON_PRIMARY_QSS,
        )

        cancel_btn.clicked.connect(
            self.reject
        )
        self.restore_btn.clicked.connect(
            self.accept
        )
        self.version_list.itemDoubleClicked.connect(
            lambda _item: self.accept()
        )

        button_row.addWidget(
            cancel_btn
        )
        button_row.addStretch()
        button_row.addWidget(
            self.restore_btn
        )

        root.addWidget(title)
        root.addWidget(explanation)
        root.addWidget(
            self.version_list,
            1,
        )
        root.addWidget(
            preview_title
        )
        root.addWidget(
            self.change_preview
        )
        root.addWidget(reassurance)
        root.addLayout(button_row)

    def refresh_change_preview(
        self,
        row,
    ):
        if not (
            0 <= row < len(
                self.versions
            )
        ):
            self.change_preview.clear()
            return

        changes = (
            self.versions[
                row
            ].get(
                "changes",
                [],
            )
        )

        if not changes:
            changes = [
                "No meaningful differences."
            ]

        self.change_preview.setPlainText(
            "\n".join(
                f"• {change}"
                for change in changes
            )
        )


    def selected_version(self):
        row = self.version_list.currentRow()

        if not (
            0 <= row < len(self.versions)
        ):
            return None

        return self.versions[row]


class FantasyTemporaryNoteDialog(QDialog):
    """
    Small passive read-only reference note shown while hovering an
    Improvement's related-note icon.

    This is deliberately separate from the permanent Notes-page NoteCard.
    """

    POPUP_WIDTH = 290

    def __init__(
        self,
        title,
        body_html,
        color_key="blue",
        parent=None,
    ):
        super().__init__(parent)

        self.setModal(False)

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        # A top-level Qt window does not get truly transparent rounded
        # corners merely from QSS border-radius. Make the window itself
        # transparent and paint the rounded note on an inner frame.
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setFixedWidth(
            self.POPUP_WIDTH
        )

        dark = (
            ui_theme_module.CURRENT_THEME
            == "dark"
        )

        # The popup must use the same saved HEX and theme transformation as
        # the full Notes page; otherwise custom notes preview as default blue.
        outer_color, body_color = note_colors_for_theme(color_key)
        text_color = "#f2eee7" if dark else "#25190f"
        border_color = "#8e7446" if dark else "#c79a3b"

        set_themed_stylesheet(
            self,
            """
            QDialog {
                background: transparent;
                border: none;
            }
            """,
        )

        window_layout = QVBoxLayout(
            self
        )
        window_layout.setContentsMargins(
            0, 0, 0, 0
        )
        window_layout.setSpacing(
            0
        )

        outer_frame = QFrame()
        outer_frame.setObjectName(
            "TemporaryReferenceNote"
        )

        set_themed_stylesheet(
            outer_frame,
            f"""
            QFrame#TemporaryReferenceNote {{
                background-color: {outer_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            """,
        )

        root = QVBoxLayout(
            outer_frame
        )
        root.setContentsMargins(
            10, 8, 10, 9
        )
        root.setSpacing(
            5
        )

        title_label = QLabel(
            title
        )

        set_themed_stylesheet(
            title_label,
            f"""
            QLabel {{
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 14px;
                font-weight: 900;
                color: {text_color};
                padding: 0px 2px 2px 2px;
                margin: 0px;
            }}
            """,
        )

        body = QLabel()
        body.setTextFormat(
            Qt.TextFormat.RichText
        )
        body.setText(
            body_html
        )
        body.setWordWrap(
            True
        )

        body.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )

        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        body.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        set_themed_stylesheet(
            body,
            f"""
            QLabel {{
                background-color: {body_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                color: {text_color};
                font-family: Georgia;
                font-size: 11px;
                padding: 7px;
                margin: 0px;
            }}
            """,
        )

        root.addWidget(
            title_label
        )
        root.addWidget(
            body
        )

        window_layout.addWidget(
            outer_frame
        )

        body_width = (
            self.POPUP_WIDTH
            - 20
        )

        body.setFixedWidth(
            body_width
        )

        body_height = body.heightForWidth(
            body_width
        )

        body.setFixedHeight(
            max(
                44,
                body_height + 4,
            )
        )

        root.activate()
        outer_frame.adjustSize()
        window_layout.activate()

        self.setFixedHeight(
            max(
                82,
                outer_frame.sizeHint().height(),
            )
        )

class FantasyMenuButton(QPushButton):
    """Tools button with a painted menu icon instead of an emoji glyph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(fantasy_runtime_color("#6c5428")), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = self.width() / 2.0
        half = min(8.0, self.width() * 0.23)
        for offset in (-6.0, 0.0, 6.0):
            y = self.height() / 2.0 + offset
            painter.drawLine(QPointF(cx-half, y), QPointF(cx+half, y))
        painter.end()



class ExternalSvgIcon(QWidget):
    """Render an SVG file from the redesign icon folders."""

    def __init__(self, path, size=30, parent=None):
        super().__init__(parent)

        self.renderer = (
            QSvgRenderer(path)
            if QSvgRenderer is not None
            and os.path.exists(path)
            else None
        )

        self.setFixedSize(size, size)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

    def paintEvent(self, event):
        if (
            self.renderer is None
            or not self.renderer.isValid()
        ):
            return

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        self.renderer.render(
            painter,
            QRectF(
                0,
                0,
                self.width(),
                self.height(),
            ),
        )

        painter.end()


def normalize_improvement_icon_key(value):
    return "".join(
        character
        for character in str(value or "").lower()
        if character.isalnum()
    )


def find_improvement_icon_path(row):
    """
    Find the matching SVG inside icons/improvements.

    Example:
        icons/improvements/Sharpshooter.svg
    """

    improvement = getattr(
        row,
        "improvement",
        None,
    )

    candidates = []

    if improvement is not None:
        if getattr(improvement, "catalog_id", "") == "custom":
            chosen_icon = str((improvement.choices or {}).get("_custom_icon", ""))
            if chosen_icon and os.path.basename(chosen_icon) == chosen_icon:
                candidates.append(chosen_icon.removesuffix(".svg"))
        candidates.extend(
            [
                getattr(
                    improvement,
                    "catalog_id",
                    "",
                ),
                getattr(
                    improvement,
                    "name",
                    "",
                ),
            ]
        )

    display = getattr(
        row,
        "display",
        None,
    )

    if isinstance(
        display,
        dict,
    ):
        candidates.append(
            display.get(
                "name",
                "",
            )
        )

    name_label = getattr(
        row,
        "name_label",
        None,
    )

    if name_label is not None:
        candidates.append(
            name_label.text()
        )

    if not os.path.isdir(
        IMPROVEMENT_ICON_DIR
    ):
        return None

    # First try the obvious filenames.
    for candidate in candidates:
        candidate = str(
            candidate or ""
        ).strip()

        if not candidate:
            continue

        filenames = [
            f"{candidate}.svg",
            f"{candidate.lower()}.svg",
            (
                f"{normalize_improvement_icon_key(candidate)}"
                ".svg"
            ),
        ]

        for filename in filenames:
            path = os.path.join(
                IMPROVEMENT_ICON_DIR,
                filename,
            )

            if os.path.exists(path):
                return path

    # Then scan the folder case-insensitively and ignore spaces/punctuation.
    wanted = {
        normalize_improvement_icon_key(
            candidate
        )
        for candidate in candidates
        if str(candidate or "").strip()
    }

    try:
        filenames = os.listdir(
            IMPROVEMENT_ICON_DIR
        )
    except OSError:
        return None

    for filename in filenames:
        if not filename.lower().endswith(
            ".svg"
        ):
            continue

        stem = os.path.splitext(
            filename
        )[0]

        if (
            normalize_improvement_icon_key(
                stem
            )
            in wanted
        ):
            return os.path.join(
                IMPROVEMENT_ICON_DIR,
                filename,
            )

    return None



class RelatedNoteHoverIcon(QWidget):
    """
    Hover-only icon for an improvement's temporary reference note.

    Optional SVG files:
        icons/notes/spellcasting.svg
        icons/notes/sneak_attack.svg

    If the SVG is missing, a small painted page icon is used instead.
    """

    def __init__(
        self,
        icon_path=None,
        on_hover=None,
        on_leave=None,
        on_click=None,
        on_double_click=None,
        size=22,
        parent=None,
        note_color=None,
    ):
        super().__init__(parent)

        self._note_color = note_color
        self._on_hover = on_hover
        self._on_leave = on_leave
        self._on_click = on_click
        self._on_double_click = on_double_click
        self._renderer = None
        icon_path = find_note_icon_path(icon_path)
        self._uses_custom_note_svg = bool(
            icon_path
            and os.path.basename(icon_path).lower() == "custom.svg"
        )

        if (
            icon_path
            and QSvgRenderer is not None
            and os.path.exists(icon_path)
        ):
            renderer = QSvgRenderer(
                icon_path
            )

            if renderer.isValid():
                self._renderer = renderer

        self._glyph_size = size
        self.setFixedSize(size + 6, size + 6)

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setMouseTracking(
            True
        )

    def enterEvent(self, event):
        self.update()
        if getattr(self.window(), "_pinned_improvement_note_preview", False):
            return super().enterEvent(event)
        if callable(
            self._on_hover
        ):
            self._on_hover(
                self
            )

        super().enterEvent(
            event
        )

    def leaveEvent(self, event):
        self.update()
        if callable(
            self._on_leave
        ):
            self._on_leave()

        super().leaveEvent(
            event
        )

    def mousePressEvent(self, event):
        if callable(self._on_click):
            self._on_click(self)
            event.accept()
            return

        super().mousePressEvent(event)


    def mouseDoubleClickEvent(self, event):
        if callable(self._on_double_click):
            self._on_double_click()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        if self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(199, 152, 67, 45))
            painter.drawRoundedRect(QRectF(self.rect()), 5, 5)
        painter.translate(3, 3)

        if (
            self._note_color is None
            and self._renderer is not None
            and self._renderer.isValid()
        ):
            if self._uses_custom_note_svg:
                svg_rect = QRectF(
                    0,
                    0,
                    self._glyph_size,
                    self._glyph_size,
                )
            else:
                svg_rect = QRectF(
                    1,
                    1,
                    self._glyph_size - 2,
                    self._glyph_size - 2,
                )

            self._renderer.render(
                painter,
                svg_rect,
            )

            painter.end()
            return

        border = QColor(
            fantasy_runtime_color(
                "#a87824"
            )
        )

        fill = QColor(
            fantasy_runtime_color(
                "#fffaf0"
            )
        )

        if self._note_color is not None:
            key = self._note_color() if callable(self._note_color) else self._note_color
            fill = QColor(note_colors_for_theme(str(key or "yellow"))[0])
            # Ink stays legible on both light and dark/custom note colors.
            border = QColor("#f6ead2" if fill.lightnessF() < 0.48 else "#59462d")

        painter.setPen(
            QPen(
                border,
                1.5,
            )
        )

        painter.setBrush(
            fill
        )

        page = QRectF(
            4,
            3,
            self._glyph_size - 8,
            self._glyph_size - 6,
        )

        painter.drawRoundedRect(
            page,
            2,
            2,
        )

        painter.drawLine(
            QPointF(
                page.left() + 3,
                page.top() + 5,
            ),
            QPointF(
                page.right() - 3,
                page.top() + 5,
            ),
        )

        painter.drawLine(
            QPointF(
                page.left() + 3,
                page.top() + 9,
            ),
            QPointF(
                page.right() - 3,
                page.top() + 9,
            ),
        )

        painter.end()


class FantasyIcon(QWidget):
    """
    Small line-art fantasy icon used by the redesign.

    kind:
        sheet, improvements, inventory,
        agility, finesse, instinct, knowledge, presence, strength
    """

    def __init__(
        self,
        kind,
        accent="#a87824",
        size=34,
        circular=False,
        parent=None,
    ):
        super().__init__(parent)

        self.kind = kind
        self.accent = QColor(accent)
        self.circular = circular

        self.svg_renderer = None
        self._uses_custom_note_svg = False

        svg_filename = ABILITY_ICON_FILES.get(
            self.kind
        )

        if self.kind == "notes" and QSvgRenderer is not None:
            note_icon_path = find_note_icon_path()
            if note_icon_path:
                renderer = QSvgRenderer(note_icon_path)
                if renderer.isValid():
                    self.svg_renderer = renderer
                    self._uses_custom_note_svg = (
                        os.path.normcase(os.path.basename(note_icon_path))
                        == "custom.svg"
                    )

        if (
            svg_filename
            and QSvgRenderer is not None
        ):
            svg_path = os.path.join(
                APP_DIR,
                "icons",
                svg_filename,
            )

            if os.path.exists(svg_path):
                renderer = QSvgRenderer(
                    svg_path
                )

                if renderer.isValid():
                    self.svg_renderer = renderer

        self.setFixedSize(
            size,
            size,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        w = float(self.width())
        h = float(self.height())

        pen_width = max(
            1.4,
            w / 22.0,
        )

        pen = QPen(
            self.accent,
            pen_width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )

        painter.setPen(pen)
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        if self.circular:
            painter.setBrush(
                QBrush(
                    QColor(fantasy_runtime_color("#fffdf7"))
                )
            )

            painter.drawEllipse(
                QRectF(
                    1.5,
                    1.5,
                    w - 3,
                    h - 3,
                )
            )

            painter.setBrush(
                Qt.BrushStyle.NoBrush
            )

        if self.svg_renderer is not None:
            # Custom note artwork should be allowed to use the icon box.
            # The generic 16% inset made custom.svg look permanently tiny
            # regardless of how large its artwork was drawn in the SVG.
            if self._uses_custom_note_svg:
                padding = 1.0
            else:
                # Leave a little breathing room inside the circular badge.
                padding = max(
                    3.0,
                    min(w, h) * 0.16,
                )

            self.svg_renderer.render(
                painter,
                QRectF(
                    padding,
                    padding,
                    max(1.0, w - (padding * 2)),
                    max(1.0, h - (padding * 2)),
                ),
            )

            painter.end()
            return

        if self.kind in {
            "sheet",
            "improvements",
        }:
            self._draw_compass_star(
                painter,
                w,
                h,
            )

        elif self.kind == "inventory":
            self._draw_bag(
                painter,
                w,
                h,
            )

        elif self.kind == "notes":
            self._draw_book(
                painter,
                w,
                h,
            )

        elif self.kind == "agility":
            self._draw_wing(
                painter,
                w,
                h,
            )

        elif self.kind == "finesse":
            self._draw_crossed_blades(
                painter,
                w,
                h,
            )

        elif self.kind == "instinct":
            self._draw_eye(
                painter,
                w,
                h,
            )

        elif self.kind == "knowledge":
            self._draw_book(
                painter,
                w,
                h,
            )

        elif self.kind == "presence":
            self._draw_mask(
                painter,
                w,
                h,
            )

        elif self.kind == "strength":
            self._draw_fist(
                painter,
                w,
                h,
            )

        painter.end()

    def _draw_compass_star(
        self,
        painter,
        w,
        h,
    ):
        cx = w / 2
        cy = h / 2

        outer = min(
            w,
            h,
        ) * 0.36

        inner = outer * 0.35

        points = []

        for index in range(16):
            angle = (
                -90
                + index * 22.5
            )

            radius = (
                outer
                if index % 2 == 0
                else inner
            )

            import math

            radians = math.radians(
                angle
            )

            points.append(
                QPointF(
                    cx
                    + math.cos(radians)
                    * radius,
                    cy
                    + math.sin(radians)
                    * radius,
                )
            )

        painter.drawPolygon(
            QPolygonF(points)
        )

        painter.drawEllipse(
            QPointF(cx, cy),
            max(1.5, w * 0.045),
            max(1.5, h * 0.045),
        )

    def _draw_bag(
        self,
        painter,
        w,
        h,
    ):
        body = QRectF(
            w * 0.24,
            h * 0.38,
            w * 0.52,
            h * 0.42,
        )

        painter.drawRoundedRect(
            body,
            w * 0.10,
            w * 0.10,
        )

        painter.drawLine(
            QPointF(
                w * 0.37,
                h * 0.38,
            ),
            QPointF(
                w * 0.42,
                h * 0.27,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.63,
                h * 0.38,
            ),
            QPointF(
                w * 0.58,
                h * 0.27,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.39,
                h * 0.28,
            ),
            QPointF(
                w * 0.61,
                h * 0.28,
            ),
        )

        painter.drawArc(
            QRectF(
                w * 0.33,
                h * 0.13,
                w * 0.34,
                h * 0.30,
            ),
            20 * 16,
            140 * 16,
        )

    def _draw_wing(
        self,
        painter,
        w,
        h,
    ):
        path = QPainterPath()

        path.moveTo(
            w * 0.25,
            h * 0.69,
        )

        path.cubicTo(
            w * 0.34,
            h * 0.33,
            w * 0.57,
            h * 0.23,
            w * 0.76,
            h * 0.27,
        )

        path.cubicTo(
            w * 0.62,
            h * 0.41,
            w * 0.50,
            h * 0.52,
            w * 0.25,
            h * 0.69,
        )

        painter.drawPath(path)

        painter.drawLine(
            QPointF(
                w * 0.31,
                h * 0.62,
            ),
            QPointF(
                w * 0.62,
                h * 0.35,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.37,
                h * 0.57,
            ),
            QPointF(
                w * 0.72,
                h * 0.34,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.42,
                h * 0.51,
            ),
            QPointF(
                w * 0.68,
                h * 0.48,
            ),
        )

    def _draw_crossed_blades(
        self,
        painter,
        w,
        h,
    ):
        painter.drawLine(
            QPointF(
                w * 0.30,
                h * 0.25,
            ),
            QPointF(
                w * 0.70,
                h * 0.75,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.70,
                h * 0.25,
            ),
            QPointF(
                w * 0.30,
                h * 0.75,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.25,
                h * 0.68,
            ),
            QPointF(
                w * 0.38,
                h * 0.80,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.75,
                h * 0.68,
            ),
            QPointF(
                w * 0.62,
                h * 0.80,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.25,
                h * 0.32,
            ),
            QPointF(
                w * 0.38,
                h * 0.20,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.75,
                h * 0.32,
            ),
            QPointF(
                w * 0.62,
                h * 0.20,
            ),
        )

    def _draw_eye(
        self,
        painter,
        w,
        h,
    ):
        eye = QPainterPath()

        eye.moveTo(
            w * 0.20,
            h * 0.50,
        )

        eye.quadTo(
            w * 0.50,
            h * 0.25,
            w * 0.80,
            h * 0.50,
        )

        eye.quadTo(
            w * 0.50,
            h * 0.75,
            w * 0.20,
            h * 0.50,
        )

        painter.drawPath(eye)

        painter.setBrush(
            QBrush(self.accent)
        )

        painter.drawEllipse(
            QPointF(
                w * 0.50,
                h * 0.50,
            ),
            w * 0.09,
            h * 0.09,
        )

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

    def _draw_book(
        self,
        painter,
        w,
        h,
    ):
        left = QPainterPath()

        left.moveTo(
            w * 0.18,
            h * 0.30,
        )

        left.quadTo(
            w * 0.35,
            h * 0.24,
            w * 0.50,
            h * 0.36,
        )

        left.lineTo(
            w * 0.50,
            h * 0.74,
        )

        left.quadTo(
            w * 0.34,
            h * 0.62,
            w * 0.18,
            h * 0.68,
        )

        left.closeSubpath()

        right = QPainterPath()

        right.moveTo(
            w * 0.82,
            h * 0.30,
        )

        right.quadTo(
            w * 0.65,
            h * 0.24,
            w * 0.50,
            h * 0.36,
        )

        right.lineTo(
            w * 0.50,
            h * 0.74,
        )

        right.quadTo(
            w * 0.66,
            h * 0.62,
            w * 0.82,
            h * 0.68,
        )

        right.closeSubpath()

        painter.drawPath(left)
        painter.drawPath(right)

        painter.drawLine(
            QPointF(
                w * 0.50,
                h * 0.36,
            ),
            QPointF(
                w * 0.50,
                h * 0.74,
            ),
        )

    def _draw_mask(
        self,
        painter,
        w,
        h,
    ):
        mask = QPainterPath()

        mask.moveTo(
            w * 0.30,
            h * 0.25,
        )

        mask.quadTo(
            w * 0.50,
            h * 0.16,
            w * 0.70,
            h * 0.25,
        )

        mask.lineTo(
            w * 0.67,
            h * 0.62,
        )

        mask.quadTo(
            w * 0.50,
            h * 0.82,
            w * 0.33,
            h * 0.62,
        )

        mask.closeSubpath()

        painter.drawPath(mask)

        painter.drawLine(
            QPointF(
                w * 0.36,
                h * 0.43,
            ),
            QPointF(
                w * 0.45,
                h * 0.45,
            ),
        )

        painter.drawLine(
            QPointF(
                w * 0.64,
                h * 0.43,
            ),
            QPointF(
                w * 0.55,
                h * 0.45,
            ),
        )

        painter.drawArc(
            QRectF(
                w * 0.40,
                h * 0.50,
                w * 0.20,
                h * 0.16,
            ),
            200 * 16,
            140 * 16,
        )

    def _draw_fist(
        self,
        painter,
        w,
        h,
    ):
        knuckle_y = h * 0.34

        for index in range(4):
            x = (
                w * 0.29
                + index
                * w * 0.14
            )

            painter.drawRoundedRect(
                QRectF(
                    x,
                    knuckle_y,
                    w * 0.13,
                    h * 0.18,
                ),
                w * 0.035,
                w * 0.035,
            )

        painter.drawRoundedRect(
            QRectF(
                w * 0.30,
                h * 0.48,
                w * 0.45,
                h * 0.27,
            ),
            w * 0.07,
            w * 0.07,
        )

        painter.drawArc(
            QRectF(
                w * 0.20,
                h * 0.46,
                w * 0.30,
                h * 0.28,
            ),
            70 * 16,
            160 * 16,
        )



class AbilityDescriptionPopup(QDialog):
    """
    Passive ability-description popup.

    Unlike QToolTip, this window is positioned manually and Qt does not
    decide to flip it above/below the hovered ability. Therefore every
    ability uses the exact same relative position.
    """

    POPUP_WIDTH = 295

    def __init__(
        self,
        title,
        description,
        accent,
        parent=None,
    ):
        super().__init__(parent)

        self.setModal(False)

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setFixedWidth(
            self.POPUP_WIDTH
        )

        dark = (
            ui_theme_module.CURRENT_THEME
            == "dark"
        )

        if dark:
            surface = "#18232e"
            text_color = "#f2eee7"
            border = "#8e7446"
        else:
            surface = "#fffdf7"
            text_color = "#25190f"
            border = "#cdaa63"

        set_themed_stylesheet(
            self,
            """
            QDialog {
                background: transparent;
                border: none;
            }
            """,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(
            0, 0, 0, 0
        )
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName(
            "AbilityDescriptionPopupFrame"
        )

        set_themed_stylesheet(
            frame,
            f"""
            QFrame#AbilityDescriptionPopupFrame {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 9px;
            }}
            """,
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            14, 11, 14, 11
        )
        layout.setSpacing(3)

        title_label = QLabel(
            title
        )

        set_themed_stylesheet(
            title_label,
            f"""
            QLabel {{
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 14px;
                font-weight: 900;
                color: {accent};
                padding: 0px;
                margin: 0px;
            }}
            """,
        )

        body_label = QLabel(
            description
        )

        body_label.setWordWrap(
            True
        )

        body_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )

        set_themed_stylesheet(
            body_label,
            f"""
            QLabel {{
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                color: {text_color};
                padding: 0px;
                margin: 0px;
            }}
            """,
        )

        usable_width = (
            self.POPUP_WIDTH
            - 28
        )

        title_label.setFixedWidth(
            usable_width
        )

        body_label.setFixedWidth(
            usable_width
        )

        body_metrics = QFontMetrics(
            body_label.font()
        )

        body_rect = body_metrics.boundingRect(
            0,
            0,
            usable_width,
            10000,
            int(
                Qt.TextFlag.TextWordWrap
                | Qt.TextFlag.TextExpandTabs
            ),
            description,
        )

        body_label.setFixedHeight(
            max(
                body_metrics.height(),
                body_rect.height() + 2,
            )
        )

        layout.addWidget(
            title_label
        )
        layout.addWidget(
            body_label
        )

        root.addWidget(
            frame
        )

        layout.activate()
        frame.adjustSize()
        root.activate()

        self.setFixedHeight(
            frame.sizeHint().height()
        )



class RedesignStatRow(QFrame):
    clicked = Signal(str)
    optionsRequested = Signal(str, QPoint)

    """
    Redesign-only horizontal ability row.

    It intentionally exposes the same important attributes used elsewhere
    by the working frontend:
        character
        stat_key
        bottom_label
        refresh()

    So load/new-character/theme behavior continues to work unchanged.
    """

    def __init__(self, stat_label, stat_key, character):
        super().__init__()

        self.stat_label = stat_label
        self.stat_key = stat_key
        self.character = character

        accent = ABILITY_ACCENTS.get(
            stat_key,
            "#2f5f91",
        )

        self.setObjectName(
            f"RedesignStatRow_{stat_key}"
        )

        self.setFixedHeight(56)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        ability_description = (
            ABILITY_DESCRIPTIONS.get(
                stat_key,
                "",
            )
        )

        description_html = (
            ability_description
            .replace(
                "\n",
                "<br>",
            )
        )

        self._ability_tooltip_html = (
            "<div style='white-space: normal;'>"
            f"<span style='font-family: Georgia; "
            f"font-size: 14px; font-weight: 700; "
            f"color: {accent};'>"
            f"{stat_label}"
            "</span>"
            "<br>"
            f"<span>{description_html}</span>"
            "</div>"
        )

        self._ability_tooltip_title = (
            stat_label
        )
        self._ability_tooltip_text = (
            ability_description
        )
        self._ability_tooltip_accent = (
            accent
        )
        self._ability_popup = None
        self._dice_roll_active = False

        # Do not register a native QToolTip here. Qt is allowed to
        # automatically move native tooltips near screen edges, which is
        # exactly what made lower abilities appear at inconsistent heights.
        self.setToolTip("")

        set_themed_stylesheet(
            self,
            f"""
            QFrame#{self.objectName()} {{
                background-color: #fffdf7;
                border: 1px solid #e2cfaa;
                border-radius: 10px;
            }}
            """,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            7, 4, 8, 4
        )
        layout.setSpacing(8)

        # --------------------------------------------------------
        # Illustrated ability emblem
        # --------------------------------------------------------

        self.emblem_label = FantasyIcon(
            stat_key,
            accent=accent,
            size=44,
            circular=True,
        )

        # --------------------------------------------------------
        # Die
        # --------------------------------------------------------

        self.center_label = QLabel()
        self.center_label.setFixedWidth(50)
        self.center_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            self.center_label,
            f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {accent};
                font-size: 22px;
                font-weight: 900;
                padding: 0px;
                margin: 0px;
            }}
            """,
        )

        # --------------------------------------------------------
        # Ability name
        #
        # Keep the name as bottom_label because the existing ThemeMixin
        # refers to stat_row.bottom_label when switching themes.
        # --------------------------------------------------------

        self.bottom_label = QLabel(
            stat_label
        )

        self.bottom_label.setMinimumWidth(0)

        self.bottom_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        set_themed_stylesheet(
            self.bottom_label,
            f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {accent};
                font-size: 14px;
                font-weight: 900;
                padding: 0px;
                margin: 0px;
            }}
            """,
        )

        # --------------------------------------------------------
        # Bonus
        # --------------------------------------------------------

        self.small_box = QLabel()
        self.small_box.setFixedSize(
            42,
            28,
        )

        self.small_box.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            self.small_box,
            """
            QLabel {
                background-color: #f4fbff;
                border: 1px solid #d9bd82;
                border-radius: 7px;
                color: black;
                font-size: 13px;
                font-weight: 900;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        layout.addWidget(
            self.emblem_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        layout.addWidget(
            self.center_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        layout.addWidget(
            self.bottom_label,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )

        layout.addWidget(
            self.small_box,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        # Make the entire ability rectangle one continuous hover target.
        for child in (
            self.emblem_label,
            self.center_label,
            self.bottom_label,
            self.small_box,
        ):
            child.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

        self.setMouseTracking(True)
        self.refresh()

    def enterEvent(self, event):
        self.hide_ability_popup()

        if self._dice_roll_active:
            super().enterEvent(
                event
            )
            return

        if self._ability_tooltip_text:
            self._ability_popup = (
                AbilityDescriptionPopup(
                    self._ability_tooltip_title,
                    self._ability_tooltip_text,
                    self._ability_tooltip_accent,
                    parent=self,
                )
            )

            popup_position = (
                self.mapToGlobal(
                    QPoint(
                        self.width() + 8,
                        0,
                    )
                )
            )

            # Deliberately do not let Qt choose or flip the position.
            # Every ability popup starts at the same offset from its row.
            self._ability_popup.move(
                popup_position
            )
            self._ability_popup.show()
            self._ability_popup.raise_()

        super().enterEvent(
            event
        )

    def leaveEvent(self, event):
        self.hide_ability_popup()

        super().leaveEvent(
            event
        )

    def hide_ability_popup(self):
        popup = getattr(
            self,
            "_ability_popup",
            None,
        )

        self._ability_popup = None

        if popup is None:
            return

        try:
            popup.hide()
            popup.deleteLater()
        except (
            RuntimeError,
            ReferenceError,
        ):
            pass


    def set_dice_rolling(
        self,
        active,
    ):
        self._dice_roll_active = bool(
            active
        )

        if self._dice_roll_active:
            self.hide_ability_popup()


    def mousePressEvent(
        self,
        event,
    ):
        if (
            event.button()
            == Qt.MouseButton.RightButton
        ):
            self.hide_ability_popup()

            self.optionsRequested.emit(
                self.stat_key,
                event.globalPosition().toPoint(),
            )

            event.accept()
            return

        super().mousePressEvent(
            event
        )


    def mouseDoubleClickEvent(
        self,
        event,
    ):
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.hide_ability_popup()

            self.clicked.emit(
                self.stat_key
            )

            event.accept()
            return

        super().mouseDoubleClickEvent(
            event
        )


    def get_stat(self):
        return self.character.stats.get_stat(
            self.stat_key
        )

    def refresh(self):
        stat = self.get_stat()

        if stat is None:
            self.center_label.setText("?")
            self.small_box.setText("?")
            return

        self.center_label.setText(
            f"d{stat.die_size}"
        )

        self.small_box.setText(
            f"+{stat.bonus}"
        )




class ShieldValueWidget(QWidget):
    """
    Numeric BDV / DR badge.

    Preferred artwork:
        icons/defenses/bdv.svg
        icons/defenses/dr.svg

    The SVG is used as the complete background/emblem and the numeric
    value is drawn on top of it. If the file is missing or invalid,
    the original painted shield remains as a fallback.
    """

    def __init__(
        self,
        value="0",
        accent="#9f2d2d",
        defense_kind="bdv",
        parent=None,
    ):
        super().__init__(parent)

        self._text = str(value)
        self.accent = QColor(accent)

        self.defense_kind = (
            str(defense_kind or "")
            .strip()
            .lower()
        )

        # Large artwork area.  The number is drawn separately below,
        # so enlarging this does NOT enlarge the number.
        self.setFixedSize(
            58,
            58,
        )

        self._svg_path = os.path.join(
            DEFENSE_ICON_DIR,
            f"{self.defense_kind}.svg",
        )

        self._svg_renderer = None
        self._reload_svg_renderer()

    def _reload_svg_renderer(self):
        """
        Load the current SVG from disk.

        Keeping the filename fixed means you can replace bdv.svg or dr.svg
        later without changing any Python code.
        """

        self._svg_renderer = None

        if (
            QSvgRenderer is None
            or not os.path.exists(
                self._svg_path
            )
        ):
            return

        renderer = QSvgRenderer(
            self._svg_path
        )

        if renderer.isValid():
            self._svg_renderer = renderer

    def setText(self, value):
        self._text = str(value)
        self.update()

    def text(self):
        return self._text

    def _draw_default_shield(
        self,
        painter,
        w,
        h,
    ):
        """
        Original redesign shield, used only when no custom SVG exists.
        """

        shield = QPainterPath()

        shield.moveTo(
            w * 0.20,
            h * 0.13,
        )

        shield.lineTo(
            w * 0.80,
            h * 0.13,
        )

        shield.lineTo(
            w * 0.78,
            h * 0.58,
        )

        shield.quadTo(
            w * 0.72,
            h * 0.78,
            w * 0.50,
            h * 0.90,
        )

        shield.quadTo(
            w * 0.28,
            h * 0.78,
            w * 0.22,
            h * 0.58,
        )

        shield.closeSubpath()

        painter.setPen(
            QPen(
                self.accent,
                2.2,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )

        painter.setBrush(
            QBrush(
                QColor(
                    fantasy_runtime_color(
                        "#fffdf7"
                    )
                )
            )
        )

        painter.drawPath(
            shield
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        w = float(self.width())
        h = float(self.height())

        # --------------------------------------------------------
        # Background/emblem
        # --------------------------------------------------------

        if self.defense_kind == "bdv":
            # Match the Animal Buddy BDV starburst at the regular sheet size.
            cx, cy = w / 2, h / 2
            points = []
            for n in range(24):
                angle = -pi / 2 + n * pi / 12
                radius = 27 if n % 2 == 0 else 19
                points.append(QPointF(cx + radius * cos(angle),
                                      cy + radius * sin(angle)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#c82541"))
            painter.drawPolygon(QPolygonF(points))

        elif (
            self._svg_renderer is not None
            and self._svg_renderer.isValid()
        ):
            # Preserve the SVG's natural proportions.  The previous code
            # forced every defense SVG into the same square, which made the
            # BDV fist look horizontally squashed.
            inset = 0.5

            source_rect = (
                self._svg_renderer.viewBoxF()
            )

            available_width = (
                w - inset * 2
            )
            available_height = (
                h - inset * 2
            )

            if (
                source_rect.width() > 0
                and source_rect.height() > 0
            ):
                scale = min(
                    available_width
                    / source_rect.width(),
                    available_height
                    / source_rect.height(),
                )

                # The two defense symbols have very different silhouettes.
                # Give each one its own visual scale so they feel balanced:
                # BDV fist larger, DR shield smaller.
                if self.defense_kind == "bdv":
                    visual_scale = 0.82

                elif self.defense_kind == "dr":
                    visual_scale = 0.82

                else:
                    visual_scale = 1.0

                render_width = (
                    source_rect.width()
                    * scale
                    * visual_scale
                )

                render_height = (
                    source_rect.height()
                    * scale
                    * visual_scale
                )

                render_rect = QRectF(
                    (w - render_width) / 2,
                    (h - render_height) / 2,
                    render_width,
                    render_height,
                )

            else:
                render_rect = QRectF(
                    inset,
                    inset,
                    available_width,
                    available_height,
                )

            self._svg_renderer.render(
                painter,
                render_rect,
            )

        else:
            self._draw_default_shield(
                painter,
                w,
                h,
            )

        # --------------------------------------------------------
        # Numeric value on top of either the SVG or fallback shield.
        # --------------------------------------------------------

        painter.setPen(
            QColor("#f5eee3")
        )

        font = painter.font()

        font.setFamily(
            "Georgia"
        )
        font.setBold(
            True
        )

        # Keep BDV and DR values at one consistent size.
        # This restores the balanced size used before the 17pt experiment.
        font.setPointSize(12 if self.defense_kind == "bdv" else 11)

        painter.setFont(
            font
        )

        painter.drawText(
            QRectF(
                0,
                0,
                w,
                h,
            ),
            Qt.AlignmentFlag.AlignCenter,
            self._text,
        )

        painter.end()


class RedesignSmallTopBox(QFrame):
    """
    Redesign-only BDV / DR control.

    The title sits above a shield-shaped numeric badge, matching the
    reference drawing more closely.

    Existing frontend compatibility is preserved:
        title_label
        val
        set_value()
    """

    def __init__(
        self,
        title,
        value="0",
    ):
        super().__init__()

        accent = (
            "#a12d2d"
            if title.strip().upper() == "BDV"
            else "#2f5f91"
        )

        # Give the enlarged defense artwork enough room without changing
        # the size of the BDV / DR heading text.
        self.setFixedSize(
            62,
            78,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(
            self,
            """
            QFrame {
                background: transparent;
                border: none;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            0, 0, 0, 0
        )
        layout.setSpacing(
            0
        )

        self.title_label = QLabel(
            title
        )

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            self.title_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 10px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        self.val = ShieldValueWidget(
            value,
            accent=accent,
            defense_kind=title.strip().lower(),
        )

        self._defense_title = (
            title.strip().upper()
        )

        self._defense_accent = accent
        self._defense_tooltip_html = ""

        # Make BDV / DR behave like one single hover target, just like the
        # redesigned ability rows. Moving from the heading onto the SVG or
        # number must not restart the tooltip timer.
        for child in (
            self.title_label,
            self.val,
        ):
            child.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

        self.setMouseTracking(
            True
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        layout.addWidget(
            self.title_label,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        layout.addWidget(
            self.val,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

    def setToolTip(self, text):
        """
        Keep compatibility with the existing refresh_top_boxes() logic,
        but display its changing BDV / DR explanation instantly and with
        the same visual treatment used for ability descriptions.
        """

        plain_text = str(
            text or ""
        )

        description_html = (
            plain_text
            .replace(
                "&",
                "&amp;",
            )
            .replace(
                "<",
                "&lt;",
            )
            .replace(
                ">",
                "&gt;",
            )
            .replace(
                "\n",
                "<br>",
            )
        )

        self._defense_tooltip_html = (
            "<div style='white-space: normal;'>"
            f"<span style='font-family: Georgia; "
            f"font-size: 14px; font-weight: 700; "
            f"color: {self._defense_accent};'>"
            f"{self._defense_title}"
            "</span>"
            "<br>"
            f"<span>{description_html}</span>"
            "</div>"
        )

        # Keep Qt's normal tooltip data as a fallback.
        super().setToolTip(
            self._defense_tooltip_html
        )

        self.setToolTipDuration(
            12000
        )

    def enterEvent(self, event):
        if self._defense_tooltip_html:
            QToolTip.showText(
                self.mapToGlobal(
                    QPoint(
                        self.width() + 6,
                        8,
                    )
                ),
                self._defense_tooltip_html,
                self,
            )

        super().enterEvent(
            event
        )

    def leaveEvent(self, event):
        QToolTip.hideText()

        super().leaveEvent(
            event
        )

    def set_value(self, value):
        self.val.setText(
            str(value)
        )

class FantasyAbilityEditorDialog(AbilityEditorDialog):
    """
    Redesign skin/layout for the working AbilityEditorDialog.

    All ability rules, legal-array checks, point accounting, reset behavior,
    and saving stay in dialogs.AbilityEditorDialog.  This class only changes
    presentation and the stat-card arrangement.
    """

    CELL_SIZE = 132

    def __init__(
        self,
        character,
        parent=None,
        allowed_array_ids=None,
        restrict_to_array_dice=False,
    ):
        self.restrict_to_array_dice = bool(
            restrict_to_array_dice
        )

        # During the base constructor refresh_all() is called.  Keep the
        # original one-row reorder behavior until the fantasy grid exists.
        self._fantasy_grid_ready = False

        super().__init__(
            character,
            parent,
            allowed_array_ids=allowed_array_ids,
        )

        self.setWindowTitle(
            "Edit Abilities"
        )
        self.setFixedSize(
            720,
            405,
        )

        root = self.layout()
        root.setContentsMargins(
            18, 14, 18, 16
        )
        root.setSpacing(
            12
        )

        set_themed_stylesheet(
            self,
            """
            QDialog {
                background-color: #f7f1e5;
            }

            QLabel {
                background: transparent;
                border: none;
                color: #25190f;
            }

            QFrame#StatCell {
                background-color: #fffdf7;
                border: 1px solid #d9bd82;
                border-radius: 14px;
            }

            QFrame#StatCellSelected {
                background-color: #fff6df;
                border: 3px solid #a87824;
                border-radius: 14px;
            }

            QPushButton#DieButton {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 25px;
                font-weight: 900;
                color: #25190f;
                padding: 0px;
                margin: 0px;
            }

            QPushButton#InfoButton {
                background-color: #fffdf7;
                border: 1px solid #cdaa63;
                border-radius: 16px;
                font-family: Georgia;
                font-size: 17px;
                font-weight: 900;
                color: #6c5428;
                padding: 0px;
                margin: 0px;
            }

            QPushButton#InfoButton:hover {
                background-color: #d8eef8;
                color: #25190f;
            }
            """
        )

        # --------------------------------------------------------
        # Header
        # --------------------------------------------------------

        header_layout = None

        if root.count() > 0:
            header_layout = root.itemAt(
                0
            ).layout()

        if header_layout is not None:
            self.header_icon = FantasyIcon(
                "sheet",
                accent="#a87824",
                size=30,
            )

            self.header_title = QLabel(
                "Edit Abilities"
            )

            set_themed_stylesheet(
                self.header_title,
                """
                QLabel {
                    background: transparent;
                    border: none;
                    font-family: Georgia;
                    font-size: 23px;
                    font-weight: 900;
                    color: #25190f;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

            header_layout.insertWidget(
                0,
                self.header_icon,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

            header_layout.insertWidget(
                1,
                self.header_title,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        self.info_btn.setFixedSize(
            32,
            32,
        )

        set_themed_stylesheet(
            self.info_btn,
            BUTTON_ICON_QSS,
        )

        self.reset_btn.setFixedSize(
            34,
            34,
        )

        set_themed_stylesheet(
            self.reset_btn,
            BUTTON_ICON_QSS,
        )

        # Put the information button beside the reset arrow at the right
        # side of the header instead of beside the title.
        if header_layout is not None:
            header_layout.removeWidget(
                self.info_btn
            )

            reset_index = header_layout.indexOf(
                self.reset_btn
            )

            if reset_index >= 0:
                header_layout.insertWidget(
                    reset_index,
                    self.info_btn,
                    0,
                    Qt.AlignmentFlag.AlignVCenter,
                )
            else:
                header_layout.addWidget(
                    self.info_btn,
                    0,
                    Qt.AlignmentFlag.AlignVCenter,
                )

        self._arrays_info_window = None

        self.points_label.setMinimumWidth(
            115
        )
        self.points_label.setFixedHeight(
            38
        )
        self.points_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            self.points_label,
            """
            QLabel {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 17px;
                font-family: Georgia;
                font-size: 21px;
                font-weight: 900;
                color: #25190f;
                padding: 1px 12px;
                margin: 0px;
            }
            """
        )

        # --------------------------------------------------------
        # Replace the original six-card horizontal row with 2 x 3.
        # The base dialog continues to own every card and all behavior.
        # --------------------------------------------------------

        old_stats_row = self.stats_row
        old_stats_index = -1

        for index in range(
            root.count()
        ):
            item = root.itemAt(
                index
            )

            if item.layout() is old_stats_row:
                old_stats_index = index
                break

        while old_stats_row.count():
            old_stats_row.takeAt(
                0
            )

        if old_stats_index >= 0:
            root.takeAt(
                old_stats_index
            )
        else:
            old_stats_index = 1

        self.stats_grid_widget = QWidget(
            self
        )

        self.stats_grid = QGridLayout(
            self.stats_grid_widget
        )

        self.stats_grid.setContentsMargins(
            0, 0, 0, 0
        )

        self.stats_grid.setHorizontalSpacing(
            12
        )

        self.stats_grid.setVerticalSpacing(
            10
        )

        for column in range(
            3
        ):
            self.stats_grid.setColumnStretch(
                column,
                1,
            )

        self.stats_row = self.stats_grid
        self._fantasy_grid_ready = True

        root.insertWidget(
            old_stats_index,
            self.stats_grid_widget,
        )

        # --------------------------------------------------------
        # Restyle the six working stat cells.
        # --------------------------------------------------------

        for stat_name in STAT_NAMES:
            inputs = self.stat_inputs[
                stat_name
            ]

            cell = inputs[
                "cell"
            ]

            die_button = inputs[
                "button"
            ]

            cell.setFixedSize(
                200,
                125,
            )

            accent = ABILITY_ACCENTS.get(
                stat_name,
                "#a87824",
            )

            self_icon = FantasyIcon(
                stat_name,
                accent=accent,
                size=46,
                circular=True,
                parent=cell,
            )

            cell_layout = cell.layout()

            if cell_layout is not None:
                cell_layout.insertWidget(
                    0,
                    self_icon,
                    0,
                    Qt.AlignmentFlag.AlignHCenter,
                )

                cell_layout.setContentsMargins(
                    8, 7, 8, 7
                )

                cell_layout.setSpacing(
                    1
                )

            set_themed_stylesheet(
                die_button,
                f"""
                QPushButton#DieButton {{
                    background: transparent;
                    border: none;
                    font-family: Georgia;
                    font-size: 25px;
                    font-weight: 900;
                    color: {accent};
                    padding: 0px;
                    margin: 0px;
                }}
                """
            )

            for label in cell.findChildren(
                QLabel
            ):
                set_themed_stylesheet(
                    label,
                    f"""
                    QLabel {{
                        background: transparent;
                        border: none;
                        font-family: Georgia;
                        font-size: 13px;
                        font-weight: 900;
                        color: {accent};
                        padding: 0px;
                        margin: 0px;
                    }}
                    """
                )

        # --------------------------------------------------------
        # Footer buttons
        # --------------------------------------------------------

        self.cancel_btn.setFixedSize(
            120,
            38,
        )

        self.save_btn.setFixedSize(
            120,
            38,
        )

        set_themed_stylesheet(
            self.cancel_btn,
            BUTTON_SECONDARY_QSS,
        )

        set_themed_stylesheet(
            self.save_btn,
            BUTTON_PRIMARY_QSS,
        )

        # The original options_bar is not used by the current popup-die
        # workflow, but keep it available in case dialogs.py uses it later.
        self.options_bar.setMaximumHeight(
            0
        )

        # Remove the large base-dialog stretch that created the dead space
        # between the ability cards and the footer.
        for index in range(root.count() - 1, -1, -1):
            item = root.itemAt(index)
            if item.spacerItem() is not None:
                root.takeAt(index)

        root.setSpacing(8)
        root.activate()

        self.refresh_all()

        self.finished.connect(
            self.close_arrays_info_window
        )


    def close_arrays_info_window(self, *_args):
        dialog = getattr(self, "_arrays_info_window", None)
        if dialog is None:
            return

        try:
            dialog.close()
            dialog.deleteLater()
        except RuntimeError:
            pass

        self._arrays_info_window = None


    def refresh_stat_cells(self):
        super().refresh_stat_cells()
        if not getattr(self, "_fantasy_grid_ready", False):
            return
        for stat_name, inputs in self.stat_inputs.items():
            cell = inputs["cell"]
            if stat_name == self.selected_stat_name:
                background, border, border_width = "#fff6df", "#a87824", 2
            else:
                background, border, border_width = "#eef8fc", "#d9bd82", 1
            set_themed_stylesheet(
                cell,
                f"""QFrame {{
                    background-color: {background};
                    border: {border_width}px solid {border};
                    border-radius: 14px;
                }}"""
            )

    def open_dice_menu(self, stat_name):
        """Pretty compact die picker anchored to the chosen ability."""

        menu = QMenu(self)
        menu.setFixedWidth(205)

        set_themed_stylesheet(
            menu,
            """
            QMenu {
                background-color: #fffdf7;
                border: 1px solid #cdaa63;
                border-radius: 11px;
                padding: 6px;
                color: #25190f;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 700;
            }

            QMenu::item {
                background-color: #fffaf0;
                border: 1px solid transparent;
                border-radius: 7px;
                color: #25190f;
                padding: 7px 11px;
                margin: 2px 1px;
            }

            QMenu::item:selected {
                background-color: #d8edf7;
                border-color: #c79a3b;
                color: #25190f;
            }

            QMenu::item:disabled {
                background: transparent;
                border: none;
                color: #a87824;
                font-size: 12px;
                font-weight: 900;
                padding: 4px 8px 6px 8px;
            }

            QMenu::separator {
                height: 1px;
                background-color: #d9bd82;
                margin: 2px 7px 4px 7px;
            }
            """,
        )

        title_action = menu.addAction(
            f"Choose {stat_name.title()} Die"
        )
        title_action.setEnabled(False)
        menu.addSeparator()

        possible_dice = self.get_possible_dice_for_stat(
            stat_name
        )
        current_die = self.stat_inputs[
            stat_name
        ]["die"]

        for die_size in possible_dice:
            if die_size == current_die:
                continue

            cost = STAT_POINT_COSTS.get(
                die_size,
                0,
            )
            point_word = (
                "point"
                if cost == 1
                else "points"
            )

            action = menu.addAction(
                f"d{die_size:<2}                 {cost} {point_word}"
            )
            action.triggered.connect(
                lambda checked=False, s=stat_name, d=die_size:
                    self.choose_die(s, d)
            )

        die_button = self.stat_inputs[
            stat_name
        ]["button"]

        menu.exec(
            die_button.mapToGlobal(
                QPoint(
                    die_button.width() + 6,
                    -4,
                )
            )
        )

    def open_arrays_info(self):
        """
        Toggle the Legal Ability Arrays companion window.

        The (i) button owns this window: click once to open it and click
        again to close it. It also closes automatically with Edit Abilities.
        """

        existing = getattr(
            self,
            "_arrays_info_window",
            None,
        )

        if (
            existing is not None
            and existing.isVisible()
        ):
            existing.close()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Legal Ability Arrays"
        )
        dialog.setModal(False)
        dialog.setWindowFlag(
            Qt.WindowType.Tool,
            True,
        )
        dialog.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )
        dialog.setFixedWidth(
            345
        )

        set_themed_stylesheet(
            dialog,
            FANTASY_DIALOG_QSS,
        )

        root = QVBoxLayout(dialog)
        root.setContentsMargins(
            10, 8, 10, 9
        )
        root.setSpacing(3)

        list_frame = QFrame()
        set_themed_stylesheet(
            list_frame,
            """
            QFrame {
                background-color: #fffaf0;
                border: 1px solid #cdaa63;
                border-radius: 9px;
            }
            """,
        )

        list_layout = QVBoxLayout(
            list_frame
        )
        list_layout.setContentsMargins(
            8, 5, 8, 5
        )
        list_layout.setSpacing(1)

        for ability_array in self.available_ability_arrays():
            dice_text = ", ".join(
                f"d{die}"
                for die in ability_array["dice"]
            )

            row = QLabel(
                (
                    f"<b>{ability_array['name']}</b>"
                    f"&nbsp;&nbsp;—&nbsp;&nbsp;"
                    f"{dice_text}"
                )
            )
            row.setTextFormat(
                Qt.TextFormat.RichText
            )
            row.setWordWrap(False)
            set_themed_stylesheet(
                row,
                """
                QLabel {
                    background: transparent;
                    border: none;
                    font-family: Georgia;
                    font-size: 12px;
                    color: #25190f;
                    padding: 1px 1px;
                }
                """,
            )
            list_layout.addWidget(row)

        root.addWidget(list_frame)

        root.activate()
        dialog.setFixedHeight(
            max(
                125,
                root.sizeHint().height(),
            )
        )

        self._arrays_info_window = dialog

        dialog.destroyed.connect(
            lambda *_:
                setattr(
                    self,
                    "_arrays_info_window",
                    None,
                )
        )

        screen = QApplication.screenAt(
            self.frameGeometry().center()
        )

        if screen is not None:
            available = screen.availableGeometry()
        else:
            available = (
                QApplication.primaryScreen()
                .availableGeometry()
            )

        # Put Legal Ability Arrays exactly between the Cancel and Save
        # buttons. Its top edge aligns with the buttons' top edge.
        cancel_top_left = self.cancel_btn.mapToGlobal(
            QPoint(0, 0)
        )
        save_top_left = self.save_btn.mapToGlobal(
            QPoint(0, 0)
        )

        cancel_right = (
            cancel_top_left.x()
            + self.cancel_btn.width()
        )
        save_left = save_top_left.x()

        gap_center_x = (
            cancel_right
            + save_left
        ) // 2

        x = (
            gap_center_x
            - dialog.width() // 2
        )

        y = min(
            cancel_top_left.y(),
            save_top_left.y(),
        )

        x = max(
            available.left(),
            min(
                x,
                available.right()
                - dialog.width()
                + 1,
            ),
        )

        y = max(
            available.top(),
            min(
                y,
                available.bottom()
                - dialog.height()
                + 1,
            ),
        )

        dialog.show()

        center_global = self.mapToGlobal(
            self.rect().center()
        )

        x = (
            center_global.x()
            - dialog.width() // 2
            - 45
        )

        cancel_pos = self.cancel_btn.mapToGlobal(
            QPoint(0, 0)
        )

        y = cancel_pos.y()

        dialog.move(x, y)
        dialog.raise_()

    def refresh_points(self):
        super().refresh_points()

        if not getattr(
            self,
            "_fantasy_grid_ready",
            False,
        ):
            return

        remaining = None

        remaining_method = getattr(
            self,
            "remaining_points",
            None,
        )

        if callable(
            remaining_method
        ):
            try:
                remaining = remaining_method()
            except Exception:
                remaining = None

        if remaining is None:
            remaining = getattr(
                self,
                "_remaining_points",
                None,
            )

        if remaining is None:
            text = self.points_label.text()
            try:
                remaining = int(
                    str(text).split(
                        "/",
                        1,
                    )[0].strip()
                )
            except Exception:
                remaining = 0

        color = (
            "#aa0000"
            if remaining < 0
            else "#25190f"
        )

        set_themed_stylesheet(
            self.points_label,
            f"""
            QLabel {{
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 17px;
                font-family: Georgia;
                font-size: 21px;
                font-weight: 900;
                color: {color};
                padding: 1px 12px;
                margin: 0px;
            }}
            """
        )


    def reorder_stat_cells(self):
        if not getattr(
            self,
            "_fantasy_grid_ready",
            False,
        ):
            return super().reorder_stat_cells()

        while self.stats_row.count():
            self.stats_row.takeAt(
                0
            )

        for index, stat_name in enumerate(
            self.get_sorted_stat_names()
        ):
            row = index // 3
            column = index % 3

            self.stats_row.addWidget(
                self.stat_inputs[
                    stat_name
                ][
                    "cell"
                ],
                row,
                column,
            )
        

    def can_choose_die(
        self,
        stat_name,
        candidate_die,
    ):

        candidate_array = (
            self.available_ability_arrays()
        )

        if not self.allowed_array_ids:
            return super().can_choose_die(
                stat_name,
                candidate_die,
            )

        chosen_dice = []

        for other_stat_name, inputs in (
            self.stat_inputs.items()
        ):
            if other_stat_name == stat_name:
                continue

            if not inputs.get(
                "locked",
                False,
            ):
                continue

            chosen_dice.append(
                int(
                    inputs["die"]
                )
            )

        chosen_dice.append(
            candidate_die
        )

        for ability_array in available_arrays:
            remaining = [
                int(die_size)
                for die_size
                in ability_array.get(
                    "dice",
                    []
                )
            ]

            possible = True

            for chosen_die in chosen_dice:
                if chosen_die not in remaining:
                    possible = False
                    break

                remaining.remove(
                    chosen_die
                )

            if possible:
                return True
        return False


class LongPressReorderFilter(QObject):
    """Press and hold a card, then move and release it to reorder."""

    HOLD_MS = 800
    MOVE_TOLERANCE = 7

    def __init__(self, row, drop_callback, parent=None):
        super().__init__(parent or row)
        self.row = row
        self.drop_callback = drop_callback
        self.target = getattr(row, "main_box", row)
        self._press_global = None
        self._active = False

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(self.HOLD_MS)
        self.timer.timeout.connect(self._activate_drag)

        self.outline = QFrame(row)
        self.outline.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.outline.hide()
        set_themed_stylesheet(
            self.outline,
            """
            QFrame {
                background: transparent;
                border: 2px dashed #a87824;
                border-radius: 14px;
            }
            """,
        )

        self.target.installEventFilter(self)

    def _activate_drag(self):
        if self._press_global is None:
            return

        self._active = True
        self.row.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.outline.setGeometry(self.row.rect())
        self.outline.show()
        self.outline.raise_()

    def _reset(self):
        self.timer.stop()
        self._press_global = None
        self._active = False
        self.row.unsetCursor()
        self.outline.hide()

    def eventFilter(self, watched, event):
        event_type = event.type()

        if event_type == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False

            self._press_global = event.globalPosition().toPoint()
            self._active = False
            self.timer.start()
            return False

        if event_type == QEvent.Type.MouseMove:
            if self._press_global is None:
                return False

            current = event.globalPosition().toPoint()

            if not self._active:
                if (
                    current - self._press_global
                ).manhattanLength() > self.MOVE_TOLERANCE:
                    self.timer.stop()
                    self._press_global = None

                return False

            self.outline.setGeometry(self.row.rect())
            return True

        if event_type == QEvent.Type.MouseButtonRelease:
            if event.button() != Qt.MouseButton.LeftButton:
                return False

            was_active = self._active
            release_position = event.globalPosition().toPoint()
            self._reset()

            if was_active and callable(self.drop_callback):
                self.drop_callback(release_position)
                return True

            return False

        if event_type in {
            QEvent.Type.Leave,
            QEvent.Type.Hide,
            QEvent.Type.Destroy,
        }:
            if not self._active:
                self.timer.stop()

        return False


def improvement_two_column_width(available_width, spacing):
    """One source of truth for the two equal Improvement card widths.

    Both layout positioning and text measurement must use this same result,
    otherwise wrapped descriptions can resize/move when the list redraws.
    """
    return max(1, (max(0, int(available_width)) - max(0, int(spacing))) // 2)


class IndependentTwoColumnImprovementLayout(QLayout):
    """
    Two completely independent vertical improvement columns.

    Improvements are added:
        1 -> left
        2 -> right
        3 -> left
        4 -> right

    Opening something in the right column therefore does NOT
    move anything in the left column, and vice versa.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._items = []

        self.column_spacing = 14
        self.vertical_spacing = 8

        self.setContentsMargins(
            0, 0, 0, 0
        )

        # One continuous divider between both columns.
        self.divider = QFrame(parent)

        self.divider.setFixedWidth(1)

        set_themed_stylesheet(
            self.divider,
            """
            QFrame {
                background-color: #d9bd82;
                border: none;
            }
            """
        )

        self.divider.show()

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]

        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)

        return None

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        margins = self.contentsMargins()

        left_height = 0
        right_height = 0

        left_width = 0
        right_width = 0

        left_count = 0
        right_count = 0

        for index, item in enumerate(self._items):
            hint = item.sizeHint()

            if index % 2 == 0:
                left_width = max(
                    left_width,
                    hint.width(),
                )

                if left_count:
                    left_height += self.vertical_spacing

                left_height += hint.height()
                left_count += 1

            else:
                right_width = max(
                    right_width,
                    hint.width(),
                )

                if right_count:
                    right_height += self.vertical_spacing

                right_height += hint.height()
                right_count += 1

        # The scroll-content width is explicitly controlled by the viewport.
        # Never allow a rich-text card's natural size hint to become a
        # minimum *horizontal* width of the entire application.
        # Expanded Improvement descriptions must wrap within their column.
        height = (
            max(
                left_height,
                right_height,
            )
            + margins.top()
            + margins.bottom()
        )

        return QSize(0, height)

    def setGeometry(self, rect):
        super().setGeometry(rect)

        margins = self.contentsMargins()

        x = (
            rect.x()
            + margins.left()
        )

        y = (
            rect.y()
            + margins.top()
        )

        available_width = (
            rect.width()
            - margins.left()
            - margins.right()
        )

        column_width = improvement_two_column_width(
            available_width, self.column_spacing
        )

        left_x = x

        right_x = (
            x
            + column_width
            + self.column_spacing
        )

        left_y = y
        right_y = y

        for index, item in enumerate(self._items):
            widget = item.widget()

            if widget is None:
                continue

            height = widget.height()

            if height <= 0:
                height = item.sizeHint().height()

            if index % 2 == 0:
                item.setGeometry(
                    QRect(
                        left_x,
                        left_y,
                        column_width,
                        height,
                    )
                )

                left_y += (
                    height
                    + self.vertical_spacing
                )

            else:
                item.setGeometry(
                    QRect(
                        right_x,
                        right_y,
                        column_width,
                        height,
                    )
                )

                right_y += (
                    height
                    + self.vertical_spacing
                )

        divider_x = (
            x
            + column_width
            + int(
                self.column_spacing / 2
            )
        )

        divider_height = max(
            left_y,
            right_y,
        ) - y

        if self._items:
            divider_height -= self.vertical_spacing

        self.divider.setGeometry(
            divider_x,
            y,
            1,
            max(
                0,
                divider_height,
            ),
        )

        self.divider.raise_()


class _PortraitHoverWatcher(QObject):
    """Keep overlay controls hidden until the cursor is actually over the image."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def eventFilter(self, watched, event):
        # Qt can synthesize Enter during initial widget layout. Only an
        # actual pointer movement over the portrait activates the overlay.
        if event.type() == QEvent.Type.MouseMove:
            self.owner._portrait_hover_activated = True
            QTimer.singleShot(0, self.owner._update_portrait_overlay_hover)
        elif event.type() == QEvent.Type.Leave:
            QTimer.singleShot(0, self.owner._update_portrait_overlay_hover)
        return False


class MainWindow(BaseMainWindow):

    def apply_current_theme(self):
        """
        Use the existing theme engine, then refresh the redesign-only
        app-level tooltip and custom-painted widgets.
        """

        super().apply_current_theme()

        apply_fantasy_application_style()

        for widget_name in (
            "tools_toggle_btn",
            "sheet_header_icon",
            "hp_panel",
            "at_box",
            "bdv_box",
            "dr_box",
        ):
            widget = getattr(
                self,
                widget_name,
                None,
            )

            if widget is not None:
                widget.update()

        # Portrait overlay controls use theme-specific translucent colors,
        # so refresh them explicitly whenever Light/Dark mode changes.
        if hasattr(
            self,
            "prev_image_btn",
        ):
            self.style_portrait_overlay_controls()

        notes_frame = getattr(
            self,
            "notes_frame",
            None,
        )

        if notes_frame is not None:
            for card in notes_frame.findChildren(
                NoteCard
            ):
                self.style_redesign_note_card(
                    card
                )


    # ============================================================
    # TOP BAR
    # ============================================================

    def build_top_bar(self, outer_layout):
        top_frame = QFrame()
        self.redesign_top_frame = top_frame
        top_frame.setObjectName("RedesignTopBar")

        set_themed_stylesheet(
            top_frame,
            """
            QFrame#RedesignTopBar {
                background-color: white;
                border: none;
                border-bottom: 1px solid #d9bd82;
            }
            """
        )

        top_bar = QHBoxLayout(top_frame)
        top_bar.setContentsMargins(6, 4, 6, 5)
        top_bar.setSpacing(10)

        title = QLabel("Character Sheet")

        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 27px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        self.tools_toggle_btn = FantasyMenuButton()
        self.tools_toggle_btn.setFixedSize(38, 34)

        set_themed_stylesheet(
            self.tools_toggle_btn,
            BUTTON_ICON_QSS,
        )

        self.tools_toggle_btn.clicked.connect(
            self.toggle_tools_menu
        )

        # These still belong to MainWindow logically,
        # but Phase 1 places them under the portrait.
        self.character_name_label = QLineEdit()
        self.character_name_label.setPlaceholderText(
            "Unnamed Character"
        )
        self.character_name_label.editingFinished.connect(
            self.update_character_name_from_ui
        )

        self.species_label = SpeciesSelectionField()
        self.species_label.setPlaceholderText(
            "Choose Species"
        )
        self.species_label.activated.connect(self.choose_species_from_sheet)

        for field in (
            self.character_name_label,
            self.species_label,
        ):
            field.setMinimumWidth(0)

            set_themed_stylesheet(
                field,
                """
                QLineEdit {
                    background-color: transparent;
                    border: none;
                    border-bottom: 1px solid #d9bd82;
                    font-family: Georgia;
                    font-size: 15px;
                    font-weight: 800;
                    color: #25190f;
                    padding: 3px 2px;
                    margin: 0px;
                }

                QLineEdit:focus {
                    border-bottom: 2px solid #a87824;
                }
                """
            )

        self.name_caption = QLabel("Name")
        self.species_caption = QLabel("Species")

        for caption in (
            self.name_caption,
            self.species_caption,
        ):
            set_themed_stylesheet(
                caption,
                """
                QLabel {
                    background: transparent;
                    border: none;
                    font-family: Georgia;
                    font-size: 10px;
                    font-weight: 900;
                    color: #765d34;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

        self.character_name_label.setFixedHeight(28)
        self.species_label.setFixedHeight(28)

        self.character_name_label.setMinimumWidth(110)
        self.character_name_label.setMaximumWidth(230)
        self.species_label.setMinimumWidth(80)
        self.species_label.setMaximumWidth(170)

        self.character_name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.species_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(
            self.character_name_label,
            """
            QLineEdit {
                background-color: transparent;
                border: none;
                border-bottom: 1px solid #d9bd82;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 800;
                color: #25190f;
                padding: 1px 2px;
                margin: 0px;
            }

            QLineEdit:focus {
                border-bottom: 2px solid #a87824;
            }
            """
        )

        set_themed_stylesheet(
            self.species_label,
            """
            QLineEdit {
                background-color: transparent;
                border: none;
                border-bottom: 1px solid #d9bd82;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 800;
                color: #25190f;
                padding: 1px 2px;
                margin: 0px;
            }

            QLineEdit:focus {
                border-bottom: 2px solid #a87824;
            }
            """
        )

        self.save_status_label = QLabel("Saved")
        self.save_status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.save_status_label.setMinimumWidth(125)

        # The redesigned header replaces the legacy status widgets. Keep a
        # dedicated, fixed-width connection cell next to the actual Saved label.
        # An always-reserved cell prevents the top bar from shifting on sync.
        self.phone_connection_label = QLabel("")
        self.phone_connection_label.setObjectName("PhoneConnectionStatus")
        self.phone_connection_label.setFixedWidth(142)
        self.phone_connection_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        set_themed_stylesheet(self.phone_connection_label, """
            QLabel#PhoneConnectionStatus {
                color: #159447;
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 800;
            }
        """)

        set_themed_stylesheet(
            self.save_status_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-size: 12px;
                font-weight: 800;
                color: #555555;
                padding: 0px 8px;
            }
            """
        )

        self.undo_redo_frame = QFrame()
        self.undo_redo_frame.setObjectName(
            "UndoRedoTopBar"
        )

        undo_redo_layout = QHBoxLayout(
            self.undo_redo_frame
        )

        undo_redo_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        undo_redo_layout.setSpacing(
            6
        )

        self.undo_btn = QPushButton(
            "↶  Undo"
        )

        self.redo_btn = QPushButton(
            "Redo  ↷"
        )

        for button in (
            self.undo_btn,
            self.redo_btn,
        ):
            button.setFixedHeight(
                34
            )

            button.setMinimumWidth(
                76
            )

            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            set_themed_stylesheet(
                button,
                BUTTON_SECONDARY_QSS,
            )

        # Hovering these buttons teaches the keyboard shortcuts too.
        self.undo_btn.setToolTip(
            "Undo — Ctrl+Z"
        )

        self.redo_btn.setToolTip(
            "Redo — Ctrl+Y or Ctrl+Shift+Z"
        )

        self.undo_btn.clicked.connect(
            self.undo_character_change
        )

        self.redo_btn.clicked.connect(
            self.redo_character_change
        )

        undo_redo_layout.addWidget(
            self.undo_btn
        )

        undo_redo_layout.addWidget(
            self.redo_btn
        )

        self.update_undo_redo_button_state()

        self.theme_toggle_btn = QPushButton()
        self.theme_toggle_btn.setFixedSize(38, 34)
        self.theme_toggle_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        set_themed_stylesheet(
            self.theme_toggle_btn,
            BUTTON_ICON_QSS,
        )

        self.theme_toggle_btn.clicked.connect(
            self.toggle_theme_from_button
        )
        self.theme_toggle_btn.clicked.connect(
            lambda: QTimer.singleShot(0, self.refresh_notes)
        )
        self.theme_toggle_btn.clicked.connect(
            lambda: QTimer.singleShot(0, self.refresh_improvements)
        )

        self.update_theme_toggle_button()

        self.sheet_header_icon = FantasyIcon(
            "sheet",
            accent="#a87824",
            size=34,
        )

        top_bar.addWidget(
            self.sheet_header_icon,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addWidget(
            title,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addSpacing(22)

        top_bar.addWidget(
            self.name_caption,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        top_bar.addWidget(
            self.character_name_label,
            2,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addSpacing(8)

        top_bar.addWidget(
            self.species_caption,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        top_bar.addWidget(
            self.species_label,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addStretch()

        top_bar.addWidget(
            self.save_status_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        top_bar.addWidget(
            self.phone_connection_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addWidget(
            self.undo_redo_frame,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addWidget(
            self.theme_toggle_btn,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        top_bar.addWidget(
            self.tools_toggle_btn,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        outer_layout.addWidget(top_frame)



    
    # ============================================================
    # REDESIGNED CHARACTER PORTRAIT
    # ============================================================

    @qt_lifecycle_safe
    @qt_lifecycle_safe
    def update_history_button_state(self):
        has_earlier_version = False

        if self.current_character_filepath:
            try:
                history_files = (
                    CharacterStorageSystem
                    .get_meaningful_character_history(
                        self.current_character_filepath
                    )
                )

                has_earlier_version = (
                    len(
                        history_files
                    )
                    > 1
                )

            except Exception:
                traceback.print_exc()

        self._has_earlier_versions = (
            has_earlier_version
        )

        self.update_undo_redo_button_state()



    def style_portrait_overlay_controls(self):
        """Apply portrait overlay control colors for the active Light/Dark theme."""
        if not hasattr(
            self,
            "prev_image_btn",
        ):
            return

        dark_mode = (
            ui_theme_module.CURRENT_THEME
            == "dark"
        )

        button_bg = (
            "rgba(24, 39, 52, 235)"
            if dark_mode
            else "rgba(255, 253, 247, 225)"
        )

        button_hover_bg = (
            "#21384a"
            if dark_mode
            else "#fff4df"
        )

        button_pressed_bg = (
            "#13212d"
            if dark_mode
            else "#f5ead2"
        )

        button_text = (
            "#f5eee3"
            if dark_mode
            else "#6c5428"
        )

        button_hover_text = (
            "#ffffff"
            if dark_mode
            else "#a87824"
        )

        counter_text = (
            "#f5eee3"
            if dark_mode
            else "#6c5428"
        )

        overlay_button_style = f"""
            QPushButton {{
                background-color: {button_bg};
                border: 1px solid #cdaa63;
                border-radius: 9px;
                font-size: 16px;
                font-weight: 900;
                color: {button_text};
                padding: 0px;
                margin: 0px;
            }}

            QPushButton:hover {{
                background-color: {button_hover_bg};
                border: 1px solid #cdaa63;
                color: {button_hover_text};
            }}

            QPushButton:pressed {{
                background-color: {button_pressed_bg};
                border: 1px solid #cdaa63;
            }}
        """

        for button in (
            self.prev_image_btn,
            self.next_image_btn,
            self.add_image_btn,
        ):
            set_themed_stylesheet(
                button,
                overlay_button_style,
            )

        remove_hover_bg = (
            "#2c1820"
            if dark_mode
            else "#fff4df"
        )

        remove_hover_border = (
            "#ff8a8a"
            if dark_mode
            else "#aa0000"
        )

        remove_hover_text = (
            "#ffd7d7"
            if dark_mode
            else "#aa0000"
        )

        set_themed_stylesheet(
            self.remove_image_btn,
            f"""
            QPushButton {{
                background-color: {button_bg};
                border: 1px solid #d9bd82;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 900;
                color: {button_text};
                padding: 0px;
                margin: 0px;
            }}

            QPushButton:hover {{
                background-color: {remove_hover_bg};
                border: 1px solid {remove_hover_border};
                color: {remove_hover_text};
            }}

            QPushButton:pressed {{
                background-color: {button_pressed_bg};
            }}
            """
        )

        set_themed_stylesheet(
            self.image_counter_label,
            f"""
            QLabel {{
                background-color: {button_bg};
                border: 1px solid #d9bd82;
                border-radius: 8px;
                font-family: Georgia;
                font-size: 10px;
                font-weight: 900;
                color: {counter_text};
                padding: 0px;
                margin: 0px;
            }}
            """
        )


    def build_character_image_carousel(self, center_col):
        """
        Fantasy portrait frame.

        The picture uses nearly the whole portrait area. Carousel controls
        sit ON the portrait instead of consuming a separate row below it.
        All image add/remove/previous/next behavior is unchanged.
        """

        self.image_frame = QFrame()
        self.image_frame.setObjectName(
            "RedesignImageFrame"
        )

        self.image_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # A portrait must never contribute a minimum horizontal size to the
        # left column. Different pixmap dimensions should change only the
        # crop inside this frame, never the column geometry.
        self.image_frame.setMinimumWidth(
            0
        )

        set_themed_stylesheet(
            self.image_frame,
            """
            QFrame#RedesignImageFrame {
                background-color: #fffdf7;
                border: 2px solid #cdaa63;
                border-radius: 13px;
            }
            """
        )

        image_layout = QVBoxLayout(
            self.image_frame
        )

        image_layout.setContentsMargins(
            5, 5, 5, 5
        )

        image_layout.setSpacing(
            0
        )

        # --------------------------------------------------------
        # Main portrait
        # --------------------------------------------------------

        self.image_label = QLabel(
            "＋\nAdd Portrait"
        )

        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.image_label.setMinimumHeight(
            0
        )

        # IMPORTANT:
        # QLabel.sizeHint() normally follows its pixmap size. Every time a
        # different portrait was loaded, that pixmap sizeHint could make Qt
        # widen the entire first column. The newly widened label was then used
        # as the crop width for the next image, causing the column to grow
        # again each time the arrows were pressed.
        #
        # Ignore the pixmap's sizeHint horizontally and let the surrounding
        # layout decide the portrait width.
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self.image_label.setMinimumWidth(
            0
        )

        self.image_label.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        set_themed_stylesheet(
            self.image_label,
            """
            QLabel {
                background-color: #fffaf0;
                border: 1px solid #e2cfaa;
                border-radius: 9px;
                font-family: Georgia;
                font-size: 17px;
                font-weight: 800;
                color: #a87824;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        self.image_label.mousePressEvent = (
            lambda event:
                self.add_character_image_from_ui()
        )

        image_layout.addWidget(
            self.image_label,
            1,
        )

        # --------------------------------------------------------
        # Overlay controls
        # --------------------------------------------------------

        self.remove_image_btn = QPushButton(
            "×",
            self.image_label,
        )

        self.prev_image_btn = QPushButton(
            "‹",
            self.image_label,
        )

        self.next_image_btn = QPushButton(
            "›",
            self.image_label,
        )

        self.add_image_btn = QPushButton(
            "＋",
            self.image_label,
        )

        self.image_counter_label = QLabel(
            "0 / 0",
            self.image_label,
        )

        self.remove_image_btn.clicked.connect(
            self.confirm_remove_character_image
        )

        self.prev_image_btn.clicked.connect(
            self.previous_character_image
        )

        self.next_image_btn.clicked.connect(
            self.next_character_image
        )

        self.add_image_btn.clicked.connect(
            self.add_character_image_from_ui
        )

        self.image_counter_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.remove_image_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.prev_image_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.next_image_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.add_image_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.remove_image_btn.setFixedSize(
            24,
            24,
        )

        self.prev_image_btn.setFixedSize(
            30,
            30,
        )

        self.next_image_btn.setFixedSize(
            30,
            30,
        )

        self.add_image_btn.setFixedSize(
            28,
            28,
        )

        self.image_counter_label.setFixedSize(
            54,
            24,
        )
        self._portrait_hover_activated = False
        self._portrait_hover_watcher = _PortraitHoverWatcher(self)
        self.image_label.setMouseTracking(True)
        for control in (self.remove_image_btn, self.prev_image_btn,
                        self.next_image_btn, self.add_image_btn,
                        self.image_counter_label):
            control.setMouseTracking(True)
        for watched in (self.image_label, self.remove_image_btn,
                        self.prev_image_btn, self.next_image_btn,
                        self.add_image_btn, self.image_counter_label):
            watched.installEventFilter(self._portrait_hover_watcher)


        self.style_portrait_overlay_controls()

        self.remove_image_btn.hide()
        self.prev_image_btn.hide()
        self.next_image_btn.hide()
        self.add_image_btn.hide()
        self.image_counter_label.hide()

        # The portrait is the only vertically flexible part of the left
        # column. Extra screen height enlarges the framed portrait instead of
        # becoming a blank gap before the ability rows.
        center_col.addWidget(
            self.image_frame,
            1,
        )

    def add_character_image_from_ui(self):
        """Import one or several portraits in their selected order."""
        if self.block_if_readonly():
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Character Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.ico *.jfif *.avif *.heic *.heif);;All Files (*)",
        )
        if not paths:
            return

        # Normalize to PNG so every decoded image (including WEBP) survives
        # serialization and reopening even when the original plugin is absent.
        def prepare_images():
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice
            prepared, failures = [], []
            for path in paths:
                try:
                    with open(path, "rb") as source:
                        raw = source.read()
                    image = QImage.fromData(raw)
                    if image.isNull():
                        # Qt supports WEBP on most installations. Pillow is a
                        # fallback for additional installed formats/plugins.
                        import io
                        from PIL import Image, ImageOps
                        with Image.open(io.BytesIO(raw)) as picture:
                            picture = ImageOps.exif_transpose(picture)
                            picture = picture.convert("RGBA")
                            stream = io.BytesIO()
                            picture.save(stream, format="PNG")
                            png_bytes = stream.getvalue()
                    else:
                        encoded = QByteArray()
                        output = QBuffer(encoded)
                        if not output.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(output, "PNG"):
                            raise ValueError("Could not convert image to PNG")
                        png_bytes = bytes(encoded)
                    prepared.append("data:image/png;base64," +
                                    base64.b64encode(png_bytes).decode("ascii"))
                except Exception as error:
                    failures.append(f"{os.path.basename(path)}: {error}")
            return prepared, failures

        prepared, failures = run_loading_task(self, f"Importing {len(paths)} picture(s)…", prepare_images)
        added = sum(bool(ImageSystem.add_image(self.character, data)) for data in prepared)
        if added:
            self.mark_dirty(auto_save=True)
            self.refresh_character_image()
        if failures:
            QMessageBox.warning(
                self, "Some images were not added", "\n".join(failures)
            )


    def _update_portrait_overlay_hover(self):
        if not hasattr(self, "image_label") or not hasattr(self, "character"):
            return
        image = getattr(self.character, "image", None)
        total = len(getattr(image, "images", []) or []) if image else 0
        # If no portrait exists, keep the add-portrait affordance visible.
        hover = self.image_label.rect().contains(
            self.image_label.mapFromGlobal(QCursor.pos())
        )
        if not hover:
            self._portrait_hover_activated = False
        visible = (total > 0 and hover
                   and getattr(self, "_portrait_hover_activated", False)
                   and self.isVisible())
        for widget in (self.add_image_btn, self.remove_image_btn,
                       self.image_counter_label):
            widget.setVisible(visible)
        for widget in (self.prev_image_btn, self.next_image_btn):
            widget.setVisible(visible and total > 1)

    @qt_lifecycle_safe
    def position_portrait_controls(self):
        """
        Position the controls over the image after Qt finishes resizing it.
        """

        if not hasattr(
            self,
            "image_label",
        ):
            return

        width = self.image_label.width()
        height = self.image_label.height()

        if width <= 1 or height <= 1:
            return

        margin = 7

        self.remove_image_btn.move(
            width
            - self.remove_image_btn.width()
            - margin,
            margin,
        )

        self.prev_image_btn.move(
            margin,
            height
            - self.prev_image_btn.height()
            - margin,
        )

        self.next_image_btn.move(
            width
            - self.next_image_btn.width()
            - margin,
            height
            - self.next_image_btn.height()
            - margin,
        )

        self.add_image_btn.move(
            margin,
            margin,
        )

        self.image_counter_label.move(
            int(
                (width - self.image_counter_label.width())
                / 2
            ),
            height
            - self.image_counter_label.height()
            - margin,
        )

        for widget in (
            self.remove_image_btn,
            self.prev_image_btn,
            self.next_image_btn,
            self.add_image_btn,
            self.image_counter_label,
        ):
            widget.raise_()


    def refresh_character_image(self):
        """
        Preserve the working image loading/cropping logic and then apply
        the redesign-specific portrait controls.
        """

        ImageMixin.refresh_character_image(
            self
        )

        # Dark-mode presentation only:
        # make a large edge-connected white canvas transparent while leaving
        # the image stored in the character completely untouched.
        displayed_pixmap = (
            self.image_label.pixmap()
        )

        if (
            displayed_pixmap is not None
            and not displayed_pixmap.isNull()
        ):
            self.image_label.setPixmap(
                portrait_pixmap_for_current_theme(
                    displayed_pixmap
                )
            )

        # setPixmap() changes QLabel.sizeHint(). Re-assert that the portrait
        # pixmap is presentation-only and must not affect column width.
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self.image_label.setMinimumWidth(
            0
        )
        self.image_label.updateGeometry()

        total = len(
            self.character.image.images
        )

        image_entry = (
            self.character
            .image
            .current_image()
        )

        if isinstance(
            image_entry,
            dict,
        ):
            image_data = (
                image_entry.get("display")
                or image_entry.get("original")
            )
        else:
            image_data = image_entry

        if total <= 0 or not image_data:
            self.image_label.setText(
                "＋\nAdd Portrait"
            )

            set_themed_stylesheet(
                self.image_label,
                """
                QLabel {
                    background-color: #fffaf0;
                    border: 1px dashed #cdaa63;
                    border-radius: 9px;
                    font-family: Georgia;
                    font-size: 17px;
                    font-weight: 800;
                    color: #a87824;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

            self.remove_image_btn.hide()
            self.prev_image_btn.hide()
            self.next_image_btn.hide()
            self.add_image_btn.hide()
            self.image_counter_label.hide()

            return

        self.image_label.setText(
            ""
        )

        set_themed_stylesheet(
            self.image_label,
            """
            QLabel {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 9px;
            }
            """
        )

        # With an existing portrait:
        # - delete and add-image controls are always available;
        # - arrows appear only when there is something to navigate;
        # - the count stays as a subtle bottom-center badge.
        # Never expose portrait controls during initial render or refresh.
        # Visibility is controlled exclusively by the hover handler.
        for control in (self.remove_image_btn, self.add_image_btn,
                        self.image_counter_label, self.prev_image_btn,
                        self.next_image_btn):
            control.hide()

        self.image_counter_label.setText(
            f"{self.character.image.current_index + 1} / {total}"
        )
        QTimer.singleShot(0, self._update_portrait_overlay_hover)

        QTimer.singleShot(
            0,
            self.position_portrait_controls,
        )

        QTimer.singleShot(
            0,
            self.keep_sheet_horizontally_locked,
        )
        QTimer.singleShot(
            0,
            self.keep_sheet_vertically_locked,
        )

        QTimer.singleShot(
            30,
            self.keep_sheet_horizontally_locked,
        )

        QTimer.singleShot(
            40,
            self.refresh_character_image_after_layout,
        )

    @qt_lifecycle_safe
    def refresh_character_image_after_layout(self):
        """
        Re-render the portrait once Qt has finished laying out the sheet.

        This makes the white-background removal work immediately even when
        the character has only one portrait and the user never presses the
        previous/next buttons.
        """

        ImageMixin.refresh_character_image(
            self
        )

        displayed_pixmap = (
            self.image_label.pixmap()
        )

        if (
            displayed_pixmap is not None
            and not displayed_pixmap.isNull()
        ):
            self.image_label.setPixmap(
                portrait_pixmap_for_current_theme(
                    displayed_pixmap
                )
            )

        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self.image_label.setMinimumWidth(
            0
        )

        self.image_label.updateGeometry()

        self.position_portrait_controls()


    # ============================================================
    # LEFT COLUMN
    # Portrait -> Name + Species -> Abilities
    # ============================================================

    def build_stats_column(self, main_layout):
        left_frame = QFrame()
        self.redesign_left_frame = left_frame
        left_frame.setObjectName("RedesignLeftPanel")

        # Keep the original sheet height as the minimum, but let the left
        # column use extra vertical room on taller windows. The portrait is
        # the flexible element; the ability rows keep their normal geometry.
        left_frame.setMinimumHeight(
            REGULAR_SHEET_HEIGHT
        )

        left_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        set_themed_stylesheet(
            left_frame,
            """
            QFrame#RedesignLeftPanel {
                background-color: white;
                border: 2px solid #d9bd82;
                border-radius: 14px;
            }
            """
        )

        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(5)
        left_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        # ---------------- Portrait ----------------

        self.build_character_image_carousel(
            left_layout
        )

        # Keep the normal portrait size on compact windows, but on taller
        # screens let the portrait itself absorb the extra height. This avoids
        # creating an empty spacer between the portrait and the abilities.
        # Allow the portrait to shrink on compact screens. A 270px minimum
        # could force the six fixed-height ability rows below the viewport.
        self.image_frame.setMinimumHeight(120)
        self.image_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # ---------------- Abilities ----------------


        self.stats_col = QVBoxLayout()
        self.stats_col.setSpacing(4)
        self.stats_col.setContentsMargins(
            0, 0, 0, 0
        )
        self.stats_col.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.stat_rows = {}

        stat_display_names = {
            "agility": "Agility",
            "strength": "Strength",
            "finesse": "Finesse",
            "instinct": "Instinct",
            "presence": "Presence",
            "knowledge": "Knowledge",
        }

        for stat_key in STAT_NAMES:
            row = RedesignStatRow(
                stat_display_names[stat_key],
                stat_key,
                self.character,
            )

            # Clicking anywhere on the ability row rolls its current die + bonus.
            row.clicked.connect(
                self.roll_stat_from_ui
            )

            row.optionsRequested.connect(
                self.open_dice_options_for_stat
            )

            self.stat_rows[
                stat_key
            ] = row

        stats_widget = QWidget()
        stats_widget.setLayout(
            self.stats_col
        )

        stats_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        left_layout.addWidget(
            stats_widget
        )

        self.refresh_stats()

        main_layout.addWidget(
            left_frame,
            3,
            Qt.AlignmentFlag.AlignTop,
        )

    def refresh_identity(self):
        """
        Same identity behavior as the working frontend, with the Species
        caption shown/hidden together with the Species field.
        """

        name = self.character.name.strip()

        if not self.character_name_label.hasFocus():
            self.character_name_label.setText(
                name
            )

        self.character_name_label.setPlaceholderText(
            "Unnamed Character"
        )

        species_improvement = (
            self.get_species_improvement()
        )

        if not species_field_visible(self.character):
            self.species_label.hide()

            if hasattr(self, "species_caption"):
                self.species_caption.hide()
            return

        # Required campaign characters must show the Species chooser even
        # before an actual Species improvement exists. No fake selection is
        # written to the character; the click opens the real catalog picker.
        species_name = ""
        if species_improvement is not None:
            species_name = str(
                (species_improvement.choices or {}).get("_species_name", "")
                or self.character.species_name
                or ""
            ).strip()

        # This field is a read-only picker, never a text editor. Always update
        # it after a selection, even if it still owns keyboard focus.
        self.species_label.setText(species_name)
        self.species_label.setPlaceholderText("Choose Species" if not species_name else "Species")

        self.species_label.show()

        if hasattr(
            self,
            "species_caption",
        ):
            self.species_caption.show()


    def refresh_stats(self):
        """
        Same sorting rule as the working sheet, but let the redesigned
        ability rows expand across the full left-column width.
        """
        sorted_stats = sorted(
            STAT_NAMES,
            key=lambda stat_name: (
                -self.character.stats.get_stat(
                    stat_name
                ).die_size,
                -self.character.stats.get_stat(
                    stat_name
                ).bonus,
                stat_name,
            ),
        )

        while self.stats_col.count():
            item = self.stats_col.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.setParent(None)

        for stat_name in sorted_stats:
            row = self.stat_rows[
                stat_name
            ]

            row.refresh()

            # No AlignLeft here: the row should occupy the entire width.
            self.stats_col.addWidget(
                row
            )


    # ============================================================
    # CENTER COLUMN
    # HP / AT / BDV / DR -> Improvements
    # ============================================================

    def build_center_column(self, main_layout):
        center_widget = QWidget()
        self.redesign_center_widget = center_widget

        center_widget.setFixedHeight(
            REGULAR_SHEET_HEIGHT
        )

        center_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        center_col = QVBoxLayout(
            center_widget
        )

        center_col.setContentsMargins(
            0, 0, 0, 0
        )

        center_col.setSpacing(4)

        # ========================================================
        # COMPACT RESOURCE PANEL
        # ========================================================

        resources_frame = QFrame()
        self.redesign_resources_frame = resources_frame

        resources_frame.setObjectName(
            "RedesignResources"
        )

        resources_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(
            resources_frame,
            """
            QFrame#RedesignResources {
                background-color: white;
                border: 2px solid #d9bd82;
                border-radius: 14px;
            }
            """
        )

        resources_layout = QVBoxLayout(
            resources_frame
        )

        resources_layout.setContentsMargins(
            10, 4, 3, 4
        )

        resources_layout.setSpacing(2)

        # --------------------------------------------------------
        # HEARTS ROW
        # Hearts on the left, BDV/DR on the right.
        # --------------------------------------------------------

        hearts_row = QHBoxLayout()
        hearts_row.setContentsMargins(
            0, 0, 0, 0
        )
        hearts_row.setSpacing(2)

        hearts_block = QWidget()
        hearts_block_layout = QVBoxLayout(
            hearts_block
        )

        hearts_block_layout.setContentsMargins(
            0, 0, 0, 0
        )
        hearts_block_layout.setSpacing(1)

        self.hp_panel = HeartsPanel(
            self.character
        )

        hearts_block_layout.addWidget(
            self.hp_panel,
            0,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
        )

        hearts_row.addWidget(
            hearts_block,
            1,
        )

        defense_row = QHBoxLayout()
        defense_row.setContentsMargins(
            0, 0, 0, 0
        )
        defense_row.setSpacing(0)
        defense_row.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        self.bdv_box = RedesignSmallTopBox(
            "BDV",
            "0",
        )

        self.dr_box = RedesignSmallTopBox(
            "DR",
            "0",
        )

        defense_row.addWidget(
            self.bdv_box
        )
        defense_row.addWidget(
            self.dr_box
        )

        hearts_row.addLayout(
            defense_row
        )

        resources_layout.addLayout(
            hearts_row
        )

        # --------------------------------------------------------
        # AT ROW
        # --------------------------------------------------------

        at_block = QWidget()
        at_block_layout = QVBoxLayout(
            at_block
        )

        at_block_layout.setContentsMargins(
            0, 0, 0, 0
        )
        at_block_layout.setSpacing(0)

        self.at_box =  ATWidget(
            self.character
        )

        at_block_layout.addWidget(
            self.at_box
        )

        resources_layout.addWidget(
            at_block
        )

        resources_layout.activate()

        resources_frame.setFixedHeight(
            int(
                resources_frame.sizeHint().height()
            )
        )

        center_col.addWidget(
            resources_frame
        )

        # ========================================================
        # 3D DICE
        # ========================================================
        # The dice view is intentionally NOT inserted into this layout.
        # It is a floating overlay over the sheet, D&D Beyond style, so
        # rolling never pushes Hearts/AT/Improvements around.

        # ========================================================
        # IMPROVEMENTS HOST
        # ========================================================

        self.redesign_improvements_host = QWidget()

        self.redesign_improvements_layout = QVBoxLayout(
            self.redesign_improvements_host
        )

        self.redesign_improvements_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.redesign_improvements_layout.setSpacing(
            0
        )

        center_col.addWidget(
            self.redesign_improvements_host
        )

        main_layout.addWidget(
            center_widget,
            7,
            Qt.AlignmentFlag.AlignTop,
        )


    # ============================================================
    # INVENTORY
    # Right column, existing behavior for now
    # ============================================================

    def build_inventory_column(self, main_layout):
        inv_frame = QFrame()
        self.inventory_frame = inv_frame

        inv_frame.setObjectName(
            "RedesignInventoryFrame"
        )

        inv_frame.setFixedHeight(
            REGULAR_SHEET_HEIGHT
        )

        inv_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(
            inv_frame,
            """
            QFrame#RedesignInventoryFrame {
                background-color: #fffdf7;
                border: 2px solid #cdaa63;
                border-radius: 14px;
            }
            """
        )

        inv_layout = QVBoxLayout(
            inv_frame
        )

        inv_layout.setContentsMargins(
            10, 8, 3, 10
        )

        inv_layout.setSpacing(7)

        # --------------------------------------------------------
        # Header: illustration + title + Add Item
        # --------------------------------------------------------

        self.inventory_header_widget = QWidget()

        header = QHBoxLayout(
            self.inventory_header_widget
        )

        header.setContentsMargins(
            0, 0, 0, 0
        )

        header.setSpacing(7)

        inventory_header_path = os.path.join(
            HEADER_ICON_DIR,
            "inventory.svg",
        )

        if os.path.exists(
            inventory_header_path
        ):
            inventory_icon = ExternalSvgIcon(
                inventory_header_path,
                size=30,
            )
        else:
            inventory_icon = FantasyIcon(
                "inventory",
                accent="#8b6724",
                size=30,
            )

        inv_title = QLabel(
            "Inventory"
        )

        set_themed_stylesheet(
            inv_title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 21px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        self.add_item_btn = QPushButton(
            "+  Add Item"
        )

        self.add_item_btn.setFixedHeight(
            32
        )

        set_themed_stylesheet(
            self.add_item_btn,
            BUTTON_PRIMARY_QSS,
        )

        self.add_item_btn.clicked.connect(
            self.add_inventory_item_from_ui
        )

        header.addWidget(
            inventory_icon
        )

        header.addWidget(
            inv_title
        )

        header.addStretch()

        header.addWidget(
            self.add_item_btn
        )

        inv_layout.addWidget(
            self.inventory_header_widget
        )

        # --------------------------------------------------------
        # Inventory list
        # --------------------------------------------------------

        self.inventory_scroll = QScrollArea()

        self.inventory_scroll.setWidgetResizable(
            False
        )

        self.inventory_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.inventory_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # This panel scrolls with the wheel/trackpad when its contents
        # overflow. Do not show a gold scrollbar or reserve its width:
        # the viewport stays constant while inventory rows expand/collapse.
        self.inventory_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        set_themed_stylesheet(
            self.inventory_scroll,
            """
            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 9px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background-color: #d9bd82;
                border-radius: 4px;
                min-height: 24px;
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
        )

        self.inventory_list_widget = QWidget()

        self.inventory_list_layout = QVBoxLayout(
            self.inventory_list_widget
        )

        self.inventory_list_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.inventory_list_layout.setSpacing(
            6
        )

        self.inventory_scroll.setWidget(
            self.inventory_list_widget
        )

        inv_layout.addWidget(
            self.inventory_scroll
        )

        inv_layout.addStretch()

        main_layout.addWidget(
            inv_frame,
            3,
            Qt.AlignmentFlag.AlignTop,
        )

    # ============================================================
    # IMPROVEMENTS
    # Existing Improvements UI, but placed inside CENTER
    # ============================================================

    def build_improvements_column(self, main_layout):
        imp_frame = QFrame()
        self.improvements_frame = imp_frame

        imp_frame.setObjectName(
            "RedesignImprovementsFrame"
        )

        imp_frame.setFixedHeight(
            365
        )

        imp_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(
            imp_frame,
            """
            QFrame#RedesignImprovementsFrame {
                background-color: #fffdf7;
                border: 2px solid #cdaa63;
                border-radius: 14px;
            }
            """
        )

        imp_layout = QVBoxLayout(
            imp_frame
        )

        imp_layout.setContentsMargins(
            10, 8, 10, 10
        )

        imp_layout.setSpacing(
            7
        )

        # --------------------------------------------------------
        # Header
        # illustration + title + FREE + Add Improvement + IP
        # --------------------------------------------------------

        self.improvements_header_widget = QWidget()

        header = QHBoxLayout(
            self.improvements_header_widget
        )

        header.setContentsMargins(
            0, 0, 0, 0
        )

        header.setSpacing(
            7
        )

        improvements_header_path = os.path.join(
            HEADER_ICON_DIR,
            "improvements.svg",
        )

        if os.path.exists(
            improvements_header_path
        ):
            imp_icon = ExternalSvgIcon(
                improvements_header_path,
                size=30,
            )
        else:
            imp_icon = FantasyIcon(
                "improvements",
                accent="#a87824",
                size=30,
            )

        imp_title = QLabel(
            "Improvements"
        )

        set_themed_stylesheet(
            imp_title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 21px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        self.free_heightened_label = QLabel()
        self.free_heightened_label.setWordWrap(
            False
        )

        self.free_heightened_label.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.free_heightened_label.mousePressEvent = (
            lambda event:
                self.manage_free_heightened_abilities_from_ui()
        )

        set_themed_stylesheet(
            self.free_heightened_label,
            """
            QLabel {
                background-color: #fffaf0;
                border: 2px solid #c79a3b;
                border-radius: 9px;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 900;
                color: #25190f;
                padding: 4px 10px;
                margin: 0px;
            }
            QLabel:hover {
                background-color: #fff4df;
                border-color: #a87824;
                color: #25190f;
            }
            """
        )

        self.add_improvement_btn = QPushButton(
            "+  Add Improvement"
        )

        self.add_improvement_btn.setFixedHeight(
            32
        )

        set_themed_stylesheet(
            self.add_improvement_btn,
            BUTTON_PRIMARY_QSS,
        )

        self.add_improvement_btn.clicked.connect(
            self.add_improvement_from_ui
        )

        self.count_box = IPLabel(
            "0 / 0"
        )

        self.count_box.setFixedSize(
            64,
            32
        )

        self.count_box.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        set_themed_stylesheet(
            self.count_box,
            """
            QLabel {
                background-color: #f4fbff;
                border: 1px solid #d9bd82;
                border-radius: 7px;
                font-size: 13px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        left_header = QWidget()
        left_header_layout = QHBoxLayout(
            left_header
        )

        left_header_layout.setContentsMargins(
            0, 0, 0, 0
        )

        left_header_layout.setSpacing(
            7
        )

        left_header_layout.addWidget(
            imp_icon
        )

        left_header_layout.addWidget(
            imp_title
        )

        left_header_layout.addStretch()


        middle_header = QWidget()
        middle_header_layout = QHBoxLayout(
            middle_header
        )

        middle_header_layout.setContentsMargins(
            50, 0, 0, 0
        )

        middle_header_layout.setSpacing(
            7
        )

        middle_header_layout.addStretch()

        middle_header_layout.addWidget(
            self.add_improvement_btn,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        middle_header_layout.addStretch()


        right_header = QWidget()
        right_header_layout = QHBoxLayout(
            right_header
        )

        right_header_layout.setContentsMargins(
            0, 0, 0, 0
        )

        right_header_layout.setSpacing(
            7
        )

        right_header_layout.addStretch()

        right_header_layout.addWidget(
            self.free_heightened_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        right_header_layout.addWidget(
            self.count_box,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )


        left_header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        middle_header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        right_header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )


        header.addWidget(
            left_header,
            2,
        )

        header.addWidget(
            middle_header,
            2,
        )

        header.addWidget(
            right_header,
            3,
        )
        
        imp_layout.addWidget(
            self.improvements_header_widget
        )

        # --------------------------------------------------------
        # Scrollable Improvement list
        # --------------------------------------------------------

        self.improvement_scroll = QScrollArea()

        self.improvement_scroll.setWidgetResizable(
            False
        )

        self.improvement_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.improvement_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Hide the decorative scrollbar, keeping its internal scroll range
        # accessible to mouse wheel and trackpad gestures.
        self.improvement_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        set_themed_stylesheet(
            self.improvement_scroll,
            """
            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 9px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background-color: #d9bd82;
                border-radius: 4px;
                min-height: 24px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #c6a15d;
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
        )

        self.improvement_list_widget = QWidget()

        set_themed_stylesheet(
            self.improvement_list_widget,
            "background: transparent;"
        )

        self.improvement_list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.improvement_list_layout = IndependentTwoColumnImprovementLayout(
            self.improvement_list_widget
        )

        self.improvement_scroll.setWidget(
            self.improvement_list_widget
        )

        self.improvement_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.improvement_scroll.setMinimumHeight(
            0
        )

        self.improvement_scroll.setFixedHeight(
            0
        )

        imp_layout.addWidget(
            self.improvement_scroll
        )

        imp_layout.addStretch()

        self.redesign_improvements_layout.addWidget(
            imp_frame,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

    def open_ability_editor(self):
        """
        Use the working AbilityEditorDialog logic from the current frontend,
        with only the redesign presentation changed.
        """

        if self.block_if_readonly():
            return

        allowed_array_ids = None
        restrict_to_array_dice = False

        if getattr(
            self.character,
            "creation_rules_active",
            False,
        ):
            allowed_array_ids = list(
                getattr(
                    self.character,
                    "creation_allowed_ability_array_ids",
                    [],
                )
            )
            restrict_to_array_dice = bool(
                getattr(
                    self.character,
                    "creation_restrict_ability_dice_to_allowed_arrays",
                    False,
                )
            )

        dialog = FantasyAbilityEditorDialog(
            self.character,
            self,
            allowed_array_ids=allowed_array_ids,
            restrict_to_array_dice=restrict_to_array_dice,
        )

        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            self.mark_dirty(
                auto_save=True
            )
            self.refresh_all()

    def prepare_inventory_row_for_width(self, row, total_width):
        """Use InventoryRow's single responsive height/width calculation.

        It measures the real header (including any linked-note icons) and
        the actual styled font, so the title cannot overlap the remove button
        or lose lines when items expand, collapse or the window is resized.
        """
        return row.required_height(total_width)


    @qt_lifecycle_safe
    def refresh_inventory_scroll_geometry(self):
        if not hasattr(
            self,
            "inventory_scroll",
        ):
            return

        layout = self.inventory_list_layout
        item_count = layout.count()

        if item_count == 0:
            self.inventory_scroll.hide()
            self.inventory_scroll.setFixedHeight(
                0
            )
            return

        self.inventory_scroll.show()

        viewport_width = (
            self.inventory_scroll
            .viewport()
            .width()
        )

        if viewport_width <= 0:
            viewport_width = (
                self.inventory_scroll.width()
            )

        content_width = max(
            1,
            viewport_width,
        )

        self.inventory_list_widget.setFixedWidth(
            content_width
        )

        content_height = 0
        widget_count = 0

        for index in range(
            item_count
        ):
            item = layout.itemAt(
                index
            )

            widget = item.widget()

            if widget is None:
                continue

            widget.setFixedWidth(
                content_width
            )

            row_height = (
                self.prepare_inventory_row_for_width(
                    widget,
                    content_width,
                )
            )

            widget.setFixedHeight(
                row_height
            )

            content_height += row_height
            widget_count += 1

        if widget_count > 1:
            content_height += (
                layout.spacing()
                * (widget_count - 1)
            )

        margins = (
            layout.contentsMargins()
        )

        content_height += (
            margins.top()
            + margins.bottom()
        )

        self.inventory_list_widget.setFixedHeight(
            content_height
        )

        frame_layout = (
            self.inventory_frame.layout()
        )

        frame_margins = (
            frame_layout.contentsMargins()
        )

        header_height = (
            self.inventory_header_widget
            .sizeHint()
            .height()
        )

        maximum_height = (
            self.inventory_frame.height()
            - frame_margins.top()
            - frame_margins.bottom()
            - header_height
            - frame_layout.spacing()
            - 4
        )

        self.inventory_scroll.setFixedHeight(
            min(
                content_height,
                max(
                    0,
                    maximum_height,
                ),
            )
        )

        QTimer.singleShot(
            0,
            self.lock_character_sheet_anchor,
        )


    def refresh_improvements(self):
        # A grouped Improvement may need a full list refresh (or another
        # command may refresh all Improvements). Preserve the scroll position
        # for the same character so opening a card never jumps to the top.
        character = getattr(self, 'character', None)
        character_key = str(getattr(character, 'id', None) or id(character))
        scroll = getattr(self, 'improvement_scroll', None)
        previous_key = getattr(self, '_improvement_scroll_character_key', None)
        old_scroll_position = (
            scroll.verticalScrollBar().value()
            if scroll is not None and character_key == previous_key
            else 0
        )
        self._improvement_scroll_character_key = character_key
        restore_generation = getattr(self, '_improvement_scroll_restore_generation', 0) + 1
        self._improvement_scroll_restore_generation = restore_generation

        # Keep all working purchase/sort/display logic from the normal
        # ImprovementsMixin.
        ImprovementsMixin.refresh_improvements(
            self
        )

        free_used = len(
            self.character
            .free_heightened_ability_stats
        )

        free_total = (
            self.character
            .free_heightened_ability_slots
        )

        if free_total > 0:
            self.free_heightened_label.setText(
                f"Free Heightened: {free_used}/{free_total}  ✎"
            )
            self.free_heightened_label.show()
        else:
            self.free_heightened_label.hide()

        set_themed_stylesheet(
            self.free_heightened_label,
            """
            QLabel {
                background-color: #fffaf0;
                border: 2px solid #c79a3b;
                border-radius: 9px;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 900;
                color: #25190f;
                padding: 4px 10px;
                margin: 0px;
            }
            QLabel:hover {
                background-color: #fff4df;
                border-color: #a87824;
                color: #25190f;
            }
            """
        )

        # The normal ImprovementsMixin creates several different row
        # classes (normal improvements, Heightened Ability groups,
        # Skilled At groups). Restyle whichever rows it generated.
        for index in range(
            self.improvement_list_layout.count()
        ):
            item = (
                self.improvement_list_layout
                .itemAt(index)
            )

            row = item.widget()

            if row is not None:
                self.style_redesign_improvement_row(
                    row
                )
                self.enable_improvement_long_press_reorder(
                    row
                )

        QTimer.singleShot(
            0,
            self.refresh_improvement_scroll_geometry,
        )
        QTimer.singleShot(
            0,
            lambda key=character_key, position=old_scroll_position, gen=restore_generation:
                self._restore_improvement_scroll_position(key, position, gen),
        )

    def _restore_improvement_scroll_position(self, character_key, position, generation):
        # A delayed callback must never overwrite a newer refresh or restore
        # an unrelated character's scroll position after a character switch.
        if generation != getattr(self, '_improvement_scroll_restore_generation', None):
            return
        character = getattr(self, 'character', None)
        current_key = str(getattr(character, 'id', None) or id(character))
        if current_key != character_key:
            return
        scroll = getattr(self, 'improvement_scroll', None)
        if scroll is not None:
            bar = scroll.verticalScrollBar()
            bar.setValue(min(max(0, int(position)), bar.maximum()))

    def measure_improvement_label_height(
        self,
        label,
        width,
    ):
        """
        Measure a wrapped QLabel using QTextDocument when needed.

        This is especially important for rich-text AutoWrapLabel summaries:
        fontMetrics().boundingRect() sees the raw HTML markup rather than
        the actual rendered rich text, which can under-size the label.
        """

        width = max(
            20,
            int(width),
        )

        text = label.text()

        document = QTextDocument()
        # Do not count QTextDocument's default internal margin when sizing
        # labels that already live inside a padded Improvement card.
        document.setDocumentMargin(0)
        document.setDefaultFont(
            label.font()
        )

        text_format = label.textFormat()

        looks_rich = (
            text_format
            == Qt.TextFormat.RichText
            or (
                "<" in text
                and ">" in text
            )
        )

        if looks_rich:
            document.setHtml(
                text
            )
        else:
            document.setPlainText(
                text
            )

        document.setTextWidth(
            width
        )

        height = int(
            document
            .documentLayout()
            .documentSize()
            .height()
            + 0.999
        )

        return max(
            label.fontMetrics().height(),
            height + 1,
        )


    def prepare_improvement_card_for_width(
        self,
        widget,
        card_width,
    ):
        """
        Give every wrapped label its full rendered height BEFORE asking
        the card layout for its size.

        Returns the full height required by the improvement card.
        """

        # Use the real column width, including when a user narrows the
        # Windows app. A hard 180px minimum forced the right column to
        # overflow its viewport at smaller window sizes.
        card_width = max(1, int(card_width))

        widget.setFixedWidth(
            card_width
        )

        main_box = getattr(
            widget,
            "main_box",
            None,
        )

        count_box = getattr(
            widget,
            "count_box",
            None,
        )

        count_width = (
            count_box.width()
            if count_box is not None
            else 34
        )

        outer_layout = (
            widget.layout()
        )

        outer_spacing = (
            outer_layout.spacing()
            if outer_layout is not None
            else 5
        )

        main_width = max(1, card_width - count_width - outer_spacing)

        if main_box is None:
            widget.adjustSize()

            return max(
                42,
                widget.sizeHint().height(),
            )

        main_box.setFixedWidth(
            main_width
        )

        box_layout = (
            main_box.layout()
        )

        if box_layout is None:
            return max(
                42,
                widget.sizeHint().height(),
            )

        box_margins = (
            box_layout.contentsMargins()
        )

        inner_width = max(1, main_width - box_margins.left() - box_margins.right())

        # --------------------------------------------------------
        # Name
        # --------------------------------------------------------

        name_label = getattr(
            widget,
            "name_label",
            None,
        )

        if name_label is not None:
            # SVGs and linked-note buttons live in the same header as the
            # Improvement title. Their actual space must be subtracted
            # *before* measuring a long, wrapped name.
            header_item = box_layout.itemAt(0) if box_layout.count() else None
            header_layout = header_item.layout() if header_item is not None else None
            if header_layout is not None:
                header_margins = header_layout.contentsMargins()
                reserved = header_margins.left() + header_margins.right()
                reserved += max(0, header_layout.count() - 1) * max(0, header_layout.spacing())
                for index in range(header_layout.count()):
                    element = header_layout.itemAt(index)
                    control = element.widget()
                    if control is name_label:
                        continue
                    if control is not None:
                        reserved += max(0, control.sizeHint().width())
                    elif element.spacerItem() is not None:
                        reserved += max(0, element.spacerItem().sizeHint().width())
                name_width = max(1, inner_width - reserved)
            else:
                name_width = max(1, inner_width - 48)

            name_height = (
                self.measure_improvement_label_height(
                    name_label,
                    name_width,
                )
            )

            name_label.setFixedWidth(
                name_width
            )

            name_label.setFixedHeight(
                name_height
            )

        # --------------------------------------------------------
        # Every wrapped label in the expanded content.
        #
        # Use a slightly conservative width so nested/indented labels
        # always receive enough vertical space.
        # --------------------------------------------------------

        safe_text_width = max(1, inner_width - 18)

        expanded = bool(
            getattr(widget, 'expanded',
                    getattr(getattr(widget, 'improvement', None), 'expanded', True))
        )
        for label in main_box.findChildren(
            QLabel
        ):
            if label is name_label:
                continue
            if not expanded:
                # Hidden descriptions should not retain measured heights
                # when a grouped card is collapsed in place.
                continue

            if not label.wordWrap():
                continue

            label_height = (
                self.measure_improvement_label_height(
                    label,
                    safe_text_width,
                )
            )

            if label.objectName() == "SpellcastingSchoolText":
                # QLabel knows the exact rich-text wrap used for the school
                # name + description. Prefer it over the generic document
                # estimate so the following Empowerments heading sits close.
                exact_height = label.heightForWidth(safe_text_width)
                if exact_height > 0:
                    label_height = exact_height + 1
            elif label.property("compact_improvement_line"):
                # A short empowerment is one line. QTextDocument's block
                # margins otherwise create a conspicuous gap between rows.
                if label.fontMetrics().horizontalAdvance(label.text()) <= safe_text_width:
                    label_height = label.fontMetrics().lineSpacing() + 2
            elif label.property("compact_choice_line"):
                # Keep the land name and description together; this QLabel
                # contains both lines instead of a stretching nested layout.
                exact_height = label.heightForWidth(safe_text_width)
                if exact_height > 0:
                    label_height = exact_height + 2

            label.setMinimumWidth(
                0
            )

            label.setFixedWidth(
                safe_text_width
            )

            label.setFixedHeight(
                label_height
            )

        box_layout.invalidate()
        box_layout.activate()

        # QVBoxLayout will now include the explicitly measured wrapped
        # labels, including the full Spellcasting summary/schools.
        main_height = max(
            box_layout.sizeHint().height(),
            box_layout.minimumSize().height(),
        )

        if box_layout.hasHeightForWidth():
            hfw = box_layout.heightForWidth(
                main_width
            )

            if hfw > 0:
                main_height = max(
                    main_height,
                    hfw,
                )

        bubble_height = (
            count_box.height()
            if count_box is not None
            else 34
        )

        required_height = max(
            42,
            bubble_height,
            main_height,
        )

        widget.setFixedHeight(
            required_height
        )

        return required_height


    @qt_lifecycle_safe
    def refresh_improvement_scroll_geometry(self, changed_widget=None):
        if not hasattr(
            self,
            "improvement_scroll",
        ):
            return

        layout = self.improvement_list_layout

        item_count = layout.count()

        if item_count == 0:
            self.improvement_scroll.hide()
            self.improvement_scroll.setFixedHeight(
                0
            )
            return

        self.improvement_scroll.show()

        viewport_width = (
            self.improvement_scroll
            .viewport()
            .width()
        )

        if viewport_width <= 1:
            viewport_width = (
                self.improvement_scroll.width()
            )

        content_width = max(
            1,
            viewport_width - 2,
        )

        self.improvement_list_widget.setFixedWidth(
            content_width
        )

        margins = layout.contentsMargins()

        # Exactly match IndependentTwoColumnImprovementLayout.setGeometry.
        # Never measure cards wider than the column they will occupy.
        card_width = improvement_two_column_width(
            content_width - margins.left() - margins.right(),
            layout.column_spacing,
        )

        left_height = 0
        right_height = 0

        left_count = 0
        right_count = 0

        for index in range(
            item_count
        ):
            item = layout.itemAt(
                index
            )

            widget = item.widget()

            if widget is None:
                continue

            # On an arrow click only one card was rebuilt.  Do not
            # re-measure every other open card: Qt rich-text labels can
            # produce slightly different height-for-width results across
            # repeated layout passes, which caused an untouched Spellcasting
            # card in the opposite column to grow internal blank space.
            #
            # A full refresh (changed_widget is None) still measures all
            # cards, and a real column-width change also forces remeasurement.
            current_width = widget.width()
            width_changed = abs(current_width - card_width) > 1

            if (
                changed_widget is None
                or widget is changed_widget
                or width_changed
                or widget.height() <= 0
            ):
                required_height = (
                    self.prepare_improvement_card_for_width(
                        widget,
                        card_width,
                    )
                )
            else:
                required_height = max(
                    42,
                    widget.height(),
                )

            if index % 2 == 0:
                if left_count:
                    left_height += (
                        layout.vertical_spacing
                    )

                left_height += required_height
                left_count += 1

            else:
                if right_count:
                    right_height += (
                        layout.vertical_spacing
                    )

                right_height += required_height
                right_count += 1

        content_height = max(
            left_height,
            right_height,
        )

        content_height += (
            margins.top()
            + margins.bottom()
        )

        self.improvement_list_widget.setFixedHeight(
            content_height
        )

        # Force the custom layout to recalculate positions.
        layout.invalidate()
        layout.activate()

        frame_layout = (
            self.improvements_frame.layout()
        )

        frame_margins = (
            frame_layout.contentsMargins()
        )

        header_height = (
            self.improvements_header_widget
            .sizeHint()
            .height()
        )

        maximum_height = (
            self.improvements_frame.height()
            - frame_margins.top()
            - frame_margins.bottom()
            - header_height
            - frame_layout.spacing()
            - 4
        )

        self.improvement_scroll.setFixedHeight(
            min(
                content_height,
                max(
                    0,
                    maximum_height,
                ),
            )
        )

        # Hide the decorative scrollbar, keeping its internal scroll range
        # accessible to mouse wheel and trackpad gestures.
        self.improvement_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.improvement_list_widget.updateGeometry()
        self.improvement_scroll.updateGeometry()

        QTimer.singleShot(
            0,
            self.lock_character_sheet_anchor,
        )

    # ============================================================
    # REDESIGNED INVENTORY / IMPROVEMENT ROWS
    # ============================================================

    def style_redesign_inventory_row(self, row):
        """
        Restyle the normal InventoryRow without replacing any of its
        existing behavior.
        """

        if not hasattr(
            row,
            "main_box",
        ):
            return

        # InventoryRow creates its remove button without putting it in the
        # header layout. Keep it in the layout so the title cannot cover it.
        header_layout = row.header_widget.layout()
        if header_layout is not None and header_layout.indexOf(row.remove_btn) < 0:
            header_layout.addWidget(row.remove_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            row.remove_btn.show()

        item_id = "item:" + str(row.item.id)
        linked_notes = [note for note in self.character.notes.list_of_notes
                        if str(note.linked_improvement_id or "") == item_id]
        if linked_notes and not hasattr(row, "_linked_note_icons"):
            box_layout = row.main_box.layout()
            top_layout = row.header_widget.layout()
            if top_layout is not None:
                row._linked_note_icons = []
                insert_index = top_layout.indexOf(row.name_label) + 1
                for note in linked_notes[:3]:
                    def show_item_note(icon, nid=note.id, link=item_id):
                        self.open_linked_improvement_notes(link, icon, note_id=nid)
                    icon = RelatedNoteHoverIcon(
                        on_hover=show_item_note,
                        on_leave=self.close_improvement_note_preview_on_leave,
                        on_click=lambda icon, show=show_item_note: self.toggle_pinned_improvement_note_preview(icon, show),
                        on_double_click=self.open_notes_page_from_related_icon,
                        size=22, parent=row.main_box,
                        note_color=lambda n=note: n.color)
                    icon.setAccessibleName(str(note.title or "Untitled Note"))
                    top_layout.insertWidget(insert_index, icon, 0, Qt.AlignmentFlag.AlignVCenter)
                    row._linked_note_icons.append(icon)
                    insert_index += 1
                if len(linked_notes) > 3:
                    more = QPushButton(f"+{len(linked_notes)-3}", row.main_box)
                    more.setFixedSize(32, 24)
                    more.clicked.connect(lambda checked=False, items=linked_notes[3:], button=more:
                                         self.choose_linked_improvement_note(items, button))
                    top_layout.insertWidget(insert_index, more, 0, Qt.AlignmentFlag.AlignVCenter)

        set_themed_stylesheet(
            row.main_box,
            """
            QFrame {
                background-color: #fffdf7;
                border: 1px solid #e2cfaa;
                border-radius: 10px;
            }
            """
        )

        if hasattr(
            row,
            "arrow_btn",
        ):
            set_themed_stylesheet(
                row.arrow_btn,
                """
                QPushButton {
                    background-color: transparent;
                    border: none;
                    font-weight: 900;
                    font-size: 15px;
                    color: #6c5428;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    color: #a87824;
                }
                """
            )

        if hasattr(
            row,
            "name_label",
        ):
            set_themed_stylesheet(
                row.name_label,
                """
                QLabel {
                    border: none;
                    background: transparent;
                    font-family: Georgia;
                    font-size: 14px;
                    font-weight: 800;
                    color: #25190f;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

        if hasattr(
            row,
            "description_label",
        ):
            set_themed_stylesheet(
                row.description_label,
                """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 11px;
                    color: #3b332a;
                    padding: 1px 0px 0px 0px;
                    margin: 0px;
                }
                """
            )

        if hasattr(
            row,
            "remove_btn",
        ):
            set_themed_stylesheet(
                row.remove_btn,
                """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: #765d34;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
                """
            )

        if hasattr(
            row,
            "quantity_label",
        ):
            set_themed_stylesheet(
                row.quantity_label,
                """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 13px;
                    font-weight: 900;
                    color: #25190f;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

        for button_name in (
            "plus_btn",
            "minus_btn",
        ):
            button = getattr(
                row,
                button_name,
                None,
            )

            if button is None:
                continue

            set_themed_stylesheet(
                button,
                """
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 900;
                    color: #765d34;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    background-color: #f5ead2;
                    color: #a87824;
                }
                """
            )

        # InventoryRow does not store its quantity QFrame as an attribute,
        # so locate the small direct child frame that is not main_box.
        for child_frame in row.findChildren(
            QFrame,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        ):
            if child_frame is row.main_box:
                continue

            set_themed_stylesheet(
                child_frame,
                """
                QFrame {
                    background-color: #fffaf0;
                    border: 1px solid #d9bd82;
                    border-radius: 9px;
                }
                """
            )


    def open_notes_page_from_related_icon(self):
        self.close_improvement_note_preview()
        self.show_notes_page()
        QTimer.singleShot(0, self.refresh_notes)

    def close_improvement_note_preview(self):
        self._pinned_improvement_note_preview = False
        dialog = getattr(
            self,
            "_improvement_note_preview",
            None,
        )

        if dialog is None:
            return

        try:
            dialog.close()

        except RuntimeError:
            pass

        self._improvement_note_preview = None

    def close_improvement_note_preview_on_leave(self):
        if not getattr(self, "_pinned_improvement_note_preview", False):
            self.close_improvement_note_preview()

    def toggle_pinned_improvement_note_preview(self, icon, show_note):
        if (getattr(self, "_pinned_improvement_note_preview", False)
                and getattr(self, "_pinned_note_anchor", None) is icon):
            self.close_improvement_note_preview()
            return
        self.close_improvement_note_preview()
        show_note(icon)
        self._pinned_note_anchor = icon
        self._pinned_improvement_note_preview = True

    def position_improvement_note_popup(self, dialog, anchor_widget):
        """Keep the popup beside its hover icon, including at screen edges."""
        if anchor_widget is None:
            return
        anchor = anchor_widget.mapToGlobal(QPoint(0, 0))
        screen = QApplication.screenAt(anchor)
        if screen is None:
            return
        available = screen.availableGeometry()
        right = anchor.x() + anchor_widget.width() + 8
        left = anchor.x() - dialog.width() - 8
        if right + dialog.width() <= available.right():
            x = right
        elif left >= available.left():
            x = left
        else:
            x = max(available.left(), min(right, available.right() - dialog.width()))
        y = max(available.top(), min(anchor.y(), available.bottom() - dialog.height()))
        dialog.move(x, y)


    def open_improvement_note_preview(
        self,
        improvement,
        anchor_widget=None,
    ):
        """
        Open the automatic note associated with an improvement without
        creating or changing a persistent character note.
        """

        import html

        catalog_id = getattr(
            improvement,
            "catalog_id",
            "",
        )

        if catalog_id in {"spellcasting", "magic_novice"}:
            title = "Spellcasting Verbs"
            color_key = "blue"

            body_html = format_system_note_html(self.spellcasting_note_html(improvement))

        elif catalog_id == "sneak_attack":
            title = "Sneak Attack"
            color_key = "red"

            note_text = ""

            existing_note = self.find_note_by_title(
                "Sneak Attack"
            )

            if existing_note is not None:
                note_text = existing_note.text
            else:
                builder = getattr(
                    self,
                    "build_sneak_attack_note_text",
                    None,
                )

                if callable(builder):
                    note_text = builder(
                        improvement
                    )

            escaped = str(note_text or "").replace(
                "\n",
                "<br>",
            )
            body_html = format_system_note_html(note_text)

        else:
            return

        old_window = getattr(
            self,
            "_improvement_note_preview",
            None,
        )

        if old_window is not None:
            try:
                old_window.close()
            except RuntimeError:
                pass

        dialog = FantasyTemporaryNoteDialog(
            title,
            body_html,
            color_key=color_key,
            parent=self,
        )

        self._improvement_note_preview = dialog

        try:
            self.position_improvement_note_popup(dialog, anchor_widget)
        except RuntimeError:
            pass

        dialog.show()
        dialog.raise_()


    def open_animal_buddy_note_popup(self, note, anchor_widget=None):
        """Show the exact same Animal Buddy card used on the Notes page."""
        old_window = getattr(self, "_improvement_note_preview", None)
        if old_window is not None:
            try:
                old_window.close()
            except RuntimeError:
                pass

        dialog = QDialog(self)
        dialog.setModal(False)
        dialog.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog._buddy_sheet_owner = self
        # Forward the model/save hooks used by AnimalBuddyPanel.
        dialog.character = self.character
        dialog.is_readonly_character = self.is_readonly_character
        dialog.synchronize_animal_buddy_note = self.synchronize_animal_buddy_note
        dialog.mark_dirty = self.mark_dirty
        dialog.refresh_all = self.refresh_all
        dialog.auto_save_character = self.auto_save_character
        dialog.refresh_notes = self.refresh_notes

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        card = AnimalBuddyNoteCard(
            note, self.character, self.on_note_changed, dialog
        )
        layout.addWidget(card)
        dialog.adjustSize()
        self._improvement_note_preview = dialog

        try:
            self.position_improvement_note_popup(dialog, anchor_widget)
        except RuntimeError:
            pass

        dialog.show()
        dialog.raise_()

    def choose_linked_improvement_note(self, notes, anchor_widget=None):
        """Choose a single note; never concatenate separately saved notes."""
        self.close_improvement_note_preview()
        menu = QMenu(self)
        set_themed_stylesheet(menu, FANTASY_MENU_QSS)
        for note in notes:
            action = menu.addAction(str(note.title or "Untitled Note"))
            action.triggered.connect(
                lambda checked=False, n=note: self.toggle_pinned_improvement_note_preview(
                    anchor_widget,
                    lambda icon: self.open_linked_improvement_notes(
                        n.linked_improvement_id, icon, note_id=n.id)))
        if anchor_widget is not None:
            menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))
        else:
            menu.exec(self.mapToGlobal(self.rect().center()))

    def open_linked_improvement_notes(
        self, improvement_id, anchor_widget=None, note_id=None,
    ):
        """Preview exactly one linked note, preserving its title and color."""
        import html
        linked_notes = [
            note for note in self.character.notes.list_of_notes
            if str(getattr(note, "linked_improvement_id", "") or "")
            == str(improvement_id or "")
            and (note_id is None or str(note.id) == str(note_id))
        ]
        if not linked_notes:
            return
        if len(linked_notes) > 1:
            self.choose_linked_improvement_note(linked_notes, anchor_widget)
            return
        note = linked_notes[0]
        title = str(note.title or "Untitled Note")
        if title.strip().lower() == "animal buddy":
            self.open_animal_buddy_note_popup(note, anchor_widget)
            return
        content = str(note.text or "")
        if content.startswith("<!--DID_RICH_NOTE-->"):
            body_html = content
        elif title.strip().lower() in {"mighty", "spellcasting verbs", "sneak attack"}:
            body_html = format_system_note_html(content)
        else:
            body_html = html.escape(content).replace("\n", "<br>")
        color_key = str(getattr(note, "color", "yellow") or "yellow")

        old_window = getattr(
            self,
            "_improvement_note_preview",
            None,
        )

        if old_window is not None:
            try:
                old_window.close()
            except RuntimeError:
                pass

        dialog = FantasyTemporaryNoteDialog(
            title,
            body_html,
            color_key=color_key,
            parent=self,
        )

        self._improvement_note_preview = (
            dialog
        )

        try:
            self.position_improvement_note_popup(dialog, anchor_widget)
        except RuntimeError:
            pass

        dialog.show()
        dialog.raise_()



    def style_redesign_improvement_row(self, row):
        """
        Apply the new light-fantasy visual language to all improvement
        row types while leaving their existing logic untouched.
        """

        # --------------------------------------------------------
        # Optional per-improvement SVG.
        # Looks for:
        #     icons/improvements/<Improvement Name>.svg
        # --------------------------------------------------------

        improvement_icon_path = (
            find_improvement_icon_path(
                row
            )
        )

        if (
            improvement_icon_path
            and not hasattr(
                row,
                "_redesign_improvement_icon",
            )
        ):
            main_box_for_icon = getattr(
                row,
                "main_box",
                None,
            )

            if (
                main_box_for_icon
                is not None
            ):
                box_layout_for_icon = (
                    main_box_for_icon.layout()
                )

                top_row_for_icon = None

                if (
                    box_layout_for_icon
                    is not None
                    and box_layout_for_icon.count()
                    > 0
                ):
                    first_item = (
                        box_layout_for_icon
                        .itemAt(0)
                    )

                    if first_item is not None:
                        top_row_for_icon = (
                            first_item.layout()
                        )

                if (
                    top_row_for_icon
                    is not None
                ):
                    row._redesign_improvement_icon = (
                        ExternalSvgIcon(
                            improvement_icon_path,
                            size=24,
                            parent=main_box_for_icon,
                        )
                    )

                    # arrow -> icon -> improvement name
                    top_row_for_icon.insertWidget(
                        1,
                        row._redesign_improvement_icon,
                        0,
                        Qt.AlignmentFlag.AlignVCenter,
                    )


        main_box = getattr(
            row,
            "main_box",
            None,
        )

        improvement = getattr(
            row,
            "improvement",
            None,
        )

        if (
            main_box is not None
            and improvement is not None
            and getattr(
                improvement,
                "catalog_id",
                "",
            )
            in {
                "spellcasting",
                "magic_novice",
                "sneak_attack",
            }
            and not hasattr(
                row,
                "_related_note_icon",
            )
        ):
            box_layout = main_box.layout()
            top_layout = None

            if (
                box_layout is not None
                and box_layout.count() > 0
            ):
                first_item = box_layout.itemAt(
                    0
                )

                if first_item is not None:
                    top_layout = first_item.layout()

            if top_layout is not None:
                catalog_id = getattr(
                    improvement,
                    "catalog_id",
                    "",
                )

                note_icon_path = os.path.join(
                    RELATED_NOTE_ICON_DIR,
                    f"{'spellcasting' if catalog_id == 'magic_novice' else catalog_id}.svg",
                )

                def show_related_note(
                    icon,
                    imp=improvement,
                ):
                    self.open_improvement_note_preview(
                        imp,
                        anchor_widget=icon,
                    )

                row._related_note_icon = (
                    RelatedNoteHoverIcon(
                        icon_path=note_icon_path,
                        note_color=lambda cid=catalog_id: getattr(
                            self.find_note_by_title("Sneak Attack" if cid == "sneak_attack" else "Spellcasting Verbs"),
                            "color", "red" if cid == "sneak_attack" else "blue"),
                        on_hover=show_related_note,
                        on_leave=self.close_improvement_note_preview_on_leave,
                        on_click=lambda icon: self.toggle_pinned_improvement_note_preview(
                            icon, show_related_note),
                        on_double_click=self.open_notes_page_from_related_icon,
                        size=22,
                        parent=main_box,
                    )
                )

                name_label = getattr(
                    row,
                    "name_label",
                    None,
                )

                name_index = (
                    top_layout.indexOf(
                        name_label
                    )
                    if name_label is not None
                    else -1
                )

                insert_index = (
                    name_index + 1
                    if name_index >= 0
                    else max(
                        0,
                        top_layout.count() - 1,
                    )
                )

                top_layout.insertWidget(
                    insert_index,
                    row._related_note_icon,
                    0,
                    Qt.AlignmentFlag.AlignVCenter,
                )

        linked_notes = []

        if (
            main_box is not None
            and improvement is not None
        ):
            linked_notes = [
                note
                for note in (
                    self.character
                    .notes
                    .list_of_notes
                )
                if str(
                    getattr(
                        note,
                        "linked_improvement_id",
                        "",
                    )
                    or ""
                ) == str(improvement.id)
            ]

        # The built-in icon already opens its managed note. Player notes
        # each get a separate ID-bound preview and retain their own color.
        related_icon = getattr(row, "_related_note_icon", None)
        builtin_title = {
            "spellcasting": "spellcasting verbs",
            "magic_novice": "spellcasting verbs",
            "sneak_attack": "sneak attack",
        }.get(getattr(improvement, "catalog_id", ""))
        notes = [note for note in linked_notes
                 if not (related_icon is not None
                         and note.title.strip().lower() == builtin_title)]
        if notes and not hasattr(row, "_individual_note_icons"):
            box_layout = main_box.layout()
            top_layout = box_layout.itemAt(0).layout() if box_layout and box_layout.count() else None
            if top_layout is not None:
                row._individual_note_icons = []
                name_index = top_layout.indexOf(getattr(row, "name_label", None))
                insert_index = (top_layout.indexOf(related_icon) + 1
                                if related_icon is not None else max(0, name_index + 1))
                capacity = 2 if related_icon is not None else 3
                for note in notes[:capacity]:
                    def show_note(icon, nid=note.id, iid=improvement.id):
                        self.open_linked_improvement_notes(iid, icon, note_id=nid)
                    icon = RelatedNoteHoverIcon(
                        on_hover=show_note,
                        on_leave=self.close_improvement_note_preview_on_leave,
                        on_click=lambda icon, show=show_note: self.toggle_pinned_improvement_note_preview(icon, show),
                        on_double_click=self.open_notes_page_from_related_icon,
                        size=22, parent=main_box,
                        note_color=lambda n=note: n.color)
                    icon.setAccessibleName(str(note.title or "Untitled Note"))
                    row._individual_note_icons.append(icon)
                    top_layout.insertWidget(insert_index, icon, 0, Qt.AlignmentFlag.AlignVCenter)
                    insert_index += 1
                remaining = notes[capacity:]
                if remaining:
                    more = QPushButton(f"+{len(remaining)}", main_box)
                    more.setToolTip("More linked notes")
                    more.setFixedSize(32, 24)
                    more.clicked.connect(lambda checked=False, items=remaining, button=more:
                                         self.choose_linked_improvement_note(items, button))
                    top_layout.insertWidget(insert_index, more, 0, Qt.AlignmentFlag.AlignVCenter)
                    row._individual_note_icons.append(more)


        if main_box is not None:
            set_themed_stylesheet(
                main_box,
                """
                QFrame {
                    background-color: #fffdf7;
                    border: 1px solid #e2cfaa;
                    border-radius: 10px;
                }
                """
            )

        count_box = getattr(
            row,
            "count_box",
            None,
        )

        if count_box is not None:
            count_box.setFixedSize(
                34,
                34,
            )

            set_themed_stylesheet(
                count_box,
                """
                QLabel {
                    background-color: #fffaf0;
                    border: 1px solid #d9bd82;
                    border-radius: 17px;
                    font-size: 13px;
                    font-weight: 900;
                    color: #25190f;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

        arrow = getattr(
            row,
            "arrow_btn",
            None,
        )

        if arrow is None:
            arrow = getattr(
                row,
                "expand_btn",
                None,
            )

        if arrow is not None:
            set_themed_stylesheet(
                arrow,
                """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 15px;
                    font-weight: 900;
                    color: #6c5428;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    color: #a87824;
                }
                """
            )

        name_label = getattr(
            row,
            "name_label",
            None,
        )

        if name_label is not None:
            set_themed_stylesheet(
                name_label,
                """
                QLabel {
                    border: none;
                    background: transparent;
                    font-family: Georgia;
                    font-size: 13px;
                    font-weight: 800;
                    color: #25190f;
                    padding: 0px;
                    margin: 0px;
                }
                """
            )

        remove_btn = getattr(
            row,
            "remove_btn",
            None,
        )

        if remove_btn is None:
            remove_btn = getattr(
                row,
                "remove_all_btn",
                None,
            )

        if remove_btn is not None:
            set_themed_stylesheet(
                remove_btn,
                """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: #765d34;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
                """
            )


    def enable_inventory_long_press_reorder(self, row):
        if not hasattr(row, "item"):
            return

        controller = LongPressReorderFilter(
            row,
            lambda global_pos, item_id=row.item.id:
                self.reorder_inventory_from_drop(item_id, global_pos),
            row,
        )

        row._long_press_reorder_controller = controller

    def reorder_inventory_from_drop(self, item_id, global_pos):
        if self.block_if_readonly():
            return
        rows = []
        for index in range(self.inventory_list_layout.count()):
            widget = self.inventory_list_layout.itemAt(index).widget()
            if widget is not None and hasattr(widget, "item"):
                rows.append(widget)
        dragged = next((row for row in rows if row.item.id == item_id), None)
        if dragged is None:
            return
        local_pos = self.inventory_list_widget.mapFromGlobal(global_pos)
        remaining = [row for row in rows if row is not dragged]
        insert_at = len(remaining)
        for index, row in enumerate(remaining):
            if local_pos.y() < row.geometry().center().y():
                insert_at = index
                break
        ordered_ids = [row.item.id for row in remaining]
        ordered_ids.insert(insert_at, item_id)
        if InventorySystem.reorder_items(self.character, ordered_ids):
            self.mark_dirty(auto_save=True)
            self.refresh_inventory()

    def improvement_drag_ids_for_row(self, row):
        if isinstance(row, HeightenedAbilityRow):
            return []
        if hasattr(row, "skilled_improvements"):
            return [improvement.id for improvement in row.skilled_improvements]
        improvement = getattr(row, "improvement", None)
        if improvement is None:
            return []
        if str(getattr(improvement, "id", "")).startswith("free_heightened_paid_"):
            return []
        return [improvement.id]

    def enable_improvement_long_press_reorder(self, row):
        improvement_ids = self.improvement_drag_ids_for_row(row)

        if not improvement_ids:
            return

        controller = LongPressReorderFilter(
            row,
            lambda global_pos, ids=tuple(improvement_ids):
                self.reorder_improvements_from_drop(list(ids), global_pos),
            row,
        )

        row._long_press_reorder_controller = controller

    def reorder_improvements_from_drop(self, dragged_ids, global_pos):
        if self.block_if_readonly():
            return
        groups = []
        for index in range(self.improvement_list_layout.count()):
            widget = self.improvement_list_layout.itemAt(index).widget()
            if widget is None:
                continue
            ids = self.improvement_drag_ids_for_row(widget)
            if ids:
                groups.append((widget, ids))
        dragged_set = set(dragged_ids)
        remaining = [pair for pair in groups if not (set(pair[1]) & dragged_set)]
        local_pos = self.improvement_list_widget.mapFromGlobal(global_pos)
        insert_at = len(remaining)
        if remaining:
            nearest_index = min(
                range(len(remaining)),
                key=lambda index: (
                    (remaining[index][0].geometry().center().x() - local_pos.x()) ** 2
                    + (remaining[index][0].geometry().center().y() - local_pos.y()) ** 2
                ),
            )
            nearest_widget = remaining[nearest_index][0]
            insert_at = nearest_index
            if local_pos.y() >= nearest_widget.geometry().center().y():
                insert_at += 1
        reordered_groups = [ids for _, ids in remaining]
        reordered_groups.insert(insert_at, list(dragged_ids))
        ordered_ids = [
            improvement_id
            for group in reordered_groups
            for improvement_id in group
        ]
        if ImprovementSystem.reorder_improvements(self.character, ordered_ids):
            self.mark_dirty(auto_save=True)
            self.refresh_improvements()


    def refresh_inventory(self):
        # Build the real rows using the working InventoryMixin.
        InventoryMixin.refresh_inventory(
            self
        )

        for index in range(
            self.inventory_list_layout.count()
        ):
            item = (
                self.inventory_list_layout
                .itemAt(index)
            )

            row = item.widget()

            if row is not None:
                self.style_redesign_inventory_row(
                    row
                )
                self.enable_inventory_long_press_reorder(
                    row
                )

        QTimer.singleShot(
            0,
            self.refresh_inventory_scroll_geometry,
        )

        QTimer.singleShot(
            30,
            self.refresh_inventory_scroll_geometry,
        )


    # ============================================================
    # CHARACTER / NOTES PAGE NAVIGATION
    # ============================================================

    def build_notes_board(self, outer_layout):
        """
        The working NotesMixin still creates the actual notes controls,
        cards, editing behavior, deletion behavior, and autosave behavior.

        In the redesign, however, Notes are a separate VIEW rather than
        something that expands underneath the character sheet.

        The always-visible bottom bar switches between:
            Character | Notes
        """

        self.redesign_content_layout = outer_layout

        NotesMixin.build_notes_board(
            self,
            outer_layout,
        )

        # --------------------------------------------------------
        # Dedicated Notes page styling
        # --------------------------------------------------------

        self.notes_frame.setObjectName(
            "RedesignNotesPage"
        )

        set_themed_stylesheet(
            self.notes_frame,
            """
            QFrame#RedesignNotesPage {
                background-color: #fffdf7;
                border: 2px solid #cdaa63;
                border-radius: 14px;
            }
            """
        )

        notes_layout = self.notes_frame.layout()

        notes_layout.setContentsMargins(
            14, 10, 14, 12
        )

        notes_layout.setSpacing(
            8
        )

        # Keep all Notes content anchored to the TOP of the dedicated
        # page instead of letting the grid consume/distribute the extra
        # vertical space.
        notes_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.notes_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )

        # Existing first layout is the Notes header.
        header_layout = (
            notes_layout
            .itemAt(0)
            .layout()
        )

        # Style the existing Notes title.
        for label in self.notes_frame.findChildren(
            QLabel
        ):
            if label.text().strip() == "Notes":
                set_themed_stylesheet(
                    label,
                    """
                    QLabel {
                        background: transparent;
                        border: none;
                        font-family: Georgia;
                        font-size: 24px;
                        font-weight: 900;
                        color: #25190f;
                        padding: 0px;
                        margin: 0px;
                    }
                    """
                )

        # The page no longer needs its old collapse arrow.
        self.close_notes_btn.hide()

        # Move Add Note into the Notes header.
        old_add_layout = None

        for index in range(
            notes_layout.count()
        ):
            item = notes_layout.itemAt(
                index
            )

            child_layout = item.layout()

            if child_layout is None:
                continue

            for child_index in range(
                child_layout.count()
            ):
                child_item = child_layout.itemAt(
                    child_index
                )

                if child_item.widget() is self.add_note_btn:
                    old_add_layout = child_layout
                    break

            if old_add_layout is not None:
                break

        if old_add_layout is not None:
            old_add_layout.removeWidget(
                self.add_note_btn
            )

        self.add_note_btn.setText(
            "+  Add Note"
        )

        self.add_note_btn.setFixedSize(
            105,
            32,
        )

        set_themed_stylesheet(
            self.add_note_btn,
            BUTTON_PRIMARY_QSS,
        )

        if header_layout is not None:
            self.notes_header_icon = FantasyIcon(
                "notes",
                accent="#a87824",
                size=(
                    36
                    if os.path.basename(find_note_icon_path() or "").lower()
                    == "custom.svg"
                    else 30
                ),
            )

            header_layout.insertWidget(
                0,
                self.notes_header_icon,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

            header_layout.addWidget(
                self.add_note_btn,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        # --------------------------------------------------------
        # Reuse notes_reopen_row as the PERMANENT bottom nav bar.
        # --------------------------------------------------------

        self.notes_reopen_row.setFixedHeight(
            38
        )

        nav_layout = (
            self.notes_reopen_row.layout()
        )

        while nav_layout.count():
            item = nav_layout.takeAt(
                0
            )

            widget = item.widget()

            if widget is not None:
                widget.setParent(
                    None
                )

        nav_layout.setContentsMargins(
            14, 4, 14, 4
        )

        nav_layout.setSpacing(
            8
        )

        self.character_page_btn = QPushButton(
            "Character"
        )

        self.notes_page_btn = QPushButton(
            "Notes"
        )

        for button in (
            self.character_page_btn,
            self.notes_page_btn,
        ):
            button.setFixedHeight(
                32
            )

            button.setMinimumWidth(
                175
            )

            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

        self.character_page_btn.clicked.connect(
            self.show_character_page
        )

        self.notes_page_btn.clicked.connect(
            self.open_notes_board
        )

        nav_layout.addWidget(
            self.character_page_btn,
            1,
        )

        nav_layout.addWidget(
            self.notes_page_btn,
            1,
        )

        self.current_redesign_page = (
            "character"
        )

        # Unlike the old reopen-row behavior, navigation is ALWAYS shown.
        self.notes_reopen_row.show()

        # Notes page starts hidden.
        self.notes_frame.hide()

        self.update_page_navigation_styles()


    def move_page_navigation_to_window_bottom(self):
        """
        Fixed Character / Notes overlay directly under Inventory.
        It consumes no layout height, so the left and center columns
        can extend farther down.
        """

        if not hasattr(self, "notes_reopen_row"):
            return

        content_layout = getattr(self, "redesign_content_layout", None)
        if content_layout is not None:
            content_layout.removeWidget(self.notes_reopen_row)

        window_layout = self.layout()
        if window_layout is not None:
            window_layout.removeWidget(self.notes_reopen_row)

        viewport = self.scroll.viewport() if hasattr(self, "scroll") else self

        self.notes_reopen_row.setParent(viewport)
        self.notes_reopen_row.setFixedHeight(38)
        self.notes_reopen_row.show()
        self.notes_reopen_row.raise_()

        QTimer.singleShot(
            0,
            self.sync_bottom_navigation_to_right_column,
        )


    @qt_lifecycle_safe
    def sync_bottom_navigation_to_right_column(self):
        if not hasattr(self, "notes_reopen_row"):
            return

        if not hasattr(self, "inventory_frame"):
            return

        viewport = self.scroll.viewport() if hasattr(self, "scroll") else self

        nav_width = max(1, self.inventory_frame.width())
        nav_height = self.notes_reopen_row.height()

        self.notes_reopen_row.setFixedWidth(nav_width)

        nav_layout = self.notes_reopen_row.layout()

        if nav_layout is not None:
            nav_layout.setContentsMargins(3, 3, 3, 3)
            nav_layout.setSpacing(5)

            if hasattr(self, "character_page_btn"):
                self.character_page_btn.setMinimumWidth(0)
                self.character_page_btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )

            if hasattr(self, "notes_page_btn"):
                self.notes_page_btn.setMinimumWidth(0)
                self.notes_page_btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )

        inventory_pos = self.inventory_frame.mapTo(
            viewport,
            self.inventory_frame.rect().topLeft(),
        )

        x = inventory_pos.x()
        y = viewport.height() - nav_height - 2

        self.notes_reopen_row.move(
            x,
            max(0, y),
        )

        self.notes_reopen_row.raise_()


    def update_page_layout_stretch(self):
        """
        Character and Notes use the same scroll viewport.

        Character page:
            main three-column layout gets the available space.

        Notes page:
            the empty hidden character layout must NOT keep a stretch factor;
            the Notes page gets the available space instead.
        """

        layout = getattr(
            self,
            "redesign_content_layout",
            None,
        )

        if layout is None:
            return

        main_index = -1
        notes_index = layout.indexOf(
            self.notes_frame
        )

        for index in range(
            layout.count()
        ):
            item = layout.itemAt(
                index
            )

            if item.layout() is self.main_layout:
                main_index = index
                break

        page = getattr(
            self,
            "current_redesign_page",
            "character",
        )

        if main_index >= 0:
            layout.setStretch(
                main_index,
                1 if page == "character" else 0,
            )

        if notes_index >= 0:
            layout.setStretch(
                notes_index,
                1 if page == "notes" else 0,
            )


    def update_page_navigation_styles(self):
        active_style = NAV_ACTIVE_QSS
        inactive_style = NAV_INACTIVE_QSS

        if (
            getattr(
                self,
                "current_redesign_page",
                "character",
            )
            == "notes"
        ):
            set_themed_stylesheet(
                self.character_page_btn,
                inactive_style,
            )

            set_themed_stylesheet(
                self.notes_page_btn,
                active_style,
            )

        else:
            set_themed_stylesheet(
                self.character_page_btn,
                active_style,
            )

            set_themed_stylesheet(
                self.notes_page_btn,
                inactive_style,
            )


    def set_character_page_visible(
        self,
        visible,
    ):
        for widget_name in (
            "redesign_left_frame",
            "redesign_center_widget",
            "inventory_frame",
        ):
            widget = getattr(
                self,
                widget_name,
                None,
            )

            if widget is not None:
                widget.setVisible(
                    visible
                )


    def show_character_page(self):
        """
        UI-only navigation. Does NOT mark the character dirty.
        """

        if (
            getattr(
                self,
                "current_redesign_page",
                "character",
            )
            == "character"
        ):
            return

        self.current_redesign_page = (
            "character"
        )

        self.notes_board_visible = False

        self.notes_frame.hide()

        self.set_character_page_visible(
            True
        )

        self.notes_reopen_row.show()

        self.update_page_layout_stretch()
        self.update_page_navigation_styles()

        if hasattr(
            self,
            "scroll",
        ):
            self.scroll.verticalScrollBar().setValue(
                0
            )

        self.lock_character_sheet_anchor()

        QTimer.singleShot(
            0,
            self.apply_redesign_height_to_viewport,
        )
        QTimer.singleShot(
            0,
            self.lock_character_sheet_anchor,
        )


    def show_notes_page(self):
        """
        Switch to the dedicated Notes view.
        """

        self.current_redesign_page = (
            "notes"
        )

        self.notes_board_visible = True

        self.set_character_page_visible(
            False
        )

        self.notes_frame.show()

        self.notes_reopen_row.show()

        self.update_page_layout_stretch()
        self.update_page_navigation_styles()

        if hasattr(
            self,
            "scroll",
        ):
            self.scroll.verticalScrollBar().setValue(
                0
            )

        QTimer.singleShot(
            0,
            self.apply_redesign_height_to_viewport,
        )


    def _current_note_card_signature(self):
        """Identity and visible data, not just a count of notes."""
        return (
            id(self.character),
            self.calculate_note_columns(),
            tuple(
                (
                    id(note),
                    note.id,
                    note.title,
                    note.text,
                    note.color,
                    note.expanded,
                    note.linked_improvement_id,
                )
                for note in self.character.notes.list_of_notes
            ),
        )

    def _visible_note_cards_are_current(self):
        """Never reuse an empty, stale, deleted or different character's grid."""
        notes = self.character.notes.list_of_notes
        if not notes or getattr(self, "_rendered_note_signature", None) != (
            self._current_note_card_signature()
        ):
            return False
        layout = self.notes_grid_layout
        cards = self._note_grid_cards()
        if len(cards) != len(notes):
            return False
        try:
            for card in cards:
                if not isinstance(card, NoteCard) or card.note not in notes:
                    return False
                # Access the Qt object; destroyed C++ widgets raise RuntimeError.
                if not card.objectName():
                    return False
        except (RuntimeError, ReferenceError):
            return False
        return True

    def _note_grid_cards(self):
        cards = []
        for column in range(self.notes_grid_layout.count()):
            item = self.notes_grid_layout.itemAt(column)
            stack = item.layout() if item is not None else None
            if stack is None:
                if item is not None and isinstance(item.widget(), NoteCard):
                    cards.append(item.widget())
                continue
            for index in range(stack.count()):
                entry = stack.itemAt(index)
                if entry is not None and isinstance(entry.widget(), NoteCard):
                    cards.append(entry.widget())
        return cards

    def open_notes_board(self):
        """
        Preserve the old Notes behavior:
        - opening Notes does not mark dirty;
        - if notes already exist, simply show them;
        - if there are no notes, create the first blank note.

        Then display Notes as the dedicated Notes page.
        """

        if (
            getattr(
                self,
                "current_redesign_page",
                "character",
            )
            == "notes"
        ):
            return

        if self.block_if_readonly():
            return

        # Always validate current data before reusing any painted widgets.
        # The previous optimization merely checked whether notes EXISTED;
        # after loading another character this incorrectly showed an empty
        # grid. We require every widget to belong to the current character,
        # contain the exact current note object, and match its last rendering.
        self.ensure_character_notes()
        if self._visible_note_cards_are_current():
            self.show_notes_page()
            return

        # New/changed characters, changed note text, different column count,
        # and empty boards use the original, fully working refresh path.
        NotesMixin.open_notes_board(self)
        self.show_notes_page()


    def close_notes_board(self):
        """
        The old whole-board collapse action now means:
        return to the Character page.
        """

        self.show_character_page()


    def toggle_notes_board(self):
        if (
            getattr(
                self,
                "current_redesign_page",
                "character",
            )
            == "notes"
        ):
            self.show_character_page()
        else:
            self.open_notes_board()


    def style_redesign_note_card(self, card):
        """
        Give every note a genuinely colored body in Light mode and a
        readable, color-preserving card in Dark mode.
        """

        dark = (
            ui_theme_module.CURRENT_THEME
            == "dark"
        )

        # Use the same theme projection as the Notes models, sidebar previews,
        # and the Animal Buddy card.  Keep note.color itself unchanged.
        color_name = getattr(card.note, "color", "yellow")
        outer_color, body_color = note_colors_for_theme(color_name)
        if dark:
            text_color = "#f2eee7"
            border_color = "#8e7446"
            muted_color = "#d6b66f"
        else:
            text_color = "#25190f"
            border_color = "#c79a3b"
            muted_color = "#6c5428"

        set_themed_stylesheet(
            card,
            f"""
            QFrame#NoteCard {{
                background-color: {outer_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            """
        )

        title_widget = getattr(
            card,
            "title_edit",
            None,
        )

        if title_widget is not None:
            set_themed_stylesheet(
                title_widget,
                f"""
                QLineEdit {{
                    background: transparent;
                    border: none;
                    color: {text_color};
                    font-family: Georgia;
                    font-size: 14px;
                    font-weight: 900;
                    padding: 0px 2px;
                    margin: 0px;
                    selection-background-color: rgba(255, 255, 255, 70);
                }}

                QLineEdit:hover {{
                    background-color: rgba(255, 255, 255, 28);
                    border-radius: 4px;
                }}

                QLineEdit:focus {{
                    background-color: rgba(255, 255, 255, 42);
                    border: 1px solid {border_color};
                    border-radius: 4px;
                }}
                """
            )

        body_widget = getattr(
            card,
            "text_edit",
            None,
        )

        if body_widget is not None:
            set_themed_stylesheet(
                body_widget,
                f"""
                QTextEdit, QLabel {{
                    background-color: {body_color};
                    border: 1px solid {border_color};
                    border-radius: 9px;
                    color: {text_color};
                    font-family: Georgia;
                    font-size: 12px;
                    padding: 8px;
                }}

                QTextEdit:focus {{
                    border: 1px solid {muted_color};
                    background-color: {body_color};
                }}
                """
            )

        if getattr(card, "is_system_note", False) and isinstance(body_widget, QLabel):
            body_widget.setStyleSheet(body_widget.styleSheet().replace("padding: 8px;", "padding: 4px 8px;"))
        options_btn = getattr(card, "options_btn", None)
        if options_btn is not None:
            set_themed_stylesheet(options_btn, f"QPushButton {{background: transparent; border: none; color: {text_color}; font-size: 20px; padding: 0;}} QPushButton:hover {{background: {body_color}; border-radius: 4px;}}")

        arrow_btn = getattr(
            card,
            "arrow_btn",
            None,
        )

        if arrow_btn is not None:
            set_themed_stylesheet(
                arrow_btn,
                f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {muted_color};
                    font-size: 15px;
                    font-weight: 900;
                    padding: 0px;
                    margin: 0px;
                }}

                QPushButton:hover {{
                    color: {text_color};
                }}
                """
            )

        link_btn = getattr(
            card,
            "link_btn",
            None,
        )

        if link_btn is not None:
            set_themed_stylesheet(
                link_btn,
                f"""
                QPushButton {{
                    background-color: {body_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    color: {text_color};
                    font-family: Georgia;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 1px 5px;
                    margin: 0px;
                }}

                QPushButton:hover {{
                    background-color: {outer_color};
                    border-color: {muted_color};
                }}
                """,
            )


        color_btn = getattr(
            card,
            "color_btn",
            None,
        )

        if color_btn is not None:
            set_themed_stylesheet(
                color_btn,
                f"""
                QPushButton {{
                    background-color: {outer_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    color: {text_color};
                    font-size: 9px;
                    font-weight: 900;
                    padding: 0px;
                    margin: 0px;
                }}

                QPushButton:hover {{
                    background-color: {body_color};
                    border-color: {muted_color};
                }}
                """
            )

        # Notes-page controls use one final style for every note type.
        # Animal Buddy is rendered through an embedded AnimalBuddyNoteCard,
        # so styling only the outer NoteCard leaves its controls on the older
        # blue-border path in Dark mode.  Apply the exact same final control
        # rules to both standard cards and that embedded managed-note card.
        pin_qss = """
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

        pin_btn = getattr(card, "pin_btn", None)
        if pin_btn is not None:
            set_themed_stylesheet(pin_btn, pin_qss)

        animal_buddy_card = getattr(card, "animal_buddy_card", None)
        if animal_buddy_card is not None:
            buddy_color_btn = getattr(animal_buddy_card, "color_btn", None)
            if buddy_color_btn is not None:
                set_themed_stylesheet(
                    buddy_color_btn,
                    f"""
                    QPushButton {{
                        background-color: {outer_color};
                        border: 1px solid {border_color};
                        border-radius: 10px;
                        color: {text_color};
                        font-size: 9px;
                        font-weight: 900;
                        padding: 0px;
                        margin: 0px;
                    }}

                    QPushButton:hover {{
                        background-color: {body_color};
                        border-color: {muted_color};
                    }}
                    """
                )

            buddy_pin_btn = getattr(animal_buddy_card, "pin_btn", None)
            if buddy_pin_btn is not None:
                set_themed_stylesheet(buddy_pin_btn, pin_qss)

        delete_btn = getattr(
            card,
            "delete_btn",
            None,
        )

        if delete_btn is not None:
            set_themed_stylesheet(
                delete_btn,
                f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: {text_color};
                    padding: 0px;
                    margin: 0px;
                }}

                QPushButton:hover {{
                    color: #ff6b6b;
                }}
                """
            )

    def resize_redesign_note_card(self, card):
        """
        Resize a styled NoteCard to its full text instead of clipping it.

        refresh_notes() can rebuild all NoteCards while a short delayed
        resize from the previous build is still queued. If that happens,
        the old Python wrapper may point to an already deleted Qt widget.
        A stale delayed resize is harmless and should simply do nothing.
        """

        try:
            if card is None:
                return

            # Animal Buddy uses a NoteCard host with its own layout and
            # AnimalBuddyPanel, and returns before outer_layout is created.
            # Its embedded card calculates its own height.
            if getattr(card, "animal_buddy_card", None) is not None:
                layout = card.layout()
                if layout is not None:
                    layout.invalidate()
                    layout.activate()
                card.adjustSize()
                card.updateGeometry()
                return

            if not getattr(
                card.note,
                "expanded",
                False,
            ):
                card.updateGeometry()
                return

            body = getattr(
                card,
                "text_edit",
                None,
            )

            if body is None:
                return

            if isinstance(
                body,
                QTextEdit,
            ):
                body.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )

                body.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )

                width = max(
                    80,
                    card.width() - 34,
                )

                body.setFixedWidth(
                    width
                )

                document = body.document()

                document.setTextWidth(
                    max(
                        1,
                        width - 18,
                    )
                )

                required = int(
                    document
                    .documentLayout()
                    .documentSize()
                    .height()
                    + 0.999
                )

                body.setFixedHeight(
                    max(
                        42,
                        required + 20,
                    )
                )

            elif isinstance(
                body,
                QLabel,
            ):
                # Match NoteCard's QTextDocument-based system-note sizing.
                # Two different measurement methods were producing a second
                # height jump when NoteCard's queued resize ran.
                card.resize_text_edit()

            layout = card.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            card.adjustSize()
            card.updateGeometry()

        except (
            RuntimeError,
            ReferenceError,
        ):
            return


    def refresh_notes(self):
        """
        Let the working NotesMixin rebuild all NoteCards, but override its
        old show/hide behavior afterwards so the bottom navigation is
        permanent and Notes remain a separate page.
        """

        # NotesMixin returns without building cards while the board is
        # closed. Never stamp an existing (possibly stale) grid as current
        # in that case, even if its card COUNT happens to match.
        rebuilt_cards = bool(self.notes_board_visible)
        self._rendered_note_signature = None
        NotesMixin.refresh_notes(
            self
        )

        # The working refresh hides notes_reopen_row when Notes are open.
        # In the redesign this row IS the permanent navigation bar.
        self.notes_reopen_row.show()

        if (
            getattr(
                self,
                "current_redesign_page",
                "character",
            )
            == "notes"
        ):
            self.notes_board_visible = True

            self.set_character_page_visible(
                False
            )

            self.notes_frame.show()

        else:
            self.notes_board_visible = False

            self.notes_frame.hide()

            self.set_character_page_visible(
                True
            )

        # Keep the note grid compact at the top of the page.
        notes = self.character.notes.list_of_notes
        columns = max(
            1,
            self.calculate_note_columns(),
        )

        populated_rows = (
            (len(notes) + columns - 1) // columns
            if notes
            else 0
        )

        for row_index in range(
            populated_rows
        ):
            self.notes_grid_layout.setRowStretch(
                row_index,
                0,
            )

        # Preserve each note's chosen paper color, just replace the
        for card in self._note_grid_cards():
            if isinstance(card, NoteCard):
                self.style_redesign_note_card(
                    card
                )
                self.resize_redesign_note_card(
                    card
                )

                # Do not resize again 25 ms AFTER the page has appeared.
                # This delayed size change caused a visible loading flash.

        self.no_notes_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )

        self.update_page_layout_stretch()
        self.update_page_navigation_styles()

        # Only mark this grid reusable after the complete, styled rebuild.
        # Navigation can NEVER reuse a grid from a previous character.
        self._rendered_note_signature = (
            self._current_note_card_signature()
            if rebuilt_cards and len(self._note_grid_cards()) == len(notes) and notes
            else None
        )

        QTimer.singleShot(
            0,
            self.keep_sheet_horizontally_locked,
        )
        QTimer.singleShot(
            0,
            self.keep_sheet_vertically_locked,
        )

    def calculate_note_columns(self):
        """
        Notes now have the full application width, so allow more cards
        per row when the window has room.
        """

        width = self.width()

        if width >= 1550:
            return 5

        if width >= 1250:
            return 4

        if width >= 950:
            return 3

        if width >= 650:
            return 2

        return 1


    # ============================================================
    # RESPONSIVE REDESIGN HEIGHT
    # ============================================================

    @qt_lifecycle_safe
    def apply_redesign_height_to_viewport(self):
        """
        Fit the three main redesign columns into the ACTUAL visible
        QScrollArea viewport.

        This avoids tuning the sheet to one resolution/DPI scale.
        Notes may still make the page taller when opened, but the normal
        closed-notes character sheet should fit vertically.
        """

        if not hasattr(self, "scroll"):
            return

        if not hasattr(self, "redesign_left_frame"):
            return

        viewport_height = self.scroll.viewport().height()

        if viewport_height <= 1:
            return

        top_height = 0

        if hasattr(self, "redesign_top_frame"):
            top_height = max(
                self.redesign_top_frame.height(),
                self.redesign_top_frame.sizeHint().height(),
            )

        # Character / Notes is an overlay and consumes no layout height.
        bottom_height = 0

        # Keep a small breathing gap so the bottom border never touches
        # or slips underneath the viewport edge.
        safety_margin = 1

        sheet_height = (
            viewport_height
            - top_height
            - bottom_height
            - safety_margin
        )

        # Do not let a very small manually resized window destroy the layout.
        sheet_height = max(
            500,
            sheet_height,
        )

        # --------------------------------------------------------
        # All three main columns end at exactly the same place.
        # --------------------------------------------------------

        self.redesign_left_frame.setFixedHeight(
            sheet_height
        )

        self.redesign_center_widget.setFixedHeight(
            sheet_height
        )

        nav_height = (
            self.notes_reopen_row.height()
            if hasattr(self, "notes_reopen_row")
            else 38
        )

        self.inventory_frame.setFixedHeight(
            max(
                300,
                sheet_height
                - nav_height
                - 6,
            )
        )

        if hasattr(
            self,
            "notes_frame",
        ):
            # Notes occupy a separate full page. This is a MINIMUM only:
            # lots of notes may make the page taller and use the outer
            # application scrollbar.
            self.notes_frame.setMinimumHeight(
                sheet_height
            )

        # --------------------------------------------------------
        # Fit portrait + identity + six abilities inside left panel.
        # --------------------------------------------------------

        # Measure the REAL ability rows instead of assuming 48 px.
        # RedesignStatRow is currently 56 px tall; using the old 48 px
        # estimate made the last ability row extend below the left panel.
        ability_rows = list(self.stat_rows.values())

        ability_height = sum(
            row.height() if row.height() > 0 else row.sizeHint().height()
            for row in ability_rows
        )

        ability_gaps = max(
            0,
            len(ability_rows) - 1,
        ) * self.stats_col.spacing()

        left_layout = self.redesign_left_frame.layout()
        left_margins = left_layout.contentsMargins()

        non_portrait_height = (
            ability_height
            + ability_gaps
            + left_margins.top()
            + left_margins.bottom()
            + left_layout.spacing()
        )

        portrait_height = (
            sheet_height
            - non_portrait_height
        )

        # Do not cap the portrait at 330px: on tall windows that left a
        # blank area below Strength. The portrait consumes all remaining
        # height; the six 56px ability rows keep their fixed geometry and
        # finish at the left panel's bottom content margin.
        portrait_height = max(
            120,
            portrait_height,
        )

        portrait_size_changed = (
            self.image_frame.height() != portrait_height
        )
        self.image_frame.setFixedHeight(
            portrait_height
        )

        # Portrait pixmaps are cropped at their displayed QLabel size.
        # Re-crop after Qt applies the larger frame geometry, otherwise a
        # loaded image may keep its old size inside the expanded portrait.
        # A single-shot timer coalesces rapid window-resize events.
        if portrait_size_changed and self.character.image.current_image():
            timer = getattr(self, "_portrait_resize_refresh_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self.refresh_character_image_after_layout)
                self._portrait_resize_refresh_timer = timer
            timer.start(60)

        QTimer.singleShot(
            0,
            self.position_portrait_controls,
        )

        # --------------------------------------------------------
        # Improvements use whatever remains below HP/AT.
        # --------------------------------------------------------

        resource_height = int(
            self.redesign_resources_frame.sizeHint().height(),
        )

        improvements_height = (
            sheet_height
            - resource_height
            - 4
        )

        self.improvements_frame.setFixedHeight(
            max(
                220,
                improvements_height,
            )
        )

        # Existing inventory/improvement geometry functions calculate
        # internal scroller heights from their frame height.
        if hasattr(
            self,
            "refresh_inventory_scroll_geometry",
        ):
            QTimer.singleShot(
                0,
                self.refresh_inventory_scroll_geometry,
            )

        if hasattr(
            self,
            "refresh_improvement_scroll_geometry",
        ):
            QTimer.singleShot(
                0,
                self.refresh_improvement_scroll_geometry,
            )

        QTimer.singleShot(
            0,
            self.sync_bottom_navigation_to_right_column,
        )


    def resizeEvent(self, event):
        super().resizeEvent(event)

        # Wait until Qt finishes the resize/layout pass before measuring
        # the viewport.
        QTimer.singleShot(
            0,
            self.apply_redesign_height_to_viewport,
        )

        QTimer.singleShot(
            0,
            self.lock_character_sheet_anchor,
        )

        QTimer.singleShot(
            0,
            self.position_portrait_controls,
        )


    # ============================================================
    # UPDATE SYSTEM
    # ============================================================

    def initialize_update_system(self):
        """
        Called only by the real application startup, not by test windows.
        """
        if not hasattr(
            self,
            "_available_update_release",
        ):
            self._available_update_release = None

        if getattr(
            self,
            "_did_update_manager",
            None,
        ) is None:
            self._did_update_manager = (
                DIDUpdateManager(
                    self
                )
            )

        if not hasattr(
            self,
            "_pending_update_installer_path",
        ):
            self._pending_update_installer_path = None

        app = QApplication.instance()

        if (
            app is not None
            and not getattr(
                self,
                "_did_update_quit_hook_installed",
                False,
            )
        ):
            app.aboutToQuit.connect(
                self.launch_pending_update_installer
            )
            self._did_update_quit_hook_installed = True

    def check_for_updates_on_startup(self):
        """
        Delay the quiet startup check while another modal startup dialog
        (welcome/recovery/etc.) is still open.
        """
        modal = QApplication.activeModalWidget()

        if (
            modal is not None
            and modal is not self
        ):
            QTimer.singleShot(
                2000,
                self.check_for_updates_on_startup,
            )
            return

        self.initialize_update_system()

        self._did_update_manager.check_for_updates(
            silent=True
        )

    def check_for_updates_from_ui(self):
        self.initialize_update_system()

        if self._did_update_manager.available_update:
            self._did_update_manager.offer_available_update()
            return

        # Kept as a safe fallback for callers outside the Tools menu.
        self._did_update_manager.check_for_updates(
            silent=False
        )

    def launch_pending_update_installer(self):
        """
        aboutToQuit handler.

        A detached PowerShell helper waits for this exact DID process to end,
        waits until the installed EXE is genuinely unlocked, runs Inno Setup
        silently, waits for it to finish, then reopens DID Character Sheet.
        """
        installer_path = getattr(
            self,
            "_pending_update_installer_path",
            None,
        )

        if (
            not installer_path
            or not os.path.isfile(installer_path)
        ):
            return

        self._pending_update_installer_path = None

        process_id = os.getpid()

        installed_exe = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs",
            "DID Character Sheet",
            "DID Character Sheet.exe",
        )

        escaped_installer = installer_path.replace("'", "''")
        escaped_exe = installed_exe.replace("'", "''")

        command = (
            "$ErrorActionPreference='SilentlyContinue'; "
            f"Wait-Process -Id {process_id}; "
            f"$exe='{escaped_exe}'; "
            "$deadline=(Get-Date).AddSeconds(45); "
            "while ((Get-Date) -lt $deadline) { "
            "  $unlocked=$false; "
            "  if (-not (Test-Path -LiteralPath $exe)) { "
            "    $unlocked=$true; "
            "  } else { "
            "    try { "
            "      $s=[System.IO.File]::Open("
            "$exe,"
            "[System.IO.FileMode]::Open,"
            "[System.IO.FileAccess]::ReadWrite,"
            "[System.IO.FileShare]::None"
            "); "
            "      $s.Close(); "
            "      $s.Dispose(); "
            "      $unlocked=$true; "
            "    } catch { "
            "      $unlocked=$false; "
            "    } "
            "  } "
            "  if ($unlocked) { break } "
            "  Start-Sleep -Milliseconds 300; "
            "} "
            "Start-Sleep -Milliseconds 500; "
            f"$installer='{escaped_installer}'; "
            "$setup=Start-Process "
            "-FilePath $installer "
            "-ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-' "
            "-Wait -PassThru; "
            "if ($setup -and $setup.ExitCode -eq 0 -and "
            "(Test-Path -LiteralPath $exe)) { "
            "  Start-Process -FilePath $exe; "
            "} "
            "Start-Sleep -Milliseconds 500; "
            "Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue;"
        )

        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

        launch_environment = os.environ.copy()
        launch_environment[
            "PYINSTALLER_RESET_ENVIRONMENT"
        ] = "1"

        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-WindowStyle",
                    "Hidden",
                    "-Command",
                    command,
                ],
                creationflags=creation_flags,
                close_fds=True,
                env=launch_environment,
            )

        except Exception as error:
            try:
                with open(
                    "crash_log.txt",
                    "a",
                    encoding="utf-8",
                ) as log:
                    log.write("Update installer launch failed:\n")
                    log.write(f"{error}\n")
            except Exception:
                pass

    # ============================================================
    # WINDOW
    # ============================================================

    def __init__(self):
        super().__init__()

        install_fantasy_runtime_ui()

        # Use almost the entire application window.
        root_layout = self.layout()

        if root_layout is not None:
            root_layout.setContentsMargins(
                2, 2, 2, 2
            )

            root_layout.setSpacing(
                2
            )

        # Keep the scroll content itself flush with the viewport.
        if hasattr(
            self,
            "content_widget",
        ):
            content_layout = (
                self.content_widget.layout()
            )

            if content_layout is not None:
                content_layout.setContentsMargins(
                    2, 0, 2, 0
                )

                content_layout.setSpacing(
                    2
                )

        # Reduce space between the three character columns.
        if hasattr(
            self,
            "main_layout",
        ):
            self.main_layout.setContentsMargins(
                0, 0, 0, 0
            )

            self.main_layout.setSpacing(
                4
            )

        self.setWindowTitle(
            f"DID Character Sheet {APP_VERSION}[*]"
        )

        # MainWindow creates the scroll area and all UI first.
        # Measure it only after Qt performs the initial layout pass.
        QTimer.singleShot(
            0,
            self.apply_redesign_height_to_viewport,
        )

        # MainWindow has now finished assembling its own layout, so the
        # navigation can safely be moved below the scroll area.
        self.move_page_navigation_to_window_bottom()
        self.update_page_layout_stretch()

        QTimer.singleShot(
            0,
            self.apply_redesign_height_to_viewport,
        )

        QTimer.singleShot(
            100,
            self.apply_redesign_height_to_viewport,
        )

        QTimer.singleShot(
            0,
            self.update_history_button_state,
        )


if __name__ == "__main__":
    # The one-file Windows installer has no standalone python.exe. Dashboard
    # subprocesses restart this same executable in a dedicated, headless mode.
    # Dispatch before constructing Qt widgets or touching character data.
    if len(sys.argv) > 1 and sys.argv[1] == "--did-dashboard-server":
        import dashboard_server
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        dashboard_server.main()
        sys.exit(0)
    try:
        app = QApplication(sys.argv)

        # Explicitly set the icon for the running Qt application/window.
        # PyInstaller also embeds the same icon into the EXE, but setting it
        # here guarantees that the title bar and taskbar use the DID icon too.
        app_icon_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)
            ),
            "app_icon.ico",
        )

        if os.path.exists(
            app_icon_path
        ):
            app.setWindowIcon(
                QIcon(
                    app_icon_path
                )
            )

        install_fantasy_runtime_ui()

        startup_settings = QSettings(
            "DID",
            "CharacterSheet",
        )
        startup_theme = startup_settings.value(
            "theme",
            "light",
            type=str,
        )

        if startup_theme not in THEME:
            startup_theme = "light"

        set_runtime_theme(
            startup_theme
        )
        app.setPalette(
            build_application_palette(
                startup_theme
            )
        )

        win = MainWindow()
        win.initialize_update_system()
        geometry = startup_settings.value("window_geometry")
        if geometry:
            win.restoreGeometry(geometry)
        if startup_settings.value("window_maximized", True, type=bool):
            win.showMaximized()
        else:
            win.show()

        # Quietly check GitHub after the normal startup UI has settled.
        QTimer.singleShot(
            5000,
            win.check_for_updates_on_startup,
        )

        sys.exit(app.exec())

    except Exception:
        import traceback

        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(traceback.format_exc())
            f.write("\n\n")

        raise
