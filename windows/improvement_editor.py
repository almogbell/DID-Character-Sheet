
"""
Embedded Improvement & Empowerment Editor
=========================================
Drop this file next to character_API.py and import/open it from the main sheet.

Design goals:
- Non-programmers edit through forms, never Python/JSON.
- Edits are drafts/suggestions. The live catalog is unchanged until owner approval.
- Validation runs before approval.
- Version snapshots make rollback possible.
- Works standalone for testing, but is designed to be embedded in a PyQt/PySide sheet.

Supported Qt bindings: PyQt6, PySide6, PyQt5, PySide2.
"""

from __future__ import annotations
import copy
import datetime as _dt
import hashlib
import html as _html
from html.parser import HTMLParser
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

from suggestion_cloud import (CloudClient, CloudError, load_config, enqueue,
                              flush_outbox, read_outbox)

# ---------- Qt compatibility ----------
QT_API = None
try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    QT_API = "PyQt6"
    Signal = QtCore.pyqtSignal
    ALIGN_TOP = QtCore.Qt.AlignmentFlag.AlignTop
    USER_ROLE = QtCore.Qt.ItemDataRole.UserRole
    YES = QtWidgets.QMessageBox.StandardButton.Yes
    NO = QtWidgets.QMessageBox.StandardButton.No
except Exception:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        QT_API = "PySide6"
        Signal = QtCore.Signal
        ALIGN_TOP = QtCore.Qt.AlignmentFlag.AlignTop
        USER_ROLE = QtCore.Qt.ItemDataRole.UserRole
        YES = QtWidgets.QMessageBox.StandardButton.Yes
        NO = QtWidgets.QMessageBox.StandardButton.No
    except Exception:
        try:
            from PyQt5 import QtCore, QtGui, QtWidgets
            QT_API = "PyQt5"
            Signal = QtCore.pyqtSignal
            ALIGN_TOP = QtCore.Qt.AlignTop
            USER_ROLE = QtCore.Qt.UserRole
            YES = QtWidgets.QMessageBox.Yes
            NO = QtWidgets.QMessageBox.No
        except Exception:
            from PySide2 import QtCore, QtGui, QtWidgets
            QT_API = "PySide2"
            Signal = QtCore.Signal
            ALIGN_TOP = QtCore.Qt.AlignTop
            USER_ROLE = QtCore.Qt.UserRole
            YES = QtWidgets.QMessageBox.Yes
            NO = QtWidgets.QMessageBox.No


# ---------- Character-sheet visual theme ----------
# Uses the same light-fantasy palette and ui_theme translation system as
# frontend_2_8.py. When embedded in the sheet, dark/light mode follows the
# sheet automatically. Standalone testing falls back to the light palette.
try:
    from ui_theme import (
        set_themed_stylesheet as _sheet_set_stylesheet,
        theme_color as _sheet_theme_color,
    )
except Exception:
    _sheet_set_stylesheet = None
    _sheet_theme_color = None

FANTASY_EDITOR_QSS = """
QDialog, QWidget#ImprovementEditorRoot {
    background-color: #fffdf7;
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
QLabel#EditorTitle {
    font-family: Georgia;
    font-size: 23px;
    font-weight: 900;
    color: #25190f;
}
QLabel#MutedText {
    color: #765d34;
    font-size: 12px;
}
QGroupBox {
    background-color: #fffaf0;
    border: 1px solid #cdaa63;
    border-radius: 11px;
    margin-top: 13px;
    padding: 12px 10px 10px 10px;
    color: #6c5428;
    font-family: Georgia;
    font-size: 13px;
    font-weight: 900;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 5px;
    background-color: #fffdf7;
    color: #6c5428;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
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
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus {
    border: 1px solid #a87824;
    background-color: #fffdf7;
}
QListWidget, QTableWidget {
    background-color: #fffaf0;
    alternate-background-color: #fffdf7;
    border: 1px solid #cdaa63;
    border-radius: 11px;
    padding: 6px;
    color: #25190f;
    font-family: Georgia;
    font-size: 14px;
    outline: none;
}
QListWidget::item {
    padding: 7px 9px;
    margin: 1px 0px;
    border-radius: 7px;
}
QListWidget::item:hover {
    background-color: #fff4df;
}
QListWidget::item:selected {
    background-color: #d8edf7;
    color: #25190f;
}
QHeaderView::section {
    background-color: #fff4df;
    border: none;
    border-right: 1px solid #d9bd82;
    border-bottom: 1px solid #d9bd82;
    padding: 6px;
    color: #6c5428;
    font-family: Georgia;
    font-weight: 900;
}
QPushButton {
    background-color: #fffdf7;
    border: 1px solid #c79a3b;
    border-radius: 10px;
    min-height: 32px;
    font-family: Georgia;
    font-size: 13px;
    font-weight: 800;
    color: #4f3b18;
    padding: 0px 14px;
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
    background-color: #eee9df;
    border-color: #d8ccb5;
    color: #9b9388;
}
QPushButton#PrimaryButton {
    background-color: #d8edf7;
    color: #25190f;
}
QPushButton#PrimaryButton:hover {
    background-color: #e8f5fb;
    border-color: #a87824;
}
QPushButton#PrimaryButton:pressed {
    background-color: #c9e3ef;
}
QPushButton#DangerButton:hover {
    border-color: #aa0000;
    color: #aa0000;
}
QCheckBox {
    color: #25190f;
    font-family: Georgia;
    font-size: 13px;
    spacing: 7px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QSplitter::handle {
    background-color: #d9bd82;
    width: 1px;
}

/* Compact embedded-editor overrides */
QLabel { font-size: 11px; }
QLabel#EditorTitle { font-size: 17px; }
QLabel#MutedText { font-size: 10px; }

QGroupBox {
    border-radius: 8px;
    margin-top: 9px;
    padding: 7px 7px 6px 7px;
    font-size: 11px;
}
QGroupBox::title {
    left: 9px;
    padding: 0 4px;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    border-radius: 6px;
    padding: 3px 6px;
    font-size: 11px;
    min-height: 20px;
}
QListWidget, QTableWidget {
    border-radius: 8px;
    padding: 3px;
    font-size: 11px;
}
QListWidget::item {
    padding: 4px 6px;
    margin: 0px;
    border-radius: 5px;
}
QHeaderView::section {
    padding: 4px;
    font-size: 11px;
}
QPushButton {
    border-radius: 7px;
    min-height: 25px;
    font-size: 10px;
    padding: 0px 5px;
}
QCheckBox {
    font-size: 11px;
    spacing: 5px;
}


QTextEdit#ImprovementRichEditor {
    font-family: Georgia;
    font-size: 14px;
    padding: 12px 14px;
    background: #fffdf7;
    border: 1px solid #d9bd82;
    border-radius: 9px;
}
QTextBrowser#ImprovementLivePreview {
    font-family: Georgia;
    font-size: 12px;
    padding: 8px 12px;
    background: #fffaf0;
    border: 1px solid #d9bd82;
    border-radius: 8px;
}
QWidget#DescriptionWritingSurface QToolButton {
    background: #fffdf7;
    border: 1px solid #d9bd82;
    border-radius: 6px;
    color: #4f3b18;
    font-family: Georgia;
    font-size: 12px;
    font-weight: bold;
    padding: 0px;
    margin: 0px;
}
QWidget#DescriptionWritingSurface QToolButton:hover {
    background: #e8f5fb;
}
QWidget#DescriptionWritingSurface QToolButton#FormatToolButton {
    min-width: 38px;
    max-width: 38px;
    min-height: 32px;
    max-height: 32px;
}
QMenu#TagPickerMenu {
    background: #fffdf7;
    border: 1px solid #cdaa63;
    border-radius: 8px;
    padding: 6px;
}
QMenu#TagPickerMenu QCheckBox {
    font-size: 11px;
    padding: 2px 3px;
}

QToolButton#TagPickerField {
    background-color: #fffaf0;
    border: 1px solid #d9bd82;
    border-radius: 6px;
    padding: 3px 25px 3px 7px;
    color: #25190f;
    font-family: Georgia;
    font-size: 11px;
    text-align: left;
}
QToolButton#TagPickerField:hover,
QToolButton#TagPickerField:focus {
    border: 1px solid #a87824;
    background-color: #fffdf7;
}
QToolButton#TagPickerField::menu-button {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 23px;
    border-left: 1px solid #d9bd82;
}

QComboBox {
    padding-right: 26px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #d9bd82;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background-color: #fffdf7;
}
QComboBox::drop-down:hover {
    background-color: #fff4df;
}


QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QComboBox::drop-down {
    width: 25px;
    border-left: 1px solid #d9bd82;
}

/* Unified Catalog Editor controls */
QPushButton, QToolButton {
    background-color: #fffdf7;
    border: 1px solid #c79a3b;
    border-radius: 7px;
    min-height: 28px;
    color: #4f3b18;
    font-family: Georgia;
    font-size: 11px;
    font-weight: 800;
    padding: 0 10px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #fff4df;
    border-color: #a87824;
    color: #25190f;
}
QPushButton:pressed, QToolButton:pressed {
    background-color: #f5ead2;
}
QToolButton::menu-indicator { image: none; width: 0px; }
QToolButton#ToolbarMenuButton { padding: 0 11px; }
QToolButton#IconMenuButton {
    min-width: 30px; max-width: 30px;
    padding: 0px;
    font-size: 16px;
}
QToolButton#SectionNavButton {
    background-color: #fffaf0;
    border-color: #d9bd82;
    min-height: 25px;
    padding: 0 10px;
    font-weight: 700;
}
QToolButton#SectionNavButton:hover {
    background-color: #e8f5fb;
    border-color: #c79a3b;
}
QPushButton#PrimaryButton {
    background-color: #d8edf7;
    border-color: #c79a3b;
    color: #25190f;
}
QPushButton#PrimaryButton:hover { background-color: #e8f5fb; }
QPushButton#DangerButton { color: #aa0000; }
QPushButton#DangerButton:hover {
    background-color: #f3a6a6;
    border-color: #aa0000;
    color: #aa0000;
}
QTabWidget::pane {
    border: 1px solid #d9bd82;
    border-radius: 8px;
    background: #fffdf7;
    top: -1px;
}
QTabBar::tab {
    background: #fffaf0;
    border: 1px solid #d9bd82;
    border-bottom: none;
    padding: 6px 12px;
    margin-right: 3px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #6c5428;
    font-family: Georgia;
    font-size: 11px;
}
QTabBar::tab:selected {
    background: #fffdf7;
    color: #25190f;
    font-weight: 800;
}
QMenu {
    background-color: #fffdf7;
    border: 1px solid #cdaa63;
    color: #25190f;
    font-family: Georgia;
    font-size: 11px;
    padding: 4px;
}
QMenu::item { padding: 6px 22px 6px 10px; border-radius: 5px; }
QMenu::item:selected { background-color: #e8f5fb; }


/* Direct-edit catalog workspace */
QLabel#InlineTitleValue {
    font-family: Georgia;
    font-size: 20px;
    font-weight: 900;
    color: #25190f;
    padding: 2px 3px;
}
QLabel#InlineMetaValue {
    font-family: Georgia;
    font-size: 11px;
    color: #6c5428;
    padding: 3px 4px;
    border-radius: 5px;
}
QLabel#InlineTitleValue:hover,
QLabel#InlineMetaValue:hover {
    background-color: #fff4df;
}
QLineEdit#InlineTitleEditor {
    font-family: Georgia;
    font-size: 20px;
    font-weight: 900;
    color: #25190f;
    min-height: 34px;
    padding: 2px 6px;
}
QSpinBox#InlineMetaEditor,
QComboBox#InlineMetaEditor,
QToolButton#InlineTagsEditor {
    font-family: Georgia;
    font-size: 11px;
    color: #6c5428;
    min-height: 28px;
}
QTabBar#DescriptionModeBar::tab {
    background: #fffaf0;
    border: 1px solid #d9bd82;
    border-radius: 7px;
    padding: 7px 18px;
    margin-right: 6px;
    color: #6c5428;
    font-family: Georgia;
    font-size: 11px;
    min-height: 24px;
}
QTabBar#DescriptionModeBar::tab:selected {
    background: #fffdf7;
    border-color: #c79a3b;
    color: #25190f;
    font-weight: 800;
}
QLabel#SectionHeading {
    font-family: Georgia;
    font-size: 13px;
    font-weight: 900;
    color: #4f3b18;
}
QLabel#EmptySectionText {
    color: #765d34;
    font-style: italic;
    padding: 4px 2px;
}
QToolButton#SmallAddButton {
    background: transparent;
    border: 1px solid #d9bd82;
    border-radius: 12px;
    color: #6c5428;
    font-family: Georgia;
    font-size: 16px;
    font-weight: 900;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0px;
}
QToolButton#SmallAddButton:hover {
    background: #fff4df;
    border-color: #a87824;
    color: #25190f;
}
QToolButton#MainFormatButton {
    background: #fffdf7;
    border: 1px solid #d9bd82;
    border-radius: 6px;
    color: #4f3b18;
    font-family: Georgia;
    font-size: 12px;
    font-weight: 900;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
    padding: 0px;
    margin: 0px;
}
QToolButton#MainFormatButton:hover { background: #e8f5fb; }
QListWidget#CompactEditList {
    background: transparent;
    border: none;
    padding: 0px;
    font-size: 12px;
}
QListWidget#CompactEditList::item {
    padding: 5px 8px;
    margin: 1px 0px;
    border: 1px solid #d9bd82;
    border-radius: 7px;
    background: #fffaf0;
}
QListWidget#CompactEditList::item:hover { background: #fff4df; }
QListWidget#CompactEditList::item:selected {
    background: #e8f5fb;
    color: #25190f;
}
QWidget#DirectDescriptionCard {
    background: transparent;
}
QFrame#ThinDivider {
    background: #d9bd82;
    max-height: 1px;
    min-height: 1px;
}
"""

def apply_character_sheet_theme(widget):
    if _sheet_set_stylesheet is not None:
        _sheet_set_stylesheet(widget, FANTASY_EDITOR_QSS)
    else:
        widget.setStyleSheet(FANTASY_EDITOR_QSS)

def _editor_theme_color(key, fallback):
    if _sheet_theme_color is not None:
        try:
            return _sheet_theme_color(key)
        except Exception:
            pass
    return fallback

BASE_DIR = Path(__file__).resolve().parent


def _persistent_editor_root():
    # In the one-file PyInstaller build, __file__ points into a temporary
    # extraction folder. Store editable catalog data beside the installed EXE
    # instead so approved changes survive restarts and app updates.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return BASE_DIR


PERSISTENT_ROOT = _persistent_editor_root()
DATA_DIR = PERSISTENT_ROOT / "catalog_editor_data"
LIVE_FILE = DATA_DIR / "live_catalog.json"
DRAFT_FILE = DATA_DIR / "draft_catalog.json"
PENDING_FILE = DATA_DIR / "pending_changes.json"
HISTORY_DIR = DATA_DIR / "history"
SUGGESTIONS_CONFIG = PERSISTENT_ROOT / "suggestions_config.json"
SUGGESTIONS_OUTBOX = DATA_DIR / "suggestions_outbox.json"

