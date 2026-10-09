from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "campaign_dashboard_bridge.py",
    "dashboard_server.py",
    "campaign_supabase_phase4.sql",
    "test_campaign_dashboard.py",
    "campaign_dashboard_smoke_test.py",
)

UI_IMPORT_NEEDLE = "from campaign_cloud import CampaignCloudError\n"
UI_IMPORT_REPLACEMENT = (
    UI_IMPORT_NEEDLE
    + "from campaign_dashboard_bridge import open_dm_dashboard as launch_dm_dashboard\n"
)

DASHBOARD_ROW_NEEDLE = '''        root.addLayout(second_row)\n\n        close_row = QHBoxLayout()\n'''
DASHBOARD_ROW_REPLACEMENT = '''        root.addLayout(second_row)\n\n        dashboard_row = QHBoxLayout()\n        self.dashboard_btn = QPushButton("Open DM Dashboard")\n        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)\n        dashboard_row.addStretch()\n        dashboard_row.addWidget(self.dashboard_btn)\n        root.addLayout(dashboard_row)\n\n        close_row = QHBoxLayout()\n'''

BUTTON_ENABLE_NEEDLE = '''        self.edit_rules_btn.setEnabled(has_campaign and role == "dm")\n        self.create_character_btn.setEnabled(has_campaign)\n'''
BUTTON_ENABLE_REPLACEMENT = '''        self.edit_rules_btn.setEnabled(has_campaign and role == "dm")\n        self.dashboard_btn.setEnabled(has_campaign and role == "dm")\n        self.create_character_btn.setEnabled(has_campaign)\n'''

METHOD_NEEDLE = '''    def _choose_rules_for_new_campaign(self, campaign_name):\n'''
METHOD_REPLACEMENT = '''    def open_dm_dashboard(self):\n        if (\n            not self.current_campaign\n            or self.current_campaign.get("role") != "dm"\n            or self.client is None\n        ):\n            return\n\n        try:\n            result = launch_dm_dashboard(\n                self.client,\n                self.current_campaign["id"],\n                app_dir=Path(__file__).resolve().parent,\n            )\n        except Exception as error:\n            self._show_error("Open DM Dashboard Failed", error)\n            return\n\n        QMessageBox.information(\n            self,\n            "DM Dashboard",\n            "The live DM dashboard has been opened in your browser.\\n\\n"\n            "If the browser does not connect automatically, enter this one-time "\n            f"code within 10 minutes:\\n\\n{result.get('code', '')}",\n        )\n\n    def _choose_rules_for_new_campaign(self, campaign_name):\n'''

FRONTEND_IMPORT_NEEDLE = "from campaign_ui import open_campaign_manager\n"
FRONTEND_IMPORT_REPLACEMENT = (
    FRONTEND_IMPORT_NEEDLE
    + "from campaign_dashboard_bridge import install_presence_heartbeat\n"
)

