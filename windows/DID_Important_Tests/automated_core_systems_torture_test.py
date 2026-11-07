"""
DID CHARACTER SHEET - CORE SYSTEMS TORTURE TEST

This is the second destructive automated suite.

It focuses on:
    - character math / derived values
    - improvements and IP accounting
    - inventory
    - notes
    - save/load compatibility
    - repeated round trips
    - randomized cross-system mutation ("fuzz") testing
    - selected frontend autosave/dirty-state contracts

Place this file in the SAME folder as:
    backend_2_1.py
    frontend_2_8.py
    character_API.py
    inventory_ui.py
    notes_ui.py
    improvements_ui.py
    ...

Run:
    python automated_core_systems_torture_test.py

SAFETY:
All save/recovery paths are redirected to temporary folders.
The test does not intentionally write to the normal DID character folder.

No pytest installation is required.
"""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import os
import random
import sys
import tempfile
import traceback
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RESULTS = []
SEED = 20260828


# ============================================================================
# Basic test framework
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


def first_difference(before, after, path="root"):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                return f"{path}.{key}: missing from {'before' if key not in before else 'after'}"
            difference = first_difference(before[key], after[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return f"{path}: list lengths {len(before)} -> {len(after)}"
        for index, (left, right) in enumerate(zip(before, after)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return None
    if before != after:
        return f"{path}: before={before!r}, after={after!r}"
    return None


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


# ============================================================================
# Local imports
# ============================================================================

# Application and test files deliberately live in different directories.
from test_support import app_dir, HERE as TEST_DIR
APP_DIR = app_dir()
REPORT_DIR = Path(os.environ.get("DID_TEST_REPORT_DIR", str(TEST_DIR / "reports"))).resolve()
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR = APP_DIR
sys.path.insert(0, str(BASE_DIR))


def import_local_module(module_name):
    exact = BASE_DIR / f"{module_name}.py"

    if exact.exists():
        path = exact
    else:
        candidates = list(
            BASE_DIR.glob(f"{module_name}*.py")
        )

        if not candidates:
            return importlib.import_module(
                module_name
            )

        path = max(
            candidates,
            key=lambda item: item.stat().st_mtime,
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load {module_name} from {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


print("=" * 86)
print("DID CHARACTER SHEET - CORE SYSTEMS TORTURE TEST")
print(f"Random seed: {SEED}")
print("=" * 86)

try:
    backend = import_local_module(
        "backend_2_1"
    )

    catalog = import_local_module(
        "character_API"
    )

    record(
        "Import backend and catalog",
        "PASS",
        Path(backend.__file__).name,
    )

except Exception as exc:
    record(
        "Import backend and catalog",
        "FAIL",
        str(exc),
    )
    raise


try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QMessageBox as RealQMessageBox,
    )

    frontend = import_local_module(
        "frontend_2_8"
    )
    # This suite does not test dice; avoid spawning GPU WebEngine during Qt stress.
    frontend.QWebEngineView = None

    # IMPORTANT:
    # frontend_2_8 imports these feature modules itself. Re-importing them
    # here would create second module objects, so monkey-patching ask_yes_no
    # in the test would not affect the NotesMixin / InventoryMixin methods
    # already attached to MainWindow. Reuse the exact module instances that
    # frontend imported.
    notes_ui = sys.modules.get(
        "notes_ui"
    )

    if notes_ui is None:
        notes_ui = import_local_module(
            "notes_ui"
        )

    inventory_ui = sys.modules.get(
        "inventory_ui"
    )

    if inventory_ui is None:
        inventory_ui = import_local_module(
            "inventory_ui"
        )

    character_template = sys.modules.get(
        "character_template"
    )

    if character_template is None:
        character_template = import_local_module(
            "character_template"
        )

    record(
        "Import frontend feature modules",
        "PASS",
        Path(frontend.__file__).name,
    )

except Exception as exc:
    record(
        "Import frontend feature modules",
        "FAIL",
        str(exc),
    )
    raise


app = QApplication.instance() or QApplication(
    sys.argv
)


# ============================================================================
# Prevent modal startup behavior while constructing windows.
# ============================================================================

REAL_STARTUP_RECOVERY = getattr(
    frontend.MainWindow,
    "check_for_recovery_on_startup",
    None,
)

REAL_CLOSE_EVENT = getattr(
    frontend.MainWindow,
    "closeEvent",
    None,
)

frontend.MainWindow.check_for_recovery_on_startup = (
    lambda self: None
)

frontend.MainWindow.show_welcome_dialog_if_needed = (
    lambda self: None
)

frontend.MainWindow.closeEvent = (
    lambda self, event: event.accept()
)

frontend.QMessageBox.information = staticmethod(
    lambda *a, **k:
    RealQMessageBox.StandardButton.Ok
)

frontend.QMessageBox.warning = staticmethod(
    lambda *a, **k:
    RealQMessageBox.StandardButton.Ok
)

frontend.QMessageBox.critical = staticmethod(
    lambda *a, **k:
    RealQMessageBox.StandardButton.Ok
)

frontend.ask_yes_no = (
    lambda *a, **k: True
)

notes_ui.ask_yes_no = (
    lambda *a, **k: True
)

inventory_ui.ask_yes_no = (
    lambda *a, **k: True
)


# ============================================================================
# Temporary storage isolation
# ============================================================================

class StorageSandbox:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp.name
        )

        self.save_dir = (
            self.root
            / "Saved_characters"
        )

        self.recovery_dir = (
            self.root
            / "Recovery"
        )

        self.save_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.recovery_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.targets = []

        for module in (
            backend,
            frontend,
        ):
            storage = (
                module.CharacterStorageSystem
            )

            old_save = storage.SAVE_DIR
            old_recovery = getattr(
                storage,
                "RECOVERY_DIR",
                None,
            )

            self.targets.append(
                (
                    storage,
                    old_save,
                    old_recovery,
                )
            )

            storage.SAVE_DIR = str(
                self.save_dir
            )

            if hasattr(
                storage,
                "RECOVERY_DIR",
            ):
                storage.RECOVERY_DIR = str(
                    self.recovery_dir
                )

        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        for (
            storage,
            old_save,
            old_recovery,
        ) in self.targets:
            storage.SAVE_DIR = old_save

            if old_recovery is not None:
                storage.RECOVERY_DIR = (
                    old_recovery
                )

        self.temp.cleanup()


# ============================================================================
# Shared helpers
# ============================================================================

def fresh(
    name="Core Torture",
    rich=True,
):
    c = backend.Character.create_new_character(
        name
    )

    if rich:
        # Give destructive improvement tests enough IP without changing level
        # formulas in tests that explicitly create rich=False characters.
        c.progression.current_IP = 500

    c.validate()
    return c


def snapshot(character):
    return (
        backend.CharacterStorageSystem
        .character_to_dict(
            character
        )
    )


def clone_character(character):
    return (
        backend.CharacterStorageSystem
        .character_from_dict(
            copy.deepcopy(
                snapshot(character)
            )
        )
    )


def assert_roundtrip_equal(
    character,
    message="Character changed during dict round trip",
):
    before = snapshot(character)

    loaded = (
        backend.CharacterStorageSystem
        .character_from_dict(
            copy.deepcopy(before)
        )
    )

    after = snapshot(loaded)

    assert_equal(
        after,
        before,
        f"{message}; {first_difference(before, after)}",
    )

    return loaded


def file_roundtrip(
    character,
    filepath,
):
    backend.CharacterStorageSystem.export_character_file(
        character,
        str(filepath),
    )

    loaded = (
        backend.CharacterStorageSystem
        .import_character_file(
            str(filepath)
        )
    )

    assert_equal(
        snapshot(loaded),
        snapshot(character),
        "Character changed during .didchar file round trip",
    )

    return loaded


def make_window(character=None):
    w = frontend.MainWindow()
    w.hide()

    if character is not None:
        w.character = character
        w.current_character_filepath = None
        w.saved_character_name = (
            character.name
        )

        w.reconnect_character_references()
        w.refresh_all()

    app.processEvents()
    return w


def safe_close(window):
    try:
        if hasattr(
            window,
            "_recovery_write_timer",
        ):
            window._recovery_write_timer.stop()
    except Exception:
        pass

    try:
        window.hide()
    except Exception:
        pass

    try:
        window.deleteLater()
    except Exception:
        pass

    app.processEvents()


def generic_choices_for(
    purchase,
):
    required = purchase.get(
        "requires_choices",
        [],
    ) or []

    values = {
        "stat_name": "strength",
        "magic_school": "Test School",
        "magic_school_description": "Automated test school.",
        "buddy_name": "Test Buddy",
        "buddy_stat_d6": "agility",
        "buddy_stat_d8_a": "strength",
        "buddy_stat_d8_b": "finesse",
        "buddy_stat_d10": "instinct",
        "buddy_perk": "Test Perk",
        "buddy_training_stat": "knowledge",
        "attuned_land": "forest",
        "tell": "glowing eyes",
        "deity_name": "Test Deity",
        "deity_domain": "Testing",
        "skill_name": "Testing",
        "skill_description": "Automated skill.",
        "artificer_item_description": "Automated item.",
        "specific_magic_effect": "Automated magical effect.",
    }

    choices = {}

    for key in required:
        choices[key] = values.get(
            key,
            f"Test {key}",
        )

    return choices


def get_available(
    character,
):
    return (
        backend.ImprovementSystem
        .get_available_purchases(
            character
        )
    )


def buy_option(
    character,
    purchase,
):
    return (
        backend.ImprovementSystem
        .buy_purchase(
            character,
            purchase,
            choices=generic_choices_for(
                purchase
            ),
        )
    )


def buy_by(
    character,
    *,
    catalog_id=None,
    group_id=None,
    kind=None,
):
    for purchase in get_available(
        character
    ):
        if (
            catalog_id is not None
            and purchase.get(
                "catalog_id"
            ) != catalog_id
        ):
            continue

        if (
            group_id is not None
            and purchase.get(
                "group_id"
            ) != group_id
        ):
            continue

        if (
            kind is not None
            and purchase.get(
                "kind"
            ) != kind
        ):
            continue

        if not buy_option(
            character,
            purchase,
        ):
            raise AssertionError(
                f"Could not buy {purchase}"
            )

        return purchase

    raise AssertionError(
        "Purchase not available: "
        f"catalog_id={catalog_id}, "
        f"group_id={group_id}, "
        f"kind={kind}"
    )


VALID_NOTE_COLORS = {
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
}


def assert_character_invariants(
    character,
):
    character.validate()

    # Stats
    for name in backend.STAT_NAMES:
        stat = character.stats.get_stat(
            name
        )

        assert_true(
            stat is not None,
            f"Missing stat {name}",
        )

        assert_true(
            stat.die_size
            in backend.VALID_DIE_SIZES,
            (
                f"{name} has invalid die "
                f"d{stat.die_size}"
            ),
        )

        assert_true(
            stat.bonus >= 0,
            f"{name} bonus became negative",
        )

    # HP
    assert_true(
        character.HP.max_HP >= 0
    )

    assert_true(
        0
        <= character.HP.current_HP
        <= character.HP.max_HP,
        "Current HP left valid bounds",
    )

    assert_true(
        0
        <= character.HP.temp_HP
        <= character.HP.max_HP,
        "Temp HP left valid bounds",
    )

    # AT
    assert_true(
        character.adversity.max_AT
        >= 0
    )

    assert_true(
        0
        <= character.adversity.current_AT
        <= character.adversity.max_AT,
        "Current AT left valid bounds",
    )

    # Inventory
    for item in (
        character.inventory
        .list_of_items
    ):
        assert_true(
            item.quantity >= 0,
            "Inventory quantity became negative",
        )

        assert_true(
            isinstance(
                item.name,
                str,
            )
        )

        assert_true(
            isinstance(
                item.description,
                str,
            )
        )

    # Notes
    for note in (
        character.notes
        .list_of_notes
    ):
        assert_true(
            isinstance(
                note,
                backend.CharacterNote,
            ),
            "Invalid note object survived validation",
        )

        assert_true(
            note.color
            in VALID_NOTE_COLORS,
            "Invalid note color survived validation",
        )

    # IP is a derived invariant in current backend.
    # Mirror the documented tier/credit calculation, independently of
    # progression.used_IP.  Heightened Ability IP rows are already represented
    # by stat bonus tiers, and species-granted tiers must not cost IP.
    free_stats = character.free_heightened_ability_stats[:character.free_heightened_ability_slots]
    tiers = {name: character.free_heightened_ability_stats.count(name)
             for name in backend.STAT_NAMES}
    paid_heightened = 0
    species_heightened_credit = 0
    for improvement in character.improvements.list_of_taken_improvements:
        name = improvement.choices.get("stat_name")
        if improvement.catalog_id != "heightened_ability" or name not in tiers:
            continue
        tiers[name] += 1
        if improvement.source == "ip":
            paid_heightened += tiers[name]
        else:
            species_heightened_credit += tiers[name]
    expected_used_ip = (
        character.improvements.total_cost()
        - paid_heightened
        + character.stats.total_bonus_cost(free_stats)
        - species_heightened_credit
    )

    assert_equal(
        character.progression.used_IP,
        expected_used_ip,
        "used_IP does not match derived improvement/stat cost",
    )

    assert_equal(
        character.progression.available_IP,
        (
            character.progression.current_IP
            - character.progression.used_IP
        ),
    )

    # JSON serializability is essential for save/recovery.
    json.dumps(
        snapshot(character),
        ensure_ascii=False,
    )


# ============================================================================
# API / structural tests
# ============================================================================

@test("Required core backend APIs exist")
def _():
    requirements = {
        "Character": [
            "create_new_character",
            "validate",
            "set_level",
        ],
        "ImprovementSystem": [
            "get_available_purchases",
            "buy_purchase",
            "remove_improvement",
            "remove_empowerment",
        ],
        "InventorySystem": [
            "add_item",
            "remove_item",
            "set_quantity",
            "adjust_quantity",
            "toggle_expanded",
        ],
        "HPSystem": [
            "set_HP",
            "add_HP",
            "remove_HP",
        ],
        "ATSystem": [
            "set_current_AT",
            "click_at_slot",
        ],
        "StatSystem": [
            "set_die_size",
            "add_free_heightened_ability",
            "remove_free_heightened_ability",
        ],
        "CharacterStorageSystem": [
            "character_to_dict",
            "character_from_dict",
            "export_character_file",
            "import_character_file",
        ],
    }

    for class_name, names in requirements.items():
        cls = getattr(
            backend,
            class_name,
            None,
        )

        assert_true(
            cls is not None,
            f"Missing backend.{class_name}",
        )

        for name in names:
            assert_true(
                hasattr(
                    cls,
                    name,
                ),
                f"Missing {class_name}.{name}()",
            )


@test("Explicit tied improvement sort orders survive serialization")
def _():
    c = fresh()
    for index in range(2):
        c.improvements.list_of_taken_improvements.append(
            backend.Improvement(
                id=str(uuid4()),
                catalog_id="custom",
                name=f"Sort order {index}",
                cost=0,
                description="",
                sort_order=3,
            )
        )
    c.validate()
    assert_roundtrip_equal(c, "Tied sort orders changed on load")

    # In older saves without sort_order, derive stable indices from list order.
    legacy = snapshot(c)
    for item in legacy["improvements"]["list_of_taken_improvements"]:
        item.pop("sort_order", None)
    migrated = backend.CharacterStorageSystem.character_from_dict(legacy)
    assert_equal(
        [imp.sort_order for imp in migrated.improvements.list_of_taken_improvements],
        [0, 1],
        "Legacy improvement list order was not migrated",
    )


# ============================================================================
# Character math
# ============================================================================

@test("Level 1-27 progression math has no drift")
def _():
    for level in range(
        1,
        28,
    ):
        c = fresh(
            rich=False
        )

        c.set_level(
            level
        )

        milestones = level - 1

        assert_equal(
            c.progression.level,
            level,
        )

        assert_equal(
            c.progression.current_IP,
            (
                backend.STARTING_IP
                + milestones * 2
            ),
        )

        assert_equal(
            c.adversity.max_AT,
            (
                backend.STARTING_AT
                + milestones
            ),
        )

        assert_equal(
            c.HP.max_hearts,
            (
                backend.STARTING_HEARTS
                + milestones
            ),
        )

        assert_equal(
            c.HP.max_HP,
            c.HP.max_hearts * 4,
        )

        assert_character_invariants(
            c
        )


@test("Repeated set_level calls are idempotent")
def _():
    c = fresh(
        rich=False
    )

    for _ in range(20):
        c.set_level(17)

    first = snapshot(
        c
    )

    for _ in range(20):
        c.set_level(17)

    second = snapshot(
        c
    )

    assert_equal(
        second,
        first,
        "Repeated set_level accumulated drift",
    )


@test("set_level without healing preserves current HP when possible")
def _():
    c = fresh(
        rich=False
    )

    backend.HPSystem.set_HP(
        c,
        3,
    )

    c.set_level(
        10,
        heal_to_new_max=False,
    )

    assert_equal(
        c.HP.current_HP,
        3,
    )

    assert_character_invariants(
        c
    )


@test("HP and temp HP clamp against extreme values")
def _():
    c = fresh(
        rich=False
    )

    backend.HPSystem.set_HP(
        c,
        10**9,
    )

    assert_equal(
        c.HP.current_HP,
        c.HP.max_HP,
    )

    backend.HPSystem.set_HP(
        c,
        -(10**9),
    )

    assert_equal(
        c.HP.current_HP,
        0,
    )

    c.HP.temp_HP = 10**9
    c.validate()

    assert_equal(
        c.HP.temp_HP,
        c.HP.max_HP,
    )

    c.HP.temp_HP = -999
    c.validate()

    assert_equal(
        c.HP.temp_HP,
        0,
    )


@test("AT click semantics stay within bounds for every slot")
def _():
    c = fresh(
        rich=False
    )

    c.set_level(12)

    for index in range(
        c.adversity.max_AT
    ):
        c.adversity.current_AT = 0
        c.validate()

        assert_true(
            backend.ATSystem.click_at_slot(
                c,
                index,
            )
        )

        assert_equal(
            c.adversity.current_AT,
            index + 1,
        )

        assert_true(
            backend.ATSystem.click_at_slot(
                c,
                index,
            )
        )

        assert_equal(
            c.adversity.current_AT,
            index,
        )

    assert_false(
        backend.ATSystem.click_at_slot(
            c,
            -1,
        )
    )

    assert_false(
        backend.ATSystem.click_at_slot(
            c,
            c.adversity.max_AT,
        )
    )


@test("Defense DR follows selected stat and its derived bonus")
def _():
    c = fresh(
        rich=False
    )

    assert_true(
        backend.StatSystem.set_die_size(
            c,
            "strength",
            12,
        )
    )

    assert_true(
        backend.StatSystem.set_die_size(
            c,
            "agility",
            8,
        )
    )

    assert_equal(
        c.defense_stat_name,
        "strength",
    )

    assert_equal(
        c.DR,
        6,
    )

    c.selected_defense_stat_name = (
        "agility"
    )

    c.validate()

    assert_equal(
        c.defense_stat_name,
        "agility",
    )

    assert_equal(
        c.DR,
        4,
    )

    assert_true(
        backend.StatSystem.add_free_heightened_ability(
            c,
            "agility",
        )
    )

    assert_equal(
        c.DR,
        5,
    )


@test("Validation is idempotent across 100 passes")
def _():
    c = fresh()

    backend.InventorySystem.add_item(
        c,
        "Rope",
        "Long rope",
        5,
    )

    c.notes.list_of_notes.append(
        backend.CharacterNote(
            id=str(uuid4()),
            title="Test",
            text="Text",
            color="green",
        )
    )

    before = snapshot(
        c
    )

    for _ in range(100):
        c.validate()

    after = snapshot(
        c
    )

    assert_equal(
        after,
        before,
        "Repeated validation changed a stable character",
    )


# ============================================================================
# Heightened ability / IP accounting
# ============================================================================

@test("Heightened Ability add/remove always preserves IP derivation")
def _():
    c = fresh()

    sequence = [
        "strength",
        "agility",
        "strength",
        "strength",
    ]

    for stat_name in sequence:
        backend.StatSystem.add_free_heightened_ability(
            c,
            stat_name,
        )

        assert_character_invariants(
            c
        )

    while (
        c.free_heightened_ability_stats
    ):
        target = (
            c.free_heightened_ability_stats[
                -1
            ]
        )

        assert_true(
            backend.StatSystem.remove_free_heightened_ability(
                c,
                target,
            )
        )

        assert_character_invariants(
            c
        )

    assert_equal(
        c.progression.used_IP,
        0,
    )


# ============================================================================
# Inventory
# ============================================================================

@test("Inventory clamps negative quantities and rejects missing IDs")
def _():
    c = fresh()

    backend.InventorySystem.add_item(
        c,
        "Negative",
        "Testing negative quantity",
        -500,
    )

    item = (
        c.inventory
        .list_of_items[0]
    )

    assert_equal(
        item.quantity,
        0,
    )

    assert_false(
        backend.InventorySystem.set_quantity(
            c,
            "missing-id",
            10,
        )
    )

    assert_false(
        backend.InventorySystem.remove_item(
            c,
            "missing-id",
        )
    )

    assert_false(
        backend.InventorySystem.toggle_expanded(
            c,
            "missing-id",
        )
    )


@test("Inventory survives 1,000 hostile quantity changes")
def _():
    rng = random.Random(
        SEED + 1
    )

    c = fresh()

    backend.InventorySystem.add_item(
        c,
        "Counter",
        "Stress quantity",
        1,
    )

    item = (
        c.inventory
        .list_of_items[0]
    )

    for _ in range(1000):
        delta = rng.randint(
            -1000,
            1000,
        )

        assert_true(
            backend.InventorySystem.adjust_quantity(
                c,
                item.id,
                delta,
            )
        )

        assert_true(
            item.quantity >= 0,
            "Quantity became negative",
        )

    assert_character_invariants(
        c
    )


@test("Large Unicode inventory survives exact file round trip")
def _():
    with StorageSandbox() as env:
        c = fresh()

        for index in range(75):
            backend.InventorySystem.add_item(
                c,
                (
                    f"Item {index} — "
                    "שלום 日本語 🐉"
                ),
                (
                    "Description\n"
                    f"line {index}\n"
                    "symbols: <>&\"'"
                ),
                index,
            )

        path = (
            env.save_dir
            / "unicode_inventory.didchar"
        )

        loaded = file_roundtrip(
            c,
            path,
        )

        assert_equal(
            len(
                loaded.inventory
                .list_of_items
            ),
            75,
        )


# ============================================================================
# Notes
# ============================================================================

@test("Note validation cleans invalid colors and invalid list members")
def _():
    c = fresh()

    valid = backend.CharacterNote(
        id=str(uuid4()),
        title="  Valid title  ",
        text="Text",
        color="not-real",
    )

    c.notes.list_of_notes = [
        valid,
        "not a note",
        None,
        123,
    ]

    c.validate()

    assert_equal(
        len(
            c.notes.list_of_notes
        ),
        1,
    )

    assert_equal(
        c.notes.list_of_notes[0].title,
        "Valid title",
    )

    assert_equal(
        c.notes.list_of_notes[0].color,
        "yellow",
    )


@test("Large multiline Unicode notes survive exact round trip")
def _():
    with StorageSandbox() as env:
        c = fresh()

        text = "\n".join(
            (
                f"Line {i}: "
                "שלום / 日本語 / 🐉 / <tag>"
            )
            for i in range(250)
        )

        c.notes.list_of_notes.append(
            backend.CharacterNote(
                id=str(uuid4()),
                title="Very Long Note",
                text=text,
                color="purple",
                expanded=True,
            )
        )

        c.validate()

        loaded = file_roundtrip(
            c,
            (
                env.save_dir
                / "notes.didchar"
            ),
        )

        assert_equal(
            loaded.notes.list_of_notes[0].text,
            text,
        )


@test("Opening Notes never duplicates an existing note")
def _():
    with StorageSandbox():
        c = fresh()

        c.notes.list_of_notes.append(
            backend.CharacterNote(
                id=str(uuid4()),
                title="Existing",
                text="Keep me",
                color="yellow",
            )
        )

        c.validate()

        w = make_window(
            c
        )

        w.unsaved_changes = False

        original_count = len(
            w.character.notes
            .list_of_notes
        )

        for _ in range(10):
            w.open_notes_board()
            w.close_notes_board()

        assert_equal(
            len(
                w.character.notes
                .list_of_notes
            ),
            original_count,
            "Repeated opening duplicated notes",
        )

        assert_false(
            w.unsaved_changes,
            "Opening/closing Notes marked character dirty",
        )

        safe_close(
            w
        )


@test("Empty note deletion is immediate; non-empty cancellation is safe")
def _():
    with StorageSandbox():
        c = fresh()

        empty = backend.CharacterNote(
            id=str(uuid4()),
            title="",
            text="",
            color="yellow",
        )

        nonempty = backend.CharacterNote(
            id=str(uuid4()),
            title="Important",
            text="Do not delete",
            color="blue",
        )

        c.notes.list_of_notes = [
            empty,
            nonempty,
        ]

        c.validate()

        # ------------------------------------------------------------
        # Logic-only NotesMixin harness
        # ------------------------------------------------------------
        #
        # This test is specifically about deletion semantics.
        #
        # frontend_2_8's MainWindow creates a much richer responsive UI and
        # installs application-level Qt styling/event hooks. Constructing and
        # destroying a complete window here can leave queued Qt layout events
        # involving widgets from earlier tests. That is unrelated to whether
        # confirm_delete_note() correctly removes/preserves model data.
        #
        # So invoke the REAL NotesMixin method on the smallest object that
        # satisfies its contract. The dedicated redesign UI torture suite will
        # separately exercise actual NoteCard destruction/rebuilding.
        class NoteDeleteHarness:
            confirm_delete_note = (
                notes_ui.NotesMixin.confirm_delete_note
            )

            def __init__(self, character):
                self.character = character
                self.autosave_count = 0
                self.refresh_count = 0

            def block_if_readonly(self):
                return False

            def ensure_character_notes(self):
                self.character.notes.validate()

            def mark_dirty(self, auto_save=False):
                if auto_save:
                    self.autosave_count += 1

            def refresh_all(self):
                self.refresh_count += 1

            def refresh_note_links(self):
                self.refresh_count += 1

        harness = NoteDeleteHarness(c)

        # Empty -> immediate deletion and autosave request.
        harness.confirm_delete_note(
            empty
        )

        assert_false(
            empty in (
                harness.character.notes
                .list_of_notes
            )
        )

        assert_equal(
            harness.autosave_count,
            1,
        )

        assert_equal(
            harness.refresh_count,
            1,
        )

        # Non-empty -> cancellation must preserve it and must not
        # create an additional autosave/refresh.
        old_ask = notes_ui.ask_yes_no

        notes_ui.ask_yes_no = (
            lambda *a, **k: False
        )

        try:
            harness.confirm_delete_note(
                nonempty
            )

        finally:
            notes_ui.ask_yes_no = old_ask

        assert_true(
            nonempty in (
                harness.character.notes
                .list_of_notes
            )
        )

        assert_equal(
            harness.autosave_count,
            1,
        )

        assert_equal(
            harness.refresh_count,
            1,
        )


@test("System NoteCard cannot edit title or body")
def _():
    c = fresh()

    note = backend.CharacterNote(
        id=str(uuid4()),
        title="Spellcasting Verbs",
        text=notes_ui.SPELLCASTING_VERBS_NOTE_TEXT,
        color="blue",
    )

    original_title = note.title
    original_text = note.text

    changed = {
        "count": 0
    }

    card = notes_ui.NoteCard(
        note,
        lambda: changed.__setitem__(
            "count",
            changed["count"] + 1,
        ),
        lambda *_: None,
    )

    card.on_title_edited(
        "HACKED TITLE"
    )

    card.on_text_changed()

    assert_equal(
        note.title,
        original_title,
    )

    assert_equal(
        note.text,
        original_text,
    )

    assert_equal(
        changed["count"],
        0,
    )

    card.deleteLater()
    app.processEvents()


# ============================================================================
# Improvements
# ============================================================================

@test("Available purchase list never contains an unaffordable positive-IP option")
def _():
    c = fresh(
        rich=False
    )

    c.progression.current_IP = (
        c.progression.used_IP
    )

    c.validate()

    purchases = get_available(
        c
    )

    for purchase in purchases:
        source = purchase.get(
            "source",
            "ip",
        )

        cost = int(
            purchase.get(
                "cost",
                0,
            )
        )

        if (
            source == "ip"
            and cost > 0
        ):
            raise AssertionError(
                "Unaffordable purchase leaked into available list: "
                f"{purchase}"
            )


@test("Every successful purchase preserves derived IP accounting")
def _():
    rng = random.Random(
        SEED + 2
    )

    c = fresh()

    successes = 0

    for _ in range(120):
        options = get_available(
            c
        )

        if not options:
            break

        purchase = rng.choice(
            options
        )

        if buy_option(
            c,
            purchase,
        ):
            successes += 1

            assert_character_invariants(
                c
            )

            if successes % 5 == 0:
                assert_roundtrip_equal(
                    c
                )

    assert_true(
        successes >= 20,
        (
            "Stress purchase test could buy only "
            f"{successes} options"
        ),
    )


@test("Buying then removing a simple improvement refunds its IP")
def _():
    c = fresh()

    before = (
        c.progression.used_IP
    )

    assert_true(
        backend.ImprovementSystem.add_from_catalog(
            c,
            "wild_eyes",
        )
    )

    improvement = (
        c.improvements
        .get_first_by_catalog_id(
            "wild_eyes"
        )
    )

    assert_true(
        improvement is not None
    )

    assert_true(
        c.progression.used_IP
        > before
    )

    assert_true(
        backend.ImprovementSystem.remove_improvement(
            c,
            improvement.id,
        )
    )

    assert_equal(
        c.progression.used_IP,
        before,
    )

    assert_character_invariants(
        c
    )


@test("Hearty scaling adds/removes only one rank at a time")
def _():
    c = fresh()

    base_hp = c.HP.max_HP

    for rank in (
        1,
        2,
        3,
    ):
        assert_true(
            backend.ImprovementSystem.add_from_catalog(
                c,
                "hearty",
            )
        )

        improvement = (
            c.improvements
            .get_first_by_catalog_id(
                "hearty"
            )
        )

        assert_equal(
            improvement.times_taken,
            rank,
        )

        assert_character_invariants(
            c
        )

    assert_false(
        backend.ImprovementSystem.add_from_catalog(
            c,
            "hearty",
        )
    )

    improvement = (
        c.improvements
        .get_first_by_catalog_id(
            "hearty"
        )
    )

    assert_true(
        c.HP.max_HP
        > base_hp
    )

    assert_true(
        backend.ImprovementSystem.remove_improvement(
            c,
            improvement.id,
        )
    )

    assert_equal(
        improvement.times_taken,
        2,
    )

    assert_character_invariants(
        c
    )


@test("Species purchase costs zero IP and second species is blocked")
def _():
    c = fresh()

    before = (
        c.progression.used_IP
    )

    assert_true(
        backend.ImprovementSystem.add_from_catalog(
            c,
            "wild_eyes",
            source="species",
        )
    )

    assert_equal(
        c.progression.used_IP,
        before,
    )

    assert_false(
        backend.ImprovementSystem.add_from_catalog(
            c,
            "camouflage",
            source="species",
        )
    )

    assert_character_invariants(
        c
    )


# ============================================================================
# Save/load compatibility
# ============================================================================

@test("Current .didchar wrapper is exactly round-trip stable")
def _():
    with StorageSandbox() as env:
        c = fresh(
            "Compatibility Current"
        )

        backend.InventorySystem.add_item(
            c,
            "Rope",
            "50 feet",
            2,
        )

        c.notes.list_of_notes.append(
            backend.CharacterNote(
                id=str(uuid4()),
                title="Notes",
                text="Text",
                color="green",
            )
        )

        backend.StatSystem.add_free_heightened_ability(
            c,
            "strength",
        )

        c.validate()

        file_roundtrip(
            c,
            (
                env.save_dir
                / "current.didchar"
            ),
        )


@test("Legacy raw JSON character format still imports")
def _():
    with StorageSandbox() as env:
        c = fresh(
            "Legacy Raw"
        )

        backend.InventorySystem.add_item(
            c,
            "Legacy Item",
            "Old raw JSON",
            3,
        )

        raw = snapshot(
            c
        )

        path = (
            env.save_dir
            / "legacy_raw.json"
        )

        path.write_text(
            json.dumps(
                raw,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        assert_true(
            backend.CharacterStorageSystem.looks_like_character_file(
                str(path)
            )
        )

        loaded = (
            backend.CharacterStorageSystem
            .import_character_file(
                str(path)
            )
        )

        assert_equal(
            snapshot(loaded),
            raw,
        )


@test("Missing optional legacy sections load using safe defaults")
def _():
    c = fresh(
        "Missing Optional"
    )

    raw = snapshot(
        c
    )

    for key in (
        "notes",
        "image",
        "bonus_dice",
        "creation_rules",
        "selected_defense_stat_name",
        "combat_mode_enabled",
    ):
        raw.pop(
            key,
            None,
        )

    loaded = (
        backend.CharacterStorageSystem
        .character_from_dict(
            raw
        )
    )

    assert_equal(
        loaded.name,
        c.name,
    )

    assert_true(
        hasattr(
            loaded,
            "notes",
        )
    )

    assert_true(
        hasattr(
            loaded,
            "image",
        )
    )

    assert_true(
        hasattr(
            loaded,
            "bonus_dice",
        )
    )

    assert_character_invariants(
        loaded
    )


@test("Unknown future fields are ignored without damaging known data")
def _():
    c = fresh(
        "Future Fields"
    )

    raw = snapshot(
        c
    )

    raw["future_top_level"] = {
        "anything": [
            1,
            2,
            3,
        ]
    }

    raw["stats"]["strength"][
        "future_stat_field"
    ] = "future"

    loaded = (
        backend.CharacterStorageSystem
        .character_from_dict(
            raw
        )
    )

    assert_equal(
        loaded.id,
        c.id,
    )

    assert_equal(
        loaded.name,
        c.name,
    )

    assert_character_invariants(
        loaded
    )


@test("Fifty consecutive save/load cycles do not accumulate drift")
def _():
    with StorageSandbox() as env:
        c = fresh(
            "Repeated Roundtrip"
        )

        backend.InventorySystem.add_item(
            c,
            "Persistent",
            "Repeated save",
            9,
        )

        c.notes.list_of_notes.append(
            backend.CharacterNote(
                id=str(uuid4()),
                title="Persistent Note",
                text="This must survive.",
                color="orange",
            )
        )

        backend.StatSystem.add_free_heightened_ability(
            c,
            "strength",
        )

        backend.ImprovementSystem.add_from_catalog(
            c,
            "wild_eyes",
        )

        c.validate()

        expected = snapshot(
            c
        )

        path = (
            env.save_dir
            / "repeat.didchar"
        )

        for _ in range(50):
            backend.CharacterStorageSystem.export_character_file(
                c,
                str(path),
            )

            c = (
                backend.CharacterStorageSystem
                .import_character_file(
                    str(path)
                )
            )

            assert_equal(
                snapshot(c),
                expected,
                "Character drifted during repeated save/load",
            )


# ============================================================================
# Frontend dirty/autosave contracts
# ============================================================================

@test("Inventory quantity buttons mark dirty but do not normal-autosave")
def _():
    with StorageSandbox():
        c = fresh()

        backend.InventorySystem.add_item(
            c,
            "Counter",
            "Quantity contract",
            1,
        )

        item = (
            c.inventory
            .list_of_items[0]
        )

        w = make_window(
            c
        )

        autosaves = {
            "count": 0
        }

        old_auto = w.auto_save_character

        w.auto_save_character = (
            lambda:
            autosaves.__setitem__(
                "count",
                autosaves["count"] + 1,
            )
        )

        w.unsaved_changes = False

        w.increase_inventory_item(
            item
        )

        assert_equal(
            item.quantity,
            2,
        )

        assert_true(
            w.unsaved_changes
        )

        assert_equal(
            autosaves["count"],
            0,
            "Quantity + triggered normal autosave",
        )

        w.unsaved_changes = False

        w.decrease_inventory_item(
            item
        )

        assert_equal(
            item.quantity,
            1,
        )

        assert_true(
            w.unsaved_changes
        )

        assert_equal(
            autosaves["count"],
            0,
            "Quantity - triggered normal autosave",
        )

        w.auto_save_character = (
            old_auto
        )

        safe_close(
            w
        )


@test("Note body edit marks dirty without immediate normal autosave")
def _():
    with StorageSandbox():
        c = fresh()

        note = backend.CharacterNote(
            id=str(uuid4()),
            title="Editable",
            text="Original",
            color="yellow",
        )

        c.notes.list_of_notes.append(
            note
        )

        w = make_window(
            c
        )

        autosaves = {
            "count": 0
        }

        old_auto = w.auto_save_character

        w.auto_save_character = (
            lambda:
            autosaves.__setitem__(
                "count",
                autosaves["count"] + 1,
            )
        )

        card = notes_ui.NoteCard(
            note,
            w.on_note_changed,
            w.confirm_delete_note,
            w,
        )

        w.unsaved_changes = False

        card.text_edit.setPlainText(
            "Changed but still focused"
        )

        app.processEvents()

        assert_equal(
            note.text,
            "Changed but still focused",
        )

        assert_true(
            w.unsaved_changes
        )

        assert_equal(
            autosaves["count"],
            0,
            "Note typing immediately normal-autosaved",
        )

        card.deleteLater()

        w.auto_save_character = (
            old_auto
        )

        safe_close(
            w
        )


# ============================================================================
# Randomized destructive cross-system testing
# ============================================================================

def random_operation(
    rng,
    character,
):
    operation = rng.choice(
        (
            "hp",
            "at",
            "stat",
            "inventory_add",
            "inventory_qty",
            "inventory_remove",
            "note_add",
            "note_mutate",
            "heightened_add",
            "heightened_remove",
            "improvement_buy",
            "improvement_remove",
            "empowerment_remove",
        )
    )

    if operation == "hp":
        backend.HPSystem.set_HP(
            character,
            rng.randint(
                -10000,
                10000,
            ),
        )

    elif operation == "at":
        backend.ATSystem.set_current_AT(
            character,
            rng.randint(
                -1000,
                1000,
            ),
        )

    elif operation == "stat":
        name = rng.choice(
            list(
                backend.STAT_NAMES
            )
        )

        die = rng.choice(
            [
                4,
                6,
                8,
                10,
                12,
            ]
        )

        backend.StatSystem.set_die_size(
            character,
            name,
            die,
        )

    elif operation == "inventory_add":
        backend.InventorySystem.add_item(
            character,
            f"Fuzz {rng.randint(0, 999)} 🐉",
            (
                "Random description "
                f"{rng.randint(0, 99999)}"
            ),
            rng.randint(
                -20,
                100,
            ),
        )

    elif operation == "inventory_qty":
        items = (
            character.inventory
            .list_of_items
        )

        if items:
            item = rng.choice(
                items
            )

            backend.InventorySystem.adjust_quantity(
                character,
                item.id,
                rng.randint(
                    -100,
                    100,
                ),
            )

    elif operation == "inventory_remove":
        items = (
            character.inventory
            .list_of_items
        )

        if items:
            item = rng.choice(
                items
            )

            backend.InventorySystem.remove_item(
                character,
                item.id,
            )

    elif operation == "note_add":
        character.notes.list_of_notes.append(
            backend.CharacterNote(
                id=str(uuid4()),
                title=(
                    f"Fuzz Note "
                    f"{rng.randint(0, 999)}"
                ),
                text=(
                    "Random note "
                    f"{rng.randint(0, 99999)}\n"
                    "שלום 日本語 🐉"
                ),
                color=rng.choice(
                    tuple(
                        VALID_NOTE_COLORS
                    )
                ),
                expanded=bool(
                    rng.randint(
                        0,
                        1,
                    )
                ),
            )
        )

        character.validate()

    elif operation == "note_mutate":
        notes = (
            character.notes
            .list_of_notes
        )

        if notes:
            note = rng.choice(
                notes
            )

            note.text += (
                f"\nmutation-{rng.randint(0, 9999)}"
            )

            if rng.random() < 0.1:
                note.color = "invalid"

            character.validate()

    elif operation == "heightened_add":
        backend.StatSystem.add_free_heightened_ability(
            character,
            rng.choice(
                list(
                    backend.STAT_NAMES
                )
            ),
        )

    elif operation == "heightened_remove":
        if (
            character
            .free_heightened_ability_stats
        ):
            backend.StatSystem.remove_free_heightened_ability(
                character,
                rng.choice(
                    character
                    .free_heightened_ability_stats
                ),
            )

    elif operation == "improvement_buy":
        options = get_available(
            character
        )

        if options:
            purchase = rng.choice(
                options
            )

            buy_option(
                character,
                purchase,
            )

    elif operation == "improvement_remove":
        improvements = (
            character.improvements
            .list_of_taken_improvements
        )

        candidates = [
            item
            for item in improvements
            if item.source != "species"
        ]

        if candidates:
            target = rng.choice(
                candidates
            )

            backend.ImprovementSystem.remove_improvement(
                character,
                target.id,
            )

    elif operation == "empowerment_remove":
        candidates = []

        for improvement in (
            character.improvements
            .list_of_taken_improvements
        ):
            for empowerment in (
                improvement.empowerments
            ):
                candidates.append(
                    (
                        improvement,
                        empowerment,
                    )
                )

        if candidates:
            (
                improvement,
                empowerment,
            ) = rng.choice(
                candidates
            )

            backend.ImprovementSystem.remove_empowerment(
                character,
                improvement.id,
                empowerment.id,
            )


@test("5,000 randomized cross-system operations preserve all invariants")
def _():
    rng = random.Random(
        SEED
    )

    total_operations = 0
    total_roundtrips = 0

    for character_number in range(
        25
    ):
        c = fresh(
            (
                "Fuzz Character "
                f"{character_number}"
            )
        )

        # The high current-IP pool prevents fuzz purchases from becoming
        # invalid simply because the test exhausts normal campaign resources.
        c.progression.current_IP = 1000
        c.validate()

        for step in range(
            200
        ):
            random_operation(
                rng,
                c,
            )

            total_operations += 1

            assert_character_invariants(
                c
            )

            if step % 20 == 0:
                c = assert_roundtrip_equal(
                    c,
                    (
                        "Fuzz round trip changed character "
                        f"{character_number} at step {step}"
                    ),
                )

                total_roundtrips += 1

    assert_equal(
        total_operations,
        5000,
    )

    assert_true(
        total_roundtrips >= 250,
    )




# ============================================================================
# Current Creation Rules / template-backed character state
# ============================================================================

@test("CharacterCreationRules validation normalizes hostile values safely")
def _():
    rules = character_template.CharacterCreationRules(
        level=-50,
        extra_ip=-12,
        species_mode="not-a-mode",
        starting_hearts=0,
        starting_at=-9,
        allowed_ability_array_ids="not-a-list",
        improvement_mode="broken",
        improvement_ids="not-a-list",
    )

    rules.validate()

    assert_equal(rules.level, 1)
    assert_equal(rules.extra_ip, 0)
    assert_equal(rules.species_mode, "normal")
    assert_equal(rules.starting_hearts, 1)
    assert_equal(rules.starting_at, 0)
    assert_equal(rules.allowed_ability_array_ids, [])
    assert_equal(rules.improvement_mode, "all")
    assert_equal(rules.improvement_ids, [])


@test("Template application and character round trip preserve Creation Rules")
def _():
    array_ids = [
        str(item.get("id"))
        for item in getattr(catalog, "ABILITY_ARRAYS", [])
        if item.get("id")
    ]
    improvement_ids = [
        str(key)
        for key in getattr(catalog, "IMPROVEMENT_CATALOG", {})
        if key != "custom"
    ]

    assert_true(array_ids, "No ability arrays available")
    assert_true(improvement_ids, "No improvements available")

    c = fresh("Template Core", rich=False)
    template = character_template.CharacterTemplate(
        name="Core Template",
        rules=character_template.CharacterCreationRules(
            level=4,
            extra_ip=5,
            species_mode="required",
            starting_hearts=6,
            starting_at=7,
            allow_custom_improvements=False,
            allowed_ability_array_ids=array_ids[:2],
            improvement_mode="allow_only",
            improvement_ids=improvement_ids[:3],
        ),
    )

    character_template.apply_template_to_character(c, template)
    c.validate()

    assert_equal(c.progression.level, 4)
    assert_equal(c.HP.max_hearts, 6)
    assert_equal(c.HP.current_HP, 24)
    assert_equal(c.adversity.max_AT, 7)
    assert_equal(c.creation_template_name, "Core Template")
    assert_equal(c.creation_species_mode, "required")
    assert_false(c.creation_allow_custom_improvements)

    loaded = assert_roundtrip_equal(
        c,
        "Creation Rules changed during character dict round trip",
    )

    for attr in (
        "creation_rules_active",
        "creation_template_name",
        "creation_species_mode",
        "creation_allow_custom_improvements",
        "creation_allowed_ability_array_ids",
        "creation_improvement_mode",
        "creation_improvement_ids",
    ):
        assert_equal(getattr(loaded, attr), getattr(c, attr), attr)


@test("Two free Heightened Abilities on different stats cost zero IP")
def _():
    c = fresh("Two Free Different", rich=False)
    before = c.progression.used_IP

    assert_true(backend.StatSystem.add_free_heightened_ability(c, "strength"))
    assert_true(backend.StatSystem.add_free_heightened_ability(c, "agility"))

    assert_equal(c.progression.used_IP, before)
    assert_equal(len(c.free_heightened_ability_stats), 2)
    assert_character_invariants(c)


@test("Second free Heightened Ability on the same stat costs exactly one IP")
def _():
    c = fresh("Two Free Same", rich=False)
    before = c.progression.used_IP

    assert_true(backend.StatSystem.add_free_heightened_ability(c, "strength"))
    assert_true(backend.StatSystem.add_free_heightened_ability(c, "strength"))

    assert_equal(c.progression.used_IP, before + 1)
    assert_equal(c.free_heightened_ability_stats.count("strength"), 2)

    assert_true(backend.StatSystem.remove_free_heightened_ability(c, "strength"))
    assert_equal(c.progression.used_IP, before)
    assert_character_invariants(c)


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
print("=" * 86)
print(
    "CORE SYSTEMS TORTURE TEST COMPLETE: "
    f"{passed} passed / {failed} failed"
)
print("=" * 86)

report_path = (
    REPORT_DIR
    / "automated_core_systems_torture_report.json"
)

with open(
    report_path,
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        {
            "seed": SEED,
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
