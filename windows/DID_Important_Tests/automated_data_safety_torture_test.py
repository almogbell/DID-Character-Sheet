"""
DID CHARACTER SHEET - DATA SAFETY TORTURE TEST

Place this file in the SAME folder as the current DID program files, especially:
    frontend_2_8.py
    backend_2_1.py
    character_API.py

Run:
    python automated_data_safety_torture_test.py

What it tests:
- atomic .didchar writes
- interrupted/failed atomic replacement
- version-history snapshots
- 20-version history pruning
- history migration after character rename
- corrupt history-file tolerance
- recovery write/list/delete
- stale recovery cleanup
- multiple recovery candidates
- frontend recovery debounce
- successful save -> history + recovery cleanup
- history failure does not block the real save
- Earlier Versions restore behavior
- Load Character ignores _history
- cancelled Load does not discard recovery
- successful Load with "Don't Save" discards abandoned recovery
- silent startup recovery
- last-opened character reopening
- Delete Character storage cleanup
- normal close Cancel / Don't Save recovery behavior

SAFETY:
All character/recovery files created by this test are redirected into temporary
folders. It does NOT intentionally write into your normal Saved_characters or
Recovery folders.

This runner does not require pytest.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
import importlib
import importlib.util
from pathlib import Path

# Keep Qt windows invisible during automation.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RESULTS = []


# ============================================================================
# Test helpers
# ============================================================================

def record(name, status, detail=""):
    RESULTS.append(
        {
            "name": name,
            "status": status,
            "detail": detail,
        }
    )

    marker = "PASS" if status == "PASS" else "FAIL"
    print(f"[{marker}] {name}")

    if detail:
        print(f"       {detail}")


def test(name):
    def decorator(func):
        try:
            func()
            record(name, "PASS")

        except Exception as exc:
            record(
                name,
                "FAIL",
                f"{type(exc).__name__}: {exc}",
            )
            traceback.print_exc()

        return func

    return decorator


def assert_true(value, message="Expected True"):
    if not value:
        raise AssertionError(message)


def assert_false(value, message="Expected False"):
    if value:
        raise AssertionError(message)


def assert_equal(actual, expected, message=""):
    if actual != expected:
        raise AssertionError(
            message
            or f"Expected {expected!r}, got {actual!r}"
        )


def assert_not_equal(actual, expected, message=""):
    if actual == expected:
        raise AssertionError(
            message
            or f"Expected values to differ, both were {actual!r}"
        )


def safe_close(window, app):
    try:
        window.hide()
    except Exception:
        pass

    try:
        window.deleteLater()
    except Exception:
        pass

    try:
        app.processEvents()
    except Exception:
        pass


# ============================================================================
# Local-module loading
# ============================================================================

# Application and test files deliberately live in different directories.
from test_support import app_dir, HERE as TEST_DIR
APP_DIR = app_dir()
REPORT_DIR = Path(os.environ.get("DID_TEST_REPORT_DIR", str(TEST_DIR / "reports"))).resolve()
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR = APP_DIR
sys.path.insert(0, str(BASE_DIR))


def newest_local_file(base_name):
    exact = BASE_DIR / f"{base_name}.py"

    candidates = list(
        BASE_DIR.glob(f"{base_name}*.py")
    )

    candidates = [
        path
        for path in candidates
        if path.name != Path(__file__).name
    ]

    if exact.exists():
        # Prefer the exact working filename. This avoids accidentally testing
        # an older numbered copy sitting beside it.
        return exact

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def import_local_module(module_name):
    path = newest_local_file(module_name)

    if path is None:
        return importlib.import_module(module_name)

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load {module_name} from {path}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


print("=" * 84)
print("DID CHARACTER SHEET - DATA SAFETY TORTURE TEST")
print("=" * 84)


try:
    backend = import_local_module(
        "backend_2_1"
    )

    record(
        "Import backend",
        "PASS",
        Path(backend.__file__).name,
    )

except Exception as exc:
    record(
        "Import backend",
        "FAIL",
        str(exc),
    )
    raise


try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QMessageBox as RealQMessageBox,
    )

    frontend = import_local_module(
        "frontend_2_8"
    )
    # This suite does not test dice; avoid spawning GPU WebEngine during Qt stress.
    frontend.QWebEngineView = None

    character_template = sys.modules.get(
        "character_template"
    )

    if character_template is None:
        character_template = import_local_module(
            "character_template"
        )

    record(
        "Import frontend",
        "PASS",
        Path(frontend.__file__).name,
    )

except Exception as exc:
    record(
        "Import frontend",
        "FAIL",
        str(exc),
    )
    raise


app = QApplication.instance() or QApplication(sys.argv)


class FakeQSettings:
    """In-memory replacement so torture tests never touch the real registry."""

    _stores = {}

    def __init__(self, *identity):
        self.identity = tuple(identity) or ("default",)
        self.store = self._stores.setdefault(
            self.identity,
            {},
        )

    @classmethod
    def clear_all(cls):
        cls._stores.clear()

    def value(self, key, default=None, type=None):
        value = self.store.get(key, default)

        if type is None:
            return value

        if type is bool:
            if isinstance(value, str):
                return value.strip().lower() in {
                    "1", "true", "yes", "on"
                }
            return bool(value)

        try:
            return type(value)
        except Exception:
            return default

    def setValue(self, key, value):
        self.store[key] = value

    def remove(self, key):
        self.store.pop(key, None)

    def sync(self):
        pass


# Last-opened-character logic is part of the data-safety suite. Redirect all
# QSettings calls in frontend_2_8 to memory so tests cannot alter real settings.
frontend.QSettings = FakeQSettings



# ============================================================================
# Preserve the real frontend methods before suppressing startup/modal behavior.
# ============================================================================

REAL_CHECK_RECOVERY = getattr(
    frontend.MainWindow,
    "check_for_recovery_on_startup",
    None,
)

REAL_CLOSE_EVENT = getattr(
    frontend.MainWindow,
    "closeEvent",
    None,
)

REAL_SHOW_WELCOME = getattr(
    frontend.MainWindow,
    "show_welcome_dialog_if_needed",
    None,
)

# Prevent delayed startup dialogs from appearing in ordinary tests.
frontend.MainWindow.check_for_recovery_on_startup = (
    lambda self: None
)

frontend.MainWindow.show_welcome_dialog_if_needed = (
    lambda self: None
)

# Prevent accidental close dialogs during ordinary cleanup.
frontend.MainWindow.closeEvent = (
    lambda self, event: event.accept()
)

# Suppress ordinary informational dialogs.
frontend.QMessageBox.information = staticmethod(
    lambda *a, **k: RealQMessageBox.StandardButton.Ok
)
frontend.QMessageBox.warning = staticmethod(
    lambda *a, **k: RealQMessageBox.StandardButton.Ok
)
frontend.QMessageBox.critical = staticmethod(
    lambda *a, **k: RealQMessageBox.StandardButton.Ok
)

# Default confirmations to Yes. Individual tests override this as needed.
frontend.ask_yes_no = lambda *a, **k: True


# ============================================================================
# Temporary storage sandbox
# ============================================================================

class StorageSandbox:
    def __enter__(self):
        FakeQSettings.clear_all()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.save_dir = self.root / "Saved_characters"
        self.recovery_dir = self.root / "Recovery"

        self.save_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.recovery_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.old_backend_save = (
            backend.CharacterStorageSystem.SAVE_DIR
        )
        self.old_frontend_save = (
            frontend.CharacterStorageSystem.SAVE_DIR
        )

        self.old_backend_recovery = getattr(
            backend.CharacterStorageSystem,
            "RECOVERY_DIR",
            None,
        )
        self.old_frontend_recovery = getattr(
            frontend.CharacterStorageSystem,
            "RECOVERY_DIR",
            None,
        )

        backend.CharacterStorageSystem.SAVE_DIR = str(
            self.save_dir
        )
        frontend.CharacterStorageSystem.SAVE_DIR = str(
            self.save_dir
        )

        backend.CharacterStorageSystem.RECOVERY_DIR = str(
            self.recovery_dir
        )
        frontend.CharacterStorageSystem.RECOVERY_DIR = str(
            self.recovery_dir
        )

        return self

    def __exit__(self, exc_type, exc, tb):
        backend.CharacterStorageSystem.SAVE_DIR = (
            self.old_backend_save
        )
        frontend.CharacterStorageSystem.SAVE_DIR = (
            self.old_frontend_save
        )

        if self.old_backend_recovery is not None:
            backend.CharacterStorageSystem.RECOVERY_DIR = (
                self.old_backend_recovery
            )

        if self.old_frontend_recovery is not None:
            frontend.CharacterStorageSystem.RECOVERY_DIR = (
                self.old_frontend_recovery
            )

        self.temp.cleanup()


def fresh(name="Torture Test"):
    character = (
        backend.Character.create_new_character(
            name
        )
    )
    character.validate()
    return character


def load_file(path):
    return (
        backend.CharacterStorageSystem
        .import_character_file(
            str(path)
        )
    )


def history_files_for(normal_path):
    return (
        backend.CharacterStorageSystem
        .get_character_history(
            str(normal_path)
        )
    )


def recovery_path_for(character):
    return Path(
        backend.CharacterStorageSystem
        .recovery_filepath(
            character
        )
    )


def set_hp(character, value):
    character.HP.current_HP = int(value)
    character.validate()


def make_window(character=None):
    w = frontend.MainWindow()
    w.hide()

    if character is not None:
        w.character = character
        w.current_character_filepath = None
        w.saved_character_name = character.name
        w.reconnect_character_references()
        w.refresh_all()

    app.processEvents()
    return w


# ============================================================================
# Fake QMessageBox for recovery / close-choice automation
# ============================================================================

class FakeButton:
    def __init__(self, text):
        self.text_value = text

    def setFixedSize(self, *args):
        pass

    def setObjectName(self, *args):
        pass

    def setStyleSheet(self, *args):
        pass

    def text(self):
        return self.text_value

    def setProperty(self, *args):
        pass


class FakeMessageBox:
    Icon = RealQMessageBox.Icon
    ButtonRole = RealQMessageBox.ButtonRole
    StandardButton = RealQMessageBox.StandardButton

    desired_action = "Recover"

    def __init__(self, *args, **kwargs):
        self.buttons = []
        self._text = ""
        self._title = ""

    def setIcon(self, *args):
        pass

    def setWindowTitle(self, value):
        self._title = value

    def setText(self, value):
        self._text = value

    def addButton(self, text, role):
        button = FakeButton(text)
        self.buttons.append(button)
        return button

    def exec(self):
        return 0

    def clickedButton(self):
        for button in self.buttons:
            if button.text_value == self.desired_action:
                return button

        return None

    @staticmethod
    def information(*args, **kwargs):
        return RealQMessageBox.StandardButton.Ok

    @staticmethod
    def warning(*args, **kwargs):
        return RealQMessageBox.StandardButton.Ok

    @staticmethod
    def critical(*args, **kwargs):
        return RealQMessageBox.StandardButton.Ok


class FakeCloseEvent:
    def __init__(self):
        self.accepted = False
        self.ignored = False

    def accept(self):
        self.accepted = True
        self.ignored = False

    def ignore(self):
        self.ignored = True
        self.accepted = False


class PatchRecoveryDialog:
    def __init__(self, action):
        self.action = action

    def __enter__(self):
        self.old_box = frontend.QMessageBox
        self.old_positive = frontend.make_positive_button
        self.old_negative = frontend.make_negative_button

        FakeMessageBox.desired_action = self.action

        frontend.QMessageBox = FakeMessageBox
        frontend.make_positive_button = lambda *a, **k: None
        frontend.make_negative_button = lambda *a, **k: None

    def __exit__(self, exc_type, exc, tb):
        frontend.QMessageBox = self.old_box
        frontend.make_positive_button = self.old_positive
        frontend.make_negative_button = self.old_negative


# ============================================================================
# API presence
# ============================================================================

@test("Required data-safety API exists")
def _():
    required_backend = [
        "export_character_file",
        "backup_character_file",
        "prune_character_history",
        "get_character_history",
        "migrate_character_history",
        "recovery_filepath",
        "write_recovery_file",
        "delete_recovery_file",
        "list_recovery_files",
        "find_saved_character_filepath",
        "get_recovery_candidates",
    ]

    for name in required_backend:
        assert_true(
            hasattr(
                backend.CharacterStorageSystem,
                name,
            ),
            f"Missing CharacterStorageSystem.{name}()",
        )

    required_frontend = [
        "schedule_recovery_write",
        "write_recovery_snapshot",
        "discard_current_recovery",
        "restore_previous_version_from_ui",
        "check_for_recovery_on_startup",
    ]

    for name in required_frontend:
        assert_true(
            hasattr(
                frontend.MainWindow,
                name,
            ),
            f"Missing MainWindow.{name}()",
        )


# ============================================================================
# Atomic-save tests
# ============================================================================

@test("Atomic export writes a valid complete character")
def _():
    with StorageSandbox() as env:
        c = fresh("Atomic")
        c.backstory = "complete write"

        path = env.save_dir / "Atomic.didchar"

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(path),
        )

        assert_true(path.exists())

        loaded = load_file(path)

        assert_equal(
            loaded.id,
            c.id,
        )
        assert_equal(
            loaded.backstory,
            "complete write",
        )

        leftovers = list(
            env.save_dir.glob(
                ".did_save_*.saving"
            )
        )

        assert_equal(
            leftovers,
            [],
            "Temporary atomic-save files were left behind.",
        )


@test("Injected atomic replacement failure preserves old file and cleans temp")
def _():
    with StorageSandbox() as env:
        path = env.save_dir / "AtomicFailure.didchar"

        old = fresh("Atomic Failure")
        old.backstory = "OLD SAFE STATE"

        backend.CharacterStorageSystem.export_character_file(
            old,
            str(path),
        )

        new = fresh("Atomic Failure")
        new.id = old.id
        new.backstory = "NEW STATE THAT MUST NOT PARTIALLY REPLACE OLD"

        original_replace = backend.os.replace

        def fail_replace(*args, **kwargs):
            raise OSError(
                "Injected os.replace failure"
            )

        backend.os.replace = fail_replace

        try:
            failed = False

            try:
                backend.CharacterStorageSystem.export_character_file(
                    new,
                    str(path),
                )
            except OSError:
                failed = True

            assert_true(
                failed,
                "Injected atomic-save failure did not propagate.",
            )

        finally:
            backend.os.replace = original_replace

        still_loaded = load_file(path)

        assert_equal(
            still_loaded.backstory,
            "OLD SAFE STATE",
            "The original save was damaged by a failed replacement.",
        )

        leftovers = list(
            env.save_dir.glob(
                ".did_save_*.saving"
            )
        )

        assert_equal(
            leftovers,
            [],
            "Failed atomic save left temporary .saving files behind.",
        )


# ============================================================================
# History backend tests
# ============================================================================

@test("History snapshot stores the exact current character state")
def _():
    with StorageSandbox() as env:
        c = fresh("History Exact")

        normal = env.save_dir / "History_Exact.didchar"

        set_hp(c, 7)

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(normal),
        )

        c.backstory = "SNAPSHOT VALUE"
        set_hp(c, 5)

        backend.CharacterStorageSystem.backup_character_file(
            c,
            str(normal),
        )

        history = history_files_for(
            normal
        )

        assert_equal(
            len(history),
            1,
        )

        snapshot = load_file(
            history[0]
        )

        assert_equal(
            snapshot.backstory,
            "SNAPSHOT VALUE",
        )
        assert_equal(
            snapshot.HP.current_HP,
            5,
        )


@test("Corrupt history entries are ignored")
def _():
    with StorageSandbox() as env:
        c = fresh("Corrupt History")

        normal = env.save_dir / "Corrupt_History.didchar"

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(normal),
        )

        backend.CharacterStorageSystem.backup_character_file(
            c,
            str(normal),
        )

        history_dir = (
            env.save_dir
            / "_history"
            / "Corrupt_History"
        )

        broken = history_dir / "broken.didchar"
        broken.write_text(
            "THIS IS NOT JSON",
            encoding="utf-8",
        )

        history = history_files_for(
            normal
        )

        assert_equal(
            len(history),
            1,
            "Corrupt history file was returned as a valid version.",
        )


@test("History pruning keeps exactly the newest 20 versions")
def _():
    with StorageSandbox() as env:
        c = fresh("History Limit")
        normal = env.save_dir / "History_Limit.didchar"

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(normal),
        )

        for index in range(25):
            c.backstory = f"version-{index}"

            backend.CharacterStorageSystem.backup_character_file(
                c,
                str(normal),
            )

        history = history_files_for(
            normal
        )

        assert_equal(
            len(history),
            20,
        )

        values = [
            load_file(path).backstory
            for path in history
        ]

        assert_true(
            "version-24" in values,
            "Newest history version was pruned.",
        )

        assert_false(
            "version-0" in values,
            "Oldest history version was not pruned.",
        )


@test("Character rename migrates old history to the new history folder")
def _():
    with StorageSandbox() as env:
        c = fresh("Old Name")

        old_path = env.save_dir / "Old_Name.didchar"
        new_path = env.save_dir / "New_Name.didchar"

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(old_path),
        )

        for index in range(3):
            c.backstory = f"old-history-{index}"
            backend.CharacterStorageSystem.backup_character_file(
                c,
                str(old_path),
            )

        old_history = (
            env.save_dir
            / "_history"
            / "Old_Name"
        )

        assert_true(
            old_history.exists()
        )

        backend.CharacterStorageSystem.migrate_character_history(
            str(old_path),
            str(new_path),
        )

        new_history = (
            env.save_dir
            / "_history"
            / "New_Name"
        )

        assert_true(
            new_history.exists()
        )

        assert_equal(
            len(
                list(
                    new_history.glob(
                        "*.didchar"
                    )
                )
            ),
            3,
        )

        assert_false(
            old_history.exists(),
            "Old history directory still exists after migration.",
        )


# ============================================================================
# Recovery backend tests
# ============================================================================

@test("Recovery write, list, load, and delete work")
def _():
    with StorageSandbox():
        c = fresh("Recovery Basic")
        c.backstory = "UNSAVED RECOVERY VALUE"

        path = Path(
            backend.CharacterStorageSystem.write_recovery_file(
                c
            )
        )

        assert_true(
            path.exists()
        )

        listed = (
            backend.CharacterStorageSystem
            .list_recovery_files()
        )

        assert_equal(
            [str(path)],
            listed,
        )

        loaded = load_file(
            path
        )

        assert_equal(
            loaded.backstory,
            "UNSAVED RECOVERY VALUE",
        )

        backend.CharacterStorageSystem.delete_recovery_file(
            c
        )

        assert_false(
            path.exists()
        )


@test("Corrupt recovery files are ignored")
def _():
    with StorageSandbox() as env:
        broken = (
            env.recovery_dir
            / "broken.didrecover"
        )

        broken.write_text(
            "THIS IS NOT JSON",
            encoding="utf-8",
        )

        listed = (
            backend.CharacterStorageSystem
            .list_recovery_files()
        )

        assert_equal(
            listed,
            [],
        )


@test("Stale recovery is removed; newer recovery is offered")
def _():
    with StorageSandbox() as env:
        c = fresh("Stale Recovery")
        normal = env.save_dir / "Stale_Recovery.didchar"

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(normal),
        )

        recovery = Path(
            backend.CharacterStorageSystem.write_recovery_file(
                c
            )
        )

        normal_time = os.path.getmtime(
            normal
        )

        # Force recovery older than the real save.
        os.utime(
            recovery,
            (
                normal_time - 10,
                normal_time - 10,
            ),
        )

        candidates = (
            backend.CharacterStorageSystem
            .get_recovery_candidates()
        )

        assert_equal(
            candidates,
            [],
        )

        assert_false(
            recovery.exists(),
            "Stale recovery was not deleted.",
        )

        c.backstory = "NEWER UNSAVED"
        recovery = Path(
            backend.CharacterStorageSystem.write_recovery_file(
                c
            )
        )

        newer = os.path.getmtime(
            normal
        ) + 10

        os.utime(
            recovery,
            (
                newer,
                newer,
            ),
        )

        candidates = (
            backend.CharacterStorageSystem
            .get_recovery_candidates()
        )

        assert_equal(
            len(candidates),
            1,
        )

        assert_equal(
            candidates[0]["character"].backstory,
            "NEWER UNSAVED",
        )

        assert_equal(
            os.path.normcase(
                os.path.abspath(
                    candidates[0]["normal_filepath"]
                )
            ),
            os.path.normcase(
                os.path.abspath(
                    normal
                )
            ),
        )


@test("Multiple characters can coexist as recovery candidates")
def _():
    with StorageSandbox() as env:
        candidates_expected = {}

        for name in (
            "Recovery A",
            "Recovery B",
        ):
            c = fresh(name)

            normal = (
                env.save_dir
                / (
                    backend.CharacterStorageSystem
                    .save_filename(name)
                    + ".didchar"
                )
            )

            backend.CharacterStorageSystem.export_character_file(
                c,
                str(normal),
            )

            c.backstory = f"UNSAVED {name}"

            recovery = Path(
                backend.CharacterStorageSystem.write_recovery_file(
                    c
                )
            )

            newer = (
                os.path.getmtime(normal)
                + 20
            )

            os.utime(
                recovery,
                (
                    newer,
                    newer,
                ),
            )

            candidates_expected[
                c.id
            ] = c.backstory

        candidates = (
            backend.CharacterStorageSystem
            .get_recovery_candidates()
        )

        assert_equal(
            len(candidates),
            2,
        )

        recovered = {
            item["character"].id:
            item["character"].backstory
            for item in candidates
        }

        assert_equal(
            recovered,
            candidates_expected,
        )


# ============================================================================
# Frontend recovery + save integration
# ============================================================================

@test("mark_dirty debounces recovery instead of writing immediately")
def _():
    with StorageSandbox():
        c = fresh("Debounce")
        w = make_window(c)

        recovery = recovery_path_for(
            c
        )

        assert_false(
            recovery.exists()
        )

        w.character.backstory = "typed change"
        w.mark_dirty()

        assert_true(
            w.unsaved_changes
        )

        assert_true(
            w._recovery_write_timer.isActive(),
            "Recovery debounce timer was not started.",
        )

        assert_false(
            recovery.exists(),
            "Recovery was written immediately instead of being debounced.",
        )

        QTest.qWait(900)
        app.processEvents()

        assert_true(
            recovery.exists(),
            "Debounced recovery snapshot was never written.",
        )

        recovered = load_file(
            recovery
        )

        assert_equal(
            recovered.backstory,
            "typed change",
        )

        safe_close(w, app)


@test("Successful frontend save creates history and removes recovery")
def _():
    with StorageSandbox() as env:
        c = fresh("Save Integration")
        w = make_window(c)

        w.character.backstory = "UNSAVED VALUE"
        w.mark_dirty()

        QTest.qWait(900)
        app.processEvents()

        recovery = recovery_path_for(
            c
        )

        assert_true(
            recovery.exists()
        )

        w.save_character_from_ui()

        normal = Path(
            w.current_character_filepath
        )

        assert_true(
            normal.exists()
        )

        assert_false(
            w.unsaved_changes
        )

        assert_false(
            recovery.exists(),
            "Recovery survived a successful normal save.",
        )

        history = history_files_for(
            normal
        )

        assert_true(
            len(history) >= 1
        )

        current = load_file(
            normal
        )

        newest_history = load_file(
            history[0]
        )

        assert_equal(
            current.backstory,
            "UNSAVED VALUE",
        )

        assert_equal(
            newest_history.backstory,
            "UNSAVED VALUE",
            "History snapshot did not match the successfully saved state.",
        )

        safe_close(w, app)


@test("History failure never blocks the real frontend save")
def _():
    with StorageSandbox():
        c = fresh("History Failure")
        w = make_window(c)

        w.character.backstory = "REAL SAVE MUST SUCCEED"
        w.mark_dirty()

        original_backup = (
            frontend.CharacterStorageSystem
            .backup_character_file
        )

        def injected_history_failure(
            character,
            filepath,
            **kwargs,
        ):
            raise RuntimeError(
                "Injected history failure"
            )

        frontend.CharacterStorageSystem.backup_character_file = staticmethod(
            injected_history_failure
        )

        try:
            w.save_character_from_ui()

        finally:
            frontend.CharacterStorageSystem.backup_character_file = staticmethod(
                original_backup
            )

        assert_true(
            w.current_character_filepath
        )

        assert_true(
            os.path.exists(
                w.current_character_filepath
            )
        )

        loaded = load_file(
            w.current_character_filepath
        )

        assert_equal(
            loaded.backstory,
            "REAL SAVE MUST SUCCEED",
        )

        assert_false(
            w.unsaved_changes,
            "History failure incorrectly left successful real save unsaved.",
        )

        safe_close(w, app)


@test("Frontend rename moves history and removes old normal filename")
def _():
    with StorageSandbox() as env:
        c = fresh("Before Rename")
        w = make_window(c)

        w.save_character_from_ui()

        old_normal = Path(
            w.current_character_filepath
        )

        for value in (
            "one",
            "two",
            "three",
        ):
            w.character.backstory = value
            w.unsaved_changes = True
            w.save_character_from_ui()

        old_history = (
            env.save_dir
            / "_history"
            / old_normal.stem
        )

        assert_true(
            old_history.exists()
        )

        w.character.name = "After Rename"
        w.unsaved_changes = True
        w.save_character_from_ui()

        new_normal = Path(
            w.current_character_filepath
        )

        new_history = (
            env.save_dir
            / "_history"
            / new_normal.stem
        )

        assert_true(
            new_normal.exists()
        )

        assert_false(
            old_normal.exists()
        )

        assert_true(
            new_history.exists()
        )

        assert_false(
            old_history.exists(),
            "Old history folder remained after frontend rename save.",
        )

        assert_true(
            len(
                list(
                    new_history.glob(
                        "*.didchar"
                    )
                )
            ) >= 4
        )

        safe_close(w, app)


# ============================================================================
# Restore Previous Version
# ============================================================================

@test("Earlier Versions changes RAM only and remains Unsaved")
def _():
    with StorageSandbox():
        c = fresh("Restore Test")
        w = make_window(c)

        set_hp(w.character, 8)
        w.save_character_from_ui()

        set_hp(w.character, 6)
        w.unsaved_changes = True
        w.save_character_from_ui()

        set_hp(w.character, 4)
        w.unsaved_changes = True
        w.save_character_from_ui()

        normal = Path(
            w.current_character_filepath
        )

        assert_equal(
            load_file(normal).HP.current_HP,
            4,
        )

        old_dialog = frontend.FantasyVersionHistoryDialog

        class ChooseHpSixDialog:
            def __init__(self, versions, parent=None):
                self.versions = list(versions)
                self.choice = None

                for version in self.versions:
                    candidate = load_file(
                        version["filepath"]
                    )
                    if candidate.HP.current_HP == 6:
                        self.choice = version
                        break

                if self.choice is None:
                    raise AssertionError(
                        f"Could not find HP 6 restore entry in {self.versions!r}"
                    )

            def exec(self):
                return frontend.QDialog.DialogCode.Accepted

            def selected_version(self):
                return self.choice

        frontend.FantasyVersionHistoryDialog = ChooseHpSixDialog

        try:
            w.restore_previous_version_from_ui()

        finally:
            frontend.FantasyVersionHistoryDialog = old_dialog

        assert_equal(
            w.character.HP.current_HP,
            6,
        )

        assert_true(
            w.unsaved_changes
        )

        assert_true(
            getattr(
                w,
                "_history_restore_pending",
                False,
            ),
            "Restored history state was not marked as a pending restore",
        )

        assert_equal(
            os.path.normcase(
                os.path.abspath(
                    w.current_character_filepath
                )
            ),
            os.path.normcase(
                os.path.abspath(
                    normal
                )
            ),
        )

        # Restore must not silently overwrite the normal file.
        assert_equal(
            load_file(normal).HP.current_HP,
            4,
        )

        safe_close(w, app)


# ============================================================================
# Load Character isolation / discard behavior
# ============================================================================

@test("Load Character picker ignores _history snapshots")
def _():
    with StorageSandbox() as env:
        c = fresh("Visible Character")
        normal = (
            env.save_dir
            / "Visible_Character.didchar"
        )

        backend.CharacterStorageSystem.export_character_file(
            c,
            str(normal),
        )

        backend.CharacterStorageSystem.backup_character_file(
            c,
            str(normal),
        )

        assert_true(
            history_files_for(normal)
        )

        w = make_window()
        captured = {}

        old_dialog = (
            frontend.FantasyLoadCharacterDialog
        )

        class CaptureAndCancelDialog:
            def __init__(
                self,
                records,
                parent=None,
                **kwargs,
            ):
                captured["records"] = [
                    dict(record)
                    for record in records
                ]

            def exec(self):
                return (
                    frontend.QDialog
                    .DialogCode
                    .Rejected
                )

            def selected_filepath(self):
                return None

        frontend.FantasyLoadCharacterDialog = (
            CaptureAndCancelDialog
        )

        try:
            w.load_character_from_ui()

        finally:
            frontend.FantasyLoadCharacterDialog = (
                old_dialog
            )

        paths = [
            str(
                record.get(
                    "filepath",
                    "",
                )
            )
            for record in captured.get(
                "records",
                []
            )
        ]

        assert_equal(
            len(paths),
            1,
            "History timestamp files leaked into Load Character.",
        )

        assert_equal(
            os.path.normcase(
                os.path.abspath(
                    paths[0]
                )
            ),
            os.path.normcase(
                os.path.abspath(
                    normal
                )
            ),
        )

        safe_close(
            w,
            app,
        )

@test("Cancelling Load after choosing Don't Save preserves current recovery")
def _():
    with StorageSandbox() as env:
        current = fresh(
            "Current Unsaved"
        )
        other = fresh(
            "Other Character"
        )

        other_path = (
            env.save_dir
            / "Other_Character.didchar"
        )

        backend.CharacterStorageSystem.export_character_file(
            other,
            str(other_path),
        )

        w = make_window(
            current
        )

        w.character.backstory = (
            "MUST SURVIVE CANCELLED LOAD"
        )
        w.mark_dirty()

        QTest.qWait(900)
        app.processEvents()

        recovery = recovery_path_for(
            current
        )

        assert_true(
            recovery.exists()
        )

        old_ask = frontend.ask_yes_no
        old_dialog = (
            frontend.FantasyLoadCharacterDialog
        )

        frontend.ask_yes_no = (
            lambda *a, **k: False
        )

        class CancelLoadDialog:
            def __init__(
                self,
                records,
                parent=None,
                **kwargs,
            ):
                self.records = list(
                    records
                )

            def exec(self):
                return (
                    frontend.QDialog
                    .DialogCode
                    .Rejected
                )

            def selected_filepath(self):
                return None

        frontend.FantasyLoadCharacterDialog = (
            CancelLoadDialog
        )

        try:
            w.load_character_from_ui()

        finally:
            frontend.ask_yes_no = old_ask
            frontend.FantasyLoadCharacterDialog = (
                old_dialog
            )

        assert_true(
            recovery.exists(),
            (
                "Cancelled Load discarded the current "
                "character's recovery."
            ),
        )

        assert_equal(
            w.character.id,
            current.id,
        )

        safe_close(
            w,
            app,
        )

@test("Successful Load with Don't Save discards abandoned character recovery")
def _():
    with StorageSandbox() as env:
        current = fresh(
            "Abandoned Unsaved"
        )
        other = fresh(
            "Loaded Character"
        )

        other_path = (
            env.save_dir
            / "Loaded_Character.didchar"
        )

        backend.CharacterStorageSystem.export_character_file(
            other,
            str(other_path),
        )

        w = make_window(
            current
        )

        w.character.backstory = (
            "ABANDON THIS"
        )
        w.mark_dirty()

        QTest.qWait(900)
        app.processEvents()

        recovery = recovery_path_for(
            current
        )

        assert_true(
            recovery.exists()
        )

        old_ask = frontend.ask_yes_no
        old_dialog = (
            frontend.FantasyLoadCharacterDialog
        )

        frontend.ask_yes_no = (
            lambda *a, **k: False
        )

        class ChooseLoadedCharacterDialog:
            def __init__(
                self,
                records,
                parent=None,
                **kwargs,
            ):
                self.records = list(
                    records
                )

            def exec(self):
                return (
                    frontend.QDialog
                    .DialogCode
                    .Accepted
                )

            def selected_filepath(self):
                return str(
                    other_path
                )

        frontend.FantasyLoadCharacterDialog = (
            ChooseLoadedCharacterDialog
        )

        try:
            w.load_character_from_ui()

        finally:
            frontend.ask_yes_no = old_ask
            frontend.FantasyLoadCharacterDialog = (
                old_dialog
            )

        assert_equal(
            w.character.id,
            other.id,
            "Load did not replace the current character",
        )

        assert_false(
            recovery.exists(),
            (
                "Successful Don't Save load left recovery "
                "for the abandoned character"
            ),
        )

        safe_close(
            w,
            app,
        )

def prepare_startup_recovery(env, name):
    """Create a saved character and a newer, meaningful unsaved snapshot."""
    character = fresh(name)
    normal = env.save_dir / (
        backend.CharacterStorageSystem.save_filename(name) + ".didchar"
    )
    character.backstory = "LAST SAVED VALUE"
    backend.CharacterStorageSystem.export_character_file(character, str(normal))
    character.backstory = "CRASHED UNSAVED VALUE"
    recovery = Path(
        backend.CharacterStorageSystem.write_recovery_file(character)
    )
    newer = os.path.getmtime(normal) + 20
    os.utime(recovery, (newer, newer))
    return character, normal, recovery


@test("Startup silently recovers the newest meaningful unsaved state")
def _():
    assert_true(
        REAL_CHECK_RECOVERY is not None,
        "check_for_recovery_on_startup is missing.",
    )

    with StorageSandbox() as env:
        c, normal, recovery = prepare_startup_recovery(
            env,
            "Silent Startup Recovery",
        )

        w = make_window()

        REAL_CHECK_RECOVERY(
            w
        )

        assert_equal(
            w.character.id,
            c.id,
        )

        assert_equal(
            w.character.backstory,
            "CRASHED UNSAVED VALUE",
        )

        assert_true(
            w.unsaved_changes,
            "Silently recovered work was not kept in an unsaved/protected state",
        )

        assert_true(
            getattr(w, "_silently_recovered", False),
            "Silent recovery state flag was not set",
        )

        assert_true(
            recovery.exists(),
            "Silent startup recovery deleted the safety snapshot too early",
        )

        assert_equal(
            os.path.normcase(os.path.abspath(w.current_character_filepath)),
            os.path.normcase(os.path.abspath(normal)),
        )

        safe_close(w, app)


@test("Silent startup recovery does not overwrite the normal save until Save")
def _():
    with StorageSandbox() as env:
        c, normal, recovery = prepare_startup_recovery(
            env,
            "Silent Save Boundary",
        )

        normal_before = load_file(normal).backstory

        w = make_window()
        REAL_CHECK_RECOVERY(w)

        assert_not_equal(
            normal_before,
            "CRASHED UNSAVED VALUE",
        )

        assert_equal(
            load_file(normal).backstory,
            normal_before,
            "Startup recovery silently overwrote the real save",
        )

        assert_true(
            recovery.exists(),
            "Recovery snapshot disappeared before a real save",
        )

        w.save_character_from_ui()

        assert_equal(
            load_file(normal).backstory,
            "CRASHED UNSAVED VALUE",
        )

        assert_false(
            recovery.exists(),
            "Successful real save did not clear the recovered safety snapshot",
        )

        safe_close(w, app)


@test("Startup with no recovery reopens the remembered last character")
def _():
    with StorageSandbox() as env:
        c = fresh("Remember Me")
        c.backstory = "LAST OPENED VALUE"

        normal = env.save_dir / "Remember_Me.didchar"
        backend.CharacterStorageSystem.export_character_file(
            c,
            str(normal),
        )

        settings = FakeQSettings(
            "DID",
            "CharacterSheet",
        )
        settings.setValue(
            "last_character_filepath",
            str(normal),
        )

        w = make_window()

        REAL_CHECK_RECOVERY(w)

        assert_equal(
            w.character.id,
            c.id,
        )
        assert_equal(
            w.character.backstory,
            "LAST OPENED VALUE",
        )
        assert_equal(
            os.path.normcase(os.path.abspath(w.current_character_filepath)),
            os.path.normcase(os.path.abspath(normal)),
        )
        assert_false(
            w.unsaved_changes,
            "Remembered normal save reopened as unsaved",
        )

        safe_close(w, app)


@test("Delete Character removes save, history, recovery, and last-opened reference")
def _():
    with StorageSandbox() as env:
        c = fresh("Delete Me")
        w = make_window(c)

        w.save_character_from_ui()
        normal = Path(w.current_character_filepath)

        w.character.backstory = "SECOND VERSION"
        w.unsaved_changes = True
        w.save_character_from_ui()

        history_dir = (
            env.save_dir
            / "_history"
            / normal.stem
        )

        assert_true(normal.exists())
        assert_true(history_dir.exists())

        w.character.backstory = "RECOVERY TO DELETE"
        w.mark_dirty()
        QTest.qWait(900)
        app.processEvents()

        recovery = recovery_path_for(w.character)
        assert_true(recovery.exists())

        old_id = w.character.id
        old_ask = frontend.ask_yes_no
        frontend.ask_yes_no = lambda *a, **k: True

        try:
            w.delete_current_character_from_ui()
        finally:
            frontend.ask_yes_no = old_ask

        assert_false(normal.exists(), "Delete Character left the normal save")
        assert_false(history_dir.exists(), "Delete Character left history behind")
        assert_false(recovery.exists(), "Delete Character left recovery behind")
        assert_equal(w.current_character_filepath, None)
        assert_not_equal(w.character.id, old_id)

        remembered = FakeQSettings(
            "DID",
            "CharacterSheet",
        ).value(
            "last_character_filepath",
            "",
            type=str,
        )
        assert_equal(
            remembered,
            "",
            "Delete Character left the deleted file as last-opened character",
        )

        safe_close(w, app)

# ============================================================================
# Close-event behavior
# ============================================================================

@test("Close Cancel keeps window open and keeps recovery")
def _():
    assert_true(
        REAL_CLOSE_EVENT is not None,
        "closeEvent is missing.",
    )

    with StorageSandbox():
        c = fresh("Close Cancel")
        w = make_window(c)

        w.character.backstory = "UNSAVED CLOSE VALUE"
        w.mark_dirty()

        QTest.qWait(900)
        app.processEvents()

        recovery = recovery_path_for(
            c
        )

        assert_true(
            recovery.exists()
        )

        event = FakeCloseEvent()

        with PatchRecoveryDialog(
            "Cancel"
        ):
            REAL_CLOSE_EVENT(
                w,
                event,
            )

        assert_true(
            event.ignored,
            "Cancel did not ignore the close event.",
        )

        assert_true(
            recovery.exists(),
            "Cancel incorrectly deleted recovery.",
        )

        safe_close(w, app)


@test("Close Don't Save deletes recovery and accepts close")
def _():
    with StorageSandbox():
        c = fresh("Close Dont Save")
        w = make_window(c)

        w.character.backstory = "DISCARD THIS"
        w.mark_dirty()

        QTest.qWait(900)
        app.processEvents()

        recovery = recovery_path_for(
            c
        )

        assert_true(
            recovery.exists()
        )

        event = FakeCloseEvent()

        with PatchRecoveryDialog(
            "Don't Save"
        ):
            REAL_CLOSE_EVENT(
                w,
                event,
            )

        assert_true(
            event.accepted,
            "Don't Save did not accept the close event.",
        )

        assert_false(
            recovery.exists(),
            "Don't Save did not discard recovery.",
        )

        safe_close(w, app)




# ============================================================================
# .didtemplate safety / Creation Rules recovery
# ============================================================================

@test("Atomic didtemplate save writes a complete readable template")
def _():
    with tempfile.TemporaryDirectory() as temp_dir:
        template = character_template.CharacterTemplate(
            name="Atomic Template",
            description="Complete template write",
            rules=character_template.CharacterCreationRules(
                level=3,
                extra_ip=2,
                species_mode="required",
            ),
        )

        requested = Path(temp_dir) / "atomic_template"
        saved = Path(
            character_template.CharacterTemplateStorage.save_template(
                template,
                str(requested),
            )
        )

        assert_true(saved.exists())
        assert_true(saved.name.endswith(character_template.TEMPLATE_EXTENSION))
        assert_false(Path(str(saved) + ".tmp").exists())

        loaded = character_template.CharacterTemplateStorage.load_template(str(saved))
        assert_equal(loaded.name, "Atomic Template")
        assert_equal(loaded.rules.level, 3)
        assert_equal(loaded.rules.extra_ip, 2)
        assert_equal(loaded.rules.species_mode, "required")


@test("Failed didtemplate replacement preserves the previous valid template")
def _():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "safe.didtemplate"

        old = character_template.CharacterTemplate(
            name="OLD TEMPLATE",
            description="SAFE OLD DATA",
        )
        character_template.CharacterTemplateStorage.save_template(old, str(path))

        new = character_template.CharacterTemplate(
            name="NEW TEMPLATE",
            description="MUST NOT PARTIALLY REPLACE OLD",
        )

        original_replace = character_template.os.replace

        def fail_replace(*args, **kwargs):
            raise OSError("Injected didtemplate os.replace failure")

        character_template.os.replace = fail_replace
        try:
            failed = False
            try:
                character_template.CharacterTemplateStorage.save_template(new, str(path))
            except OSError:
                failed = True
            assert_true(failed, "Injected template replacement failure did not propagate")
        finally:
            character_template.os.replace = original_replace

        loaded = character_template.CharacterTemplateStorage.load_template(str(path))
        assert_equal(loaded.name, "OLD TEMPLATE")
        assert_equal(loaded.description, "SAFE OLD DATA")
        assert_false(Path(str(path) + ".tmp").exists())


@test("Future didtemplate version is rejected instead of guessed")
def _():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "future.didtemplate"
        path.write_text(
            json.dumps(
                {
                    "file_type": character_template.TEMPLATE_FILE_TYPE,
                    "file_version": character_template.TEMPLATE_FILE_VERSION + 1,
                    "template": {"name": "Future"},
                }
            ),
            encoding="utf-8",
        )

        failed = False
        try:
            character_template.CharacterTemplateStorage.load_template(str(path))
        except ValueError:
            failed = True

        assert_true(failed, "Future template version was silently accepted")


@test("Recovery snapshot preserves Creation Rules fields")
def _():
    with StorageSandbox():
        c = fresh("Recovery Rules")
        template = character_template.CharacterTemplate(
            name="Recovery Rules Template",
            rules=character_template.CharacterCreationRules(
                level=2,
                extra_ip=3,
                species_mode="disabled",
                starting_hearts=5,
                starting_at=6,
                allow_custom_improvements=False,
                improvement_mode="ban",
                improvement_ids=["test_rule_id"],
            ),
        )
        character_template.apply_template_to_character(c, template)

        path = Path(backend.CharacterStorageSystem.write_recovery_file(c))
        loaded = load_file(path)

        for attr in (
            "creation_rules_active",
            "creation_template_name",
            "creation_species_mode",
            "creation_allow_custom_improvements",
            "creation_improvement_mode",
            "creation_improvement_ids",
        ):
            assert_equal(getattr(loaded, attr), getattr(c, attr), attr)


# ============================================================================
# Final report
# ============================================================================

passed = sum(
    result["status"] == "PASS"
    for result in RESULTS
)

failed = sum(
    result["status"] == "FAIL"
    for result in RESULTS
)

print()
print("=" * 84)
print(
    f"DATA SAFETY TORTURE TEST COMPLETE: "
    f"{passed} passed / {failed} failed"
)
print("=" * 84)

report_path = (
    REPORT_DIR
    / "automated_data_safety_torture_report.json"
)

with open(
    report_path,
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        {
            "passed": passed,
            "failed": failed,
            "results": RESULTS,
        },
        file,
        indent=2,
        ensure_ascii=False,
    )

print(
    f"Report: {report_path.name}"
)

if failed:
    sys.exit(1)
