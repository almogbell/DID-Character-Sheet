import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Application and test files deliberately live in different directories.
from test_support import app_dir, HERE
APP_DIR = app_dir()
REPORT_DIR = Path(os.environ.get("DID_TEST_REPORT_DIR", str(HERE / "reports"))).resolve()
REPORT_DIR.mkdir(parents=True, exist_ok=True)
ROOT = APP_DIR
sys.path.insert(0, str(ROOT))
REPORT_PATH = REPORT_DIR / "creation_rules_test_report.json"

results = []

def record(name, passed, details="", error=""):
    item = {"test": name, "passed": bool(passed), "details": str(details)}
    if error:
        item["error"] = str(error)
    results.append(item)
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    if details:
        print("      ", details)
    if error:
        print("       ERROR:", error)

def test(name):
    def decorator(fn):
        try:
            fn()
        except Exception as exc:
            record(name, False, "Test raised an exception.", f"{type(exc).__name__}: {exc}")
        return fn
    return decorator

# ------------------------------------------------------------
# Imports
# ------------------------------------------------------------

try:
    import backend_2_1 as backend
    record("Import backend_2_1", True)
except Exception:
    backend = None
    record("Import backend_2_1", False, error=traceback.format_exc())

try:
    import character_template as templates
    record("Import character_template", True)
except Exception:
    templates = None
    record("Import character_template", False, error=traceback.format_exc())

try:
    import character_API as catalog
    record("Import character_API", True)
except Exception:
    catalog = None
    record("Import character_API", False, error=traceback.format_exc())