TECHNICAL_KEYS = {
    "id", "purchase_rule", "requires_choices", "scaling_values", "effects", "creates",
    "scaling_empowerments", "empowerment_groups", "max_times", "base_cost",
    "cost_increase", "base_value", "increase_by", "value_key"
}

def _ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    HISTORY_DIR.mkdir(exist_ok=True)

def _legacy_catalog():
    """Read the one authoritative API; no stale seed or JSON fallback."""
    mod = importlib.import_module("character_API")
    return {
        "schema_version": 1,
        "stat_names": copy.deepcopy(mod.STAT_NAMES),
        "ability_arrays": copy.deepcopy(mod.ABILITY_ARRAYS),
        "improvements": copy.deepcopy(mod.IMPROVEMENT_CATALOG),
    }

def _write_json(path: Path, obj: Any):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def _read_json(path: Path, default=None):
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))

def _api_catalog():
    """The only approved catalog access point (also in the frozen build)."""
    return _legacy_catalog()


def _write_source_catalog(approved, expected_fingerprint):
    """Safely update character_API.py's literal catalog assignment in source mode.

    Use AST source spans; for existing IDs rewrite only modified entries,
    retaining other entries and source code. Back up before replacement.
    """
    import ast
    import pprint
    import tempfile
    import character_API as api
    api._validate_approved_catalog(approved)
    source = Path(api.__file__).resolve()
    original = source.read_text(encoding="utf-8")
    tree = ast.parse(original, filename=str(source))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "IMPROVEMENT_CATALOG"
                           for t in node.targets)]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Dict):
        raise RuntimeError("Cannot safely locate a literal IMPROVEMENT_CATALOG in character_API.py")
    original_options = ast.literal_eval(assignments[0].value)
    original_catalog = _api_catalog()
    if _fingerprint(original_catalog) != expected_fingerprint:
        raise RuntimeError("character_API.py changed since this suggestion was created. Review against the latest API.")
    # Detect source-file edits that have not been reloaded into the module.
    if original_options != original_catalog["improvements"]:
        raise RuntimeError("character_API.py was edited while DID was running. Restart DID before approving.")
    if not isinstance(approved, dict):
        raise ValueError("Approved Improvements must be a mapping")
    node = assignments[0].value
    lines = original.splitlines(keepends=True)
    def offset(line, col):
        return sum(len(line_text) for line_text in lines[:line - 1]) + col
    changes = []
    if set(approved) == set(original_options):
        for key_node, value_node in zip(node.keys, node.values):
            key = ast.literal_eval(key_node)
            if approved[key] != original_options[key]:
                start = offset(value_node.lineno, value_node.col_offset)
                end = offset(value_node.end_lineno, value_node.end_col_offset)
                indent = ' ' * value_node.col_offset
                replacement = pprint.pformat(approved[key], width=95, sort_dicts=False)
                replacement = replacement.replace('\n', '\n' + indent)
                changes.append((start, end, replacement))
    else:
        # Additions/deletions necessarily change the dictionary's structure.
        changes.append((offset(node.lineno, node.col_offset),
                        offset(node.end_lineno, node.end_col_offset),
                        pprint.pformat(approved, width=95, sort_dicts=False)))
    rewritten = original
    for start, end, replacement in sorted(changes, reverse=True):
        rewritten = rewritten[:start] + replacement + rewritten[end:]
    compile(rewritten, str(source), 'exec')
    import shutil
    stamp = _dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = source.with_name(source.name + '.backup-' + stamp)
    shutil.copy2(source, backup)
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=source.parent,
                                         prefix='.did_api_', suffix='.tmp', delete=False) as handle:
            handle.write(rewritten)
            temp_name = handle.name
        os.replace(temp_name, source)
    except Exception:
        raise RuntimeError('Could not update character_API.py; the original is backed up at ' + str(backup))
    return backup


def initialize_storage():
    _ensure_dirs()
    # Existing pre-refactor drafts have no trustworthy base version. Keep an
    # archive rather than allowing one stale draft to re-publish an old catalog.
    source = _api_catalog()
    if DRAFT_FILE.exists() and not (DATA_DIR / "draft_api_base.sha256").exists():
        draft = _read_json(DRAFT_FILE)
        if draft != source:
            stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            archived = DATA_DIR / ("legacy_draft_before_api_refactor_" + stamp + ".json")
            _write_json(archived, draft)
            _write_json(DRAFT_FILE, source)
        (DATA_DIR / "draft_api_base.sha256").write_text(
            _fingerprint(source), encoding="ascii")
    if not DRAFT_FILE.exists():
        _write_json(DRAFT_FILE, source)
        (DATA_DIR / "draft_api_base.sha256").write_text(
            _fingerprint(source), encoding="ascii")
    # On a subsequent source edit, rebase the draft only when it has no
    # unpublished edits. Otherwise preserve it but refuse a stale submission.
    marker = DATA_DIR / "draft_api_base.sha256"
    recorded = marker.read_text(encoding="ascii").strip()
    if recorded != _fingerprint(source):
        current_draft = _read_json(DRAFT_FILE)
        if recorded == _fingerprint(current_draft):
            _write_json(DRAFT_FILE, source)
            marker.write_text(_fingerprint(source), encoding="ascii")
        # Otherwise submit_draft() will reject until explicitly reset/rebased.

def live_catalog():
    initialize_storage()
    # Source edits to character_API.py have absolute priority. In a frozen
    # release that same API module alone loads the persistent approved file.
    return _api_catalog()

def draft_catalog():
    initialize_storage()
    return _read_json(DRAFT_FILE)

def reset_draft():
    live = live_catalog()
    _write_json(DRAFT_FILE, live)
    (DATA_DIR / "draft_api_base.sha256").write_text(
        _fingerprint(live), encoding="ascii")

def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return s or "new_improvement"

def _html_to_plain(text: str) -> str:
    """Plain preview without exposing HTML or legacy markdown markers."""
    class TextOnly(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
        def handle_starttag(self, tag, attrs):
            if tag.lower() in ("br", "p", "li"):
                self.parts.append("\n")
    parser = TextOnly()
    parser.feed(str(text or ""))
    return re.sub(r"\*\*([^*\n]+)\*\*", r"\1", "".join(parser.parts))

def _plain_to_html(text: str) -> str:
    """Only author-selected **spans** become bold in the catalog HTML."""
    import html
    text = html.escape(str(text or ""), quote=False)
    text = re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", text)
    return text.replace("\n", "<br>")

def _snapshot(catalog, label="approved"):
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = HISTORY_DIR / f"{stamp}-{label}.json"
    _write_json(path, catalog)
    return path

def _fingerprint(obj):
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

# ---------- Validation ----------
def validate_catalog(cat: dict) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    if not isinstance(cat, dict):
        return ["Catalog is not an object."], warnings
    imps = cat.get("improvements")
    if not isinstance(imps, dict):
        return ["Catalog has no valid improvements collection."], warnings

    seen_ids = set()
    for key, imp in imps.items():
        where = f"Improvement '{key}'"
        if not isinstance(imp, dict):
            errors.append(f"{where} is not a valid improvement.")
            continue
        iid = imp.get("id", key)
        if iid in seen_ids:
            errors.append(f"Duplicate improvement ID: {iid}")
        seen_ids.add(iid)
        if not str(imp.get("name", "")).strip():
            errors.append(f"{where} has no name.")
        cost = imp.get("cost", 0)
        if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
            errors.append(f"{where} has an invalid cost: {cost!r}")
        if not isinstance(imp.get("description", ""), str):
            errors.append(f"{where} description must be text.")

        for coll_name in ("empowerments",):
            coll = imp.get(coll_name, [])
            if coll is not None and not isinstance(coll, list):
                errors.append(f"{where}: {coll_name} must be a list.")
            for e in coll or []:
                if not isinstance(e, dict):
                    errors.append(f"{where}: invalid empowerment entry.")
                    continue
                if not str(e.get("name", "")).strip():
                    errors.append(f"{where}: an empowerment has no name.")
                ec = e.get("cost", 0)
                if not isinstance(ec, (int, float)) or isinstance(ec, bool) or ec < 0:
                    errors.append(f"{where} / {e.get('name','?')}: invalid cost.")

        se = imp.get("scaling_empowerments", {})
        if se is not None and not isinstance(se, dict):
            errors.append(f"{where}: scaling empowerments must be a mapping.")
        for sid, group in (se or {}).items():
            if not isinstance(group, dict):
                errors.append(f"{where} / {sid}: invalid scaling empowerment.")
                continue
            steps = group.get("steps", [])
            if group.get("rule") == "ordered" and not steps:
                warnings.append(f"{where} / {group.get('name',sid)} has no levels.")
            for n, step in enumerate(steps or [], 1):
                if not isinstance(step, dict):
                    errors.append(f"{where} / {sid} level {n}: invalid level.")
                    continue
                if "cost" not in step:
                    errors.append(f"{where} / {sid} level {n}: missing cost.")
                elif not isinstance(step["cost"], (int, float)) or step["cost"] < 0:
                    errors.append(f"{where} / {sid} level {n}: invalid cost.")

        # Known cross-reference: replacement improvements.
        for emp in imp.get("empowerments", []) or []:
            for effect in emp.get("effects", []) or []:
                if effect.get("type") == "replace_improvement":
                    target = effect.get("add")
                    if target and target not in imps:
                        errors.append(
                            f"{where} / {emp.get('name','empowerment')} replaces itself "
                            f"with missing improvement '{target}'."
                        )

    arrays = cat.get("ability_arrays", [])
    if not isinstance(arrays, list):
        errors.append("Ability arrays are invalid.")
    else:
        for arr in arrays:
            dice = arr.get("dice", []) if isinstance(arr, dict) else []
            if len(dice) != 6:
                errors.append(f"Ability array '{arr.get('name','?')}' must contain 6 dice.")

    return errors, warnings

# ---------- Diff / suggestions ----------
def diff_catalog(old: dict, new: dict) -> List[dict]:
    changes = []
    oi, ni = old.get("improvements", {}), new.get("improvements", {})
    for iid in sorted(set(oi) | set(ni)):
        if iid not in oi:
            changes.append({"kind": "add_improvement", "id": iid,
                            "summary": f"Add improvement: {ni[iid].get('name', iid)}",
                            "old": None, "new": ni[iid]})
            continue
        if iid not in ni:
            changes.append({"kind": "remove_improvement", "id": iid,
                            "summary": f"Remove improvement: {oi[iid].get('name', iid)}",
                            "old": oi[iid], "new": None})
            continue
        a, b = oi[iid], ni[iid]
        for field in ("name", "cost", "description", "owned_summary",
                      "owned_description", "summary", "tags", "purchase_rule",
                      "requires_choices"):
            if a.get(field) != b.get(field):
                changes.append({"kind": "field", "id": iid, "field": field,
                                "summary": f"{b.get('name', iid)}: change {field}",
                                "old": a.get(field), "new": b.get(field)})
        # Group complex empowerment/mechanics changes so the owner sees them clearly.
        for field, label in (
            ("empowerments", "normal empowerments"),
            ("scaling_empowerments", "scaling empowerments"),
            ("empowerment_groups", "empowerment groups"),
            ("effects", "automatic effects"),
            ("creates", "created companion/object"),
            ("scaling_values", "changing values"),
        ):
            if a.get(field) != b.get(field):
                changes.append({"kind": "field", "id": iid, "field": field,
                                "summary": f"{b.get('name', iid)}: change {label}",
                                "old": a.get(field), "new": b.get(field)})
    return changes

def submit_draft(author="Editor"):
    live = live_catalog()
    marker = DATA_DIR / "draft_api_base.sha256"
    if marker.exists() and marker.read_text(encoding="ascii").strip() != _fingerprint(live):
        raise RuntimeError("character_API.py changed while this draft was being edited. "
                           "Archive the old draft and reset it to the current API before submitting.")
    draft = draft_catalog()
    errors, warnings = validate_catalog(draft)
    changes = diff_catalog(live, draft)
    pending = {
        "submitted_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "author": author or "Editor",
        "base_fingerprint": _fingerprint(live),
        "errors": errors,
        "warnings": warnings,
        "changes": changes,
        "draft": draft,
        "source": "local_draft",
    }
    _write_json(PENDING_FILE, pending)
    return pending

def pending_changes():
    initialize_storage()
    return _read_json(PENDING_FILE, None)

def export_suggestion(path):
    """Export the pending proposal to a shareable JSON file; no network calls."""
    pending = pending_changes()
    if not pending or not pending.get("changes"):
        raise RuntimeError("Submit a nonempty suggestion before exporting it.")
    _write_json(Path(path), pending)
    return Path(path)

def import_suggestion(path):
    """Import, re-diff and validate a proposal without changing the live API."""
    source = Path(path)
    if source.stat().st_size > 5_000_000:
        raise ValueError("Proposal exceeds the 5 MB size limit.")
    incoming = _read_json(source)
    return accept_suggestion(incoming)


def accept_suggestion(incoming, cloud_id=None):
    """Treat remotely received proposals exactly like imported JSON proposals."""
    if not isinstance(incoming, dict) or not isinstance(incoming.get("draft"), dict):
        raise ValueError("This is not a DID Improvement Editor proposal.")
    live = live_catalog()
    if incoming.get("base_fingerprint") != _fingerprint(live):
        raise ValueError("The proposal is based on a different approved catalog. Ask the contributor to update before resubmitting.")
    draft = incoming["draft"]
    if (draft.get("stat_names") != live.get("stat_names")
            or draft.get("ability_arrays") != live.get("ability_arrays")):
        raise ValueError("This proposal changes stat names or ability arrays, which the Improvements review cannot show or approve.")
    errors, warnings = validate_catalog(draft)
    changes = diff_catalog(live, draft)
    if not changes:
        raise ValueError("This proposal contains no changes.")
    proposal = {
        "submitted_at": str(incoming.get("submitted_at", "unknown"))[:80],
        "author": str(incoming.get("author", "Editor"))[:100],
        "base_fingerprint": _fingerprint(live),
        "errors": errors,
        "warnings": warnings,
        "changes": changes,
        "draft": draft,
        "source": "online" if cloud_id else "imported",
        "cloud_id": str(cloud_id) if cloud_id else None,
    }
    _write_json(PENDING_FILE, proposal)
    return proposal

def _apply_change(cat, change):
    imps = cat["improvements"]
    iid = change["id"]
    kind = change["kind"]
    if kind == "add_improvement":
        imps[iid] = copy.deepcopy(change["new"])
    elif kind == "remove_improvement":
        imps.pop(iid, None)
    elif kind == "field":
        if iid not in imps:
            return
        field = change["field"]
        if change["new"] is None:
            imps[iid].pop(field, None)
        else:
            imps[iid][field] = copy.deepcopy(change["new"])

def approve_pending(selected_indices: Optional[List[int]] = None):
    p = pending_changes()
    if not p:
        raise RuntimeError("There are no pending changes.")
    if p.get("errors"):
        raise RuntimeError("Pending changes fail technical validation and cannot be approved.")
    live = live_catalog()
    if p.get("base_fingerprint") != _fingerprint(live):
        raise RuntimeError("The live catalog changed after this suggestion was submitted. Re-submit it first.")
    api_catalog = live_catalog()
    changes = p["changes"]
    if selected_indices is None:
        selected_indices = list(range(len(changes)))
    for i in selected_indices:
        _apply_change(live, changes[i])
    errors, warnings = validate_catalog(live)
    if errors:
        raise RuntimeError("Selected changes would make the live catalog invalid:\n- " + "\n- ".join(errors))
    # Approval writes through character_API, never bypassing that module.
    import character_API as api
    api._validate_approved_catalog(live["improvements"])
    _snapshot(api_catalog, "before-approval")
    if getattr(sys, "frozen", False):
        import hashlib
        # The packaged base is recorded by character_API before applying the
        # external approval; reuse its stable fingerprint across approvals.
        base_fingerprint = getattr(api, "_PACKAGED_API_SHA256", None)
        if not base_fingerprint:
            raise RuntimeError("Cannot identify the packaged API version safely")
        _write_json(LIVE_FILE, {**api_catalog, "improvements": live["improvements"],
                                "api_base_sha256": base_fingerprint})
    else:
        _write_source_catalog(live["improvements"], p["base_fingerprint"])
    api.apply_approved_catalog(live["improvements"])
    if not getattr(sys, "frozen", False):
        _write_json(LIVE_FILE, {**_api_catalog(),
                                "api_base_sha256": _fingerprint(api.IMPROVEMENT_CATALOG)})
    _write_json(DRAFT_FILE, _api_catalog())
    (DATA_DIR / "draft_api_base.sha256").write_text(
        _fingerprint(_api_catalog()), encoding="ascii")
    PENDING_FILE.unlink(missing_ok=True)
    return warnings

def reject_pending():
    PENDING_FILE.unlink(missing_ok=True)

def export_live_to_python(target: Optional[Path] = None):
    """
    Optional compatibility export.
    Existing sheet code can instead call get_live_api() directly.
    """
    cat = live_catalog()
    target = Path(target or (BASE_DIR / "character_API_generated.py"))
    body = "# Generated by Improvement Editor. Do not edit by hand.\n\n"
    body += "STAT_NAMES = " + repr(cat["stat_names"]) + "\n\n"
    body += "ABILITY_ARRAYS = " + repr(cat["ability_arrays"]) + "\n\n"
    body += "IMPROVEMENT_CATALOG = " + repr(cat["improvements"]) + "\n"
    target.write_text(body, encoding="utf-8")
    return target

def get_live_api():
    """Use this from the main sheet if you want the approved catalog in memory."""
    c = live_catalog()
    return c["stat_names"], c["ability_arrays"], c["improvements"]



def add_clean_combo_arrow(combo):
    """Use a simple chevron instead of the native square combo indicator."""
    arrow = QtWidgets.QLabel("⌄", combo)
    transparent_attr = (
        QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        if QT_API in ("PyQt6", "PySide6")
        else QtCore.Qt.WA_TransparentForMouseEvents
    )
    align_center = (
        QtCore.Qt.AlignmentFlag.AlignCenter
        if QT_API in ("PyQt6", "PySide6")
        else QtCore.Qt.AlignCenter
    )
    arrow.setAttribute(transparent_attr)
    arrow.setAlignment(align_center)
    arrow.setStyleSheet(
        "background: transparent; border: none; color: #6c5428;"
        "font-family: Georgia; font-size: 15px; font-weight: bold;"
    )
    arrow.setFixedWidth(24)

    old_resize = combo.resizeEvent
    def _resize(event):
        old_resize(event)
        arrow.setGeometry(combo.width() - 25, 0, 24, combo.height())
        arrow.raise_()

    combo.resizeEvent = _resize
    arrow.setGeometry(combo.width() - 25, 0, 24, combo.height())
    combo._clean_arrow_label = arrow

def hide_spinbox_arrows(spinbox):
    """Keep numeric typing, but remove the up/down arrow controls."""
    try:
        spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    except AttributeError:
        spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)

