"""Run the compact DID regression pack from this folder.

Normally DID_Important_Tests lives inside the app folder, so the runner tests
its parent directory automatically:
    python run_all_did_tests.py
Use --app only when deliberately testing a different app folder. app_path.txt
is retained as a fallback for non-standard folder layouts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from test_support import HERE, REQUIRED, app_dir

SUITES = (
    "test_core.py",
    "test_creation_rules.py",
    "test_improvements_ui.py",
    "test_notes_ui.py",
    "test_portraits.py",
    "test_mobile_sync_contract.py",
)
EXTENDED = (
    "automated_core_systems_torture_test.py",
    "automated_data_safety_torture_test.py",
    "automated_improvements_torture_test.py",
    "automated_redesign_ui_torture_test.py",
)

# Existing campaign/Discord regressions are maintained beside the app modules.
# Execute them in isolated processes using the exact app directory selected above.
CAMPAIGN = (
    "test_campaign_cloud.py", "test_campaign_shared.py",
    "test_campaign_template.py", "test_campaign_privacy.py",
    "test_campaign_session.py", "test_campaign_dashboard.py",
)
DISCORD = tuple(f"test_discord_phase{i}_{name}.py" for i, name in (
    (1, "routing"), (2, "commands"), (3, "ui"),
    (4, "session_controls"), (5, "voice_text"),
    (6, "notifications"), (7, "dm_permissions"),
    (8, "robustness"), (9, "ui"),
))
ALL_SUITES = SUITES + EXTENDED + CAMPAIGN + DISCORD


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", help="Path to the app folder; overrides app_path.txt")
    parser.add_argument("--suite", choices=ALL_SUITES, help="Run one suite")
    parser.add_argument("--full", action="store_true", help="Run all core, stress, campaign and Discord regressions")
    parser.add_argument("--release", action="store_true", help="Run core, campaign and Discord regressions (without extended stress tests)")
    options = parser.parse_args()
    if options.app:
        os.environ["DID_APP_DIR"] = options.app
    try:
        app = app_dir()
    except RuntimeError as error:
        parser.error(str(error))
    reports = HERE / "reports"
    reports.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["DID_APP_DIR"] = str(app)
    env["DID_TEST_REPORT_DIR"] = str(reports)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["PYTHONPATH"] = os.pathsep.join((str(HERE), str(app)))
    selected = ((options.suite,) if options.suite else
                ALL_SUITES if options.full else
                SUITES + CAMPAIGN + DISCORD if options.release else SUITES)
    results = []
    print(f"App: {app}\nTests: {HERE}", flush=True)
    for filename in selected:
        if not (HERE / filename).is_file() and not (app / filename).is_file():
            item = {"suite": filename, "passed": False, "returncode": None,
                    "stdout": "", "stderr": "Required test module missing from selected app"}
            print("FAIL", filename, item["stderr"], flush=True)
            results.append(item)
            continue
        print(f"\nRunning {filename}", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, str((HERE if (HERE / filename).is_file() else app) / filename)], cwd=str(HERE),
                env=env, capture_output=True, text=True, errors="replace", timeout=1200)
            item = {"suite": filename, "passed": result.returncode == 0,
                    "returncode": result.returncode, "stdout": result.stdout,
                    "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            item = {"suite": filename, "passed": False, "returncode": None,
                    "stdout": "", "stderr": "Timed out after 1200 seconds"}
        print("PASS" if item["passed"] else "FAIL", filename, flush=True)
        if not item["passed"]:
            print((item["stderr"] or item["stdout"])[-3500:], flush=True)
        results.append(item)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "app_dir": str(app), "results": results}
    path = reports / "did_important_test_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    passed = sum(item["passed"] for item in results)
    print(f"\n{passed}/{len(results)} suites passed. Report: {path}", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
