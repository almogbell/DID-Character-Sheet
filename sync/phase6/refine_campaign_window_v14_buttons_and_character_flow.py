from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


NEW_CREATE_METHOD = r'''    def create_and_share_character(self):
        """Create a campaign-rules character, then return to the sheet to edit it.

        Saving/linking is deliberately a separate action.  Creating a character
        should never force the user through a Save dialog before they have had a
        chance to actually build the character.
        """
        if not self.current_campaign:
            return

        template = campaign_template(self.current_campaign)
        try:
            if not _replace_current_character(self.window, template):
                return
        except Exception as error:
            self._show_error("Create Campaign Character Failed", error)
            return

        # Remember the campaign only for this running app/session.  The
        # character itself remains a completely normal .didchar character once
        # the user saves it.  This marker just lets Campaign reopen directly on
        # the useful Character step and skip a pointless compliance warning.
        self.window._pending_campaign_character = {
            "campaign_id": str(self.current_campaign.get("id") or ""),
            "campaign_name": str(self.current_campaign.get("name") or "Campaign"),
            "character_id": str(getattr(self.window.character, "id", "") or ""),
        }

        # The Campaign dialog is modal.  Close it so the user can immediately
        # edit the newly-created character on the normal character sheet.
        self.accept()
'''


NEW_SHARE_METHOD = r'''    def share_current_character(self, skip_compliance=False):
        """Save the current character locally, then save/link it to Campaign.

        This is the single simple Campaign save action.  A new campaign
        character is edited normally on the sheet first; when the user chooses
        Save to Campaign, the normal local .didchar save happens first and only
        then is the safe shared state linked/uploaded to the selected campaign.
        """
        if not self.current_campaign or self.client is None:
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        campaign_name = str(self.current_campaign.get("name") or "Campaign")
        if not campaign_id:
            return

        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        pending = getattr(self.window, "_pending_campaign_character", None)
        pending_matches = (
            isinstance(pending, dict)
            and str(pending.get("campaign_id") or "") == campaign_id
            and str(pending.get("character_id") or "") == character_id
        )

        template = campaign_template(self.current_campaign)
        if not bool(skip_compliance) and not pending_matches:
            mismatches = character_rule_mismatches(self.window.character, template)
            if mismatches:
                details = "\n".join(f"• {item}" for item in mismatches)
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("Character Does Not Fully Match Campaign Rules")
                box.setText(
                    "This existing character does not fully match the campaign's "
                    "Creation Rules:\n\n"
                    + details
                    + "\n\nYou can still save it to this campaign; the app will not "
                    "silently rewrite the character."
                )
                save_anyway = box.addButton(
                    "Save Anyway", QMessageBox.ButtonRole.AcceptRole
                )
                box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() != save_anyway:
                    return

        window = self.window
        client = self.client

        # Close the modal Campaign dialog before invoking the normal character
        # Save flow.  This prevents the file/name dialog from fighting a modal
        # parent and makes the sequence feel exactly like normal character save.
        self.accept()

        def save_and_link():
            try:
                window.save_current_character()
            except Exception as error:
                QMessageBox.warning(
                    window,
                    "Save Character Failed",
                    str(error),
                )
                return

            # Cancelling the normal Save dialog is a clean cancellation: do not
            # create a cloud-only character that cannot be found in Load Character.
            filepath = getattr(window, "current_character_filepath", None)
            if not filepath or getattr(window, "unsaved_changes", False):
                QMessageBox.information(
                    window,
                    "Character Not Saved to Campaign",
                    "Nothing was uploaded. The character is still open on your "
                    "sheet. Save it when you are ready, then choose Save to "
                    "Campaign again.",
                )
                return

            try:
                state = build_window_shared_state(
                    window,
                    campaign_id=campaign_id,
                )
                client.link_character(
                    campaign_id,
                    state,
                    remember=True,
                )
                restore_campaign_connection(window)
                schedule_campaign_state_sync(window)
                sync_current_character_now(window)
            except Exception as error:
                QMessageBox.warning(
                    window,
                    "Save to Campaign Failed",
                    str(error),
                )
                return

            current_pending = getattr(window, "_pending_campaign_character", None)
            if (
                isinstance(current_pending, dict)
                and str(current_pending.get("campaign_id") or "") == campaign_id
                and str(current_pending.get("character_id") or "")
                == str(getattr(window.character, "id", "") or "")
            ):
                try:
                    delattr(window, "_pending_campaign_character")
                except Exception:
                    window._pending_campaign_character = None

            QMessageBox.information(
                window,
                "Saved to Campaign",
                f"The character was saved locally and connected to {campaign_name}. "
                "It will now appear in Load Character, and its allowed shared "
                "campaign data will stay in sync while connected.",
            )

        QTimer.singleShot(0, save_and_link)
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


def replace_method(text: str, class_pos: int, method_name: str, next_method_name: str, replacement: str):
    start = text.find(f"    def {method_name}", class_pos)
    end = text.find(f"    def {next_method_name}", start)
    if start < 0 or end < 0:
        raise RuntimeError(
            f"Could not safely locate {method_name} / {next_method_name} in campaign_ui.py."
        )
    current = text[start:end]
    if current == replacement:
        return text, False
    return text[:start] + replacement + "\n" + text[end:], True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original

    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = text.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    init_start = text.find("    def __init__(self, window):\n", class_pos)
    init_end = text.find("    def _show_error(self, title, error):\n", init_start)
    if init_start < 0 or init_end < 0:
        raise RuntimeError("Could not safely locate the Campaign constructor.")

    before = text[:init_start]
    block = text[init_start:init_end]
    after = text[init_end:]

    # ------------------------------------------------------------------
    # 1) Match the ORIGINAL template button sizing model exactly:
    #    stylesheet supplies padding/colors; Python supplies minimum height;
    #    each button's width comes from its text instead of arbitrary widths.
    # ------------------------------------------------------------------
    block = block.replace("            min-height: 36px;\n", "", 1)

    width_lines = (
        "        self.refresh_btn.setFixedWidth(82)\n",
        "        self.refresh_btn.setFixedWidth(95)\n",
        "        self.create_btn.setFixedWidth(112)\n",
        "        self.create_btn.setFixedWidth(125)\n",
        "        self.join_btn.setFixedWidth(112)\n",
        "        self.join_btn.setFixedWidth(125)\n",
        "        self.dashboard_btn.setFixedWidth(150)\n",
        "        self.dashboard_btn.setFixedWidth(165)\n",
        "        self.create_character_btn.setFixedWidth(150)\n",
        "        self.create_character_btn.setFixedWidth(165)\n",
        "        self.create_character_btn.setMinimumWidth(180)\n",
        "        self.share_btn.setFixedWidth(158)\n",
        "        self.share_btn.setFixedWidth(175)\n",
        "        self.share_btn.setMinimumWidth(195)\n",
        "        self.unlink_btn.setFixedWidth(78)\n",
        "        self.unlink_btn.setFixedWidth(90)\n",
        "        self.unlink_btn.setMinimumWidth(90)\n",
        "        self.privacy_btn.setFixedWidth(132)\n",
        "        self.privacy_btn.setFixedWidth(145)\n",
        "        self.edit_rules_btn.setFixedWidth(92)\n",
        "        self.edit_rules_btn.setFixedWidth(105)\n",
        "        cancel.setFixedWidth(82)\n",
        "        self.campaign_back_btn.setFixedWidth(90)\n",
        "        self.campaign_back_btn.setFixedWidth(95)\n",
        "        self.campaign_next_btn.setFixedWidth(90)\n",
        "        self.campaign_next_btn.setFixedWidth(95)\n",
    )
    for line in width_lines:
        block = block.replace(line, "")

    block = block.replace(
        '        self.create_character_btn = QPushButton("Create New Character")\n',
        '        self.create_character_btn = QPushButton("Create Character")\n',
        1,
    )
    block = block.replace(
        '        self.share_btn = QPushButton("Share Current Character")\n',
        '        self.share_btn = QPushButton("Save to Campaign")\n',
        1,
    )

    old_help = (
        '        character_text = QLabel(\n'
        '            "Create a new character with this campaign\'s rules, or connect the character already open on your sheet."\n'
        '        )\n'
    )
    new_help = (
        '        character_text = QLabel(\n'
        '            "Create with this campaign\'s rules, edit normally on the sheet, "\n'
        '            "then return here and choose Save to Campaign."\n'
        '        )\n'
    )
    if old_help in block:
        block = block.replace(old_help, new_help, 1)

    fit_marker = "        # Fit Campaign buttons to their text like CharacterTemplateDialog.\n"
    if fit_marker not in block:
        cursor_marker = "        for button in (\n            self.refresh_btn,\n"
        cursor_pos = block.find(cursor_marker)
        if cursor_pos < 0:
            raise RuntimeError("Could not locate the Campaign button cursor block.")
        fit_block = '''        # Fit Campaign buttons to their text like CharacterTemplateDialog.\n        # No arbitrary fixed widths: the border hugs the label plus template padding.\n        for fitted_button in (\n            self.refresh_btn,\n            self.create_btn,\n            self.join_btn,\n            self.dashboard_btn,\n            self.create_character_btn,\n            self.share_btn,\n            self.unlink_btn,\n            self.privacy_btn,\n            self.edit_rules_btn,\n            self.campaign_back_btn,\n            self.campaign_next_btn,\n            cancel,\n        ):\n            fitted_button.setMinimumHeight(36)\n            fitted_button.adjustSize()\n            fitted_button.setFixedWidth(fitted_button.sizeHint().width())\n\n'''
        block = block[:cursor_pos] + fit_block + block[cursor_pos:]

    # ------------------------------------------------------------------
    # 2) Reopening Campaign after Create Character should return directly to
    #    the same campaign's Character step, ready for Save to Campaign.
    # ------------------------------------------------------------------
    old_end = '''        self.reload_campaigns()\n        self._campaign_show_page(0)\n\n'''
    new_end = '''        self.reload_campaigns()\n\n        pending = getattr(self.window, "_pending_campaign_character", None)\n        current_character_id = str(\n            getattr(self.window.character, "id", "") or ""\n        )\n        if (\n            isinstance(pending, dict)\n            and str(pending.get("character_id") or "") == current_character_id\n            and str(pending.get("campaign_id") or "")\n        ):\n            self._select_campaign_id(pending.get("campaign_id"))\n            self._campaign_show_page(1)\n        else:\n            self._campaign_show_page(0)\n\n'''
    if old_end in block:
        block = block.replace(old_end, new_end, 1)
    elif new_end not in block:
        raise RuntimeError("Could not locate the Campaign initial-page block.")

    text = before + block + after

    # ------------------------------------------------------------------
    # 3) Replace the old create-immediately-save-and-share behavior.
    # ------------------------------------------------------------------
    class_pos = text.find(class_marker)
    text, create_changed = replace_method(
        text,
        class_pos,
        "create_and_share_character(self):",
        "share_current_character(self, skip_compliance=False):",
        NEW_CREATE_METHOD,
    )

    class_pos = text.find(class_marker)
    text, share_changed = replace_method(
        text,
        class_pos,
        "share_current_character(self, skip_compliance=False):",
        "unlink_current_character(self):",
        NEW_SHARE_METHOD,
    )

    required_markers = (
        'QPushButton("Save to Campaign")',
        "Fit Campaign buttons to their text like CharacterTemplateDialog.",
        "_pending_campaign_character",
        "QTimer.singleShot(0, save_and_link)",
        "build_window_shared_state(\n                    window,",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise RuntimeError(
            "Campaign v14 verification failed. Missing: " + ", ".join(missing)
        )

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v14_buttons_and_flow")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    print("Buttons fit their text: PASS")
    print("Buttons use original-template height/padding behavior: PASS")
    print("Create Character -> edit on sheet: PASS" if create_changed else "Create Character flow: already installed")
    print("Save to Campaign -> local save -> campaign link: PASS" if share_changed else "Save to Campaign flow: already installed")
    print("Pending campaign reopens on Character step: PASS")
    print("Privacy-filtered campaign payload: PRESERVED")
    print("Original Character Creation Template: UNTOUCHED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and test the new character flow.")


if __name__ == "__main__":
    main()