def style_standard_dialog_buttons(box, middle_widget=None):
    """Use one predictable action order: Cancel left, optional action center, OK right."""
    try:
        ok_enum = QtWidgets.QDialogButtonBox.StandardButton.Ok
        cancel_enum = QtWidgets.QDialogButtonBox.StandardButton.Cancel
    except AttributeError:
        ok_enum = QtWidgets.QDialogButtonBox.Ok
        cancel_enum = QtWidgets.QDialogButtonBox.Cancel

    ok = box.button(ok_enum)
    cancel = box.button(cancel_enum)
    if ok is not None:
        ok.setObjectName("PrimaryButton")
        ok.setFixedSize(88, 28)
    if cancel is not None:
        cancel.setFixedSize(88, 28)

    layout = box.layout()
    if layout is not None and ok is not None and cancel is not None:
        layout.removeWidget(ok)
        layout.removeWidget(cancel)
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget not in (ok, cancel, middle_widget):
                widget.setParent(None)
        layout.addWidget(cancel)
        layout.addStretch(1)
        if middle_widget is not None:
            middle_widget.setFixedSize(88, 28)
            layout.addWidget(middle_widget)
            layout.addStretch(1)
        layout.addWidget(ok)

# ---------- Reusable UI widgets ----------

class TagPickerButton(QtWidgets.QToolButton):
    """
    Reliable multi-select tag picker.

    A QComboBox is designed around one current item. The old implementation
    tried to use that current-item field as a multi-select summary, so clicking
    a tag could replace the field text with the highlighted tag even though
    several different tags were actually checked.

    This version uses a tool button + menu of real checkboxes instead:
    - checked boxes are the selected tags;
    - the field always shows the selected-tag summary;
    - selecting one tag never replaces the summary with the highlighted row;
    - the menu stays open while several tags are checked/unchecked.
    """
    tagsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._tags = []
        self._available = []

        self.setObjectName("TagPickerField")

        try:
            popup_mode = (
                QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
            )
        except AttributeError:
            popup_mode = QtWidgets.QToolButton.InstantPopup

        self.setPopupMode(popup_mode)

        try:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        except AttributeError:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Fixed,
            )

        self._menu = QtWidgets.QMenu(self)
        self._menu.setObjectName("TagPickerMenu")
        self._menu.setFixedWidth(300)
        self.setMenu(self._menu)

        self._menu.aboutToShow.connect(
            self._prepare_menu
        )

        self._rebuild()


    def set_available_tags(self, tags):
        self._available = sorted(
            {
                str(tag).strip()
                for tag in (tags or [])
                if str(tag).strip()
            },
            key=str.lower,
        )

        self._rebuild()


    def set_tags(self, tags):
        clean = []

        for tag in tags or []:
            tag = str(tag).strip()

            if tag and tag not in clean:
                clean.append(tag)

        self._tags = clean
        self._rebuild()


    def tags(self):
        return list(self._tags)


    def _display_name(self, tag):
        return str(tag).replace(
            "_",
            " ",
        ).title()


    def _rebuild(self):
        self._menu.clear()

        all_tags = sorted(
            set(self._available)
            | set(self._tags),
            key=str.lower,
        )

        for tag in all_tags:
            row = QtWidgets.QWidget(
                self._menu
            )
            row.setFixedWidth(280)

            layout = QtWidgets.QHBoxLayout(
                row
            )

            layout.setContentsMargins(
                10,
                3,
                10,
                3,
            )

            layout.setSpacing(6)

            checkbox = QtWidgets.QCheckBox(
                self._display_name(tag),
                row,
            )

            checkbox.setChecked(
                tag in self._tags
            )

            checkbox.toggled.connect(
                lambda checked, current_tag=tag:
                    self._tag_toggled(
                        current_tag,
                        checked,
                    )
            )

            layout.addWidget(
                checkbox
            )

            action = QtWidgets.QWidgetAction(
                self._menu
            )

            action.setDefaultWidget(
                row
            )

            self._menu.addAction(
                action
            )

        if all_tags:
            self._menu.addSeparator()

        add_action = self._menu.addAction(
            "+ Add new tag..."
        )

        add_action.triggered.connect(
            self._add_new_tag
        )

        self._refresh_text()


    def _tag_toggled(
        self,
        tag,
        checked,
    ):
        if checked:
            if tag not in self._tags:
                self._tags.append(tag)

        else:
            if tag in self._tags:
                self._tags.remove(tag)

        self._refresh_text()
        self.tagsChanged.emit()


    def _refresh_text(self):
        full_text = ", ".join(
            self._display_name(tag)
            for tag in self._tags
        )

        if not full_text:
            full_text = "Choose tags..."

        # Keep the field compact even if many tags are selected.
        available_width = max(
            80,
            self.width() - 36,
        )

        shown_text = (
            self.fontMetrics()
            .elidedText(
                full_text,
                (
                    QtCore.Qt.TextElideMode.ElideRight
                    if QT_API in ("PyQt6", "PySide6")
                    else QtCore.Qt.ElideRight
                ),
                available_width,
            )
        )

        self.setText(
            shown_text
        )

        self.setToolTip(
            ""
            if full_text == "Choose tags..."
            else full_text
        )


    def _prepare_menu(self):
        self._menu.setMinimumWidth(
            max(
                self.width(),
                220,
            )
        )


    def resizeEvent(
        self,
        event,
    ):
        super().resizeEvent(
            event
        )

        self._refresh_text()


    def _add_new_tag(self):
        value, ok = (
            QtWidgets.QInputDialog
            .getText(
                self,
                "Add Tag",
                "New tag name:",
            )
        )

        if (
            not ok
            or not value.strip()
        ):
            return

        tag = _slug(
            value
        )

        if not tag:
            return

        if tag not in self._available:
            self._available.append(
                tag
            )

            self._available.sort(
                key=str.lower
            )

        if tag not in self._tags:
            self._tags.append(
                tag
            )

        self._rebuild()
        self.tagsChanged.emit()


