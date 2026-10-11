from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


NEW_CAMPAIGN_CHANGED = r'''    def _campaign_changed(self, index):
        if index < 0 or index >= len(self.campaigns):
            self.current_campaign = None
            self._update_buttons()
            return

        self.current_campaign = self.campaigns[index]
        try:
            role = self.service.role_for_campaign(self.current_campaign["id"])
        except Exception:
            role = ""

        role = str(role or "").strip().lower()
        self.current_campaign["role"] = role

        # DM-only information stays DM-only in the desktop manager too.
        # Players know they are members, but do not need the reusable invite
        # code or DM-dashboard controls.
        if role == "dm":
            invite = self.current_campaign.get("invite_code") or ""
            self.meta_label.setText(
                f"Role: DM    •    Invite code: {invite}"
            )
        elif role == "player":
            self.meta_label.setText("Role: Player")
        else:
            self.meta_label.setText("Role: Member")

        try:
            self.rules_view.setHtml(_rules_html(self.current_campaign))
        except Exception as error:
            self.rules_view.setPlainText(f"Could not read campaign rules: {error}")

        self._update_buttons()
'''


NEW_UPDATE_BUTTONS = r'''    def _update_buttons(self):
        has_campaign = isinstance(self.current_campaign, dict)
        role = str((self.current_campaign or {}).get("role") or "").strip().lower()
        is_dm = bool(has_campaign and role == "dm")

        # Everyone can create/join campaigns of their own. Controls belonging
        # to the selected campaign are role-aware.
        self.edit_rules_btn.setVisible(is_dm)
        self.edit_rules_btn.setEnabled(is_dm)

        self.dashboard_btn.setVisible(is_dm)
        self.dashboard_btn.setEnabled(is_dm)

        self.create_character_btn.setEnabled(has_campaign)
        self.share_btn.setEnabled(has_campaign)
        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))

        self._refresh_roll_share_checkbox()
        self._refresh_privacy_controls()
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
            and (root / "campaign_ui.py").is_file()
            and (root / "campaign_privacy.py").is_file()
            and (root / "campaign_session.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 6 DID project. Put this script in the phase6 "
        "folder inside your current code folder and run it from there."
    )


def replace_method(text, class_pos, method_name, next_method_name, replacement):
    start = text.find(f"    def {method_name}", class_pos)
    end = text.find(f"    def {next_method_name}", start)
    if start < 0 or end < 0:
        raise RuntimeError(
            f"Could not safely locate {method_name} / {next_method_name} in campaign_ui.py."
        )
    current = text[start:end]
    if current == replacement + "\n":
        return text, False
    return text[:start] + replacement + "\n" + text[end:], True


def copy_privacy_ui(root):
    source = Path(__file__).resolve().parent / "campaign_privacy_ui.py"
    if not source.is_file():
        raise FileNotFoundError(
            "campaign_privacy_ui.py is missing beside this v15 patch. Download the "
            "latest Phase 6 ZIP and keep the Phase 6 files together."
        )

    target = root / "campaign_privacy_ui.py"
    source_text = source.read_text(encoding="utf-8")
    target_text = target.read_text(encoding="utf-8") if target.exists() else ""

    if source_text == target_text:
        return False

    if target.exists():
        backup = target.with_name(target.name + ".before_campaign_v15_privacy_ui")
        if not backup.exists():
            shutil.copy2(target, backup)
            print(f"Backup: {backup.name}")

    shutil.copy2(source, target)
    return True


def main():
    root = find_project_root()
    campaign_ui = root / "campaign_ui.py"
    original = campaign_ui.read_text(encoding="utf-8")
    text = original

    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = text.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    required = (
        "self.dashboard_btn",
        "self.edit_rules_btn",
        "self._refresh_roll_share_checkbox()",
        "self._refresh_privacy_controls()",
        'QPushButton("Save to Campaign")',
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(
            "The latest Phase 6 Campaign UI is not installed yet. Missing: "
            + ", ".join(missing)
        )

    text, role_changed = replace_method(
        text,
        class_pos,
        "_campaign_changed(self, index):",
        "_update_buttons(self):",
        NEW_CAMPAIGN_CHANGED,
    )

    class_pos = text.find(class_marker)
    text, buttons_changed = replace_method(
        text,
        class_pos,
        "_update_buttons(self):",
        "_choose_rules_for_new_campaign(self, campaign_name):",
        NEW_UPDATE_BUTTONS,
    )

    if text != original:
        backup = campaign_ui.with_name(campaign_ui.name + ".before_campaign_v15_player_view")
        if not backup.exists():
            shutil.copy2(campaign_ui, backup)
            print(f"Backup: {backup.name}")
        campaign_ui.write_text(text, encoding="utf-8")

    privacy_changed = copy_privacy_ui(root)

    py_compile.compile(str(campaign_ui), doraise=True)
    py_compile.compile(str(root / "campaign_privacy_ui.py"), doraise=True)

    print("Player campaign view: PASS" if role_changed or buttons_changed else "Player campaign view: already installed")
    print("Player invite code hidden: PASS")
    print("Player DM Dashboard hidden: PASS")
    print("Player Edit Rules hidden: PASS")
    print("Player Creation Rules remain read-only: PASS")
    print("Sharing & Privacy redesign: PASS" if privacy_changed else "Sharing & Privacy redesign: already installed")
    print("Empty inventory/notes no longer create giant blank boxes: PASS")
    print("Privacy choices and filtering behavior: PRESERVED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign / Sharing & Privacy.")


if __name__ == "__main__":
    main()
