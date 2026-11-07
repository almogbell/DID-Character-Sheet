DID Important Tests
===================

The quick run covers recent changes. The full run also preserves the four
important core, data safety, improvements, and redesign stress suites from
the supplied pack. The current_app mega-suite and dated patch/editor layout
tests are omitted because they overlap or depend on historical layouts.
This pack targets the app state with multi-picture selection, before the later
automatic JPEG-to-PNG conversion. JPEGs remain JPEGs; PNG alpha is preserved.

1. Extract this folder anywhere. Keep all files in the same folder.
2. Keep DID_Important_Tests inside the app folder (next to frontend_2_8.py).
   The tests now find that parent folder automatically. app_path.txt is only
   a fallback for unusual layouts and may simply contain .. Update it if your installation moved.
3. From this test folder run:

       python run_all_did_tests.py

   For the extended regression and stress run:

       python run_all_did_tests.py --full

   Or override the path for one run:

       python run_all_did_tests.py --app "C:\path\to\current code"

   Run one suite with --suite test_notes_ui.py (or another suite name).
   Each test_*.py also runs directly and automatically tests the parent app
   folder. --app / DID_APP_DIR can still deliberately target another copy.

The runner writes reports/did_important_test_report.json in this test folder.
It does not copy or edit app source files or use the app's character saves.

Suites:
- test_core.py: API text authority, note identity/colors, image persistence.
- test_creation_rules.py: original creation-rules regression checks.
- test_improvements_ui.py: land details and empowerment rows in both themes.
- test_notes_ui.py: palette controls, combined Spellcasting note, note sizing.
- test_portraits.py: multi-select, saved PNG alpha, JPEG opacity, dark mode.
- automated_core_systems_torture_test.py: progression, resources, save/load.
- automated_data_safety_torture_test.py: recovery and storage safety.
- automated_improvements_torture_test.py: costs, upgrades, notes, accounting.
- automated_redesign_ui_torture_test.py: navigation, notes, layout, themes.

The Qt suites use QT_QPA_PLATFORM=offscreen and require the same PySide6
installation as the app. If a Qt suite fails, inspect the per-suite traceback
in the JSON report. The separate dice statistics test is omitted because it
does not cover the recent notes, improvements, and portrait changes.
