"""DID Character Sheet - CURRENT frontend_2_8 Redesign/UI Torture Test.

Updated for the current light-fantasy redesign, Creation Rules, and guided tutorial.

Run from this test folder (app_path.txt supplies the app path):
    python automated_redesign_ui_torture_test.py

Writes automated_redesign_ui_torture_report.json.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys, json, inspect, importlib, tempfile, traceback
from pathlib import Path
from uuid import uuid4

# Application and test files deliberately live in different directories.
from test_support import app_dir, HERE as TEST_DIR
APP_DIR = app_dir()
REPORT_DIR = Path(os.environ.get("DID_TEST_REPORT_DIR", str(TEST_DIR / "reports"))).resolve()
REPORT_DIR.mkdir(parents=True, exist_ok=True)
HERE = APP_DIR
sys.path.insert(0, str(HERE)) if str(HERE) not in sys.path else None

from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

backend = importlib.import_module("backend_2_1")
frontend = importlib.import_module("frontend_2_8")
# Non-dice suites must not initialize GPU-intensive WebEngine windows.
# Actual DiceBox physics is tested separately with WebGL enabled.
frontend.QWebEngineView = None

notes_ui = sys.modules["notes_ui"]
inventory_ui = sys.modules["inventory_ui"]
guided = sys.modules["guided_tutorial"]
character_template = sys.modules["character_template"]

app = QApplication.instance() or QApplication([])
frontend.BaseMainWindow.check_for_recovery_on_startup = lambda self: None
frontend.BaseMainWindow.show_welcome_dialog_if_needed = lambda self: None

RESULTS = []
ASYNC_ERRORS = []


def async_hook(t, v, tb):
    ASYNC_ERRORS.append("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = async_hook


def pump(n=4):
    """
    Flush ordinary Qt events AND DeferredDelete events.

    QWidget.deleteLater() does not guarantee destruction during a plain
    QApplication.processEvents() call.  The Notes UI intentionally rebuilds
    cards using deleteLater(), so tests must explicitly drain DeferredDelete
    before counting QObject children.
    """
    for _ in range(n):
        QApplication.processEvents()

        QCoreApplication.sendPostedEvents(
            None,
            QEvent.Type.DeferredDelete,
        )

        QApplication.processEvents()


def eq(a, b, msg=None):
    if a != b:
        raise AssertionError(msg or f"Expected {b!r}, got {a!r}")


def ok(value, msg="Expected condition to be true"):
    if not value:
        raise AssertionError(msg)


def no(value, msg="Expected condition to be false"):
    if value:
        raise AssertionError(msg)


def test(name):
    def deco(fn):
        before = len(ASYNC_ERRORS)
        try:
            fn()
            pump(6)
            if len(ASYNC_ERRORS) > before:
                raise RuntimeError("Asynchronous Qt/Python error:\n" + "\n".join(ASYNC_ERRORS[before:]))
        except Exception as e:
            RESULTS.append({"name": name, "status": "FAIL", "detail": f"{type(e).__name__}: {e}"})
        else:
            RESULTS.append({"name": name, "status": "PASS", "detail": ""})
        return fn
    return deco


class StorageSandbox:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.old_save = backend.CharacterStorageSystem.SAVE_DIR
        self.old_recovery = backend.CharacterStorageSystem.RECOVERY_DIR
        backend.CharacterStorageSystem.SAVE_DIR = str(root / "Saved_characters")
        backend.CharacterStorageSystem.RECOVERY_DIR = str(root / "Recovery")
        return root

    def __exit__(self, *args):
        backend.CharacterStorageSystem.SAVE_DIR = self.old_save
        backend.CharacterStorageSystem.RECOVERY_DIR = self.old_recovery
        self.tmp.cleanup()


def fresh(name="UI Torture"):
    c = backend.Character.create_new_character(name)
    c.progression.current_IP = 999
    c.validate()
    return c


def add_notes(c, count):
    colors = list(notes_ui.NOTE_COLOR_ORDER)
    c.notes.list_of_notes = [
        backend.CharacterNote(
            id=str(uuid4()),
            title=f"Note {i+1}",
            text=f"Body {i+1}\n" + ("Fantasy note text. " * ((i % 4) + 1)),
            color=colors[i % len(colors)],
            expanded=True,
        )
        for i in range(count)
    ]
    c.validate()


def make_window(c=None, width=1600, height=950):
    w = frontend.MainWindow()
    if c is not None:
        w.supress_dirty = True
        try:
            w.character = c
            w.current_character_filepath = None
            w.reconnect_character_references()
            w.refresh_all()
        finally:
            w.supress_dirty = False
        w.unsaved_changes = False
        w.save_status_label.setText("Saved")
    w.resize(width, height)
    w.show()
    pump(8)
    if hasattr(w, "apply_redesign_height_to_viewport"):
        w.apply_redesign_height_to_viewport()
    if hasattr(w, "sync_bottom_navigation_to_right_column"):
        w.sync_bottom_navigation_to_right_column()
    pump(5)
    return w


def destroy(w):
    if w is None:
        return
    if hasattr(w, "_recovery_write_timer"):
        w._recovery_write_timer.stop()
    w.unsaved_changes = False
    w.hide()
    w.deleteLater()
    pump(10)


def cards(w):
    """
    Return the ACTIVE NoteCards currently installed in the Notes grid.

    findChildren(NoteCard) is not the right measure immediately after a
    rebuild because Qt widgets removed with deleteLater() remain QObject
    children until DeferredDelete is processed.  Those stale widgets are no
    longer in the layout and are not visible cards.
    """
    active = []

    def visit(layout):
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, notes_ui.NoteCard):
                active.append(widget)
            child_layout = item.layout()
            if child_layout is not None:
                visit(child_layout)

    visit(w.notes_grid_layout)
    return active


@test("Import frontend_2_8 redesign and required APIs")
def _():
    eq(Path(frontend.__file__).name, "frontend_2_8.py")
    for name in (
        "MainWindow", "BaseMainWindow", "FantasyConfirmDialog",
        "FantasyAbilityEditorDialog", "FantasyIcon", "ShieldValueWidget",
        "ExternalSvgIcon", "install_fantasy_runtime_ui",
    ):
        ok(hasattr(frontend, name), f"Missing redesign API: {name}")


@test("MainWindow constructs with permanent Character/Notes navigation")
def _():
    with StorageSandbox():
        w = make_window()
        try:
            eq(w.current_redesign_page, "character")
            for attr in (
                "character_page_btn", "notes_page_btn", "notes_reopen_row",
                "redesign_left_frame", "redesign_center_widget", "inventory_frame",
                "improvements_frame", "notes_frame", "redesign_content_layout",
            ):
                ok(hasattr(w, attr), f"Missing redesign widget: {attr}")
            ok(w.notes_reopen_row.isVisible(), "Permanent navigation is hidden")
            no(w.notes_frame.isVisible(), "Notes page should start hidden")
        finally:
            destroy(w)


@test("Repeated MainWindow create/destroy cycles are lifecycle-safe")
def _():
    with StorageSandbox():
        for i in range(12):
            w = make_window(fresh(f"Lifecycle {i}"), 800 + (i % 4) * 180, 650 + (i % 3) * 90)
            w.refresh_all()
            pump(3)
            destroy(w)


@test("Fantasy confirmation dialog preserves custom-button compatibility")
def _():
    sig = inspect.signature(frontend.fantasy_ask_yes_no)
    for p in ("yes_text", "no_text", "button_width", "button_height"):
        ok(p in sig.parameters, f"Missing fantasy_ask_yes_no parameter: {p}")
    d = frontend.FantasyConfirmDialog(
        None, "Replace Character", "Save first?",
        yes_text="Save", no_text="Don't Save", button_width=137, button_height=41,
    )
    try:
        eq(d.yes_btn.text(), "Save")
        eq(d.no_btn.text(), "Don't Save")
        eq(d.yes_btn.width(), 137)
        eq(d.no_btn.height(), 41)
    finally:
        d.deleteLater(); pump(4)


@test("QMessageBox show/destroy is safe under fantasy styling")
def _():
    frontend.install_fantasy_runtime_ui()
    for i in range(20):
        box = QMessageBox()
        box.setWindowTitle(f"Message {i}")
        box.setText("Temporary redesign message")
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        box.show(); pump(2)
        box.hide(); box.deleteLater(); pump(3)


@test("Forty Light/Dark switches do not mark the character dirty")
def _():
    with StorageSandbox():
        w = make_window()
        original = w.current_theme
        try:
            w.unsaved_changes = False
            for _i in range(40):
                before = w.current_theme
                w.toggle_theme_from_button(); pump(2)
                eq(w.current_theme, "dark" if before == "light" else "light")
                no(w.unsaved_changes, "Theme switching marked dirty")
            if w.current_theme != original:
                w.set_theme(original)
        finally:
            destroy(w)


@test("Painted icons and missing-SVG fallbacks render in both themes")
def _():
    with StorageSandbox():
        w = make_window()
        original = w.current_theme
        try:
            for theme in ("light", "dark"):
                w.set_theme(theme); pump(3)
                widgets = [
                    frontend.FantasyIcon("agility", size=48, circular=True),
                    frontend.ExternalSvgIcon(str(HERE / "__missing__.svg"), size=42),
                    frontend.ShieldValueWidget("7", defense_kind="__missing__"),
                ]
                for widget in widgets:
                    no(widget.grab().isNull(), f"{type(widget).__name__} failed to render")
                    widget.deleteLater()
                pump(3)
            if w.current_theme != original:
                w.set_theme(original)
        finally:
            destroy(w)


@test("Opening existing Notes does not duplicate or dirty")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 3)
        ids = [n.id for n in c.notes.list_of_notes]
        w = make_window(c)
        try:
            w.unsaved_changes = False
            w.open_notes_board(); pump(6)
            eq(sorted(n.id for n in c.notes.list_of_notes), sorted(ids))
            eq(w.current_redesign_page, "notes")
            ok(w.notes_frame.isVisible())
            no(w.redesign_left_frame.isVisible())
            no(w.unsaved_changes, "Pure Notes navigation marked dirty")
        finally:
            destroy(w)


@test("Opening empty Notes creates one blank note without dirtying")
def _():
    with StorageSandbox():
        c = fresh(); c.notes.list_of_notes = []; c.validate()
        w = make_window(c)
        try:
            w.unsaved_changes = False
            w.open_notes_board(); pump(5)
            eq(len(c.notes.list_of_notes), 1)
            note = c.notes.list_of_notes[0]
            eq(note.title, ""); eq(note.text, "")
            no(w.unsaved_changes, "Opening empty Notes marked dirty")
            note_id = note.id
            w.show_character_page(); w.open_notes_board(); pump(5)
            eq(len(c.notes.list_of_notes), 1)
            eq(c.notes.list_of_notes[0].id, note_id)
        finally:
            destroy(w)


@test("Two hundred page switches preserve data, dirty state, and horizontal lock")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 7)
        ids = [n.id for n in c.notes.list_of_notes]
        w = make_window(c)
        try:
            w.unsaved_changes = False
            for i in range(200):
                w.show_notes_page() if i % 2 == 0 else w.show_character_page()
                w.scroll.horizontalScrollBar().setValue(999999)
                w.keep_sheet_horizontally_locked()
                eq(w.scroll.horizontalScrollBar().value(), 0)
                if i % 10 == 0: pump(2)
            eq(sorted(n.id for n in c.notes.list_of_notes), sorted(ids))
            no(w.unsaved_changes, "Navigation marked dirty")
            ok(w.notes_reopen_row.isVisible(), "Permanent navigation disappeared")
        finally:
            destroy(w)


@test("Responsive Notes breakpoint calculation reaches 1 through 5 columns")
def _():
    with StorageSandbox():
        w = make_window()
        try:
            w.setMinimumWidth(0)
            for requested in (500, 700, 1000, 1300, 1600):
                w.resize(requested, 820); pump(4)
                width = w.width()
                expected = 5 if width >= 1550 else 4 if width >= 1250 else 3 if width >= 950 else 2 if width >= 650 else 1
                eq(w.calculate_note_columns(), expected, f"Wrong breakpoint at width {width}")
        finally:
            destroy(w)


@test("Notes grid uses the responsive column count")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 11)
        w = make_window(c, 1600, 900)
        try:
            w.show_notes_page(); w.refresh_notes(); pump(8)
            cols = w.calculate_note_columns()
            eq(len(cards(w)), 11)
            # The redesigned board has one vertical stack per column; cards
            # are distributed round-robin among those stacks.
            eq(w.notes_grid_layout.count(), cols)
            stacks = []
            for col in range(cols):
                item = w.notes_grid_layout.itemAtPosition(0, col)
                ok(item is not None and item.layout() is not None,
                   f"Missing Notes column {col}")
                stacks.append(item.layout())
            eq([stack.count() for stack in stacks],
               [len(range(col, 11, cols)) for col in range(cols)])
        finally:
            destroy(w)


@test("Sixty real Notes rebuilds keep one card per note")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 15)
        w = make_window(c)
        try:
            w.show_notes_page()
            for i in range(60):
                w.refresh_notes()
                if i % 5 == 0: pump(4)
                eq(len(cards(w)), 15, "Notes rebuild duplicated/lost cards")
            pump(10)
        finally:
            destroy(w)


@test("Note expand/collapse is UI-only and does not mark dirty")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 1)
        w = make_window(c)
        try:
            w.show_notes_page(); w.refresh_notes(); pump(6)
            card = cards(w)[0]; note = c.notes.list_of_notes[0]
            w.unsaved_changes = False
            original = note.expanded
            card.toggle_expanded(); pump(3)
            eq(note.expanded, not original); no(w.unsaved_changes)
            card.toggle_expanded(); pump(3)
            eq(note.expanded, original); no(w.unsaved_changes)
        finally:
            destroy(w)


@test("Actual empty-note deletion rebuild is safe in redesigned Notes")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 4)
        empty = backend.CharacterNote(id=str(uuid4()), title="", text="", color="pink", expanded=True)
        c.notes.list_of_notes.append(empty); c.validate()
        w = make_window(c)
        try:
            w.show_notes_page(); w.refresh_notes(); pump(6)
            eq(len(cards(w)), 5)
            w.unsaved_changes = False
            w.confirm_delete_note(empty); pump(12)
            no(empty in c.notes.list_of_notes)
            eq(len(cards(w)), 4)
            ok(w.unsaved_changes, "Empty note deletion did not mark dirty")
        finally:
            destroy(w)


@test("Cancelled non-empty deletion preserves model and card")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 3)
        target = c.notes.list_of_notes[1]
        w = make_window(c)
        old = notes_ui.ask_yes_no
        notes_ui.ask_yes_no = lambda *a, **k: False
        try:
            w.show_notes_page(); w.refresh_notes(); pump(5)
            w.unsaved_changes = False
            w.confirm_delete_note(target); pump(5)
            ok(target in c.notes.list_of_notes)
            eq(len(cards(w)), 3)
            no(w.unsaved_changes, "Cancelled deletion marked dirty")
        finally:
            notes_ui.ask_yes_no = old
            destroy(w)


@test("Long editable note grows without internal scrollbars")
def _():
    with StorageSandbox():
        c = fresh()
        note = backend.CharacterNote(id=str(uuid4()), title="Long Note", text="Start", color="green", expanded=True)
        c.notes.list_of_notes = [note]; c.validate()
        w = make_window(c)
        try:
            w.show_notes_page(); w.refresh_notes(); pump(6)
            editable_cards = [item for item in cards(w) if hasattr(item.text_edit, "setPlainText")]
            eq(len(editable_cards), 1, "Expected exactly one editable note")
            card = editable_cards[0]
            long_text = "\n".join(f"Line {i}: " + ("very long fantasy reminder " * 4) for i in range(120))
            card.text_edit.setPlainText(long_text); pump(12)
            eq(card.text_edit.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            eq(card.text_edit.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            ok(card.text_edit.height() >= 200, "Long note did not grow")
            eq(note.text, long_text)
        finally:
            destroy(w)


@test("System notes remain read-only and vertically self-sized")
def _():
    with StorageSandbox():
        c = fresh()
        note = backend.CharacterNote(id=str(uuid4()), title="Spellcasting Verbs", text=notes_ui.SPELLCASTING_VERBS_NOTE_TEXT, color="blue", expanded=True)
        # Managed Spellcasting notes require their owning Improvement.
        # Without it, refresh_notes() correctly removes the orphan note.
        spell_purchase = next(
            (purchase for purchase in backend.ImprovementSystem.get_available_purchases(c)
             if purchase.get("kind") == "base"
             and purchase.get("catalog_id") == "magic_novice"),
            None,
        )
        ok(spell_purchase is not None, "Magic Novice must be purchasable")
        ok(backend.ImprovementSystem.buy_purchase(
            c, spell_purchase,
            choices={"specific_magic_effect": "Create a shield", "spellcasting_stat": "knowledge"},
        ), "Failed to create Spellcasting note owner")
        c.notes.list_of_notes = [note]; c.validate()
        w = make_window(c)
        try:
            w.show_notes_page()
            # The Notes board is collapsible and starts closed in a fresh window.
            # Showing the page alone does not open the board or build its cards.
            w.open_notes_board()
            w.refresh_notes(); pump(8)
            matching = [card for card in cards(w) if card.note.title == "Spellcasting Verbs"]
            eq(len(matching), 1, "Expected one visible managed Spellcasting note")
            card = matching[0]
            ok(card.is_system_note)
            ok(card.title_edit.isReadOnly())
            ok(isinstance(card.text_edit, QLabel), "System note body should be QLabel")
            ok(card.text_edit.height() >= 30)
            ok(bool(note.text), "Managed Spellcasting note body is empty")
            ok(bool(note.linked_improvement_id), "Managed note lost its owning Improvement")
        finally:
            destroy(w)


@test("Resize storm preserves horizontal lock and navigation alignment")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 8)
        w = make_window(c)
        sizes = [(620,600),(760,720),(980,650),(1280,760),(1600,950),(1100,880),(700,900)]
        try:
            for i in range(140):
                width, height = sizes[i % len(sizes)]
                w.resize(width, height)
                w.apply_redesign_height_to_viewport()
                w.position_portrait_controls()
                w.sync_bottom_navigation_to_right_column()
                if i % 4 == 0: pump(3)
                eq(w.scroll.horizontalScrollBar().value(), 0)
                eq(w.notes_reopen_row.width(), max(1, w.inventory_frame.width()))
                ok(w.inventory_frame.height() >= 0)
                ok(w.improvements_frame.height() >= 0)
            pump(10)
        finally:
            destroy(w)


@test("Portrait overlay controls remain within the portrait area")
def _():
    with StorageSandbox():
        w = make_window()
        try:
            controls = [w.remove_image_btn, w.prev_image_btn, w.next_image_btn, w.add_image_btn, w.image_counter_label]
            for width, height in ((650,650),(900,750),(1200,800),(1600,950)):
                w.resize(width, height); w.apply_redesign_height_to_viewport(); w.position_portrait_controls(); pump(5)
                rect = w.image_label.rect()
                ok(rect.width() >= 1 and rect.height() >= 1)
                for control in controls:
                    g = control.geometry()
                    ok(g.right() >= 0 and g.bottom() >= 0 and g.left() <= rect.right() and g.top() <= rect.bottom(),
                       f"{type(control).__name__} moved outside portrait")
        finally:
            destroy(w)


@test("Dense Inventory and Improvements keep valid scrolling geometry")
def _():
    with StorageSandbox():
        c = fresh()
        c.inventory.list_of_items = [
            backend.InventoryItem(id=str(uuid4()), name=f"Item {i}", description="Detailed description " * ((i % 5)+1), quantity=i % 12, expanded=(i % 3 == 0))
            for i in range(45)
        ]
        c.improvements.list_of_taken_improvements = [
            backend.Improvement(id=str(uuid4()), catalog_id="custom", name=f"Custom {i}", cost=0,
                                description="Long improvement description " * ((i % 4)+1), source="ip", choices={},
                                expanded=(i % 4 == 0), times_taken=1, sort_order=i)
            for i in range(36)
        ]
        c.validate()
        w = make_window(c)
        try:
            w.refresh_all(); pump(12)
            w.refresh_inventory_scroll_geometry(); w.refresh_improvement_scroll_geometry(); pump(8)
            eq(w.inventory_list_layout.count(), 45)
            ok(w.improvement_list_layout.count() >= 36)
            ok(w.inventory_scroll.height() >= 0 and w.improvement_scroll.height() >= 0)
            ok(w.inventory_list_widget.height() >= w.inventory_scroll.height())
            ok(w.improvement_list_widget.height() >= w.improvement_scroll.height())
            eq(w.inventory_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            eq(w.improvement_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        finally:
            destroy(w)


@test("Fantasy Ability Editor constructs and closes safely")
def _():
    with StorageSandbox():
        c = fresh()
        d = frontend.FantasyAbilityEditorDialog(c, None)
        try:
            d.show(); pump(8)
            eq(d.windowTitle(), "Edit Abilities")
            ok(d.width() >= 600)
            text = " ".join(x.text() for x in d.findChildren(frontend.QLabel) if hasattr(x, "text")).lower()
            for stat in backend.STAT_NAMES:
                ok(stat in text, f"Ability editor does not show {stat}")
        finally:
            d.hide(); d.deleteLater(); pump(8)


@test("Mixed redesign stress survives refresh, resize, theme, Notes, and painting")
def _():
    with StorageSandbox():
        c = fresh(); add_notes(c, 12)
        c.inventory.list_of_items = [
            backend.InventoryItem(id=str(uuid4()), name=f"Gear {i}", description="Equipment details " * 3, quantity=i+1, expanded=(i%2==0))
            for i in range(18)
        ]
        c.improvements.list_of_taken_improvements = [
            backend.Improvement(id=str(uuid4()), catalog_id="custom", name=f"Feature {i}", cost=0,
                                description="Feature description " * 4, source="ip", choices={}, expanded=(i%3==0),
                                times_taken=1, sort_order=i)
            for i in range(16)
        ]
        c.validate()
        w = make_window(c)
        original = w.current_theme
        sizes = [(700,650),(980,720),(1280,820),(1600,950)]
        try:
            w.unsaved_changes = False
            for i in range(100):
                w.resize(*sizes[i % len(sizes)])
                w.show_notes_page() if i % 2 == 0 else w.show_character_page()
                if i % 3 == 0: w.toggle_theme_from_button()
                if i % 4 == 0: w.refresh_all()
                if i % 5 == 0:
                    w.refresh_inventory_scroll_geometry(); w.refresh_improvement_scroll_geometry()
                if i % 6 == 0: w.position_portrait_controls()
                w.keep_sheet_horizontally_locked()
                if i % 5 == 0: pump(4)
                eq(w.scroll.horizontalScrollBar().value(), 0)
                ok(w.notes_reopen_row.isVisible(), "Permanent navigation disappeared")
            pump(15)
            no(w.unsaved_changes, "Presentation-only stress marked dirty")
            eq(len(c.notes.list_of_notes), 12)
            if w.current_theme != original:
                w.set_theme(original)
        finally:
            destroy(w)




# ============================================================================
# Current responsive-layout regressions
# ============================================================================

@test("Half-screen keeps Inventory and Improvements at their locked usable widths")
def _():
    with StorageSandbox():
        w = make_window(width=1600, height=900)
        try:
            # Force the same capture used by the real app after first layout.
            if not getattr(w, "_main_column_widths_locked", False):
                w.lock_normal_inventory_improvement_widths()
                pump(6)

            ok(w._main_column_widths_locked, "Main-column width lock never completed")

            inv_min = w.inventory_frame.minimumWidth()
            imp_min = w.improvements_frame.minimumWidth()

            ok(inv_min > 100, "Inventory locked to an implausibly tiny width")
            ok(imp_min > 100, "Improvements locked to an implausibly tiny width")

            w.unsaved_changes = False
            w.resize(780, 760)
            pump(8)

            ok(
                w.inventory_frame.width() >= inv_min,
                "Inventory was compressed below its captured normal width",
            )
            ok(
                w.improvements_frame.width() >= imp_min,
                "Improvements was compressed below its captured normal width",
            )
            no(w.unsaved_changes, "Responsive resizing marked the character dirty")
        finally:
            destroy(w)


@test("System Spellcasting note height is stable across repeated sizing passes")
def _():
    with StorageSandbox():
        c = fresh()
        note = backend.CharacterNote(
            id=str(uuid4()),
            title="Spellcasting Verbs",
            text=notes_ui.SPELLCASTING_VERBS_NOTE_TEXT,
            color="blue",
            expanded=True,
        )
        spell_purchase = next(
            (purchase for purchase in backend.ImprovementSystem.get_available_purchases(c)
             if purchase.get("kind") == "base"
             and purchase.get("catalog_id") == "magic_novice"),
            None,
        )
        ok(spell_purchase is not None, "Magic Novice must be purchasable")
        ok(backend.ImprovementSystem.buy_purchase(
            c, spell_purchase,
            choices={"specific_magic_effect": "Create a shield", "spellcasting_stat": "knowledge"},
        ), "Failed to create Spellcasting note owner")
        c.notes.list_of_notes = [note]
        c.validate()

        w = make_window(c, 900, 720)
        try:
            w.show_notes_page()
            w.open_notes_board()
            w.refresh_notes()
            pump(8)

            matching = [card for card in cards(w) if card.note.title == "Spellcasting Verbs"]
            eq(len(matching), 1, "Expected one visible managed Spellcasting note")
            card = matching[0]
            ok(card.is_system_note)

            # The first explicit resize can correct the height assigned by
            # Qt's initial layout. Test for convergence AFTER this normal
            # one-time adjustment, not equality with pre-layout geometry.
            initial_height = card.text_edit.height()
            ok(initial_height >= 30)
            card.resize_text_edit()
            pump(2)
            settled_height = card.text_edit.height()
            ok(settled_height >= 30)
            heights = [initial_height, settled_height]
            for _ in range(12):
                card.resize_text_edit()
                pump(1)
                heights.append(card.text_edit.height())

            eq(
                heights[2:],
                [settled_height] * 12,
                f"System note height did not settle after first resize: {heights}",
            )
        finally:
            destroy(w)


@test("Inventory Quantity editor has enough height for its number glyph")
def _():
    d = inventory_ui.InventoryItemDialog(None)
    try:
        d.show()
        pump(5)
        field = d.quantity_input
        ok(
            field.height() >= field.fontMetrics().height() + 8,
            "Quantity number can clip at the bottom on Windows",
        )
    finally:
        d.close()
        d.deleteLater()
        pump(4)


@test("Current guided tutorial survives resize and theme stress without dirtying")
def _():
    with StorageSandbox():
        w = make_window(width=1200, height=800)
        tutorial = None
        original_theme = w.current_theme
        try:
            w.unsaved_changes = False
            w.start_guided_tutorial()
            pump(8)
            tutorial = w.guided_tutorial

            ok(tutorial.running)
            eq(tutorial.current_step().title, "Name Your Character")

            sizes = [(760, 650), (1000, 720), (1350, 850), (900, 760)]
            for i in range(32):
                w.resize(*sizes[i % len(sizes)])
                if i % 4 == 0:
                    w.toggle_theme_from_button()
                pump(2)
                ok(tutorial.running, f"Tutorial stopped during UI stress cycle {i}")
                eq(tutorial.current_step().title, "Name Your Character")

            no(w.unsaved_changes, "Tutorial/resize/theme presentation stress marked dirty")
        finally:
            if tutorial is not None:
                try:
                    tutorial.stop()
                except Exception:
                    pass
            if w.current_theme != original_theme:
                w.set_theme(original_theme)
            destroy(w)


@test("Creation Rules editor remains usable through all six pages")
def _():
    d = character_template.CharacterTemplateDialog()
    try:
        d.show()
        pump(5)
        eq(d.pages.count(), 6)

        for index in range(d.pages.count()):
            d.show_page(index)
            pump(2)
            eq(d.pages.currentIndex(), index)
            ok(d.step_label.text(), f"Creation Rules page {index} has no step label")

        d.show_page(0)
        pump(2)
        eq(d.pages.currentIndex(), 0)
    finally:
        d.close()
        d.deleteLater()
        pump(5)

passed = sum(r["status"] == "PASS" for r in RESULTS)
failed = sum(r["status"] == "FAIL" for r in RESULTS)
report = {"seed": 20260906, "passed": passed, "failed": failed, "results": RESULTS, "async_errors": ASYNC_ERRORS}
report_path = REPORT_DIR / "automated_redesign_ui_torture_report.json"
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Redesign UI torture test: {passed} passed / {failed} failed")
print(f"Report: {report_path}")
for r in RESULTS:
    print(f"[{r['status']}] {r['name']}")
    if r["detail"]:
        print(f"       {r['detail']}")

if failed:
    sys.exit(1)