if backend and templates and catalog:

    @test("Normal character is unrestricted")
    def _():
        c = backend.Character.create_new_character("Normal")
        assert c.creation_rules_active is False
        assert c.creation_species_mode == "normal"
        assert c.creation_allow_custom_improvements is True
        assert c.creation_allowed_ability_array_ids == []
        assert c.creation_improvement_mode == "all"
        assert c.creation_improvement_ids == []
        record("Normal character is unrestricted", True)

    @test("Template applies level, IP, Hearts and AT")
    def _():
        template = templates.CharacterTemplate(
            name="QA Rules",
            rules=templates.CharacterCreationRules(
                level=3,
                extra_ip=5,
                species_mode="required",
                starting_hearts=7,
                starting_at=9,
                allow_custom_improvements=False,
            ),
        )
        c = backend.Character.create_new_character("Template Character")
        templates.apply_template_to_character(c, template)

        expected_ip = backend.STARTING_IP + ((3 - 1) * 2) + 5
        assert c.progression.current_IP == expected_ip
        assert c.HP.max_hearts == 7
        assert c.HP.max_HP == 28
        assert c.HP.current_HP == 28
        assert c.adversity.max_AT == 9
        assert c.adversity.current_AT == 0

        record(
            "Template applies level, IP, Hearts and AT",
            True,
            f"IP={c.progression.current_IP}, Hearts={c.HP.max_hearts}, AT={c.adversity.max_AT}",
        )

    @test("Template restrictions are copied into Character")
    def _():
        arrays = [x["id"] for x in catalog.ABILITY_ARRAYS[:2]]
        imp_ids = [x for x in catalog.IMPROVEMENT_CATALOG if x != "custom"][:2]

        template = templates.CharacterTemplate(
            name="Persistent QA",
            rules=templates.CharacterCreationRules(
                species_mode="disabled",
                allow_custom_improvements=False,
                allowed_ability_array_ids=arrays,
                improvement_mode="allow_only",
                improvement_ids=imp_ids,
            ),
        )

        c = backend.Character.create_new_character()
        templates.apply_template_to_character(c, template)

        assert c.creation_rules_active is True
        assert c.creation_template_name == "Persistent QA"
        assert c.creation_species_mode == "disabled"
        assert c.creation_allow_custom_improvements is False
        assert c.creation_allowed_ability_array_ids == arrays
        assert c.creation_improvement_mode == "allow_only"
        assert c.creation_improvement_ids == imp_ids

        record("Template restrictions are copied into Character", True)

    @test("Creation Rules survive character serialization")
    def _():
        arrays = [x["id"] for x in catalog.ABILITY_ARRAYS[:2]]
        imp_ids = [x for x in catalog.IMPROVEMENT_CATALOG if x != "custom"][:2]

        c = backend.Character.create_new_character("Persistence")
        c.creation_rules_active = True
        c.creation_template_name = "Persistence Test"
        c.creation_species_mode = "required"
        c.creation_allow_custom_improvements = False
        c.creation_allowed_ability_array_ids = arrays
        c.creation_improvement_mode = "ban"
        c.creation_improvement_ids = imp_ids
        c.validate()

        data = backend.CharacterStorageSystem.character_to_dict(c)
        loaded = backend.CharacterStorageSystem.character_from_dict(data)

        assert loaded.creation_rules_active is True
        assert loaded.creation_template_name == "Persistence Test"
        assert loaded.creation_species_mode == "required"
        assert loaded.creation_allow_custom_improvements is False
        assert loaded.creation_allowed_ability_array_ids == arrays
        assert loaded.creation_improvement_mode == "ban"
        assert loaded.creation_improvement_ids == imp_ids

        record("Creation Rules survive character serialization", True)

    @test("Old character data still loads unrestricted")
    def _():
        c = backend.Character.create_new_character("Legacy")
        data = backend.CharacterStorageSystem.character_to_dict(c)
        data.pop("creation_rules", None)

        loaded = backend.CharacterStorageSystem.character_from_dict(data)

        assert loaded.creation_rules_active is False
        assert loaded.creation_species_mode == "normal"
        assert loaded.creation_improvement_mode == "all"
        assert loaded.creation_allow_custom_improvements is True

        record("Old character data still loads unrestricted", True)

    @test(".didtemplate save/load preserves Creation Rules")
    def _():
        arrays = [x["id"] for x in catalog.ABILITY_ARRAYS[:2]]
        imp_ids = [x for x in catalog.IMPROVEMENT_CATALOG if x != "custom"][:2]

        original = templates.CharacterTemplate(
            name="Template File QA",
            description="Description",
            player_instructions="Instructions",
            rules=templates.CharacterCreationRules(
                level=4,
                extra_ip=3,
                species_mode="required",
                starting_hearts=8,
                starting_at=10,
                allow_custom_improvements=False,
                allowed_ability_array_ids=arrays,
                improvement_mode="ban",
                improvement_ids=imp_ids,
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qa.didtemplate"
            templates.CharacterTemplateStorage.save_template(original, str(path))
            loaded = templates.CharacterTemplateStorage.load_template(str(path))

        assert loaded.name == original.name
        assert loaded.rules.level == 4
        assert loaded.rules.extra_ip == 3
        assert loaded.rules.species_mode == "required"
        assert loaded.rules.starting_hearts == 8
        assert loaded.rules.starting_at == 10
        assert loaded.rules.allow_custom_improvements is False
        assert loaded.rules.allowed_ability_array_ids == arrays
        assert loaded.rules.improvement_mode == "ban"
        assert loaded.rules.improvement_ids == imp_ids

        record(".didtemplate save/load preserves Creation Rules", True)

    @test("Allow-only blocks unselected base Improvement")
    def _():
        ids = [x for x in catalog.IMPROVEMENT_CATALOG if x != "custom"]
        assert len(ids) >= 2

        c = backend.Character.create_new_character()
        c.progression.current_IP = 999
        c.creation_rules_active = True
        c.creation_improvement_mode = "allow_only"
        c.creation_improvement_ids = [ids[0]]
        c.validate()

        blocked_option = backend.ImprovementCatalogSystem.get_option(ids[1])
        assert backend.ImprovementSystem.can_buy_base(c, blocked_option) is False

        record("Allow-only blocks unselected base Improvement", True, ids[1])

    @test("Ban mode blocks selected base Improvement")
    def _():
        ids = [x for x in catalog.IMPROVEMENT_CATALOG if x != "custom"]
        banned = ids[0]

        c = backend.Character.create_new_character()
        c.progression.current_IP = 999
        c.creation_rules_active = True
        c.creation_improvement_mode = "ban"
        c.creation_improvement_ids = [banned]
        c.validate()

        option = backend.ImprovementCatalogSystem.get_option(banned)
        assert backend.ImprovementSystem.can_buy_base(c, option) is False

        record("Ban mode blocks selected base Improvement", True, banned)

    @test("Disabled Species returns no Species choices")
    def _():
        c = backend.Character.create_new_character()
        c.creation_rules_active = True
        c.creation_species_mode = "disabled"
        c.validate()

        assert backend.ImprovementSystem.get_species_options(c) == []

        record("Disabled Species returns no Species choices", True)

# ------------------------------------------------------------
# Frontend
# ------------------------------------------------------------

try:
    import frontend_2_8 as frontend
    record("Import frontend_2_8", True)
except Exception:
    frontend = None
    record("Import frontend_2_8", False, error=traceback.format_exc())

if frontend and backend and catalog:
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
    except Exception:
        app = None

    @test("Ability editor obeys allowed array IDs")
    def _():
        assert app is not None
        assert len(catalog.ABILITY_ARRAYS) >= 2

        allowed_id = catalog.ABILITY_ARRAYS[0]["id"]
        c = backend.Character.create_new_character()

        dialog = frontend.AbilityEditorDialog(
            c,
            allowed_array_ids=[allowed_id],
        )

        available = dialog.available_ability_arrays()
        assert len(available) == 1
        assert available[0]["id"] == allowed_id

        dialog.close()
        app.processEvents()

        record("Ability editor obeys allowed array IDs", True, allowed_id)

    @test("No selected ability arrays means all arrays are allowed")
    def _():
        assert app is not None

        c = backend.Character.create_new_character()
        dialog = frontend.AbilityEditorDialog(
            c,
            allowed_array_ids=[],
        )

        available = dialog.available_ability_arrays()
        assert len(available) == len(catalog.ABILITY_ARRAYS)

        dialog.close()
        app.processEvents()

        record(
            "No selected ability arrays means all arrays are allowed",
            True,
            f"{len(available)} arrays",
        )

    @test("Frontend contains all Creation Rules enforcement hooks")
    def _():
        source = (
            (ROOT / "frontend_2_8.py").read_text(encoding="utf-8")
            + "\n"
            + (ROOT / "improvements_ui.py").read_text(encoding="utf-8")
        )

        required = {
            "creation_allowed_ability_array_ids": "ability arrays",
            "creation_species_mode": "Species",
            "creation_improvement_mode": "Improvement mode",
            "creation_improvement_ids": "Improvement IDs",
            "creation_allow_custom_improvements": "Custom Improvements",
            "parent_catalog_id": "Empowerment parent filtering",
            "Species Required": "required Species save guard",
        }

        missing = [
            description
            for fragment, description in required.items()
            if fragment not in source
        ]

        assert not missing, "Missing: " + ", ".join(missing)

        record("Frontend contains all Creation Rules enforcement hooks", True)

# ------------------------------------------------------------
# JSON report
# ------------------------------------------------------------

passed = sum(1 for r in results if r["passed"])
failed = len(results) - passed

report = {
    "summary": {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "all_passed": failed == 0,
    },
    "tests": results,
}

REPORT_PATH.write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print()
print("=" * 70)
print(f"Creation Rules QA: {passed} passed / {failed} failed")
print(f"JSON report: {REPORT_PATH}")
print("=" * 70)

if failed:
    sys.exit(1)