class AutoGrowTextEdit(QtWidgets.QTextEdit):
    """Text box that grows downward with its contents, like the sheet's notes."""
    def __init__(self, parent=None, min_height=30, max_height=180):
        super().__init__(parent)
        self._min_h = min_height
        self._max_h = max_height
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff if QT_API in ("PyQt6","PySide6")
            else QtCore.Qt.ScrollBarAlwaysOff
        )
        self.document().contentsChanged.connect(self._fit_height)
        self._fit_height()

    def _fit_height(self):
        self.document().setTextWidth(max(40, self.viewport().width()))
        margins = self.contentsMargins()
        h = int(self.document().size().height() + margins.top() + margins.bottom() + 12)
        self.setFixedHeight(max(self._min_h, min(self._max_h, h)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

class _SafeRichHTML(HTMLParser):
    """Accept only formatting supported by DID's Qt rich-text labels."""
    ALLOWED = {"b", "strong", "i", "em", "u", "ul", "ol", "li", "br", "p"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.ALLOWED:
            if tag == "br":
                self.parts.append("<br>")
            else:
                self.parts.append("<" + tag + ">")
                self.open_tags.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.open_tags:
            # Close unbalanced imported markup safely.
            while self.open_tags:
                current = self.open_tags.pop()
                self.parts.append("</" + current + ">")
                if current == tag:
                    break

    def handle_data(self, data):
        # Support older descriptions that already contain explicit **bold**.
        # No markers are displayed in the visual editor.
        escaped = _html.escape(data, quote=False)
        escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", escaped)
        escaped = escaped.replace("\r\n", "\n").replace("\n", "<br>")
        self.parts.append(escaped)

    def html(self):
        for tag in reversed(self.open_tags):
            self.parts.append("</" + tag + ">")
        return "".join(self.parts)


def _safe_rich_html(value):
    sanitizer = _SafeRichHTML()
    sanitizer.feed(str(value or ""))
    return sanitizer.html()


# The catalog stores stable {rule_identifiers}; the authoring surface shows
# recognizable, non-editable-looking labels instead of raw underscores.
# The editor stores the original identifier in a QTextCharFormat anchor href.
_VARIABLE_RE = re.compile(r"d\{buddy_die\}|\{[A-Za-z][A-Za-z_0-9]*\}")
_VARIABLE_HREF_PREFIX = "did-variable:"
_VARIABLE_NAMES = {
    "buddy_die": "Buddy die",
    "buddy_hearts": "Buddy Hearts",
    "buddy_name": "Companion name",
    "buddy_perk": "Companion perk",
}


def _variable_label(key):
    if key in _VARIABLE_NAMES:
        return _VARIABLE_NAMES[key]
    return re.sub(r"_+", " ", key).strip().capitalize()


def _render_catalog_variables(value, *, editor=False):
    """Show variable labels without altering source ids or HTML elements.

    Sanitize first; substitute only text nodes, never inside HTML attributes.
    Unresolved variables in the preview are *labels*, not fabricated stats.
    """
    safe = _safe_rich_html(value)
    def text_node(text):
        def one(token):
            literal = token.group(0)
            die_prefix = literal.startswith("d{")
            key = literal[2:-1] if die_prefix else literal[1:-1]
            label = _html.escape(_variable_label(key), quote=False)
            variable_color = _editor_theme_color("blue_action", "#2f5f91")
            if editor:
                ref = ("d:" if die_prefix else "") + key
                return (f'<a href="{_VARIABLE_HREF_PREFIX}{ref}" '
                        f'style="color:{variable_color};text-decoration:none;">{label}</a>')
            return f'<span style="color:{variable_color};font-weight:600;">{label}</span>'
        return _VARIABLE_RE.sub(one, text)
    # Handle a leading plain-text node as well as text between HTML tags.
    return "".join(part if part.startswith("<") else text_node(part)
                   for part in re.split(r"(<[^>]+>)", safe) if part)



def _editor_document_html(document):
    """Serialize visual formatting without Qt's arbitrary HTML/CSS output.

    Keep curly-brace rule placeholders untouched. Only bold, italic,
    underline, line breaks, and ordered/unordered lists are allowed.
    """
    result = []
    active_list = None
    block = document.begin()
    first = True
    while block.isValid():
        text_list = block.textList()
        list_type = None
        if text_list is not None:
            style = text_list.format().style()
            decimal = QtGui.QTextListFormat.Style.ListDecimal
            list_type = "ol" if style == decimal else "ul"
        if active_list != list_type:
            if active_list:
                result.append(f"</{active_list}>")
            if list_type:
                result.append(f"<{list_type}>")
            active_list = list_type
        elif not first and list_type is None:
            result.append("<br>")
        if list_type:
            result.append("<li>")
        fragment_it = block.begin()
        while not fragment_it.atEnd():
            fragment = fragment_it.fragment()
            if fragment.isValid():
                fmt = fragment.charFormat()
                href = fmt.anchorHref() if fmt.isAnchor() else ""
                if href.startswith(_VARIABLE_HREF_PREFIX):
                    # A variable stays bound to its original catalog id even
                    # after surrounding text is edited or formatted.
                    token_id = href[len(_VARIABLE_HREF_PREFIX):]
                    die_prefix = token_id.startswith("d:")
                    key = token_id[2:] if die_prefix else token_id
                    text = (("d" if die_prefix else "") + "{" + key + "}"
                            if re.fullmatch(r"[A-Za-z][A-Za-z_0-9]*", key)
                            else _html.escape(fragment.text(), quote=False))
                else:
                    text = _html.escape(fragment.text(), quote=False).replace("\u2028", "<br>")
                if fmt.fontWeight() >= QtGui.QFont.Weight.Bold:
                    text = "<b>" + text + "</b>"
                if fmt.fontItalic():
                    text = "<i>" + text + "</i>"
                if fmt.fontUnderline():
                    text = "<u>" + text + "</u>"
                result.append(text)
            fragment_it += 1
        if list_type:
            result.append("</li>")
        first = False
        block = block.next()
    if active_list:
        result.append(f"</{active_list}>")
    return "".join(result)


class DescriptionEdit(QtWidgets.QTextEdit):
    """Real WYSIWYG; underlying catalog remains limited HTML."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ImprovementRichEditor")
        self.setAcceptRichText(True)
        # Size from content rather than leaving a huge empty page for short
        # rules. Long descriptions scroll within a capped writing surface.
        self.setMinimumHeight(88)
        self.setMaximumHeight(290)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Fixed)
        self._auto_fit_enabled = True
        self.document().contentsChanged.connect(self._queue_fit_height)
        self._fit_queued = False
        self.setPlaceholderText("Write what players should see…")
        self.setTabChangesFocus(True)
        self.setToolTip("Blue labels are rule variables. Their original IDs are preserved when you save.")
        self._queue_fit_height()

    def set_auto_fit_enabled(self, enabled):
        self._auto_fit_enabled = bool(enabled)
        if self._auto_fit_enabled:
            self._queue_fit_height()

    def _queue_fit_height(self):
        if not getattr(self, "_auto_fit_enabled", True):
            return
        if self._fit_queued:
            return
        self._fit_queued = True
        QtCore.QTimer.singleShot(0, self._fit_height)

    def _fit_height(self):
        self._fit_queued = False
        paired = getattr(self, "_paired_fit", None)
        if callable(paired):
            paired()
            return
        width = max(200, self.viewport().width())
        self.document().setTextWidth(width)
        height = int(self.document().size().height() + 24)
        needed = max(88, min(250, height))
        if needed != self.height():
            self.setFixedHeight(needed)
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded if height > 250
            else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._queue_fit_height()

    def load_catalog_html(self, value):
        self._original_html = str(value or "")
        self.setHtml(_render_catalog_variables(self._original_html, editor=True))
        self.document().setModified(False)

    def catalog_html(self):
        # Non-description edits must not rewrite or normalize untouched
        # catalog descriptions, placeholders, or existing markup.
        if not self.document().isModified() and hasattr(self, "_original_html"):
            return self._original_html
        return _editor_document_html(self.document())

    def toggle_format(self, kind):
        cursor = self.textCursor()
        fmt = QtGui.QTextCharFormat()
        if kind == "bold":
            fmt.setFontWeight(QtGui.QFont.Weight.Normal if cursor.charFormat().fontWeight() >= QtGui.QFont.Weight.Bold else QtGui.QFont.Weight.Bold)
        elif kind == "italic":
            fmt.setFontItalic(not cursor.charFormat().fontItalic())
        elif kind == "underline":
            fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        cursor.mergeCharFormat(fmt)
        self.mergeCurrentCharFormat(fmt)
        self.setFocus()

    def toggle_list(self, numbered=False):
        cursor = self.textCursor()
        existing = cursor.currentList()
        fmt = QtGui.QTextListFormat()
        fmt.setStyle(QtGui.QTextListFormat.Style.ListDecimal if numbered else QtGui.QTextListFormat.Style.ListDisc)
        if existing is None:
            cursor.createList(fmt)
        else:
            existing_fmt = existing.format()
            if existing_fmt.style() == fmt.style():
                # QTextEdit's standard list toggle removes the selected
                # blocks from the list without touching their text.
                block = cursor.block()
                cursor.setBlockFormat(QtGui.QTextBlockFormat())
            else:
                existing.setFormat(fmt)
        self.setFocus()

    def bold_selection(self):
        self.toggle_format("bold")

    def keyPressEvent(self, event):
        for shortcut, kind in ((QtGui.QKeySequence.StandardKey.Bold, "bold"),
                               (QtGui.QKeySequence.StandardKey.Italic, "italic"),
                               (QtGui.QKeySequence.StandardKey.Underline, "underline")):
            if event.matches(shortcut):
                self.toggle_format(kind)
                event.accept()
                return
        super().keyPressEvent(event)


class ImprovementPreviewBrowser(QtWidgets.QTextBrowser):
    def __init__(self):
        super().__init__()
        self.refresh_callback = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.refresh_callback is not None:
            QtCore.QTimer.singleShot(0, self.refresh_callback)


def description_editor_with_toolbar(editor, caption="Player preview", heading=None, cost=None):
    holder = QtWidgets.QWidget()
    holder.setObjectName("DescriptionWritingSurface")
    # Keep this page exactly as tall as its real controls require.  The outer
    # editor pane owns scrolling; reserving a large minimum height here creates
    # a blank band between the writing surface and the live preview.
    holder.setMinimumHeight(0)
    holder.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                         QtWidgets.QSizePolicy.Policy.Fixed)
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(7)
    toolbar = QtWidgets.QHBoxLayout()
    # Keep formatting controls visually separate.  A 3 px gap makes the
    # bordered tool buttons read as if they are touching/overlapping.
    toolbar.setSpacing(9)
    controls = (("B", "Bold (Ctrl+B)", lambda: editor.toggle_format("bold")),
                ("I", "Italic (Ctrl+I)", lambda: editor.toggle_format("italic")),
                ("U", "Underline (Ctrl+U)", lambda: editor.toggle_format("underline")),
                ("•", "Bulleted list", lambda: editor.toggle_list(False)),
                ("1.", "Numbered list", lambda: editor.toggle_list(True)))
    for text, tooltip, action in controls:
        button = QtWidgets.QToolButton()
        button.setObjectName("FormatToolButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(38, 32)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(action)
        toolbar.addWidget(button)
    toolbar.addStretch()
    layout.addLayout(toolbar)
    layout.addWidget(editor)

    row = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(caption)
    label.setObjectName("MutedText")
    row.addWidget(label)
    row.addStretch()
    hint = QtWidgets.QLabel("Blue labels represent character-specific values")
    hint.setObjectName("MutedText")
    row.addWidget(hint)
    layout.addLayout(row)

    preview = ImprovementPreviewBrowser()
    preview.setObjectName("ImprovementLivePreview")
    preview.setOpenLinks(False)
    preview.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    preview.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    preview.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    preview.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                          QtWidgets.QSizePolicy.Policy.Fixed)
    preview.setMinimumHeight(72)
    preview.setMaximumHeight(265)
    layout.addWidget(preview)

    def update_preview(*_):
        title = _html.escape(str(heading() if heading else "Improvement"), quote=False)
        price = f" · {cost()} IP" if cost is not None else ""
        body = _render_catalog_variables(editor.catalog_html())
        text_color = _editor_theme_color("fantasy_text", "#25190f")
        muted_color = _editor_theme_color("fantasy_text_muted", "#765d34")
        markup = (
            f'<div style="font-family:Georgia;color:{text_color};font-size:12pt;">'
            f'<b>{title}</b><span style="color:{muted_color};font-size:10pt;">{price}</span>'
            f'<div style="margin-top:5px;">{body}</div></div>')
        if getattr(preview, "_last_markup", None) != markup:
            preview._last_markup = markup
            preview.setHtml(markup)
        # Keep the writing box and its preview visually balanced.  They use
        # one shared height based on whichever side needs more room.
        editor.document().setTextWidth(max(200, editor.viewport().width()))
        preview.document().setTextWidth(max(200, preview.viewport().width()))
        editor_needed = int(editor.document().size().height()) + 24
        preview_needed = int(preview.document().size().height()) + 16
        shared = max(88, min(250, max(editor_needed, preview_needed)))
        if editor.height() != shared:
            editor.setFixedHeight(shared)
        if preview.height() != shared:
            preview.setFixedHeight(shared)
        editor.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded if editor_needed > shared
            else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded if preview_needed > shared
            else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    editor._paired_fit = update_preview
    editor.textChanged.connect(update_preview)
    editor.preview_update = update_preview
    preview.refresh_callback = update_preview
    update_preview()
    editor.live_preview = preview
    return holder



class _DoubleClickLabel(QtWidgets.QLabel):
    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        event.accept()


class InlineTextValue(QtWidgets.QWidget):
    """Label that becomes a line edit on double-click."""
    textChanged = Signal(str)

    def __init__(self, text="", prominent=False, placeholder="", parent=None):
        super().__init__(parent)
        self._value = str(text or "")
        self._placeholder = placeholder
        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self.label = _DoubleClickLabel()
        self.label.setObjectName("InlineTitleValue" if prominent else "InlineMetaValue")
        self.label.setCursor(QtCore.Qt.CursorShape.IBeamCursor)
        self.label.setToolTip("Double-click to edit")
        self.editor = QtWidgets.QLineEdit()
        self.editor.setObjectName("InlineTitleEditor" if prominent else "InlineMetaEditor")
        self.editor.setPlaceholderText(placeholder)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(36 if prominent else 30)
        self._stack.addWidget(self.label)
        self._stack.addWidget(self.editor)
        self._stack.setCurrentWidget(self.label)
        self.label.doubleClicked.connect(self.begin_edit)
        self.editor.returnPressed.connect(self.finish_edit)
        self.editor.editingFinished.connect(self.finish_edit)
        self._refresh_label()

    def _refresh_label(self):
        self.label.setText(self._value or self._placeholder or "—")

    def begin_edit(self):
        self.editor.setText(self._value)
        self._stack.setCurrentWidget(self.editor)
        self.editor.setFocus()
        self.editor.selectAll()

    def finish_edit(self):
        if self._stack.currentWidget() is not self.editor:
            return
        value = self.editor.text().strip()
        changed = value != self._value
        self._value = value
        self._refresh_label()
        self._stack.setCurrentWidget(self.label)
        if changed:
            self.textChanged.emit(self._value)

    def setText(self, value):
        self._value = str(value or "")
        self._refresh_label()
        self.editor.setText(self._value)

    def text(self):
        if self._stack.currentWidget() is self.editor:
            return self.editor.text()
        return self._value




class _EditorNumericEntry(QtWidgets.QLineEdit):
    """Integer editor using a text field (reliable under fantasy QSS)."""
    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 99
        self._last = 0
        self._validator = QtGui.QIntValidator(0, 99, self)
        self.setValidator(self._validator)
        self.setText("0")
        self.textChanged.connect(self._emit_value)

    def setRange(self, low, high):
        self._minimum = int(low)
        self._maximum = max(self._minimum, int(high))
        self._validator.setRange(self._minimum, self._maximum)
        self.setValue(self.value())

    def setValue(self, value):
        self.setText(str(max(self._minimum, min(self._maximum, int(value)))))

    def value(self):
        try:
            return max(self._minimum, min(self._maximum, int(self.text())))
        except ValueError:
            return self._minimum

    def _emit_value(self, text):
        if text:
            v = self.value()
            if v != self._last:
                self._last = v
                self.valueChanged.emit(v)

    def focusOutEvent(self, event):
        self.setValue(self.value())
        super().focusOutEvent(event)

class InlineIntValue(QtWidgets.QWidget):
    valueChanged = Signal(int)

    def __init__(self, value=0, suffix=" IP", parent=None):
        super().__init__(parent)
        self._value = int(value or 0)
        self._suffix = suffix
        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self.label = _DoubleClickLabel()
        self.label.setObjectName("InlineMetaValue")
        self.label.setCursor(QtCore.Qt.CursorShape.IBeamCursor)
        self.label.setToolTip("Double-click to edit")
        self.editor = _EditorNumericEntry()
        self.editor.setObjectName("InlineMetaEditor")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(30)
        self.editor.setRange(0, 999)
        self._stack.addWidget(self.label)
        self._stack.addWidget(self.editor)
        self._stack.setCurrentWidget(self.label)
        self.label.doubleClicked.connect(self.begin_edit)
        self.editor.editingFinished.connect(self.finish_edit)
        self._refresh_label()

    def _refresh_label(self):
        self.label.setText(f"{self._value}{self._suffix}")

    def begin_edit(self):
        self.editor.setValue(self._value)
        self._stack.setCurrentWidget(self.editor)
        self.editor.setFocus()
        self.editor.selectAll()

    def finish_edit(self):
        if self._stack.currentWidget() is not self.editor:
            return
        value = int(self.editor.value())
        changed = value != self._value
        self._value = value
        self._refresh_label()
        self._stack.setCurrentWidget(self.label)
        if changed:
            self.valueChanged.emit(self._value)

    def setValue(self, value):
        self._value = int(value or 0)
        self.editor.setValue(self._value)
        self._refresh_label()

    def value(self):
        return int(self.editor.value()) if self._stack.currentWidget() is self.editor else self._value


class InlineComboValue(QtWidgets.QWidget):
    currentTextChanged = Signal(str)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self._items = list(items or [])
        self._value = self._items[0] if self._items else ""
        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self.label = _DoubleClickLabel()
        self.label.setObjectName("InlineMetaValue")
        self.label.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.label.setToolTip("Double-click to edit")
        self.editor = QtWidgets.QComboBox()
        self.editor.setObjectName("InlineMetaEditor")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        # The themed QComboBox has vertical padding in addition to its minimum
        # content height. Give the stacked inline editor enough room so its
        # lower border is never clipped while it is open.
        self.setMinimumHeight(42)
        self.editor.setFixedHeight(40)
        self.editor.addItems(self._items)
        self._stack.addWidget(self.label)
        self._stack.addWidget(self.editor)
        self._stack.setCurrentWidget(self.label)
        self.label.doubleClicked.connect(self.begin_edit)
        self.editor.activated.connect(lambda *_: self.finish_edit())
        self._refresh_label()

    def _refresh_label(self):
        self.label.setText(self._value or "—")

    def begin_edit(self):
        self.editor.setCurrentText(self._value)
        self._stack.setCurrentWidget(self.editor)
        self.editor.setFocus()
        self.editor.showPopup()

    def finish_edit(self):
        if self._stack.currentWidget() is not self.editor:
            return
        value = self.editor.currentText()
        changed = value != self._value
        self._value = value
        self._refresh_label()
        self._stack.setCurrentWidget(self.label)
        if changed:
            self.currentTextChanged.emit(self._value)

    def addItems(self, items):
        for item in items:
            if item not in self._items:
                self._items.append(item)
                self.editor.addItem(item)
        if not self._value and self._items:
            self._value = self._items[0]
            self._refresh_label()

    def setCurrentText(self, value):
        self._value = str(value or "")
        if self.editor.findText(self._value) < 0 and self._value:
            self.editor.addItem(self._value)
        self.editor.setCurrentText(self._value)
        self._refresh_label()

    def currentText(self):
        return self.editor.currentText() if self._stack.currentWidget() is self.editor else self._value


class InlineTagsValue(QtWidgets.QWidget):
    tagsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags = []
        self._available = []
        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self.label = _DoubleClickLabel()
        self.label.setObjectName("InlineMetaValue")
        self.label.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.label.setToolTip("Double-click to choose tags")
        self.editor = TagPickerButton()
        self.editor.setObjectName("InlineTagsEditor")
        self._stack.addWidget(self.label)
        self._stack.addWidget(self.editor)
        self._stack.setCurrentWidget(self.label)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(30)
        self.label.doubleClicked.connect(self.begin_edit)
        self.editor.tagsChanged.connect(self._editor_changed)
        self.editor._menu.aboutToHide.connect(self.finish_edit)
        self._refresh_label()

    @staticmethod
    def _display(tag):
        return str(tag).replace("_", " ").replace("-", " ").title()

    def _refresh_label(self):
        if self._tags:
            self.label.setText("Tags: " + ", ".join(self._display(x) for x in self._tags))
        else:
            self.label.setText("Tags: none")

    def begin_edit(self):
        self.editor.set_available_tags(self._available)
        self.editor.set_tags(self._tags)
        self._stack.setCurrentWidget(self.editor)
        self.editor.setFocus()
        QtCore.QTimer.singleShot(0, self.editor.showMenu)

    def _editor_changed(self):
        values = self.editor.tags()
        changed = values != self._tags
        self._tags = values
        self._refresh_label()
        if changed:
            self.tagsChanged.emit()

    def finish_edit(self):
        if self._stack.currentWidget() is not self.editor:
            return
        self._tags = self.editor.tags()
        self._refresh_label()
        self._stack.setCurrentWidget(self.label)

    def set_available_tags(self, tags):
        self._available = list(tags or [])
        self.editor.set_available_tags(self._available)

    def set_tags(self, tags):
        self._tags = [str(x) for x in (tags or []) if str(x).strip()]
        self.editor.set_tags(self._tags)
        self._refresh_label()

    def tags(self):
        if self._stack.currentWidget() is self.editor:
            return self.editor.tags()
        return list(self._tags)


class ChoiceEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current="", available=None, allow_delete=False):
        super().__init__(parent)
        self.setWindowTitle("Player Choice")
        apply_character_sheet_theme(self)
        self.delete_requested = False
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        root.addWidget(QtWidgets.QLabel("Choice type"))
        self.choice = QtWidgets.QComboBox()
        self.choice.setEditable(True)
        values = list(dict.fromkeys([current] + list(available or [])))
        for value in values:
            if value:
                self.choice.addItem(ChoicesEdit.display_name(value), value)
        if current:
            for i in range(self.choice.count()):
                if self.choice.itemData(i) == current:
                    self.choice.setCurrentIndex(i)
                    break
        root.addWidget(self.choice)
        actions = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setFixedSize(88, 28)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        actions.addStretch(1)
        if allow_delete:
            delete = QtWidgets.QPushButton("Delete")
            delete.setObjectName("DangerButton")
            delete.setFixedSize(88, 28)
            delete.clicked.connect(self._delete)
            actions.addWidget(delete)
            actions.addStretch(1)
        ok = QtWidgets.QPushButton("OK")
        ok.setObjectName("PrimaryButton")
        ok.setFixedSize(88, 28)
        ok.clicked.connect(self.accept)
        actions.addWidget(ok)
        root.addLayout(actions)
        self.setFixedWidth(360)

    def _delete(self):
        self.delete_requested = True
        self.accept()

    def value(self):
        data = self.choice.currentData()
        if data:
            return str(data)
        return _slug(self.choice.currentText())


class AutoHeightListWidget(QtWidgets.QListWidget):
    """A compact list that grows to show every row and never scrolls internally."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._fit_queued = False
        self._last_fit_signature = None
        self.model().rowsInserted.connect(lambda *_: self.schedule_fit())
        self.model().rowsRemoved.connect(lambda *_: self.schedule_fit())
        self.model().modelReset.connect(self.schedule_fit)
        self.model().dataChanged.connect(lambda *_: self.schedule_fit())

    def schedule_fit(self):
        # A bulk refresh can insert many rows in one event-loop turn. Queue
        # one measurement instead of one full font/layout pass per row.
        if self._fit_queued:
            return
        self._fit_queued = True
        QtCore.QTimer.singleShot(0, self._run_scheduled_fit)

    def _run_scheduled_fit(self):
        self._fit_queued = False
        self.fit_to_contents()

    def fit_to_contents(self):
        count = self.count()
        if count <= 0:
            self._last_fit_signature = (0, 0, ())
            self.setFixedHeight(0)
            return

        # QListWidget.sizeHintForRow() can be stale when word wrapping changes
        # after a resize. Measure the text at the *current* viewport width and
        # give each item an explicit height, then make the list exactly tall
        # enough for every row. The outer Catalog Editor scroll area remains
        # the only vertical scrollbar.
        available = max(120, self.viewport().width() - 20)
        signature = (
            count,
            available,
            tuple(self.item(row).text() for row in range(count)),
        )
        if signature == self._last_fit_signature:
            return
        self._last_fit_signature = signature
        fm = QtGui.QFontMetrics(self.font())
        total = 2 * self.frameWidth() + 4
        for row in range(count):
            item = self.item(row)
            bounds = fm.boundingRect(
                QtCore.QRect(0, 0, available, 10000),
                int(QtCore.Qt.TextFlag.TextWordWrap | QtCore.Qt.AlignmentFlag.AlignLeft),
                item.text(),
            )
            row_height = max(38, bounds.height() + 20)
            item.setSizeHint(QtCore.QSize(0, row_height))
            total += row_height
        total += max(0, count - 1) * self.spacing()
        if self.height() != total:
            self.setFixedHeight(total)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_fit()


class ChoicesEdit(QtWidgets.QWidget):
    """Compact player-choice section. Double-click a row to edit/delete."""
    textChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Player choices")
        title.setObjectName("SectionHeading")
        header.addWidget(title)
        add = QtWidgets.QToolButton()
        add.setObjectName("SmallAddButton")
        add.setText("+")
        add.setToolTip("Add player choice")
        add.clicked.connect(self.add_choice)
        header.addWidget(add)
        header.addStretch(1)
        layout.addLayout(header)
        self.items = AutoHeightListWidget()
        self.items.setObjectName("CompactEditList")
        self.items.itemDoubleClicked.connect(self.edit_choice)
        layout.addWidget(self.items)
        self.empty = QtWidgets.QLabel("No player choices")
        self.empty.setObjectName("EmptySectionText")
        layout.addWidget(self.empty)
        self.available = []
        self._fit_list_height()

    def set_available_choices(self, ids):
        self.available = list(dict.fromkeys(str(value) for value in ids if value))

    @staticmethod
    def display_name(value):
        special = {"buddy_name": "Companion name", "buddy_perk": "Companion perk",
                   "buddy_hearts": "Companion Hearts"}
        return special.get(value, str(value).replace("_", " ").title())

    def _fit_list_height(self):
        count = self.items.count()
        self.empty.setVisible(count == 0)
        self.items.setVisible(count > 0)
        self.items.schedule_fit()

    def setPlainText(self, value):
        self.items.clear()
        for choice in [x.strip() for x in str(value).split(",") if x.strip()]:
            item = QtWidgets.QListWidgetItem(self.display_name(choice))
            item.setData(USER_ROLE, choice)
            item.setToolTip("Double-click to edit or delete")
            self.items.addItem(item)
        self._fit_list_height()

    def toPlainText(self):
        return ", ".join(self.items.item(i).data(USER_ROLE) for i in range(self.items.count()))

    def add_choice(self):
        existing = {self.items.item(i).data(USER_ROLE) for i in range(self.items.count())}
        available = [key for key in self.available if key not in existing]
        dialog = ChoiceEditDialog(self, available=available)
        accepted = dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        if not accepted:
            return
        value = dialog.value()
        if not value or value in existing:
            return
        item = QtWidgets.QListWidgetItem(self.display_name(value))
        item.setData(USER_ROLE, value)
        item.setToolTip("Double-click to edit or delete")
        self.items.addItem(item)
        self._fit_list_height()
        self.textChanged.emit()

    def edit_choice(self, item):
        current = str(item.data(USER_ROLE) or "")
        dialog = ChoiceEditDialog(self, current=current, available=self.available, allow_delete=True)
        accepted = dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        if not accepted:
            return
        if dialog.delete_requested:
            self.items.takeItem(self.items.row(item))
        else:
            value = dialog.value()
            if value:
                item.setData(USER_ROLE, value)
                item.setText(self.display_name(value))
        self._fit_list_height()
        self.textChanged.emit()


class EmpowermentDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, empowerment=None, allow_delete=False):
        super().__init__(parent)
        self.setWindowTitle("Empowerment")
        apply_character_sheet_theme(self)
        self.emp = copy.deepcopy(empowerment or {})
        self.delete_requested = False
        self.allow_delete = allow_delete
        self.setFixedWidth(470)
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(16, 14, 16, 14)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.name = QtWidgets.QLineEdit(self.emp.get("name", ""))
        self.cost = _EditorNumericEntry(); self.cost.setRange(0, 999); self.cost.setValue(int(self.emp.get("cost", 1)))
        self.repeat = QtWidgets.QCheckBox("Can be purchased more than once")
        self.repeat.setChecked(self.emp.get("purchase_rule") == "repeatable")
        self.desc = DescriptionEdit()
        self.desc.load_catalog_html(self.emp.get("description", ""))
        form.addRow("Name", self.name)
        form.addRow("Cost (IP)", self.cost)
        form.addRow("", self.repeat)
        form.addRow("Description", description_editor_with_toolbar(self.desc))
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            if QT_API in ("PyQt6","PySide6") else
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        delete = None
        if self.allow_delete:
            delete = QtWidgets.QPushButton("Delete")
            delete.setObjectName("DangerButton")
            delete.clicked.connect(self._delete)
        style_standard_dialog_buttons(buttons, delete)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _delete(self):
        self.delete_requested = True
        self.accept()

    def value(self):
        e = copy.deepcopy(self.emp)
        e["name"] = self.name.text().strip()
        e["id"] = e.get("id") or _slug(e["name"])
        e["cost"] = self.cost.value()
        e["description"] = self.desc.catalog_html()
        if self.repeat.isChecked():
            e["purchase_rule"] = "repeatable"
        elif e.get("purchase_rule") == "repeatable":
            e.pop("purchase_rule", None)
        return e

class ScalingDialog(QtWidgets.QDialog):
    """Friendly editor for ordered/scaling empowerments."""
    def __init__(self, parent=None, key="", group=None, allow_delete=False):
        super().__init__(parent)
        self.setWindowTitle("Leveled Empowerment")
        apply_character_sheet_theme(self)
        self.key = key
        self.group = copy.deepcopy(group or {})
        self.delete_requested = False
        self.allow_delete = allow_delete
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)
        form = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit(self.group.get("name", ""))
        self.rule = QtWidgets.QComboBox()
        self.rule.addItems(["ordered", "repeatable_scaling"])
        self.rule.setCurrentText(self.group.get("rule", "ordered"))
        form.addRow("Name", self.name)
        form.addRow("Type", self.rule)
        root.addLayout(form)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Value", "Cost", "Description / text"])
        self.table.setToolTip("Edit the level descriptions. Formatting options are available in the main descriptions.")
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.edit_level_description)
        root.addWidget(self.table)
        for step in self.group.get("steps", []) or []:
            self.add_row(step)
        rowbuttons = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+ Add Level"); delete = QtWidgets.QPushButton("Delete Level")
        add.clicked.connect(lambda: self.add_row({}))
        delete.clicked.connect(self.delete_row)
        rowbuttons.addWidget(add); rowbuttons.addWidget(delete); rowbuttons.addStretch()
        root.addLayout(rowbuttons)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            if QT_API in ("PyQt6","PySide6") else
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        delete = None
        if self.allow_delete:
            delete = QtWidgets.QPushButton("Delete")
            delete.setObjectName("DangerButton")
            delete.clicked.connect(self._delete)
        style_standard_dialog_buttons(buttons, delete)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.resize(520, 330)

    def _delete(self):
        self.delete_requested = True
        self.accept()

    def add_row(self, step):
        r = self.table.rowCount(); self.table.insertRow(r)
        self.table.setItem(r,0,QtWidgets.QTableWidgetItem(str(step.get("value",""))))
        self.table.setItem(r,1,QtWidgets.QTableWidgetItem(str(step.get("cost",1))))
        text_item = QtWidgets.QTableWidgetItem(_html_to_plain(step.get("text_value", "")))
        text_item.setFlags(text_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        text_item.setToolTip("Double-click to edit the formatted description")
        self.table.setItem(r, 2, text_item)
        # Preserve hidden technical mechanics on each level.
        self.table.item(r,0).setData(USER_ROLE, copy.deepcopy(step))

    def edit_level_description(self, row, column):
        if column != 2:
            return
        item = self.table.item(row, 2)
        original = self.table.item(row, 0).data(USER_ROLE) or {}
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Edit level description")
        dialog.resize(540, 410)
        layout = QtWidgets.QVBoxLayout(dialog)
        editor = DescriptionEdit()
        editor.load_catalog_html(item.data(USER_ROLE) or original.get("text_value", ""))
        layout.addWidget(description_editor_with_toolbar(editor))
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                              QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        style_standard_dialog_buttons(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            formatted = editor.catalog_html()
            item.setData(USER_ROLE, formatted)
            item.setText(_html_to_plain(formatted))

    def delete_row(self):
        r = self.table.currentRow()
        if r >= 0: self.table.removeRow(r)

    def value(self):
        g = copy.deepcopy(self.group)
        g["name"] = self.name.text().strip()
        g["rule"] = self.rule.currentText()
        steps = []
        for r in range(self.table.rowCount()):
            original = self.table.item(r,0).data(USER_ROLE) or {}
            step = copy.deepcopy(original)
            raw = self.table.item(r,0).text().strip()
            try: value = int(raw)
            except ValueError: value = raw
            step["value"] = value
            try: step["cost"] = int(self.table.item(r,1).text())
            except Exception: step["cost"] = 0
            item = self.table.item(r, 2)
            txt = item.text().strip()
            if item.data(USER_ROLE) is not None:
                step["text_value"] = item.data(USER_ROLE)
            elif txt:
                # The cell is read-only; preserve the exact existing markup.
                step["text_value"] = original.get("text_value", _plain_to_html(txt))
            elif "text_value" in step:
                step.pop("text_value")
            steps.append(step)
        g["steps"] = steps
        return g

class ImprovementEditor(QtWidgets.QWidget):
    catalogChanged = Signal()

    def __init__(self, parent=None, owner_mode=False, run_tests: Optional[Callable[[dict], Tuple[bool,str]]] = None):
        super().__init__(parent)
        self.setObjectName("ImprovementEditorRoot")
        apply_character_sheet_theme(self)
        initialize_storage()
        self.owner_mode = owner_mode
        self.run_tests = run_tests
        self._published_catalog = live_catalog()
        self.cat = draft_catalog()
        self.current_id = None
        self._building = False
        self._loading = False
        self._dirty = False
        self._build_ui()
        self.refresh_list()
        self.select_initial_improvement()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Top application bar: status, suggestion author, and the few global
        # actions that genuinely belong at application level.
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(7)

        # Keep the title over the catalog rail.  The author field begins on
        # the same horizontal line as Save / Send / More, immediately after
        # the visual split between the catalog list and the editing pane.
        heading_widget = QtWidgets.QWidget()
        heading_widget.setFixedWidth(270)
        heading = QtWidgets.QVBoxLayout(heading_widget)
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(1)
        title = QtWidgets.QLabel("Improvement Editor")
        title.setObjectName("EditorTitle")
        heading.addWidget(title)
        self.status = QtWidgets.QLabel("Draft ready · only approved changes affect the game")
        self.status.setObjectName("MutedText")
        self.status.setWordWrap(True)
        heading.addWidget(self.status)
        top.addWidget(heading_widget)
        top.addSpacing(5)

        author_label = QtWidgets.QLabel("Editor")
        self.author = QtWidgets.QLineEdit()
        self.author.setPlaceholderText("Editor name")
        self.author.setText("Editor")
        self.author.setFixedWidth(150)
        self.author.setToolTip("Name attached to suggestions you send")
        top.addWidget(author_label)
        top.addWidget(self.author)
        top.addStretch(1)

        save_top = QtWidgets.QPushButton("Save draft")
        save_top.clicked.connect(self.save_current)
        top.addWidget(save_top)
        send_top = QtWidgets.QPushButton("Send suggestion")
        send_top.setObjectName("PrimaryButton")
        send_top.clicked.connect(self.send_suggestion_online)
        top.addWidget(send_top)
        more = QtWidgets.QToolButton()
        more.setObjectName("ToolbarMenuButton")
        more.setText("More ▾")
        more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QtWidgets.QMenu(more)
        if self.owner_mode:
            menu.addAction("Review my draft…", self.review_local_draft)
            menu.addSeparator()
        menu.addAction("Reset draft to published version…", self.reload_authoritative_draft)
        advanced = menu.addMenu("Advanced / owner tools" if self.owner_mode else "Advanced / file tools")
        if self.owner_mode:
            advanced.addAction("Online suggestions…", self.open_online_inbox)
            advanced.addSeparator()
        advanced.addAction("Send queued suggestions now", self.retry_queued_suggestions)
        advanced.addAction("Save current suggestion to file…", self.export_suggestion_ui)
        if self.owner_mode:
            advanced.addAction("Open suggestion file…", self.import_suggestion_ui)
        more.setMenu(menu)
        top.addWidget(more)
        root.addLayout(top)

        # Fixed-width catalog rail: no draggable splitter, so the editor can
        # never be crushed into a thin strip.
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        left = QtWidgets.QWidget()
        left.setFixedWidth(270)
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        search_row = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search improvements...")
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(100)
        self._search_timer.timeout.connect(self.refresh_list)
        self.search.textChanged.connect(lambda *_: self._search_timer.start())
        search_row.addWidget(self.search, 1)
        add = QtWidgets.QToolButton()
        add.setObjectName("SmallAddButton")
        add.setText("+")
        add.setToolTip("New improvement")
        add.clicked.connect(self.new_imp)
        search_row.addWidget(add)
        item_more = QtWidgets.QToolButton()
        item_more.setObjectName("IconMenuButton")
        item_more.setText("⋯")
        item_more.setToolTip("Duplicate or delete selected improvement")
        item_more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        item_menu = QtWidgets.QMenu(item_more)
        item_menu.addAction("Duplicate improvement", self.duplicate_imp)
        item_menu.addAction("Delete improvement", self.delete_imp)
        item_more.setMenu(item_menu)
        search_row.addWidget(item_more)
        ll.addLayout(search_row)
        self.list = QtWidgets.QListWidget()
        self.list.currentItemChanged.connect(self.load_selected)
        ll.addWidget(self.list, 1)
        body.addWidget(left)

        right = QtWidgets.QScrollArea()
        self.editor_scroll = right
        right.setWidgetResizable(True)
        right.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pane = QtWidgets.QWidget()
        outer = QtWidgets.QHBoxLayout(pane)
        outer.setContentsMargins(0, 0, 0, 10)
        outer.addStretch(1)
        content = QtWidgets.QWidget()
        content.setMaximumWidth(940)
        content.setMinimumWidth(560)
        self.form = QtWidgets.QVBoxLayout(content)
        self.form.setContentsMargins(8, 4, 8, 12)
        self.form.setSpacing(10)
        outer.addWidget(content, 8)
        outer.addStretch(1)

        # Only the two description modes remain as top navigation.
        self.description_mode = QtWidgets.QTabBar()
        self.description_mode.setObjectName("DescriptionModeBar")
        self.description_mode.setDocumentMode(True)
        self.description_mode.addTab("Picker description")
        self.description_mode.addTab("Character sheet description")
        self.form.addWidget(self.description_mode)

        # Name, cost and tags are part of the description header.  Double-click
        # any value to edit it in place; no modal details panel is needed.
        meta = QtWidgets.QWidget()
        meta.setObjectName("DirectDescriptionCard")
        meta_layout = QtWidgets.QVBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(2)
        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(8)
        self.name = InlineTextValue("Improvement", prominent=True, placeholder="Improvement name")
        self.cost = InlineIntValue(0, " IP")
        title_row.addWidget(self.name, 1)
        title_row.addWidget(self.cost, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        meta_layout.addLayout(title_row)
        self.tags = InlineTagsValue()
        meta_layout.addWidget(self.tags)
        self.form.addWidget(meta)

        # Direct WYSIWYG editing.  The separate player preview is gone: this is
        # the surface the user edits, in the same typography used for preview.
        self.desc = DescriptionEdit()
        self.owned_desc = DescriptionEdit()
        for editor in (self.desc, self.owned_desc):
            editor.set_auto_fit_enabled(False)
            editor.setMinimumHeight(165)
            editor.setMaximumHeight(165)
            editor.setFixedHeight(165)
        self.description_stack = QtWidgets.QStackedWidget()
        self.description_stack.addWidget(self.desc)
        self.description_stack.addWidget(self.owned_desc)
        self.description_stack.setFixedHeight(165)
        self.description_mode.currentChanged.connect(self.description_stack.setCurrentIndex)
        self.form.addWidget(self.description_stack)

        # One formatting bar, below the description as requested.
        format_row = QtWidgets.QHBoxLayout()
        format_row.setSpacing(8)
        def current_editor():
            return self.desc if self.description_mode.currentIndex() == 0 else self.owned_desc
        for text, tooltip, action in (
            ("B", "Bold (Ctrl+B)", lambda: current_editor().toggle_format("bold")),
            ("I", "Italic (Ctrl+I)", lambda: current_editor().toggle_format("italic")),
            ("U", "Underline (Ctrl+U)", lambda: current_editor().toggle_format("underline")),
            ("•", "Bulleted list", lambda: current_editor().toggle_list(False)),
            ("1.", "Numbered list", lambda: current_editor().toggle_list(True)),
        ):
            button = QtWidgets.QToolButton()
            button.setObjectName("MainFormatButton")
            button.setText(text)
            button.setToolTip(tooltip)
            button.clicked.connect(action)
            format_row.addWidget(button)
        format_row.addStretch(1)
        self.form.addLayout(format_row)

        divider = QtWidgets.QFrame()
        divider.setObjectName("ThinDivider")
        self.form.addWidget(divider)

        # Purchase limit is a short inline value, not a hidden details form.
        purchase_row = QtWidgets.QHBoxLayout()
        purchase_title = QtWidgets.QLabel("Purchase limit")
        purchase_title.setObjectName("SectionHeading")
        purchase_row.addWidget(purchase_title)
        self.purchase = InlineComboValue([
            "Buy once", "Repeatable", "Scaling stat bonus", "Repeatable with increasing cost"
        ])
        purchase_row.addWidget(self.purchase)
        purchase_row.addStretch(1)
        self.form.addLayout(purchase_row)

        # Compact always-visible player choices.
        self.choices = ChoicesEdit()
        self.form.addWidget(self.choices)

        # Compact empowerments; double-click rows to edit/delete, + to add.
        emp_header = QtWidgets.QHBoxLayout()
        emp_title = QtWidgets.QLabel("Empowerments")
        emp_title.setObjectName("SectionHeading")
        emp_header.addWidget(emp_title)
        emp_add = QtWidgets.QToolButton()
        emp_add.setObjectName("SmallAddButton")
        emp_add.setText("+")
        emp_add.setToolTip("Add empowerment")
        emp_add.clicked.connect(self.add_emp)
        emp_header.addWidget(emp_add)
        emp_header.addStretch(1)
        self.form.addLayout(emp_header)
        self.emps = AutoHeightListWidget()
        self.emps.setObjectName("CompactEditList")
        self.emps.itemDoubleClicked.connect(lambda _item: self.edit_emp())
        self.form.addWidget(self.emps)

        scaling_header = QtWidgets.QHBoxLayout()
        scaling_title = QtWidgets.QLabel("Leveled / scaling empowerments")
        scaling_title.setObjectName("SectionHeading")
        scaling_header.addWidget(scaling_title)
        scaling_add = QtWidgets.QToolButton()
        scaling_add.setObjectName("SmallAddButton")
        scaling_add.setText("+")
        scaling_add.setToolTip("Add leveled empowerment")
        scaling_add.clicked.connect(self.add_scaling)
        scaling_header.addWidget(scaling_add)
        scaling_header.addStretch(1)
        self.form.addLayout(scaling_header)
        self.scaling = AutoHeightListWidget()
        self.scaling.setObjectName("CompactEditList")
        self.scaling.itemDoubleClicked.connect(lambda _item: self.edit_scaling())
        self.form.addWidget(self.scaling)
        self.form.addStretch(1)

        for field, signal in ((self.name, self.name.textChanged),
                              (self.cost, self.cost.valueChanged),
                              (self.purchase, self.purchase.currentTextChanged),
                              (self.tags, self.tags.tagsChanged),
                              (self.choices, self.choices.textChanged),
                              (self.desc, self.desc.textChanged),
                              (self.owned_desc, self.owned_desc.textChanged)):
            signal.connect(self._mark_unsaved)

        right.setWidget(pane)
        body.addWidget(right, 1)

    def jump_to_section(self, section):
        target = self.description_stack
        if section == "rules":
            target = self.choices
        elif section == "empowerments":
            target = self.emps
        QtCore.QTimer.singleShot(0, lambda: self.editor_scroll.ensureWidgetVisible(target, 0, 12))

    def _mark_unsaved(self, *args):
        if not self._loading and self.current_id:
            self._dirty = True
            self.status.setText("Unsaved draft · Save draft or switch improvements to save")

    def _draft_change_count(self):
        try:
            return len(diff_catalog(self._published_catalog, self.cat))
        except Exception:
            return 0

    def _set_saved_status(self, prefix="Draft saved locally"):
        count = self._draft_change_count()
        if count:
            self.status.setText(f"{prefix} · {count} unsent change(s) · the game is unchanged")
        else:
            self.status.setText("Draft matches the published catalog · the game is unchanged")

    def _reload_from_published(self, message):
        preferred = self.current_id
        reset_draft()
        PENDING_FILE.unlink(missing_ok=True)
        self._published_catalog = live_catalog()
        self.cat = draft_catalog()
        self.current_id = None
        self._dirty = False
        self.refresh_list()
        self.select_initial_improvement(preferred or "animal_buddy")
        self.status.setText(message)

    def select_initial_improvement(self, preferred_id="animal_buddy"):
        """Open the editor with Animal Buddy selected whenever available."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(USER_ROLE) == preferred_id:
                self.list.setCurrentRow(row)
                self.current_id = preferred_id
                self.load_selected(item)
                return
        if self.list.count():
            self.list.setCurrentRow(0)
            item = self.list.item(0)
            self.current_id = item.data(USER_ROLE)
            self.load_selected(item)

    def all_existing_tags(self):
        tags = set()
        for imp in self.cat.get("improvements", {}).values():
            for tag in imp.get("tags", []) or []:
                if tag:
                    tags.add(str(tag))
        return sorted(tags, key=str.lower)

    def refresh_list(self):
        q=self.search.text().lower().strip() if hasattr(self,"search") else ""
        cur=self.current_id
        self.list.blockSignals(True); self.list.clear()
        for iid,imp in sorted(self.cat["improvements"].items(), key=lambda kv: kv[1].get("name",kv[0]).lower()):
            if q and q not in imp.get("name","").lower(): continue
            item=QtWidgets.QListWidgetItem(imp.get("name",iid)); item.setData(USER_ROLE,iid); self.list.addItem(item)
            if iid==cur: self.list.setCurrentItem(item)
        self.list.blockSignals(False)

    def _purchase_to_ui(self, rule):
        return {"single":"Buy once","repeatable":"Repeatable","stat_bonus_scaling":"Scaling stat bonus","repeatable_scaling":"Repeatable with increasing cost"}.get(rule,"Buy once")
    def _ui_to_purchase(self, text):
        return {"Buy once":"single","Repeatable":"repeatable","Scaling stat bonus":"stat_bonus_scaling","Repeatable with increasing cost":"repeatable_scaling"}[text]

    def load_selected(self, current, previous=None):
        if not current:
            return
        incoming_id = current.data(USER_ROLE)
        if self.current_id and self.current_id != incoming_id and getattr(self, "_dirty", False):
            self.save_current()
        # save_current refreshes the sidebar. Keep its selection consistent
        # with the new item even if the old QListWidgetItem was destroyed.
        self.list.blockSignals(True)
        for row in range(self.list.count()):
            candidate = self.list.item(row)
            if candidate.data(USER_ROLE) == incoming_id:
                self.list.setCurrentItem(candidate)
                break
        self.list.blockSignals(False)
        self._loading = True
        self.current_id = incoming_id
        imp = self.cat["improvements"][self.current_id]
        self.name.setText(imp.get("name","")); self.cost.setValue(int(imp.get("cost",0)))
        self.purchase.setCurrentText(self._purchase_to_ui(imp.get("purchase_rule","single")))
        self.tags.set_available_tags(self.all_existing_tags()); self.tags.set_tags(imp.get("tags",[]) or [])
        all_choices = [choice for entry in self.cat.get("improvements", {}).values()
                       for choice in (entry.get("requires_choices") or [])]
        self.choices.set_available_choices(all_choices)
        self.choices.setPlainText(", ".join(imp.get("requires_choices",[]) or []))
        self.desc.load_catalog_html(imp.get("description",""))
        self.owned_desc.load_catalog_html(
            imp.get("owned_description", imp.get("description", ""))
        )
        self.refresh_emp_lists()
        self._loading = False
        self._dirty = False
        self._set_saved_status("Draft ready")

    def _add_emp_list_item(self, target_list, title, description, ref):
        desc = _html_to_plain(description or "").replace("\n", " ").strip()
        if len(desc) > 110:
            desc = desc[:107].rstrip() + "…"
        label = title if not desc else f"{title} — {desc}"
        item = QtWidgets.QListWidgetItem(label)
        item.setData(USER_ROLE, ref)
        item.setToolTip("Double-click to edit or delete\n" + (desc or title))
        target_list.addItem(item)

    def _fit_compact_list(self, widget, max_rows=None):
        count = widget.count()
        widget.setVisible(count > 0)
        if count <= 0:
            widget.setFixedHeight(0)
            return
        if hasattr(widget, "schedule_fit"):
            widget.schedule_fit()
        else:
            widget.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def refresh_emp_lists(self):
        if not self.current_id:
            return
        imp = self.cat["improvements"][self.current_id]
        self.emps.clear()
        self.scaling.clear()

        for i, e in enumerate(imp.get("empowerments", []) or []):
            title = f"{e.get('name','Unnamed')} · {e.get('cost',0)} IP"
            self._add_emp_list_item(self.emps, title, e.get("description", ""), ("plain", i))

        for group_key, group in (imp.get("empowerment_groups", {}) or {}).items():
            for option_index, e in enumerate(group.get("options", []) or []):
                title = f"{e.get('name','Unnamed')} · {e.get('cost',0)} IP"
                self._add_emp_list_item(
                    self.emps, title, e.get("description", ""),
                    ("group", group_key, option_index))

        for key, g in (imp.get("scaling_empowerments", {}) or {}).items():
            if g.get("rule") == "repeatable_scaling":
                cost = g.get("base_cost", g.get("cost", 0))
                title = f"{g.get('name',key)} · {cost} IP"
                self._add_emp_list_item(
                    self.emps, title, g.get("description", ""),
                    ("scaling_repeatable", key))
            else:
                title = g.get("name", key)
                self._add_emp_list_item(
                    self.scaling, title, g.get("description", ""), key)

        self._fit_compact_list(self.emps, 5)
        self._fit_compact_list(self.scaling, 4)

    def save_current(self):
        if not self.current_id: return
        imp=self.cat["improvements"][self.current_id]
        old_name = imp.get("name", self.current_id)
        imp["name"]=self.name.text().strip() or old_name
        imp["cost"]=self.cost.value()
        imp["purchase_rule"]=self._ui_to_purchase(self.purchase.currentText())
        tags=self.tags.tags()
        if tags: imp["tags"]=tags
        else: imp.pop("tags",None)
        choices=[x.strip() for x in self.choices.toPlainText().replace("\n", ",").split(",") if x.strip()]
        if choices: imp["requires_choices"]=choices
        else: imp.pop("requires_choices",None)
        imp["description"]=self.desc.catalog_html()
        imp["owned_description"]=self.owned_desc.catalog_html()
        # Legacy aliases must not silently override either canonical field.
        for obsolete in ("owned_summary", "summary", "rules_text"):
            imp.pop(obsolete, None)
        _write_json(DRAFT_FILE,self.cat)
        self._dirty = False
        self._set_saved_status()
        # Rebuilding and re-sorting the whole catalog list on every save was
        # one of the editor's largest avoidable UI costs. Only rebuild when
        # the displayed/sort name actually changed.
        if imp.get("name", self.current_id) != old_name:
            self.refresh_list()
        self.catalogChanged.emit()

    def new_imp(self):
        if getattr(self, "_dirty", False):
            self.save_current()
        name,ok=QtWidgets.QInputDialog.getText(self,"New Improvement","Name:")
        if not ok or not name.strip(): return
        iid=_slug(name)
        base=iid; n=2
        while iid in self.cat["improvements"]: iid=f"{base}_{n}"; n+=1
        self.cat["improvements"][iid]={"id":iid,"name":name.strip(),"cost":1,"purchase_rule":"single","description":""}
        _write_json(DRAFT_FILE,self.cat); self.current_id=iid; self.refresh_list()
        for i in range(self.list.count()):
            if self.list.item(i).data(USER_ROLE)==iid: self.list.setCurrentRow(i); break

    def duplicate_imp(self):
        if getattr(self, "_dirty", False):
            self.save_current()
        if not self.current_id:return
        old=self.cat["improvements"][self.current_id]
        name=old.get("name",self.current_id)+" Copy"; iid=_slug(name); n=2; base=iid
        while iid in self.cat["improvements"]: iid=f"{base}_{n}"; n+=1
        new=copy.deepcopy(old); new["id"]=iid; new["name"]=name
        self.cat["improvements"][iid]=new; _write_json(DRAFT_FILE,self.cat); self.current_id=iid; self.refresh_list()

    def delete_imp(self):
        if getattr(self, "_dirty", False):
            self.save_current()
        if not self.current_id:return
        name=self.cat["improvements"][self.current_id].get("name",self.current_id)
        if QtWidgets.QMessageBox.question(self,"Delete Improvement",f"Suggest deleting '{name}'?\n\nThis only removes it from the draft.") != YES:return
        self.cat["improvements"].pop(self.current_id,None); self.current_id=None; _write_json(DRAFT_FILE,self.cat); self.refresh_list()

    def add_emp(self):
        if not self.current_id:return
        d=EmpowermentDialog(self)
        if d.exec() if hasattr(d,"exec") else d.exec_():
            self.cat["improvements"][self.current_id].setdefault("empowerments",[]).append(d.value()); self.refresh_emp_lists(); self.save_current()
    def _selected_emp_ref(self):
        item = self.emps.currentItem()
        if not item:
            return None
        ref = item.data(USER_ROLE)
        return ref if isinstance(ref, (tuple, list)) else None

    def _get_emp_by_ref(self, ref):
        imp = self.cat["improvements"][self.current_id]
        kind = ref[0]
        if kind == "plain":
            return imp.setdefault("empowerments", [])[ref[1]]
        if kind == "group":
            return imp.setdefault("empowerment_groups", {})[ref[1]].setdefault("options", [])[ref[2]]
        if kind == "scaling_repeatable":
            return imp.setdefault("scaling_empowerments", {})[ref[1]]
        return None

    def duplicate_emp(self):
        ref = self._selected_emp_ref()
        if not ref:
            return
        imp = self.cat["improvements"][self.current_id]
        original = copy.deepcopy(self._get_emp_by_ref(ref))
        if ref[0] == "scaling_repeatable":
            groups = imp.setdefault("scaling_empowerments", {})
            original["name"] = original.get("name", ref[1]) + " Copy"
            key = _slug(original["name"]); base = key; n = 2
            while key in groups:
                key = f"{base}_{n}"; n += 1
            groups[key] = original
        else:
            # A duplicate becomes a normal empowerment so it is simple to edit.
            original["name"] = original.get("name", "Empowerment") + " Copy"
            original["id"] = _slug(original["name"])
            imp.setdefault("empowerments", []).append(original)
        self.refresh_emp_lists()
        self.save_current()

    def edit_emp(self):
        ref = self._selected_emp_ref()
        if not ref:
            return
        target = self._get_emp_by_ref(ref)
        if ref[0] == "scaling_repeatable":
            # Repeatable scaling has mechanics which the simple dialog must preserve.
            d = EmpowermentDialog(self, {
                "name": target.get("name", ""),
                "cost": target.get("base_cost", target.get("cost", 0)),
                "description": target.get("description", ""),
                "purchase_rule": "repeatable",
            }, allow_delete=True)
            accepted = d.exec() if hasattr(d, "exec") else d.exec_()
            if accepted:
                if d.delete_requested:
                    self.del_emp()
                    return
                val = d.value()
                target["name"] = val["name"]
                target["base_cost"] = val["cost"]
                target["description"] = val["description"]
        else:
            d = EmpowermentDialog(self, target, allow_delete=True)
            accepted = d.exec() if hasattr(d, "exec") else d.exec_()
            if accepted:
                if d.delete_requested:
                    self.del_emp()
                    return
                val = d.value()
                target.clear()
                target.update(val)
        self.refresh_emp_lists()
        self.save_current()

    def del_emp(self):
        ref = self._selected_emp_ref()
        if not ref:
            return
        imp = self.cat["improvements"][self.current_id]
        kind = ref[0]
        if kind == "plain":
            imp.setdefault("empowerments", []).pop(ref[1])
        elif kind == "group":
            imp.setdefault("empowerment_groups", {})[ref[1]].setdefault("options", []).pop(ref[2])
        elif kind == "scaling_repeatable":
            imp.setdefault("scaling_empowerments", {}).pop(ref[1], None)
        self.refresh_emp_lists()
        self.save_current()

    def add_scaling(self):
        if not self.current_id:
            return
        groups = self.cat["improvements"][self.current_id].setdefault("scaling_empowerments", {})
        d = ScalingDialog(self, "", {"name": "New Empowerment", "rule": "ordered", "steps": []})
        accepted = d.exec() if hasattr(d, "exec") else d.exec_()
        if not accepted:
            return
        value = d.value()
        name = value.get("name", "").strip() or "New Empowerment"
        key = _slug(name); base = key; n = 2
        while key in groups:
            key = f"{base}_{n}"; n += 1
        groups[key] = value
        self.refresh_emp_lists()
        self.save_current()
    def duplicate_scaling(self):
        item=self.scaling.currentItem()
        if not item:return
        key=item.data(USER_ROLE)
        groups=self.cat["improvements"][self.current_id].setdefault("scaling_empowerments",{})
        original=copy.deepcopy(groups[key])
        original["name"]=original.get("name",key)+" Copy"
        new_key=_slug(original["name"]); base=new_key; n=2
        while new_key in groups:
            new_key=f"{base}_{n}"; n+=1
        groups[new_key]=original
        self.refresh_emp_lists(); self.save_current()
        for r in range(self.scaling.count()):
            if self.scaling.item(r).data(USER_ROLE)==new_key:
                self.scaling.setCurrentRow(r); break

    def edit_scaling(self):
        item = self.scaling.currentItem()
        if not item:
            return
        key = item.data(USER_ROLE)
        groups = self.cat["improvements"][self.current_id].setdefault("scaling_empowerments", {})
        d = ScalingDialog(self, key, groups[key], allow_delete=True)
        accepted = d.exec() if hasattr(d, "exec") else d.exec_()
        if not accepted:
            return
        if d.delete_requested:
            groups.pop(key, None)
        else:
            groups[key] = d.value()
        self.refresh_emp_lists()
        self.save_current()
    def del_scaling(self):
        item=self.scaling.currentItem()
        if not item:return
        self.cat["improvements"][self.current_id].setdefault("scaling_empowerments",{}).pop(item.data(USER_ROLE),None); self.refresh_emp_lists(); self.save_current()

    def reload_authoritative_draft(self):
        if QtWidgets.QMessageBox.question(
            self, "Reset Draft to Published Version?",
            "Replace your current unsent draft with the published catalog? "
            "A backup of this draft will be saved first. Nothing will be published.") != YES:
            return
        self.save_current()
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        _ensure_dirs()
        backup = DATA_DIR / ("draft_backup_before_api_reload_" + stamp + ".json")
        _write_json(backup, _read_json(DRAFT_FILE))
        reset_draft()
        self._published_catalog = live_catalog()
        self.cat = draft_catalog()
        self.current_id = None
        self.refresh_list()
        self.select_initial_improvement()
        self.status.setText("Draft reset to the published version. A backup was saved at " + str(backup))

    def submit(self):
        self.save_current()
        try:
            p=submit_draft(self.author.text().strip() or "Editor")
        except (RuntimeError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Draft Needs Attention", str(error))
            return
        if not p["changes"]:
            QtWidgets.QMessageBox.information(self,"No Changes","There are no changes to submit.")
            return
        if p["errors"]:
            QtWidgets.QMessageBox.critical(self,"Validation Failed","These changes were saved as a suggestion, but cannot be approved yet:\n\n• "+"\n• ".join(p["errors"]))
        else:
            msg=f"Submitted {len(p['changes'])} suggested change(s).\n\nTechnical validation passed."
            if p["warnings"]: msg += "\n\nWarnings:\n• "+"\n• ".join(p["warnings"])
            QtWidgets.QMessageBox.information(self,"Changes Submitted",msg)

    def _online_client(self):
        config = load_config(SUGGESTIONS_CONFIG)
        existing = getattr(self, "_suggestions_client", None)
        if existing is None or existing.url != config["url"] or existing.key != config["key"]:
            existing = CloudClient(config)
            self._suggestions_client = existing
        return existing

    def send_suggestion_online(self):
        self.save_current()
        try:
            proposal = submit_draft(self.author.text().strip() or "Editor")
        except (RuntimeError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Draft Needs Attention", str(error))
            return
        if not proposal.get("changes"):
            QtWidgets.QMessageBox.information(self, "No Changes", "There are no draft changes to send.")
            return
        if proposal.get("errors"):
            QtWidgets.QMessageBox.warning(
                self, "Validation Failed",
                "Correct these errors before sending:\n\n• " + "\n• ".join(proposal["errors"])
            )
            return
        try:
            client = self._online_client()
            queued_item = enqueue(SUGGESTIONS_OUTBOX, proposal)
            sent, remaining, error = flush_outbox(SUGGESTIONS_OUTBOX, client)
            still_queued = any(
                str(item.get("id")) == str(queued_item.get("id"))
                for item in read_outbox(SUGGESTIONS_OUTBOX)
                if isinstance(item, dict)
            )
            if still_queued:
                self.status.setText("Suggestion queued safely · your draft was kept")
                QtWidgets.QMessageBox.warning(
                    self, "Queued for Retry",
                    f"This suggestion could not be confirmed online yet.\n\n"
                    f"{remaining} suggestion(s) remain safely queued. Your draft was kept so nothing is lost."
                    + (f"\n\n{error}" if error else "")
                )
                return

            change_count = len(proposal.get("changes", []))
            self._reload_from_published(
                f"Suggestion sent · {change_count} submitted change(s) cleared from this draft"
            )
            QtWidgets.QMessageBox.information(
                self, "Suggestion Sent",
                f"Sent {change_count} change(s) to the owner's online inbox.\n\n"
                "Your local draft has been reset to the published catalog, so these changes will not be sent again. "
                "Nothing has been published to the game."
            )
        except (CloudError, ValueError, OSError) as error:
            QtWidgets.QMessageBox.warning(self, "Suggestion Not Sent", str(error))

    def retry_queued_suggestions(self):
        try:
            count = len(read_outbox(SUGGESTIONS_OUTBOX))
            if not count:
                QtWidgets.QMessageBox.information(self, "Queue Empty", "There are no unsent suggestions.")
                return
            sent, remaining, error = flush_outbox(SUGGESTIONS_OUTBOX, self._online_client())
            QtWidgets.QMessageBox.information(self, "Suggestion Queue",
                f"Sent: {sent}\nRemaining: {remaining}" + (f"\n\n{error}" if error else ""))
        except (CloudError, OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Send Failed", str(error))

    def open_online_inbox(self):
        try:
            client = self._online_client()
        except CloudError as error:
            QtWidgets.QMessageBox.warning(self, "Cloud Not Configured", str(error))
            return
        if not client.access_token:
            login = QtWidgets.QDialog(self)
            login.setWindowTitle("Owner Sign In")
            apply_character_sheet_theme(login)
            form = QtWidgets.QFormLayout(login)
            email = QtWidgets.QLineEdit()
            email.setPlaceholderText("Owner email")
            password = QtWidgets.QLineEdit()
            password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            form.addRow("Email", email)
            form.addRow("Password", password)
            buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                                  QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            style_standard_dialog_buttons(buttons)
            buttons.accepted.connect(login.accept)
            buttons.rejected.connect(login.reject)
            form.addRow(buttons)
            if not login.exec():
                return
            try:
                client.login(email.text().strip(), password.text())
            except CloudError as error:
                QtWidgets.QMessageBox.warning(self, "Sign In Failed", str(error))
                return
            finally:
                password.clear()
        inbox = OnlineInboxDialog(self, client)
        inbox.exec()
        self.cat = draft_catalog()
        self.refresh_list()

    def export_suggestion_ui(self):
        self.save_current()
        try:
            proposal = submit_draft(self.author.text().strip() or "Editor")
        except (RuntimeError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Draft Needs Attention", str(error))
            return
        if not proposal.get("changes"):
            QtWidgets.QMessageBox.information(self, "Nothing to Export", "No changes from the approved catalog were found.")
            return
        target, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Share Improvement Suggestion", "DID_improvement_suggestion.json", "DID proposal (*.json)"
        )
        if target:
            try:
                export_suggestion(target)
                QtWidgets.QMessageBox.information(
                    self, "Suggestion Exported",
                    "Send this JSON file to the catalog owner. The app does not transmit it automatically."
                )
            except Exception as error:
                QtWidgets.QMessageBox.critical(self, "Export Failed", str(error))

    def import_suggestion_ui(self):
        target, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Contributor Suggestion", "", "DID proposal (*.json)"
        )
        if not target:
            return
        if pending_changes() and QtWidgets.QMessageBox.question(
            self, "Replace Pending Review?",
            "A proposal is already waiting for review. Replace it with this file?"
        ) != YES:
            return
        try:
            proposal = import_suggestion(target)
            QtWidgets.QMessageBox.information(
                self, "Suggestion Received",
                f"Imported {len(proposal['changes'])} proposed change(s) from {proposal['author']}. "
                "Nothing has been approved. Click Review Pending to inspect the differences."
            )
            self.review_pending()
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "Import Failed", str(error))

    def review_local_draft(self):
        self.save_current()
        try:
            proposal = submit_draft(self.author.text().strip() or "Editor")
        except (RuntimeError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Draft Needs Attention", str(error))
            return
        if not proposal.get("changes"):
            QtWidgets.QMessageBox.information(self, "No Changes", "The draft matches the published catalog.")
            return
        self.review_pending()

    def review_pending(self):
        d=ReviewDialog(self,run_tests=self.run_tests)
        d.exec() if hasattr(d,"exec") else d.exec_()
        self.cat=draft_catalog(); self.refresh_list()
        self._set_saved_status()

class ReviewDialog(QtWidgets.QDialog):
    def __init__(self,parent=None,run_tests=None):
        super().__init__(parent)
        self.run_tests=run_tests
        self.setWindowTitle("Review Suggested Changes")
        apply_character_sheet_theme(self)
        self.resize(760, 560)
        self.setMinimumSize(650, 470)
        root=QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        self.p=pending_changes()
        if not self.p:
            root.addWidget(QtWidgets.QLabel("There are no pending changes.")); return
        import html
        root.addWidget(QtWidgets.QLabel(
            "<b>Submitted by:</b> " + html.escape(str(self.p.get("author", "Editor")))
            + " &nbsp;&nbsp; <b>At:</b> " + html.escape(str(self.p.get("submitted_at", "unknown")))
        ))
        self.validation=QtWidgets.QLabel(); self.validation.setWordWrap(True); root.addWidget(self.validation)
        if self.p.get("errors"):
            self.validation.setText("<b>Technical validation FAILED.</b><br>"+ "<br>".join("• "+e for e in self.p["errors"]))
        else:
            txt="<b>Technical validation passed.</b>"
            if self.p.get("warnings"): txt+="<br>"+ "<br>".join("• "+w for w in self.p["warnings"])
            self.validation.setText(txt)
        self.list=QtWidgets.QListWidget(); root.addWidget(self.list,1)
        for i,ch in enumerate(self.p["changes"]):
            item=QtWidgets.QListWidgetItem(ch["summary"]); item.setData(USER_ROLE,i); item.setCheckState(
                QtCore.Qt.CheckState.Checked if QT_API in ("PyQt6","PySide6") else QtCore.Qt.Checked
            ); self.list.addItem(item)
        self.details=QtWidgets.QTextBrowser()
        self.details.setReadOnly(True)
        self.details.setOpenExternalLinks(False)
        self.details.setMinimumHeight(180)
        root.addWidget(self.details, 1)
        self.list.currentItemChanged.connect(self.show_detail)
        buttons=QtWidgets.QHBoxLayout()
        test=QtWidgets.QPushButton("Run Sheet Tests")
        test.setEnabled(bool(run_tests))
        test.clicked.connect(self.do_tests)
        buttons.addWidget(test)
        buttons.addStretch()
        reject=QtWidgets.QPushButton("Reject"); reject.setObjectName("DangerButton"); reject.clicked.connect(self.reject_all); buttons.addWidget(reject)
        approve=QtWidgets.QPushButton("Approve Selected"); approve.setObjectName("PrimaryButton"); approve.setEnabled(not bool(self.p.get("errors"))); approve.clicked.connect(self.approve); buttons.addWidget(approve)
        root.addLayout(buttons)

    def show_detail(self,item,prev=None):
        if not item:
            return
        ch=self.p["changes"][item.data(USER_ROLE)]
        old, new = ch.get("old"), ch.get("new")
        summary = _html.escape(str(ch.get("summary", "Change")))
        if isinstance(old, str) and isinstance(new, str):
            old_plain = _html_to_plain(old)
            new_plain = _html_to_plain(new)
            import difflib
            diff_lines = []
            for line in difflib.ndiff(old_plain.splitlines(), new_plain.splitlines()):
                if line.startswith("? "):
                    continue
                diff_lines.append(line)
            diff = _html.escape("\n".join(diff_lines) or "No textual difference")
            before = _safe_rich_html(old)
            after = _safe_rich_html(new)
            self.details.setHtml(
                f"<h3 style='margin:0 0 8px 0'>{summary}</h3>"
                "<b>Before</b>"
                f"<div style='margin:5px 0 12px 0;padding:8px;border:1px solid #d9bd82'>{before or '<i>Empty</i>'}</div>"
                "<b>Suggested</b>"
                f"<div style='margin:5px 0 12px 0;padding:8px;border:1px solid #c79a3b'>{after or '<i>Empty</i>'}</div>"
                "<b>Text difference</b>"
                f"<pre style='white-space:pre-wrap'>{diff}</pre>"
            )
        else:
            import difflib
            old_json = json.dumps(old, indent=2, ensure_ascii=False)
            new_json = json.dumps(new, indent=2, ensure_ascii=False)
            changes = "\n".join(difflib.unified_diff(
                old_json.splitlines(), new_json.splitlines(),
                fromfile="before", tofile="suggested", lineterm=""
            ))
            body = _html.escape(changes or "No textual differences")
            self.details.setHtml(
                f"<h3 style='margin:0 0 8px 0'>{summary}</h3>"
                f"<pre style='white-space:pre-wrap'>{body}</pre>"
            )

    def do_tests(self):
        if not self.run_tests:return
        try:
            ok,report=self.run_tests(self.p["draft"])
            QtWidgets.QMessageBox.information(self,"Sheet Tests",("PASSED\n\n" if ok else "FAILED\n\n")+str(report))
        except Exception:
            QtWidgets.QMessageBox.critical(self,"Sheet Tests","Test callback crashed:\n\n"+traceback.format_exc())

    def approve(self):
        checked=[]
        checked_state=QtCore.Qt.CheckState.Checked if QT_API in ("PyQt6","PySide6") else QtCore.Qt.Checked
        for r in range(self.list.count()):
            it=self.list.item(r)
            if it.checkState()==checked_state: checked.append(it.data(USER_ROLE))
        if not checked:return
        try:
            cloud_id = self.p.get("cloud_id")
            warnings=approve_pending(checked)
            sync_warning = ""
            if cloud_id and hasattr(self, "cloud_client"):
                try:
                    self.cloud_client.update_status(cloud_id, "approved")
                except Exception as error:
                    sync_warning = "\n\nOnline status could not be updated; local approval succeeded. Retry reconciliation from the inbox. " + str(error)
            QtWidgets.QMessageBox.information(self,"Approved",f"Approved {len(checked)} change(s). A rollback snapshot was created.\n\nThe authoritative API has been updated. Restart DID to refresh all existing windows. Drafts and unapproved suggestions do not affect the game." + sync_warning)
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,"Cannot Approve",str(e))
    def reject_all(self):
        source = str(self.p.get("source") or "local_draft")
        cloud_id = self.p.get("cloud_id")
        reject_pending()
        if source == "local_draft":
            reset_draft()
        sync_warning = ""
        if cloud_id and hasattr(self, "cloud_client"):
            try:
                self.cloud_client.update_status(cloud_id, "rejected")
            except Exception as error:
                sync_warning = "\n\nOnline status could not be updated. " + str(error)
        if source == "local_draft":
            message = "The local draft was discarded. The published catalog was not changed."
        else:
            message = "The suggestion was rejected. Your local draft was not changed."
        QtWidgets.QMessageBox.information(self, "Rejected", message + sync_warning)
        self.accept()


class OnlineInboxDialog(QtWidgets.QDialog):
    """Authenticated owner-only inbox; existing ReviewDialog handles per-field approval."""
    def __init__(self, editor, client):
        super().__init__(editor)
        self.editor = editor
        self.client = client
        self.records = []
        self.setWindowTitle("Online Improvement Suggestions")
        apply_character_sheet_theme(self)
        self.resize(760, 500)
        self.setMinimumSize(620, 430)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        intro = QtWidgets.QLabel("Suggestions received online. Select one to inspect its changes. Sender names are unverified.")
        intro.setObjectName("MutedText")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QtWidgets.QListWidget()
        layout.addWidget(self.list, 1)
        self.detail = QtWidgets.QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(120)
        self.detail.setMaximumHeight(180)
        layout.addWidget(self.detail)
        row = QtWidgets.QHBoxLayout()
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        more = QtWidgets.QToolButton()
        more.setObjectName("ToolbarMenuButton")
        more.setText("More ▾")
        more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QtWidgets.QMenu(more)
        menu.addAction("Reconcile online status…", self.mark_handled)
        more.setMenu(menu)
        row.addWidget(more)
        row.addStretch()
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        review = QtWidgets.QPushButton("Review selected")
        review.setObjectName("PrimaryButton")
        review.clicked.connect(self.review)
        row.addWidget(review)
        layout.addLayout(row)
        self.list.currentRowChanged.connect(self.preview)
        self.refresh()

    def refresh(self):
        try:
            self.records = self.client.pending()
        except CloudError as error:
            QtWidgets.QMessageBox.warning(self, "Inbox Unavailable", str(error))
            return
        self.list.clear()
        for item in self.records:
            proposal = item.get("proposal") or {}
            n = len(proposal.get("changes", [])) if isinstance(proposal, dict) else 0
            self.list.addItem(f"{item.get('created_at','')} | {str(item.get('author','Anonymous'))[:70]} | {n} change(s) | {str(item.get('id',''))[:8]}")
        if self.records:
            self.list.setCurrentRow(0)
        else:
            self.detail.setPlainText("No pending online suggestions.")

    def preview(self, row):
        if row < 0 or row >= len(self.records):
            self.detail.clear()
            return
        record = self.records[row]
        proposal = record.get("proposal") or {}
        changes = proposal.get("changes", []) if isinstance(proposal, dict) else []
        self.detail.setPlainText("\n".join(str(change.get("summary", "Change")) for change in changes[:100] if isinstance(change, dict)))

    def review(self):
        row = self.list.currentRow()
        if row < 0:
            return
        local_changes = diff_catalog(live_catalog(), draft_catalog())
        if local_changes:
            QtWidgets.QMessageBox.warning(
                self, "Finish Your Local Draft First",
                f"You currently have {len(local_changes)} unsent local draft change(s).\n\n"
                "Send them, or use More → Reset draft to published version…, before reviewing an online suggestion. "
                "This prevents an approval from overwriting your own draft."
            )
            return
        record = self.records[row]
        if pending_changes() and QtWidgets.QMessageBox.question(
            self, "Replace Current Local Review?", "Another proposal is currently open locally. Replace only the pending review file?"
        ) != YES:
            return
        try:
            accept_suggestion(record.get("proposal"), cloud_id=record["id"])
        except (ValueError, KeyError, TypeError) as error:
            QtWidgets.QMessageBox.warning(self, "Cannot Review", str(error))
            return
        dialog = ReviewDialog(self, run_tests=self.editor.run_tests)
        dialog.cloud_client = self.client
        dialog.exec()
        self.refresh()

    def mark_handled(self):
        """Reconcile an approval that succeeded locally but failed online."""
        row = self.list.currentRow()
        if row < 0:
            return
        record = self.records[row]
        if QtWidgets.QMessageBox.question(self, "Reconcile Status?",
             "ONLY use this if this proposal was already reviewed locally. Mark it handled online without changing the catalog?") != YES:
            return
        status, ok = QtWidgets.QInputDialog.getItem(
            self, "Online Status", "What actually happened to this proposal locally?",
            ["approved", "rejected"], 0, False
        )
        if not ok:
            return
        try:
            self.client.update_status(record["id"], status)
            self.refresh()
        except CloudError as error:
            QtWidgets.QMessageBox.warning(self, "Could Not Update", str(error))


def open_improvement_editor(parent=None, owner_mode=False, run_tests=None):
    """
    Main integration entry point for the character sheet.

    Example:
        from improvement_editor import open_improvement_editor
        self._catalog_editor = open_improvement_editor(self, owner_mode=True)

    Keep the returned window in an instance variable so Qt doesn't garbage collect it.
    """
    w=QtWidgets.QDialog(parent)
    w.setWindowTitle("Game Catalog Editor")
    apply_character_sheet_theme(w)
    screen = QtWidgets.QApplication.primaryScreen()
    available = screen.availableGeometry() if screen is not None else None
    if available is not None:
        target_w = min(940, max(780, int(available.width() * 0.82)))
        target_h = min(700, max(560, int(available.height() * 0.82)))
        w.resize(target_w, target_h)
    else:
        w.resize(900, 660)
    w.setMinimumSize(740, 520)
    lay=QtWidgets.QVBoxLayout(w)
    editor = ImprovementEditor(w, owner_mode=owner_mode, run_tests=run_tests)
    lay.addWidget(editor)
    # Preserve text when the dialog is closed without an explicit Save click.
    def save_on_close(*_args):
        if getattr(editor, "_dirty", False):
            editor.save_current()
    w.finished.connect(save_on_close)
    w.setModal(False)
    w.show()
    return w

if __name__ == "__main__":
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Improvement Editor — Standalone Test")
    win.resize(900,660)
    win.setCentralWidget(ImprovementEditor(win, owner_mode=True))
    win.show()
    sys.exit(app.exec() if hasattr(app,"exec") else app.exec_())
