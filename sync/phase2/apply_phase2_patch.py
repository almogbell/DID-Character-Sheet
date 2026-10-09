from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "campaign_cloud.py",
    "test_campaign_cloud.py",
    "campaign_cloud_smoke_test.py",
    "campaign_supabase.sql",
)


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])

    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_shared.py").is_file():
            return root

    raise FileNotFoundError(
        "Could not find the Phase 1 DID project. Put these Phase 2 files in "
        "C:\\Users\\almog\\Desktop\\current code and run this script there."
    )


def copy_if_needed(source, target):
    if source.resolve() == target.resolve():
        return
    shutil.copy2(source, target)


def main():
    root = find_project_root()
    support_dir = Path(__file__).resolve().parent

    missing = [name for name in REQUIRED_FILES if not (support_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Keep all Phase 2 files together before running the patcher. Missing: "
            + ", ".join(missing)
        )

    print(f"Project: {root}")
    print("Installing Phase 2 campaign-cloud foundation...")

    cloud_target = root / "campaign_cloud.py"
    smoke_target = root / "campaign_cloud_smoke_test.py"
    sql_target = root / "campaign_supabase.sql"
    tests_dir = root / "DID_Important_Tests"
    test_target = tests_dir / "test_campaign_cloud.py"

    copy_if_needed(support_dir / "campaign_cloud.py", cloud_target)
    copy_if_needed(support_dir / "campaign_cloud_smoke_test.py", smoke_target)
    copy_if_needed(support_dir / "campaign_supabase.sql", sql_target)

    if tests_dir.is_dir():
        copy_if_needed(support_dir / "test_campaign_cloud.py", test_target)
    else:
        test_target = root / "test_campaign_cloud.py"
        copy_if_needed(support_dir / "test_campaign_cloud.py", test_target)

    py_compile.compile(str(cloud_target), doraise=True)
    py_compile.compile(str(smoke_target), doraise=True)
    py_compile.compile(str(test_target), doraise=True)
    print("Compile: PASS")

    completed = subprocess.run(
        [sys.executable, str(test_target)],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    print("\nPhase 2 local tests: PASS")
    print("No frontend UI has been changed by this step.")
    print("\nNEXT:")
    print("1. In Supabase, enable Auth -> Anonymous Sign-Ins.")
    print("2. Run campaign_supabase.sql in the Supabase SQL Editor.")
    print("3. Back here, run: python campaign_cloud_smoke_test.py")
    print("\nThe smoke test creates two temporary anonymous users, creates a temporary")
    print("campaign, joins it as a player, uploads a character state and roll, verifies")
    print("the DM can read them, then deletes the temporary campaign.")


if __name__ == "__main__":
    main()
