"""
DID CHARACTER SHEET - IMPROVEMENTS TORTURE TEST

Focused destructive/regression suite for the Improvements system.

Place this file beside the current DID project files and run:

    python automated_improvements_torture_test.py

It tests catalog integrity, affordability, base purchases, scaling,
empowerments, ordered branches, Magic Novice -> Spellcasting conversion,
derived bonus dice, Animal Buddy / Well Trained behavior, generated-note
side effects, rule-glossary hovers, Add/Browse button state, display regressions,
Skilled At group removal, serialization stability, and a
10,000-operation seeded Improvements fuzz test.

No pytest install is required.

SAFETY:
Normal character/recovery storage is redirected into temporary folders.
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

SEED = 20260829
RESULTS = []

# ============================================================================
# Tiny test framework
# ============================================================================

def record(name, status, detail=""):
    RESULTS.append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}")
    if detail:
        print(f"       {detail}")


def test(name):
    def decorator(func):
        try:
            func()
            record(name, "PASS")
        except Exception as exc:
            record(name, "FAIL", f"{type(exc).__name__}: {exc}")
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
            message or f"Expected {expected!r}, got {actual!r}"
        )


def assert_not_equal(actual, expected, message=""):
    if actual == expected:
        raise AssertionError(
            message or f"Expected values to differ, both were {actual!r}"
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
        candidates = list(BASE_DIR.glob(f"{module_name}*.py"))
        if not candidates:
            return importlib.import_module(module_name)
        path = max(candidates, key=lambda p: p.stat().st_mtime)

    spec = importlib.util.spec_from_file_location(module_name, path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {module_name} from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


print("=" * 88)
print("DID CHARACTER SHEET - IMPROVEMENTS TORTURE TEST")
print(f"Random seed: {SEED}")
print("=" * 88)

backend = import_local_module("backend_2_1")
catalog_module = import_local_module("character_API")

record(
    "Import backend and improvement catalog",
    "PASS",
    Path(backend.__file__).name,
)

from PySide6.QtWidgets import QApplication, QMessageBox as RealQMessageBox

frontend = import_local_module("frontend_2_8")
# Non-dice suites must not initialize GPU-intensive WebEngine windows.
# Actual DiceBox physics is tested separately with WebGL enabled.
frontend.QWebEngineView = None


# Reuse the EXACT improvements_ui module object imported by frontend.
# Re-importing it here would create a second copy and could make monkeypatches
# miss the MainWindow mixin methods, potentially leaving invisible dialogs open.
improvements_ui = sys.modules.get("improvements_ui")
if improvements_ui is None:
    improvements_ui = import_local_module("improvements_ui")

dialogs = sys.modules.get("dialogs")
if dialogs is None:
    dialogs = import_local_module("dialogs")

record(
    "Import frontend Improvements module",
    "PASS",
    Path(frontend.__file__).name,
)

app = QApplication.instance() or QApplication(sys.argv)

# ============================================================================
# Suppress unrelated UI/modal behavior
# ============================================================================

frontend.MainWindow.check_for_recovery_on_startup = lambda self: None
frontend.MainWindow.show_welcome_dialog_if_needed = lambda self: None
frontend.MainWindow.closeEvent = lambda self, event: event.accept()

for module in (frontend, improvements_ui):
    module.QMessageBox.information = staticmethod(
        lambda *a, **k: RealQMessageBox.StandardButton.Ok
    )
    module.QMessageBox.warning = staticmethod(
        lambda *a, **k: RealQMessageBox.StandardButton.Ok
    )
    module.QMessageBox.critical = staticmethod(
        lambda *a, **k: RealQMessageBox.StandardButton.Ok
    )

improvements_ui.ask_yes_no = lambda *a, **k: True

# ============================================================================
# Temporary storage isolation
# ============================================================================

class StorageSandbox:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.save_dir = self.root / "Saved_characters"
        self.recovery_dir = self.root / "Recovery"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.recovery_dir.mkdir(parents=True, exist_ok=True)

        self.targets = []

        for module in (backend, frontend):
            storage = module.CharacterStorageSystem

            old_save = storage.SAVE_DIR
            old_recovery = getattr(storage, "RECOVERY_DIR", None)

            self.targets.append((storage, old_save, old_recovery))

            storage.SAVE_DIR = str(self.save_dir)

            if hasattr(storage, "RECOVERY_DIR"):
                storage.RECOVERY_DIR = str(self.recovery_dir)

        return self

    def __exit__(self, exc_type, exc, tb):
        for storage, old_save, old_recovery in self.targets:
            storage.SAVE_DIR = old_save
            if old_recovery is not None:
                storage.RECOVERY_DIR = old_recovery

        self.temp.cleanup()


# ============================================================================
# Shared helpers
# ============================================================================

CATALOG = catalog_module.IMPROVEMENT_CATALOG
STAT_NAMES = list(catalog_module.STAT_NAMES)


def fresh(name="Improvement Torture", ip=1000):
    character = backend.Character.create_new_character(name)
    character.progression.current_IP = ip
    character.validate()
    return character


def snapshot(character):
    return backend.CharacterStorageSystem.character_to_dict(character)


def clone(character):
    return backend.CharacterStorageSystem.character_from_dict(
        copy.deepcopy(snapshot(character))
    )


def expected_used_ip(character):
    return (
        character.improvements.total_cost()
        + character.stats.total_bonus_cost(
            character.free_heightened_ability_stats
        )
    )


def assert_invariants(character):
    character.validate()

    assert_equal(
        character.progression.used_IP,
        expected_used_ip(character),
        "Derived used_IP is wrong",
    )

    assert_equal(
        character.progression.available_IP,
        character.progression.current_IP - character.progression.used_IP,
    )

    improvement_ids = []

    for improvement in character.improvements.list_of_taken_improvements:
        improvement_ids.append(improvement.id)

        assert_true(improvement.cost >= 0)
        assert_true(improvement.times_taken >= 1)

        empowerment_ids = []

        for empowerment in improvement.empowerments:
            empowerment_ids.append(empowerment.id)
            assert_true(empowerment.cost >= 0)

        assert_equal(
            len(empowerment_ids),
            len(set(empowerment_ids)),
            "Duplicate empowerment instance IDs",
        )

    assert_equal(
        len(improvement_ids),
        len(set(improvement_ids)),
        "Duplicate improvement instance IDs",
    )

    json.dumps(snapshot(character), ensure_ascii=False)


def choices_for_required(required):
    values = {
        "stat_name": "strength",
        "magic_school": "Abjuration",
        "magic_school_description": "Protective and defensive magic.",
        "specific_magic_effect": "Create a magical shield",
        "buddy_name": "Milo",
        "buddy_stat_d6": "agility",
        "buddy_stat_d8_a": "strength",
        "buddy_stat_d8_b": "finesse",
        "buddy_stat_d10": "instinct",
        "buddy_perk": "Excellent nose",
        "buddy_training_stat": "agility",
        "attuned_land": "forest",
        "tell": "glowing eyes",
        "deity_name": "Test Deity",
        "deity_domain": "Protection",
        "skill_name": "Investigation",
        "skill_description": "Find clues",
        "artificer_item_description": "Clockwork key",
        "spellcasting_stat": "knowledge",
        "spellcasing_stat": "knowledge",
    }

    return {
        key: values.get(key, f"Test {key}")
        for key in (required or [])
    }


def choices_for_purchase(purchase):
    return choices_for_required(
        purchase.get("requires_choices", [])
    )


def available(character):
    return backend.ImprovementSystem.get_available_purchases(character)


def purchase_matches(
    character,
    *,
    kind=None,
    catalog_id=None,
    parent_catalog_id=None,
    group_id=None,
):
    matches = []

    for purchase in available(character):
        if kind is not None and purchase.get("kind") != kind:
            continue
        if catalog_id is not None and purchase.get("catalog_id") != catalog_id:
            continue
        if (
            parent_catalog_id is not None
            and purchase.get("parent_catalog_id") != parent_catalog_id
        ):
            continue
        if group_id is not None and purchase.get("group_id") != group_id:
            continue

        matches.append(purchase)

    return matches


def buy(character, purchase, choices=None):
    if choices is None:
        choices = choices_for_purchase(purchase)

    success = backend.ImprovementSystem.buy_purchase(
        character,
        purchase,
        choices=choices,
    )

    assert_invariants(character)
    return success


def buy_base(character, catalog_id, choices=None):
    matches = purchase_matches(
        character,
        kind="base",
        catalog_id=catalog_id,
    )

    if not matches:
        raise AssertionError(f"Base purchase {catalog_id!r} is unavailable")

    purchase = matches[0]

    if choices is None:
        choices = choices_for_purchase(purchase)

    assert_true(
        buy(character, purchase, choices=choices),
        f"Could not buy base {catalog_id}",
    )

    return character.improvements.get_first_by_catalog_id(catalog_id)


def buy_empowerment(
    character,
    *,
    catalog_id=None,
    parent_catalog_id=None,
    group_id=None,
    choices=None,
):
    matches = purchase_matches(
        character,
        kind="empowerment",
        catalog_id=catalog_id,
        parent_catalog_id=parent_catalog_id,
        group_id=group_id,
    )

    if not matches:
        raise AssertionError(
            "Empowerment unavailable: "
            f"catalog={catalog_id}, parent={parent_catalog_id}, group={group_id}"
        )

    purchase = matches[0]
    parent_id = purchase["improvement_id"]

    parent_before = next(
        improvement
        for improvement in character.improvements.list_of_taken_improvements
        if improvement.id == parent_id
    )

    before_ids = {e.id for e in parent_before.empowerments}

    if choices is None:
        choices = choices_for_purchase(purchase)

    assert_true(
        buy(character, purchase, choices=choices),
        f"Could not buy empowerment {purchase}",
    )

    # This special purchase replaces Magic Novice with Spellcasting.
    if purchase.get("catalog_id") == "upgrade_to_spellcasting":
        return purchase, None

    new_items = [
        e
        for e in parent_before.empowerments
        if e.id not in before_ids
    ]

    assert_equal(
        len(new_items),
        1,
        "Empowerment purchase did not create exactly one row",
    )

    return purchase, new_items[0]


def roundtrip(character):
    raw = snapshot(character)

    loaded = backend.CharacterStorageSystem.character_from_dict(
        copy.deepcopy(raw)
    )

    loaded_snapshot = snapshot(loaded)
    assert_equal(
        loaded_snapshot,
        raw,
        "Improvement state drifted during dict round trip; "
        + str(first_difference(raw, loaded_snapshot)),
    )

    assert_invariants(loaded)
    return loaded


def make_window(character):
    window = frontend.MainWindow()
    window.hide()

    window.character = character
    window.current_character_filepath = None
    window.saved_character_name = character.name
    window.reconnect_character_references()

    # Behavior-only tests below do not need expensive layout rebuilding.
    window.refresh_after_improvement_change = lambda: None
    window.refresh_all = lambda: None

    app.processEvents()
    return window


def safe_close(window):
    try:
        if hasattr(window, "_recovery_write_timer"):
            window._recovery_write_timer.stop()
    except Exception:
        pass

    try:
        window.hide()
        window.deleteLater()
        app.processEvents()
    except Exception:
        pass


# ============================================================================
# Current Improvements UI / glossary regressions
# ============================================================================

@test("Rule glossary definitions match the current short DID wording")
def _():
    assert_equal(
        dialogs.rule_glossary_definition("parry"),
        "Spend AT to reduce damage from a hit by 1 HP.",
    )
    assert_equal(
        dialogs.rule_glossary_definition("advantage"),
        "Roll a d6 and add it to your check.",
    )
    assert_equal(
        dialogs.rule_glossary_definition("disadvantage"),
        "Roll a d6 and subtract it from your check.",
    )
    assert_equal(
        dialogs.rule_glossary_definition("exploding_die"),
        "When a die rolls its maximum, roll it again and add the result.",
    )
    assert_equal(
        dialogs.rule_glossary_definition("snap_decision"),
        "A rushed check under pressure that must be rolled.",
    )

    protect_text = (
        "When using the Protect Action, you may protect an ally at Close range."
    )
    assert_equal(
        dialogs.rule_glossary_definition(
            "protect",
            protect_text,
        ),
        "Spend 1 AT to take an attack aimed at an ally at Close range.",
    )

    range_expectations = {
        "melee": "Within touching distance.",
        "very_close": "About 5-10 feet away.",
        "close": "About 10-30 feet away.",
        "far": "About 30-100 feet away.",
        "very_far": "About 100-300 feet away.",
        "out_of_range": "Beyond Very Far range.",
    }

    for slug, expected in range_expectations.items():
        assert_equal(
            dialogs.rule_glossary_definition(slug),
            expected,
        )


@test("Glossary links are injected into Add/Browse and owned Improvement descriptions")
def _():
    description = (
        "Parry, advantage, disadvantage, Protect Action at Close range, "
        "exploding dice, Snap Decision, Very Close range, Far range, "
        "Very Far range, and Out of Range."
    )

    rendered = dialogs.apply_rule_glossary_html(
        description
    )

    for slug in (
        "parry",
        "advantage",
        "disadvantage",
        "protect",
        "exploding_die",
        "snap_decision",
        "very_close",
        "close",
        "far",
        "very_far",
        "out_of_range",
    ):
        assert_true(
            f"rule:{slug}" in rendered,
            f"Glossary HTML did not link {slug}",
        )

    picker = dialogs.ImprovementPickerDialog(
        [
            {
                "kind": "base",
                "name": "Glossary Preview",
                "cost": 1,
                "description": description,
                "tags": [],
            }
        ],
        browse_only=True,
    )

    try:
        assert_true(
            isinstance(
                picker.description_box,
                dialogs.GlossaryTextEdit,
            ),
            "Add/Browse Improvements no longer uses the glossary-aware text box",
        )
        assert_true(
            "rule:advantage"
            in picker.description_box.document().toHtml(),
            "Add/Browse description did not receive glossary links",
        )
    finally:
        picker.close()
        picker.deleteLater()
        app.processEvents()

    c = fresh()
    improvement = backend.Improvement(
        id=str(uuid4()),
        catalog_id="custom",
        name="Glossary Owned",
        cost=0,
        description="You have advantage and exploding dice.",
        source="ip",
        choices={},
        expanded=True,
    )
    c.improvements.list_of_taken_improvements.append(
        improvement
    )
    c.validate()

    row = improvements_ui.ImprovementRow(
        c,
        improvement,
        lambda *_: None,
        lambda *_: None,
        lambda *_: None,
    )

    try:
        labels = row.findChildren(
            improvements_ui.GlossaryAutoWrapLabel
        )
        assert_true(
            labels,
            "Owned Improvement description is not using GlossaryAutoWrapLabel",
        )
        assert_true(
            any(
                "rule:advantage" in label.text()
                for label in labels
            ),
            "Owned Improvement description did not receive glossary links",
        )
    finally:
        row.deleteLater()
        app.processEvents()


@test("Add Improvement changes to Browse only at zero available IP and returns when IP exists")
def _():
    c = fresh(ip=1)
    w = make_window(c)

    try:
        w.refresh_improvements()
        assert_equal(
            w.add_improvement_btn.text(),
            "+  Add Improvement",
        )

        sink = backend.Improvement(
            id=str(uuid4()),
            catalog_id="custom",
            name="IP Sink",
            cost=1,
            description="",
            source="ip",
        )
        c.improvements.list_of_taken_improvements.append(sink)
        c.validate()
        w.refresh_improvements()

        assert_equal(
            c.progression.available_IP,
            0,
        )
        assert_equal(
            w.add_improvement_btn.text(),
            "Browse Improvements",
        )

        c.improvements.list_of_taken_improvements.remove(sink)
        c.validate()
        w.refresh_improvements()
        assert_equal(
            w.add_improvement_btn.text(),
            "+  Add Improvement",
            "Removing an Improvement did not restore Add Improvement",
        )

        # Re-create zero available IP, then restore it through Grant IP.
        c.improvements.list_of_taken_improvements.append(sink)
        c.validate()
        w.refresh_improvements()
        assert_equal(w.add_improvement_btn.text(), "Browse Improvements")

        c.progression.grant_IP(1)
        c.validate()
        w.refresh_improvements()
        assert_equal(
            w.add_improvement_btn.text(),
            "+  Add Improvement",
            "Grant IP did not restore Add Improvement",
        )

    finally:
        safe_close(w)


@test("Double-click editing a catalog Improvement with no choices is a no-op")
def _():
    c = fresh(ip=1000)

    option = next(
        option
        for option in CATALOG.values()
        if (
            not option.get("requires_choices")
            and option.get("purchase_rule", "single") == "single"
            and purchase_matches(
                c,
                kind="base",
                catalog_id=option["id"],
            )
        )
    )

    improvement = buy_base(
        c,
        option["id"],
    )

    w = make_window(c)
    old_dialog = improvements_ui.ChoiceInputDialog
    old_info = improvements_ui.QMessageBox.information
    info_calls = []

    class BombChoiceDialog:
        def __init__(self, *args, **kwargs):
            raise AssertionError(
                "ChoiceInputDialog opened for a non-editable Improvement"
            )

    improvements_ui.ChoiceInputDialog = BombChoiceDialog
    improvements_ui.QMessageBox.information = staticmethod(
        lambda *a, **k: info_calls.append((a, k))
    )

    try:
        before = snapshot(c)
        w.edit_improvement_choices(improvement)
        assert_equal(snapshot(c), before)
        assert_equal(
            info_calls,
            [],
            "Non-editable double click still showed a No Choices/info popup",
        )
    finally:
        improvements_ui.ChoiceInputDialog = old_dialog
        improvements_ui.QMessageBox.information = old_info
        safe_close(w)


@test("Private Species metadata produces no visible blank choices section")
def _():
    c = fresh()
    improvement = backend.Improvement(
        id=str(uuid4()),
        catalog_id="custom",
        name="Species Feature",
        cost=0,
        description="Species feature",
        source="species",
        choices={"_species_name": "Hidden Species Name"},
        expanded=False,
    )

    row = improvements_ui.ImprovementRow(
        c,
        improvement,
        lambda *_: None,
        lambda *_: None,
        lambda *_: None,
    )

    holder = improvements_ui.QWidget()
    layout = improvements_ui.QVBoxLayout(holder)

    try:
        assert_equal(
            row.format_choices(
                improvement.choices,
                improvement,
            ),
            "",
            "Private _species_name leaked into formatted choices",
        )

        before_count = layout.count()
        row.add_choices_section(
            layout,
            improvement,
        )
        assert_equal(
            layout.count(),
            before_count,
            "Hidden Species metadata still created an empty spacer/label",
        )
    finally:
        row.deleteLater()
        holder.deleteLater()
        app.processEvents()


@test("Animal Buddy uses a nested six-ability box with the normal ability colors")
def _():
    c = fresh(ip=1000)
    buddy = buy_base(
        c,
        "animal_buddy",
        choices={
            "buddy_name": "Milo",
            "buddy_stat_d10": "instinct",
            "buddy_stat_d8_a": "strength",
            "buddy_stat_d8_b": "finesse",
            "buddy_stat_d6": "agility",
            "buddy_perk": "Excellent nose",
        },
    )
    buddy.expanded = True

    row = improvements_ui.ImprovementRow(
        c,
        buddy,
        lambda *_: None,
        lambda *_: None,
        lambda *_: None,
    )

    try:
        boxes = [
            frame
            for frame in row.findChildren(improvements_ui.QFrame)
            if frame.objectName() == "AnimalBuddyInfoBox"
        ]
        assert_equal(
            len(boxes),
            1,
            "Animal Buddy nested information box is missing/duplicated",
        )

        assert_equal(
            improvements_ui.ABILITY_ACCENTS,
            frontend.ABILITY_ACCENTS,
            "Animal Buddy colors no longer match the regular ability colors",
        )

        labels = boxes[0].findChildren(
            improvements_ui.QLabel
        )

        for stat_name in STAT_NAMES:
            visible_name = stat_name.replace("_", " ").title()
            matching = [
                label
                for label in labels
                if label.text() == visible_name
            ]
            assert_equal(
                len(matching),
                1,
                f"Animal Buddy is missing the {visible_name} ability box",
            )
            accent = improvements_ui.ABILITY_ACCENTS[stat_name].lower()
            assert_true(
                accent in matching[0].styleSheet().lower(),
                f"Animal Buddy {visible_name} does not use its normal accent color",
            )

    finally:
        row.deleteLater()
        app.processEvents()

# ============================================================================
# Catalog / API integrity
# ============================================================================

@test("Required ImprovementSystem API exists")
def _():
    required = [
        "get_available_purchases",
        "buy_purchase",
        "add_from_catalog",
        "remove_improvement",
        "remove_empowerment",
        "build_improvement_display",
        "build_choice_lines",
        "upgrade_magic_novice_to_spellcasting",
        "get_species_options",
    ]

    for name in required:
        assert_true(
            hasattr(backend.ImprovementSystem, name),
            f"Missing ImprovementSystem.{name}()",
        )


@test("Catalog keys match option ids")
def _():
    assert_true(len(CATALOG) > 20, "Catalog unexpectedly small")

    for key, option in CATALOG.items():
        assert_equal(
            option.get("id"),
            key,
            f"Catalog key {key!r} does not match option id",
        )

        assert_true(
            str(option.get("name", "")).strip(),
            f"{key} has no name",
        )


@test("Catalog costs, rules, and required-choice declarations are sane")
def _():
    valid_rules = {
        "single",
        "repeatable",
        "repeatable_scaling",
        "stat_bonus_scaling",
    }

    def check_required(required, where):
        assert_true(
            isinstance(required, list),
            f"{where} requires_choices is not a list",
        )

        for key in required:
            assert_true(
                isinstance(key, str) and key.strip(),
                f"{where} has invalid required-choice key",
            )

    for catalog_id, option in CATALOG.items():
        rule = option.get("purchase_rule", "single")

        assert_true(
            rule in valid_rules,
            f"{catalog_id} has unknown purchase_rule {rule!r}",
        )

        for cost_key in ("cost", "base_cost", "cost_increase"):
            if cost_key in option:
                assert_true(
                    int(option[cost_key]) >= 0,
                    f"{catalog_id}.{cost_key} is negative",
                )

        check_required(
            option.get("requires_choices", []),
            catalog_id,
        )

        for group_id, group in option.get(
            "empowerment_groups", {}
        ).items():
            check_required(
                group.get("requires_choices", []),
                f"{catalog_id}.{group_id}",
            )

            for child in group.get("options", []):
                check_required(
                    child.get("requires_choices", []),
                    f"{catalog_id}.{group_id}.{child.get('id')}",
                )

        for child in option.get("empowerments", []):
            check_required(
                child.get("requires_choices", []),
                f"{catalog_id}.{child.get('id')}",
            )


# ============================================================================
# Availability / base purchases
# ============================================================================

@test("Available purchase entries are structurally valid")
def _():
    c = fresh()

    for purchase in available(c):
        assert_true(
            purchase.get("kind") in {"base", "empowerment", "custom"},
            f"Unknown purchase kind: {purchase}",
        )
        assert_true("name" in purchase)
        assert_true(int(purchase.get("cost", 0)) >= 0)


@test("No unaffordable positive-IP purchase appears")
def _():
    c = fresh(ip=backend.STARTING_IP)

    c.improvements.list_of_taken_improvements.append(
        backend.Improvement(
            id=str(uuid4()),
            catalog_id="custom",
            name="IP Sink",
            cost=c.progression.current_IP,
            description="",
            source="ip",
        )
    )
    c.validate()

    assert_equal(c.progression.available_IP, 0)

    for purchase in available(c):
        assert_false(
            int(purchase.get("cost", 0)) > 0,
            f"Unaffordable purchase leaked into list: {purchase}",
        )


@test("Forged unaffordable custom purchase is rejected")
def _():
    c = fresh(ip=6)
    before = snapshot(c)

    forged = {
        "kind": "custom",
        "name": "Impossible",
        "cost": 999,
        "description": "",
    }

    assert_false(
        backend.ImprovementSystem.buy_purchase(c, forged)
    )

    assert_equal(snapshot(c), before)


@test("Every initially available base purchase succeeds on a clone")
def _():
    root = fresh(ip=10000)

    bases = [
        purchase
        for purchase in available(root)
        if purchase.get("kind") == "base"
    ]

    assert_true(len(bases) >= 10, "Unexpectedly few base purchases")

    for purchase in bases:
        candidate = clone(root)

        assert_true(
            backend.ImprovementSystem.buy_purchase(
                candidate,
                purchase,
                choices=choices_for_purchase(purchase),
            ),
            f"Available base purchase could not be bought: {purchase}",
        )

        assert_invariants(candidate)


@test("Single-purchase improvement disappears after purchase")
def _():
    checked = 0

    for option in CATALOG.values():
        if option.get("purchase_rule", "single") != "single":
            continue

        c = fresh(ip=10000)

        matches = purchase_matches(
            c,
            kind="base",
            catalog_id=option["id"],
        )

        if not matches:
            continue

        assert_true(buy(c, matches[0]))

        assert_false(
            bool(
                purchase_matches(
                    c,
                    kind="base",
                    catalog_id=option["id"],
                )
            ),
            f"Single improvement {option['id']} remained buyable",
        )

        checked += 1

    assert_true(checked >= 10, "Too few single bases were testable")


# ============================================================================
# Repeatable-scaling base improvements
# ============================================================================

@test("All repeatable-scaling bases follow cost ladder and max")
def _():
    scaling_options = [
        option
        for option in CATALOG.values()
        if option.get("purchase_rule") == "repeatable_scaling"
    ]

    assert_true(
        scaling_options,
        "No repeatable-scaling base improvements found",
    )

    for option in scaling_options:
        c = fresh(ip=10000)
        catalog_id = option["id"]

        base_cost = int(option["base_cost"])
        increase = int(option["cost_increase"])
        max_times = int(option.get("max_times", 999))

        assert_true(
            max_times <= 50,
            f"{catalog_id} max_times unexpectedly huge",
        )

        for rank in range(1, max_times + 1):
            matches = purchase_matches(
                c,
                kind="base",
                catalog_id=catalog_id,
            )

            assert_equal(
                len(matches),
                1,
                f"{catalog_id} missing at rank {rank}",
            )

            expected_cost = base_cost + (rank - 1) * increase

            assert_equal(
                int(matches[0]["cost"]),
                expected_cost,
                f"{catalog_id} wrong cost at rank {rank}",
            )

            assert_true(buy(c, matches[0]))

            owned = c.improvements.get_first_by_catalog_id(catalog_id)

            assert_true(owned is not None)
            assert_equal(
                owned.times_taken,
                rank,
                f"{catalog_id} wrong times_taken at rank {rank}",
            )

        assert_false(
            bool(
                purchase_matches(
                    c,
                    kind="base",
                    catalog_id=catalog_id,
                )
            ),
            f"{catalog_id} remained buyable past max_times",
        )


@test("Removing a repeatable-scaling base removes only its highest rank")
def _():
    candidates = [
        option
        for option in CATALOG.values()
        if (
            option.get("purchase_rule") == "repeatable_scaling"
            and int(option.get("max_times", 0)) >= 3
        )
    ]

    assert_true(candidates)

    option = candidates[0]
    c = fresh(ip=1000)

    for _ in range(3):
        buy_base(c, option["id"])

    improvement = c.improvements.get_first_by_catalog_id(option["id"])
    before_rank = improvement.times_taken
    before_used = c.progression.used_IP

    assert_true(
        backend.ImprovementSystem.remove_improvement(
            c,
            improvement.id,
        )
    )

    assert_equal(
        improvement.times_taken,
        before_rank - 1,
    )

    assert_true(
        c.progression.used_IP < before_used,
        "Scaling-rank removal did not refund IP",
    )

    assert_invariants(c)


# ============================================================================
# Species / custom
# ============================================================================

@test("Species options obey one-species and zero-IP rules")
def _():
    c = fresh(ip=100)

    options = backend.ImprovementSystem.get_species_options(c)

    assert_true(options)

    for item in options:
        entry = CATALOG[item["catalog_id"]]

        assert_true(int(item["cost"]) in {1, 2})
        assert_equal(
            entry.get("purchase_rule", "single"),
            "single",
        )

    chosen = options[0]

    assert_true(
        backend.ImprovementSystem.add_from_catalog(
            c,
            chosen["catalog_id"],
            source="species",
            choices=choices_for_purchase(chosen),
        )
    )

    assert_true(c.improvements.has_species_improvement())
    assert_equal(
        backend.ImprovementSystem.get_species_options(c),
        [],
    )
    assert_equal(
        c.progression.used_IP,
        0,
        "Species improvement incorrectly consumed IP",
    )


@test("Custom improvement charges and refunds exact IP")
def _():
    c = fresh(ip=100)

    purchase = {
        "kind": "custom",
        "name": "Custom Stress",
        "cost": 7,
        "description": "Testing.",
    }

    before = c.progression.used_IP

    assert_true(buy(c, purchase))

    custom = c.improvements.get_first_by_catalog_id("custom")
    assert_true(custom is not None)

    assert_equal(
        c.progression.used_IP,
        before + 7,
    )

    assert_true(
        backend.ImprovementSystem.remove_improvement(
            c,
            custom.id,
        )
    )

    assert_equal(
        c.progression.used_IP,
        before,
    )


# ============================================================================
# Empowerments
# ============================================================================

@test("Every immediately available empowerment succeeds on a clone")
def _():
    tested = 0

    for catalog_id in CATALOG:
        c = fresh(ip=10000)

        base = purchase_matches(
            c,
            kind="base",
            catalog_id=catalog_id,
        )

        if not base:
            continue

        if not buy(c, base[0]):
            continue

        empowerment_options = [
            purchase
            for purchase in available(c)
            if (
                purchase.get("kind") == "empowerment"
                and purchase.get("parent_catalog_id") == catalog_id
            )
        ]

        for purchase in empowerment_options:
            candidate = clone(c)

            assert_true(
                backend.ImprovementSystem.buy_purchase(
                    candidate,
                    purchase,
                    choices=choices_for_purchase(purchase),
                ),
                f"Available empowerment could not be bought: {purchase}",
            )

            assert_invariants(candidate)
            tested += 1

    assert_true(
        tested >= 10,
        f"Too few empowerments were testable ({tested})",
    )


@test("Forged empowerment with missing parent is rejected")
def _():
    c = fresh()
    before = snapshot(c)

    forged = {
        "kind": "empowerment",
        "improvement_id": "does-not-exist",
        "parent_catalog_id": "spellcasting",
        "group_id": "magic_die",
        "catalog_id": "fake",
        "name": "Fake",
        "cost": 1,
        "description": "",
    }

    assert_false(
        backend.ImprovementSystem.buy_purchase(c, forged)
    )

    assert_equal(snapshot(c), before)


@test("Removing a normal empowerment refunds exact cost")
def _():
    chosen_character = None
    chosen_purchase = None

    for catalog_id in CATALOG:
        c = fresh(ip=1000)

        base = purchase_matches(
            c,
            kind="base",
            catalog_id=catalog_id,
        )

        if not base:
            continue

        buy(c, base[0])

        candidates = [
            p
            for p in available(c)
            if (
                p.get("kind") == "empowerment"
                and p.get("parent_catalog_id") == catalog_id
                and p.get("catalog_id") != "upgrade_to_spellcasting"
            )
        ]

        if candidates:
            chosen_character = c
            chosen_purchase = candidates[0]
            break

    assert_true(chosen_purchase is not None)

    c = chosen_character
    before_used = c.progression.used_IP

    purchase, empowerment = buy_empowerment(
        c,
        catalog_id=chosen_purchase["catalog_id"],
        parent_catalog_id=chosen_purchase["parent_catalog_id"],
        group_id=chosen_purchase["group_id"],
    )

    after_buy = c.progression.used_IP

    assert_equal(
        after_buy - before_used,
        int(purchase["cost"]),
    )

    parent = next(
        imp
        for imp in c.improvements.list_of_taken_improvements
        if imp.id == purchase["improvement_id"]
    )

    assert_true(
        backend.ImprovementSystem.remove_empowerment(
            c,
            parent.id,
            empowerment.id,
        )
    )

    assert_equal(
        c.progression.used_IP,
        before_used,
    )


def find_ordered_scaling_parent():
    for option in CATALOG.values():
        for group_id, group in option.get(
            "scaling_empowerments", {}
        ).items():
            if (
                group.get("rule") == "ordered"
                and len(group.get("steps", [])) >= 2
            ):
                return option, group_id, group
    return None


@test("Ordered scaling empowerment exposes only the next step")
def _():
    found = find_ordered_scaling_parent()
    assert_true(found is not None)

    option, group_id, group = found
    c = fresh(ip=10000)

    buy_base(c, option["id"])

    for index, step in enumerate(group["steps"]):
        matches = purchase_matches(
            c,
            kind="empowerment",
            parent_catalog_id=option["id"],
            group_id=group_id,
        )

        assert_equal(
            len(matches),
            1,
            "Ordered branch exposed more than one next step",
        )

        assert_equal(
            int(matches[0]["cost"]),
            int(step["cost"]),
            f"Ordered step cost mismatch at index {index}",
        )

        assert_true(buy(c, matches[0]))

    assert_false(
        bool(
            purchase_matches(
                c,
                kind="empowerment",
                parent_catalog_id=option["id"],
                group_id=group_id,
            )
        ),
        "Ordered branch remained available after final step",
    )


@test("Ordered branch rejects non-highest removal")
def _():
    found = find_ordered_scaling_parent()
    assert_true(found is not None)

    option, group_id, group = found
    c = fresh(ip=10000)
    parent = buy_base(c, option["id"])

    buy_empowerment(
        c,
        parent_catalog_id=option["id"],
        group_id=group_id,
    )
    buy_empowerment(
        c,
        parent_catalog_id=option["id"],
        group_id=group_id,
    )

    branch = [
        e
        for e in parent.empowerments
        if e.group_id == group_id
    ]

    assert_true(len(branch) >= 2)

    before = snapshot(c)

    assert_false(
        backend.ImprovementSystem.remove_empowerment(
            c,
            parent.id,
            branch[0].id,
        ),
        "Backend removed a non-highest ordered step",
    )

    assert_equal(snapshot(c), before)

    assert_true(
        backend.ImprovementSystem.remove_empowerment(
            c,
            parent.id,
            branch[-1].id,
        )
    )


def find_repeatable_scaling_empowerment():
    for option in CATALOG.values():
        for group_container in (
            option.get("scaling_empowerments", {}),
            option.get("empowerment_groups", {}),
        ):
            for group_id, group in group_container.items():
                if group.get("rule") == "repeatable_scaling":
                    return option, group_id, group
    return None


@test("Repeatable-scaling empowerment follows cost ladder and max")
def _():
    found = find_repeatable_scaling_empowerment()

    assert_true(
        found is not None,
        "No repeatable-scaling empowerment found",
    )

    option, group_id, group = found
    c = fresh(ip=10000)

    buy_base(c, option["id"])

    base_cost = int(
        group.get(
            "base_cost",
            group.get("cost", 0),
        )
    )
    increase = int(group.get("cost_increase", 0))
    max_times = int(group.get("max_times", 5))

    assert_true(max_times <= 25)

    for rank in range(1, max_times + 1):
        matches = purchase_matches(
            c,
            kind="empowerment",
            parent_catalog_id=option["id"],
            group_id=group_id,
        )

        assert_equal(
            len(matches),
            1,
            f"{option['id']}.{group_id} missing at rank {rank}",
        )

        expected_cost = base_cost + (rank - 1) * increase

        assert_equal(
            int(matches[0]["cost"]),
            expected_cost,
            f"{option['id']}.{group_id} wrong cost at rank {rank}",
        )

        assert_true(buy(c, matches[0]))

    assert_false(
        bool(
            purchase_matches(
                c,
                kind="empowerment",
                parent_catalog_id=option["id"],
                group_id=group_id,
            )
        ),
        f"{option['id']}.{group_id} remained buyable past max",
    )


# ============================================================================
# Magic Novice -> Spellcasting / bonus dice
# ============================================================================

@test("Magic Novice upgrade preserves IP and converts Magic Dice")
def _():
    assert_true("magic_novice" in CATALOG)
    assert_true("spellcasting" in CATALOG)

    c = fresh(ip=10000)

    novice = buy_base(
        c,
        "magic_novice",
        choices={
            "specific_magic_effect": "Create a shield",
            "spellcasting_stat": "knowledge",
        },
    )

    novice_die_count = 0

    for _ in range(2):
        matches = purchase_matches(
            c,
            kind="empowerment",
            parent_catalog_id="magic_novice",
            group_id="magic_die",
        )

        if not matches:
            break

        _, empowerment = buy_empowerment(
            c,
            parent_catalog_id="magic_novice",
            group_id="magic_die",
        )

        novice_die_count += 1

    assert_true(
        novice_die_count >= 1,
        "Magic Novice exposed no Magic Die upgrade",
    )

    before_upgrade_used = c.progression.used_IP

    upgrades = purchase_matches(
        c,
        kind="empowerment",
        catalog_id="upgrade_to_spellcasting",
        parent_catalog_id="magic_novice",
    )

    assert_equal(len(upgrades), 1)

    upgrade = upgrades[0]

    assert_true(
        backend.ImprovementSystem.buy_purchase(
            c,
            upgrade,
            choices={
                "magic_school": "Abjuration",
                "magic_school_description": "Defensive magic.",
            },
        )
    )

    assert_false(
        c.improvements.has_catalog_id("magic_novice")
    )

    spellcasting = c.improvements.get_first_by_catalog_id("spellcasting")

    assert_true(spellcasting is not None)

    assert_equal(
        c.progression.used_IP,
        before_upgrade_used + int(upgrade["cost"]),
        "Upgrade changed previously-spent Magic Novice IP",
    )

    assert_equal(
        spellcasting.choices.get("magic_school"),
        "Abjuration",
    )

    assert_equal(
        spellcasting.choices.get("spellcasting_stat"),
        "knowledge",
    )

    converted = [
        e
        for e in spellcasting.empowerments
        if e.group_id == "magic_die"
    ]

    assert_equal(
        len(converted),
        novice_die_count,
        "Magic Die upgrade count was not preserved",
    )

    roundtrip(c)


@test("Spellcasting Magic Die rises by step and rolls back on removal")
def _():
    c = fresh(ip=10000)

    spellcasting = buy_base(
        c,
        "spellcasting",
        choices={
            "magic_school": "Abjuration",
            "magic_school_description": "Defensive magic.",
        },
    )

    group = CATALOG["spellcasting"].get(
        "scaling_empowerments", {}
    ).get("magic_die")

    assert_true(group is not None)

    owned = []

    for step in group["steps"]:
        _, empowerment = buy_empowerment(
            c,
            parent_catalog_id="spellcasting",
            group_id="magic_die",
        )

        owned.append(empowerment)

        expected_die = None

        for effect in step.get("effects", []):
            if (
                effect.get("type") == "set_bonus_die"
                and effect.get("key") == "magic_die"
            ):
                expected_die = int(effect["die_size"])

        if expected_die is not None:
            assert_equal(
                c.bonus_dice.dice.get("magic_die"),
                expected_die,
            )

    assert_true(
        backend.ImprovementSystem.remove_empowerment(
            c,
            spellcasting.id,
            owned[-1].id,
        )
    )

    if len(group["steps"]) >= 2:
        expected_previous = None

        for effect in group["steps"][-2].get("effects", []):
            if (
                effect.get("type") == "set_bonus_die"
                and effect.get("key") == "magic_die"
            ):
                expected_previous = int(effect["die_size"])

        if expected_previous is not None:
            assert_equal(
                c.bonus_dice.dice.get("magic_die"),
                expected_previous,
            )


# ============================================================================
# Animal Buddy / Well Trained
# ============================================================================

@test("Animal Buddy display contains all six stats and d4 buddy die")
def _():
    c = fresh(ip=1000)

    buddy = buy_base(
        c,
        "animal_buddy",
        choices={
            "buddy_name": "Milo",
            "buddy_stat_d6": "agility",
            "buddy_stat_d8_a": "strength",
            "buddy_stat_d8_b": "finesse",
            "buddy_stat_d10": "instinct",
            "buddy_perk": "Excellent nose",
        },
    )

    text = "\n".join(
        backend.ImprovementSystem.build_choice_lines(buddy)
    ).lower()

    assert_true("milo" in text)

    for stat_name in STAT_NAMES:
        assert_true(
            stat_name in text,
            f"Animal Buddy display missing {stat_name}",
        )

    assert_equal(
        c.bonus_dice.dice.get("buddy_die"),
        4,
    )


@test("Two Well Trained choices on one buddy stat display +2")
def _():
    c = fresh(ip=1000)

    buddy = buy_base(
        c,
        "animal_buddy",
        choices={
            "buddy_name": "Milo",
            "buddy_stat_d6": "agility",
            "buddy_stat_d8_a": "strength",
            "buddy_stat_d8_b": "finesse",
            "buddy_stat_d10": "instinct",
            "buddy_perk": "Excellent nose",
        },
    )

    # This directly creates the model state expected after first/second
    # Well Trained purchases: +1 then +2 cost on the same ability.
    buddy.empowerments.extend(
        [
            backend.TakenEmpowerment(
                id=str(uuid4()),
                group_id="training",
                catalog_id="well_trained",
                name="Well Trained",
                cost=1,
                description="",
                source="ip",
                choices={"buddy_training_stat": "agility"},
            ),
            backend.TakenEmpowerment(
                id=str(uuid4()),
                group_id="training",
                catalog_id="well_trained",
                name="Well Trained",
                cost=2,
                description="",
                source="ip",
                choices={"buddy_training_stat": "agility"},
            ),
        ]
    )

    c.validate()

    text = " ".join(
        backend.ImprovementSystem.build_choice_lines(buddy)
    ).lower()

    assert_true(
        "agility d6+2" in text,
        "Two Well Trained rows did not display as Agility d6+2",
    )

    assert_equal(
        buddy.total_cost(),
        buddy.cost + 3,
    )


# ============================================================================
# Generated-note side effects through ImprovementsMixin
# ============================================================================

@test("Removing Spellcasting removes only its generated verbs note")
def _():
    c = fresh(ip=1000)

    spellcasting = buy_base(
        c,
        "spellcasting",
        choices={
            "magic_school": "Abjuration",
            "magic_school_description": "Defensive magic.",
        },
    )

    spellcasting.choices["_verbs_note_created"] = True

    c.notes.list_of_notes.extend(
        [
            backend.CharacterNote(
                id=str(uuid4()),
                title="Spellcasting Verbs",
                text="Generated",
                color="blue",
            ),
            backend.CharacterNote(
                id=str(uuid4()),
                title="Keep This",
                text="Unrelated",
                color="green",
            ),
        ]
    )

    c.validate()

    w = make_window(c)
    w.mark_dirty = lambda auto_save=False: None

    old_ask = improvements_ui.ask_yes_no
    improvements_ui.ask_yes_no = lambda *a, **k: True

    try:
        w.confirm_remove_improvement(spellcasting)
    finally:
        improvements_ui.ask_yes_no = old_ask

    titles = {
        note.title.strip().lower()
        for note in c.notes.list_of_notes
    }

    assert_false(
        c.improvements.has_catalog_id("spellcasting")
    )
    assert_false("spellcasting verbs" in titles)
    assert_true("keep this" in titles)

    safe_close(w)


@test("Removing Sneak Attack removes only its generated note")
def _():
    c = fresh(ip=1000)
    sneak = buy_base(c, "sneak_attack")

    sneak.choices["_sneak_attack_note_created"] = True

    c.notes.list_of_notes.extend(
        [
            backend.CharacterNote(
                id=str(uuid4()),
                title="Sneak Attack",
                text="Generated",
                color="red",
            ),
            backend.CharacterNote(
                id=str(uuid4()),
                title="Other Note",
                text="Keep",
                color="green",
            ),
        ]
    )

    c.validate()

    w = make_window(c)
    w.mark_dirty = lambda auto_save=False: None

    old_ask = improvements_ui.ask_yes_no
    improvements_ui.ask_yes_no = lambda *a, **k: True

    try:
        w.confirm_remove_improvement(sneak)
    finally:
        improvements_ui.ask_yes_no = old_ask

    titles = {
        note.title.strip().lower()
        for note in c.notes.list_of_notes
    }

    assert_false("sneak attack" in titles)
    assert_true("other note" in titles)

    safe_close(w)


@test("Removing Sneak Attack empowerment synchronizes generated note")
def _():
    c = fresh(ip=1000)
    sneak = buy_base(c, "sneak_attack")

    matches = [
        p
        for p in available(c)
        if (
            p.get("kind") == "empowerment"
            and p.get("parent_catalog_id") == "sneak_attack"
        )
    ]

    assert_true(
        matches,
        "Sneak Attack exposed no empowerment",
    )

    assert_true(buy(c, matches[0]))

    sneak = c.improvements.get_first_by_catalog_id("sneak_attack")
    assert_true(sneak.empowerments)

    target = sneak.empowerments[-1]
    sneak.choices["_sneak_attack_note_created"] = True

    note = backend.CharacterNote(
        id=str(uuid4()),
        title="Sneak Attack",
        text="OLD TEXT",
        color="red",
    )

    c.notes.list_of_notes.append(note)
    c.validate()

    w = make_window(c)
    w.mark_dirty = lambda auto_save=False: None

    old_ask = improvements_ui.ask_yes_no
    improvements_ui.ask_yes_no = lambda *a, **k: True

    try:
        w.confirm_remove_empowerment(sneak, target)
    finally:
        improvements_ui.ask_yes_no = old_ask

    assert_false(
        any(
            e.id == target.id
            for e in sneak.empowerments
        )
    )

    assert_not_equal(
        note.text,
        "OLD TEXT",
        "Generated Sneak Attack note was not refreshed",
    )

    assert_equal(
        note.text,
        w.build_sneak_attack_note_text(sneak),
    )

    safe_close(w)


@test("Skilled At group removal removes all rows and refunds all their IP")
def _():
    c = fresh(ip=1000)

    rows = []

    for index, stat_name in enumerate(STAT_NAMES[:3], start=1):
        row = backend.Improvement(
            id=str(uuid4()),
            catalog_id="skilled_at",
            name=f"Skilled At {stat_name.title()}",
            cost=index,
            description="",
            source="ip",
            choices={"stat_name": stat_name},
        )
        rows.append(row)
        c.improvements.list_of_taken_improvements.append(row)

    unrelated = backend.Improvement(
        id=str(uuid4()),
        catalog_id="custom",
        name="Unrelated",
        cost=4,
        description="",
        source="ip",
    )

    c.improvements.list_of_taken_improvements.append(unrelated)
    c.validate()

    before_used = c.progression.used_IP
    refund = sum(row.total_cost() for row in rows)

    w = make_window(c)
    w.mark_dirty = lambda auto_save=False: None

    old_ask = improvements_ui.ask_yes_no
    improvements_ui.ask_yes_no = lambda *a, **k: True

    try:
        w.confirm_remove_skilled_at_group(rows)
    finally:
        improvements_ui.ask_yes_no = old_ask

    assert_false(
        any(
            imp.catalog_id == "skilled_at"
            for imp in c.improvements.list_of_taken_improvements
        )
    )

    assert_true(
        unrelated in c.improvements.list_of_taken_improvements
    )

    assert_equal(
        c.progression.used_IP,
        before_used - refund,
    )

    safe_close(w)


# ============================================================================
# Display / persistence
# ============================================================================

@test("Every buyable catalog improvement builds a complete display dictionary")
def _():
    tested = 0

    for catalog_id in CATALOG:
        c = fresh(ip=10000)

        matches = purchase_matches(
            c,
            kind="base",
            catalog_id=catalog_id,
        )

        if not matches:
            continue

        if not buy(c, matches[0]):
            continue

        improvement = c.improvements.get_first_by_catalog_id(catalog_id)

        display = backend.ImprovementSystem.build_improvement_display(
            c,
            improvement,
        )

        assert_true(isinstance(display, dict))

        for key in (
            "name",
            "summary",
            "choices",
            "upgrades",
            "details",
        ):
            assert_true(
                key in display,
                f"{catalog_id} display missing {key}",
            )

        tested += 1

    assert_true(
        tested >= 20,
        f"Too few improvement displays were tested ({tested})",
    )


@test("Heavily improved character survives 30 exact file save/load cycles")
def _():
    with StorageSandbox() as env:
        c = fresh(name="Heavy Improvements", ip=10000)

        # Buy many distinct base improvements.
        for catalog_id in CATALOG:
            matches = purchase_matches(
                c,
                kind="base",
                catalog_id=catalog_id,
            )

            if not matches:
                continue

            backend.ImprovementSystem.buy_purchase(
                c,
                matches[0],
                choices=choices_for_purchase(matches[0]),
            )

            if len(c.improvements.list_of_taken_improvements) >= 25:
                break

        # Then buy a collection of empowerments.
        for _ in range(20):
            empowerment_options = [
                p
                for p in available(c)
                if p.get("kind") == "empowerment"
            ]

            if not empowerment_options:
                break

            purchase = empowerment_options[0]

            backend.ImprovementSystem.buy_purchase(
                c,
                purchase,
                choices=choices_for_purchase(purchase),
            )

        c.validate()
        assert_invariants(c)

        expected = snapshot(c)
        file_path = env.save_dir / "heavy_improvements.didchar"

        for cycle in range(30):
            backend.CharacterStorageSystem.export_character_file(
                c,
                str(file_path),
            )

            c = backend.CharacterStorageSystem.import_character_file(
                str(file_path)
            )

            assert_equal(
                snapshot(c),
                expected,
                f"Improvement state drifted on file cycle {cycle + 1}",
            )

            assert_invariants(c)


# ============================================================================
# Randomized improvement-only destructive test
# ============================================================================

def random_improvement_operation(rng, character):
    operation = rng.choice(
        (
            "buy",
            "buy",
            "remove_base",
            "remove_empowerment",
            "roundtrip",
        )
    )

    if operation == "buy":
        options = available(character)

        if options:
            purchase = rng.choice(options)

            backend.ImprovementSystem.buy_purchase(
                character,
                purchase,
                choices=choices_for_purchase(purchase),
            )

    elif operation == "remove_base":
        candidates = [
            improvement
            for improvement in character.improvements.list_of_taken_improvements
            if improvement.source != "species"
        ]

        if candidates:
            target = rng.choice(candidates)

            backend.ImprovementSystem.remove_improvement(
                character,
                target.id,
            )

    elif operation == "remove_empowerment":
        candidates = []

        for improvement in character.improvements.list_of_taken_improvements:
            for empowerment in improvement.empowerments:
                candidates.append((improvement, empowerment))

        if candidates:
            parent, empowerment = rng.choice(candidates)

            backend.ImprovementSystem.remove_empowerment(
                character,
                parent.id,
                empowerment.id,
            )

    elif operation == "roundtrip":
        character = roundtrip(character)

    character.validate()
    return character


@test("10,000 randomized improvement operations preserve invariants")
def _():
    rng = random.Random(SEED)
    total = 0

    for character_number in range(40):
        c = fresh(
            name=f"Improvement Fuzz {character_number}",
            ip=3000,
        )

        for _ in range(250):
            c = random_improvement_operation(
                rng,
                c,
            )

            assert_invariants(c)
            total += 1

    assert_equal(total, 10000)




# ============================================================================
# Current Heightened Ability / rich-description regressions
# ============================================================================

@test("Free Heightened Ability split allocation remains completely free")
def _():
    c = fresh("Free Heightened Split", ip=100)
    before = c.progression.used_IP

    assert_true(backend.StatSystem.add_free_heightened_ability(c, "strength"))
    assert_true(backend.StatSystem.add_free_heightened_ability(c, "agility"))

    assert_equal(c.progression.used_IP, before)
    assert_equal(c.free_heightened_ability_stats.count("strength"), 1)
    assert_equal(c.free_heightened_ability_stats.count("agility"), 1)
    assert_invariants(c)


@test("Free Heightened Ability double allocation charges exactly one IP")
def _():
    c = fresh("Free Heightened Double", ip=100)
    before = c.progression.used_IP

    assert_true(backend.StatSystem.add_free_heightened_ability(c, "strength"))
    assert_true(backend.StatSystem.add_free_heightened_ability(c, "strength"))

    assert_equal(c.progression.used_IP, before + 1)
    assert_equal(c.free_heightened_ability_stats.count("strength"), 2)

    assert_true(backend.StatSystem.remove_free_heightened_ability(c, "strength"))
    assert_equal(c.progression.used_IP, before)
    assert_invariants(c)


@test("Reckless Attack keeps the current rich-text emphasis")
def _():
    option = CATALOG.get("reckless_attack")
    if option is None:
        return

    description = str(option.get("description", ""))
    assert_true("<b>" in description and "</b>" in description)
    assert_true("attack on your turn" in description.lower())
    assert_true("attacks against you" in description.lower())


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
print("=" * 88)
print(
    "IMPROVEMENTS TORTURE TEST COMPLETE: "
    f"{passed} passed / {failed} failed"
)
print("=" * 88)

report_path = (
    REPORT_DIR
    / "automated_improvements_torture_report.json"
)

with open(report_path, "w", encoding="utf-8") as file:
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

print(f"Report: {report_path.name}")

if failed:
    sys.exit(1)
