from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "campaign_template.py",
    "campaign_runtime.py",
    "campaign_ui.py",
    "test_campaign_template.py",
    "campaign_template_smoke_test.py",
    "campaign_supabase_phase3.sql",
)

IMPORT_NEEDLE = (
    "from campaign_shared import build_shared_character_state, build_shared_roll_event\n"
)
IMPORT_REPLACEMENT = (
    IMPORT_NEEDLE
    + "from campaign_runtime import (\n"
    + "    initialize_campaign_runtime,\n"
    + "    schedule_campaign_state_sync,\n"
    + "    restore_campaign_connection,\n"
    + ")\n"
    + "from campaign_ui import open_campaign_manager\n"
)

INIT_NEEDLE = (
    "        self._shared_roll_events = deque(maxlen=200)\n"
    "        self._shared_roll_event_callback = None\n"
)
INIT_REPLACEMENT = (
    INIT_NEEDLE
    + "\n"
    + "        # Phase 3: Campaign owns its Creation Rules and live sync.\n"
    + "        initialize_campaign_runtime(self)\n"
)

DIRTY_NEEDLE = (
    "        self.schedule_recovery_write()\n"
    "\n"
    "        if auto_save:\n"
)
DIRTY_REPLACEMENT = (
    "        self.schedule_recovery_write()\n"
    "\n"
    "        # Campaign characters send one debounced safe-state snapshot.\n"
    "        schedule_campaign_state_sync(self)\n"
    "\n"
    "        if auto_save:\n"
)

RECONNECT_NEEDLE = (
    "        self.at_box.character = self.character\n"
    "\n"
    "\n"
    "    def capitalize_first(self, text):\n"
)
RECONNECT_REPLACEMENT = (
    "        self.at_box.character = self.character\n"
    "\n"
    "        # Switching/new/loading a character also switches its campaign link.\n"
    "        restore_campaign_connection(self)\n"
    "\n"
    "\n"
    "    def capitalize_first(self, text):\n"
)

MENU_NEEDLE = '''        template_menu = menu.addMenu(
            "Creation Rules"
        )

        create_template_action = (
            template_menu.addAction(
                "Create Template"
            )
        )

        create_template_action.triggered.connect(
            self.create_character_template_from_ui
        )

        new_from_template_action = (
            template_menu.addAction(
                "New Character From Template"
            )
        )

        new_from_template_action.triggered.connect(
            self.new_character_from_template_from_ui
        )
'''

MENU_REPLACEMENT = '''        campaign_menu = menu.addMenu(
            "Campaign & Templates"
        )

        campaign_action = campaign_menu.addAction(
            "Campaign..."
        )
        campaign_action.triggered.connect(
            lambda _checked=False: open_campaign_manager(self)
        )

        campaign_menu.addSeparator()

        create_template_action = (
            campaign_menu.addAction(
                "Create Standalone Template"
            )
        )

        create_template_action.triggered.connect(
            self.create_character_template_from_ui
        )

        new_from_template_action = (
            campaign_menu.addAction(
                "New Character From Standalone Template"
            )
        )

        new_from_template_action.triggered.connect(
            self.new_character_from_template_from_ui
        )
'''


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
            and (root / "campaign_shared.py").is_file()
            and (root / "campaign_cloud.py").is_file()
            and (root / "character_template.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 2 DID project. Put the Phase 3 files in your "
        "current code folder and run this script from there."
    )


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"Could not safely patch {label}: expected exactly one matching block, found {count}."
        )
    return text.replace(needle, replacement, 1)


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
            "Keep all Phase 3 files together before running the patcher. Missing: "
            + ", ".join(missing)
        )

    frontend = root / "frontend_2_8.py"
    original = frontend.read_text(encoding="utf-8")
    text = original

    print(f"Project:  {root}")
    print(f"Frontend: {frontend.name}")
    print("Installing Phase 3: Campaign + Creation Rules...")

    if "from campaign_ui import open_campaign_manager" not in text:
        text = replace_once(
            text,
            IMPORT_NEEDLE,
            IMPORT_REPLACEMENT,
            "Phase 3 imports",
        )

    if "initialize_campaign_runtime(self)" not in text:
        text = replace_once(
            text,
            INIT_NEEDLE,
            INIT_REPLACEMENT,
            "campaign runtime initialization",
        )

    if "schedule_campaign_state_sync(self)" not in text:
        text = replace_once(
            text,
            DIRTY_NEEDLE,
            DIRTY_REPLACEMENT,
            "automatic campaign state sync",
        )

    if "restore_campaign_connection(self)" not in text:
        text = replace_once(
            text,
            RECONNECT_NEEDLE,
            RECONNECT_REPLACEMENT,
            "campaign link restore",
        )

    if '"Campaign & Templates"' not in text:
        text = replace_once(
            text,
            MENU_NEEDLE,
            MENU_REPLACEMENT,
            "Tools Campaign/Templates menu",
        )

    backup = frontend.with_name(frontend.name + ".before_phase3")
    if text != original and not backup.exists():
        shutil.copy2(frontend, backup)
        print(f"Backup:   {backup.name}")

    for module_name in (
        "campaign_template.py",
        "campaign_runtime.py",
        "campaign_ui.py",
    ):
        copy_if_needed(support_dir / module_name, root / module_name)

    test_target = root / "test_campaign_template.py"
    smoke_target = root / "campaign_template_smoke_test.py"
    sql_target = root / "campaign_supabase_phase3.sql"

    copy_if_needed(support_dir / "test_campaign_template.py", test_target)
    copy_if_needed(support_dir / "campaign_template_smoke_test.py", smoke_target)
    copy_if_needed(support_dir / "campaign_supabase_phase3.sql", sql_target)

    frontend.write_text(text, encoding="utf-8")

    for path in (
        frontend,
        root / "campaign_template.py",
        root / "campaign_runtime.py",
        root / "campaign_ui.py",
        test_target,
        smoke_target,
    ):
        py_compile.compile(str(path), doraise=True)
    print("Compile:  PASS")

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

    print("\nPhase 3 local tests: PASS")
    if text == original:
        print("Frontend Phase 3 hooks were already installed.")
    else:
        print("Frontend Phase 3 hooks installed successfully.")

    print("\nNEXT:")
    print("1. Run campaign_supabase_phase3.sql in your Supabase SQL Editor.")
    print("2. Then run: python campaign_template_smoke_test.py")
    print("3. After PASS, launch: python frontend_2_8.py")
    print("4. Open Tools -> Campaign & Templates -> Campaign...")


if __name__ == "__main__":
    main()
