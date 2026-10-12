from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED = (
    "campaign_supabase_phase8.sql",
    "campaign_layer.js",
    "campaign_layer.css",
    "phase8_player_ui.py",
    "test_phase8.py",
    "phase8_cloud_smoke_test.py",
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
        if (
            (root / "frontend_2_8.py").is_file()
            and (root / "campaign_cloud.py").is_file()
            and (root / "campaign_role_ui.py").is_file()
            and (root / "dm_dashboard" / "index.html").is_file()
        ):
            return root
    raise FileNotFoundError(
        "Could not find the DID project. Put the phase8 folder inside your current code folder and run from there."
    )


def copy_if_needed(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes():
        return False
    shutil.copy2(source, target)
    return True


def patch_dashboard_index(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original
    css = '  <link rel="stylesheet" href="campaign_layer.css">\n'
    if css not in text:
        marker = '  <link rel="stylesheet" href="styles.css">\n'
        if marker not in text:
            raise RuntimeError("Could not locate DM dashboard stylesheet marker")
        text = text.replace(marker, marker + css, 1)

    script = '  <script src="campaign_layer.js"></script>\n'
    if script not in text:
        marker = '  <script src="app.js"></script>\n'
        if marker not in text:
            raise RuntimeError("Could not locate DM dashboard app.js marker")
        text = text.replace(marker, marker + script, 1)

    if text != original:
        backup = path.with_name(path.name + ".before_phase8")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_player_campaign_ui(path: Path):
    original = path.read_text(encoding="utf-8")
    marker = "# Phase 8 player campaign info integration"
    if marker in original:
        return False

    addition = '''

# Phase 8 player campaign info integration
from phase8_player_ui import apply_phase8_player_ui as _apply_phase8_player_ui
_apply_phase8_player_ui(PlayerCampaignsDialog)
'''
    backup = path.with_name(path.name + ".before_phase8")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(original.rstrip() + addition + "\n", encoding="utf-8")
    return True


def main():
    support = Path(__file__).resolve().parent
    root = find_project_root()
    missing = [name for name in REQUIRED if not (support / name).is_file()]
    if missing:
        raise FileNotFoundError("Keep the Phase 8 files together. Missing: " + ", ".join(missing))

    print(f"Project:  {root}")
    print("Installing Phase 8: DM campaign layer...")

    copied = []
    for name in REQUIRED:
        target = root / name if name.endswith((".sql", ".py")) else root / "dm_dashboard" / name
        if copy_if_needed(support / name, target):
            copied.append(str(target.relative_to(root)))

    index_changed = patch_dashboard_index(root / "dm_dashboard" / "index.html")
    player_ui_changed = patch_player_campaign_ui(root / "campaign_role_ui.py")

    for path in (
        root / "phase8_player_ui.py",
        root / "test_phase8.py",
        root / "phase8_cloud_smoke_test.py",
        root / "campaign_role_ui.py",
    ):
        py_compile.compile(str(path), doraise=True)
    print("Python compile: PASS")

    result = subprocess.run(
        [sys.executable, str(root / "test_phase8.py")],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    print("\nPHASE 8 INSTALL: PASS")
    print(f"DM Dashboard integration: {'PASS' if index_changed else 'already installed'}")
    print(f"Player Campaign Info integration: {'PASS' if player_ui_changed else 'already installed'}")
    print("Copied: " + (", ".join(copied) if copied else "already current"))
    print("\nNEXT:")
    print("1. Run campaign_supabase_phase8.sql in Supabase SQL Editor.")
    print("2. Run: python phase8_cloud_smoke_test.py")
    print("3. Restart: python frontend_2_8.py")
    print("4. DM: Campaign Manager -> Open DM Dashboard.")
    print("5. Player: My Campaigns -> Campaign Info.")


if __name__ == "__main__":
    main()