FRONTEND_INIT_NEEDLE = "        initialize_campaign_runtime(self)\n"
FRONTEND_INIT_REPLACEMENT = (
    FRONTEND_INIT_NEEDLE
    + "        install_presence_heartbeat(self)\n"
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
            and (root / "campaign_ui.py").is_file()
            and (root / "campaign_runtime.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 3 DID project. Copy the Phase 4 files into "
        "your current code folder and run this script there."
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
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main():
    root = find_project_root()
    support_dir = Path(__file__).resolve().parent

    missing = [name for name in REQUIRED_FILES if not (support_dir / name).is_file()]
    for asset in ("index.html", "app.js", "styles.css"):
        if not (support_dir / "dm_dashboard" / asset).is_file():
            missing.append(f"dm_dashboard/{asset}")
    if missing:
        raise FileNotFoundError(
            "Keep all Phase 4 files together before running the patcher. Missing: "
            + ", ".join(missing)
        )

    frontend = root / "frontend_2_8.py"
    campaign_ui = root / "campaign_ui.py"

    frontend_original = frontend.read_text(encoding="utf-8")
    frontend_text = frontend_original
    ui_original = campaign_ui.read_text(encoding="utf-8")
    ui_text = ui_original

    print(f"Project:  {root}")
    print("Installing Phase 4: live DM browser dashboard...")

    if "install_presence_heartbeat" not in frontend_text:
        frontend_text = replace_once(
            frontend_text,
            FRONTEND_IMPORT_NEEDLE,
            FRONTEND_IMPORT_REPLACEMENT,
            "Phase 4 frontend import",
        )
        frontend_text = replace_once(
            frontend_text,
            FRONTEND_INIT_NEEDLE,
            FRONTEND_INIT_REPLACEMENT,
            "Phase 4 presence initialization",
        )

    if "launch_dm_dashboard" not in ui_text:
        ui_text = replace_once(
            ui_text,
            UI_IMPORT_NEEDLE,
            UI_IMPORT_REPLACEMENT,
            "Phase 4 campaign UI import",
        )

    if 'QPushButton("Open DM Dashboard")' not in ui_text:
        ui_text = replace_once(
            ui_text,
            DASHBOARD_ROW_NEEDLE,
            DASHBOARD_ROW_REPLACEMENT,
            "DM dashboard button",
        )
        ui_text = replace_once(
            ui_text,
            BUTTON_ENABLE_NEEDLE,
            BUTTON_ENABLE_REPLACEMENT,
            "DM-only dashboard button state",
        )
        ui_text = replace_once(
            ui_text,
            METHOD_NEEDLE,
            METHOD_REPLACEMENT,
            "DM dashboard action",
        )

    if frontend_text != frontend_original:
        backup = frontend.with_name(frontend.name + ".before_phase4")
        if not backup.exists():
            shutil.copy2(frontend, backup)
            print(f"Backup:   {backup.name}")

    if ui_text != ui_original:
        backup = campaign_ui.with_name(campaign_ui.name + ".before_phase4")
        if not backup.exists():
            shutil.copy2(campaign_ui, backup)
            print(f"Backup:   {backup.name}")

    frontend.write_text(frontend_text, encoding="utf-8")
    campaign_ui.write_text(ui_text, encoding="utf-8")

    copy_if_needed(
        support_dir / "campaign_dashboard_bridge.py",
        root / "campaign_dashboard_bridge.py",
    )
    copy_if_needed(
        support_dir / "dashboard_server.py",
        root / "dashboard_server.py",
    )
    copy_if_needed(
        support_dir / "campaign_supabase_phase4.sql",
        root / "campaign_supabase_phase4.sql",
    )
    copy_if_needed(
        support_dir / "campaign_dashboard_smoke_test.py",
        root / "campaign_dashboard_smoke_test.py",
    )
    copy_if_needed(
        support_dir / "test_campaign_dashboard.py",
        root / "test_campaign_dashboard.py",
    )

    dashboard_target = root / "dm_dashboard"
    dashboard_target.mkdir(parents=True, exist_ok=True)
    for asset in ("index.html", "app.js", "styles.css"):
        copy_if_needed(
            support_dir / "dm_dashboard" / asset,
            dashboard_target / asset,
        )

    # Browser config contains only the same public/publishable key already used
    # by the desktop client. Never copy refresh tokens or a service-role key.
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from campaign_dashboard_bridge import prepare_dashboard_config
        prepare_dashboard_config(root)
        print("Browser config: PASS")
    except Exception as error:
        print(f"Browser config: deferred ({error})")

    for path in (
        frontend,
        campaign_ui,
        root / "campaign_dashboard_bridge.py",
        root / "dashboard_server.py",
        root / "test_campaign_dashboard.py",
        root / "campaign_dashboard_smoke_test.py",
    ):
        py_compile.compile(str(path), doraise=True)
    print("Compile:  PASS")

    completed = subprocess.run(
        [sys.executable, str(root / "test_campaign_dashboard.py")],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    print("\nPhase 4 local tests: PASS")
    print("\nNEXT:")
    print("1. Run campaign_supabase_phase4.sql in your Supabase SQL Editor.")
    print("2. Run: python campaign_dashboard_smoke_test.py")
    print("3. After PASS, launch: python frontend_2_8.py")
    print("4. Tools -> Campaign & Templates -> Campaign... -> Open DM Dashboard")


if __name__ == "__main__":
    main()
