from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


IMPORT_OLD = "from campaign_ui import CampaignRulesEditorDialog, _replace_current_character\n"
IMPORT_NEW = "from campaign_ui import CampaignManagerDialog, CampaignRulesEditorDialog, _replace_current_character\n"

FIT_OLD = '''def _fit_button(button):
    button.adjustSize()
    button.setFixedWidth(button.sizeHint().width())
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

FIT_NEW = '''def _fit_button(button):
    # Windows/Georgia can report a sizeHint a few pixels narrower than the
    # actually painted bold text.  Size from both the hint and font metrics,
    # then leave the same breathing room as the Character Template buttons.
    button.ensurePolished()
    text_width = button.fontMetrics().horizontalAdvance(button.text())
    width = max(button.sizeHint().width() + 10, text_width + 34)
    button.setMinimumHeight(36)
    button.setFixedWidth(width)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

PREFS_OLD = '''        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        self.setWindowTitle("My Campaigns")
'''

PREFS_NEW = '''        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        # These must exist even when the player has not joined a campaign yet.
        # _refresh_character_page() still builds the inventory/note rows in
        # that state, so delaying initialization until a campaign is selected
        # caused the _dm_prefs AttributeError.
        self._dm_prefs = normalize_privacy_preferences()
        self._party_prefs = normalize_party_preferences()
        self.setWindowTitle("My Campaigns")
'''

LOAD_PREFS_OLD = '''    def _load_sharing_preferences(self):
        if not self.current_campaign:
            return
'''

LOAD_PREFS_NEW = '''    def _load_sharing_preferences(self):
        if not self.current_campaign:
            self._dm_prefs = normalize_privacy_preferences()
            self._party_prefs = normalize_party_preferences()
            return
'''

OPEN_DM_OLD = '''def open_dm_campaign_manager(window):
    dialog = DMCampaignManagerDialog(window)
    dialog.exec()
    return dialog
'''

OPEN_DM_NEW = '''def open_dm_campaign_manager(window):
    # Keep every Campaign-window refinement from Phase 6.  Phase 7 adds the
    # DM-only roster and Party Dashboard on top of that window instead of
    # replacing it with a second, visually different manager.
    dialog = PreservedDMCampaignManagerDialog(window)
    dialog.exec()
    return dialog
'''

PRESERVED_DM_CLASS = r'''

class PreservedDMCampaignManagerDialog(CampaignManagerDialog):
    """DM-only extension of the already-refined Campaign manager.

    The Phase 6 Campaign window went through many layout/style/flow passes.
    Rebuilding it from scratch in Phase 7 regressed those changes.  This class
    deliberately subclasses the installed refined manager and only swaps the
    former player Character page for a DM roster, while adding Party Dashboard
    access.  The existing Campaign and Creation Rules pages remain untouched.
    """

    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle("Campaign Manager")

        # Joining and player character controls now belong in My Campaigns.
        if hasattr(self, "join_btn"):
            self.join_btn.setVisible(False)

        self._replace_character_page_with_dm_roster()
        self._install_party_dashboard_action()
        self.reload_campaigns()
        self._campaign_show_page(0)

    @staticmethod
    def _find_layout_with_widget(layout, target):
        if layout is None:
            return None
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is target:
                return layout
            child = item.layout()
            if child is not None:
                found = PreservedDMCampaignManagerDialog._find_layout_with_widget(
                    child, target
                )
                if found is not None:
                    return found
        return None

    def _install_party_dashboard_action(self):
        if not hasattr(self, "dashboard_btn"):
            return
        layout = self._find_layout_with_widget(self.layout(), self.dashboard_btn)
        if layout is None:
            return
        self.party_dashboard_btn = QPushButton("Open Party Dashboard")
        self.party_dashboard_btn.clicked.connect(self.open_party_dashboard)
        _fit_button(self.party_dashboard_btn)
        # Adding it to the same action row preserves all of the refined button
        # spacing, colors, and sizing already present in Campaign.
        layout.addWidget(self.party_dashboard_btn)

    def _replace_character_page_with_dm_roster(self):
        if not hasattr(self, "campaign_pages") or self.campaign_pages.count() < 3:
            return

        old_page = self.campaign_pages.widget(1)
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 10, 18, 2)
        box.setSpacing(7)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Campaign Characters")
        title.setObjectName("SectionTitle")
        box.addWidget(title)

        text = QLabel(
            "Characters currently connected to this campaign. Removing one "
            "disconnects it from the campaign without deleting the player's "
            "local character file."
        )
        text.setObjectName("SectionText")
        text.setWordWrap(True)
        box.addWidget(text)

        self.dm_roster_scroll = QScrollArea()
        self.dm_roster_scroll.setWidgetResizable(True)
        self.dm_roster_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.dm_roster_body = QWidget()
        self.dm_roster_layout = QVBoxLayout(self.dm_roster_body)
        self.dm_roster_layout.setContentsMargins(0, 4, 0, 4)
        self.dm_roster_layout.setSpacing(8)
        self.dm_roster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dm_roster_scroll.setWidget(self.dm_roster_body)
        box.addWidget(self.dm_roster_scroll, 1)

        self.campaign_pages.removeWidget(old_page)
        self.campaign_pages.insertWidget(1, page)
        old_page.deleteLater()

    def reload_campaigns(self):
        """Campaign Manager lists only campaigns where this user is the DM."""
        if not hasattr(self, "campaign_combo"):
            return

        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaigns = []

        if self.service is None:
            if hasattr(self, "meta_label"):
                error = getattr(
                    self.window,
                    "_campaign_runtime_error",
                    "Campaign cloud is unavailable",
                )
                self.meta_label.setText(str(error))
            self.campaign_combo.blockSignals(False)
            if hasattr(self, "_update_buttons"):
                self._update_buttons()
            return

        try:
            rows = self.service.list_campaigns()
            for campaign in rows:
                if self.service.role_for_campaign(campaign.get("id")) == "dm":
                    campaign["role"] = "dm"
                    self.campaigns.append(campaign)
        except Exception as error:
            if hasattr(self, "meta_label"):
                self.meta_label.setText(f"Could not load campaigns: {error}")
            self.campaign_combo.blockSignals(False)
            if hasattr(self, "_update_buttons"):
                self._update_buttons()
            return

        for campaign in self.campaigns:
            self.campaign_combo.addItem(
                str(campaign.get("name") or "Unnamed Campaign"),
                campaign.get("id"),
            )

        self.campaign_combo.blockSignals(False)
        if self.campaigns:
            self.campaign_combo.setCurrentIndex(0)
            self._campaign_changed(0)
        else:
            self.current_campaign = None
            if hasattr(self, "meta_label"):
                self.meta_label.setText("No campaigns you DM yet.")
            if hasattr(self, "rules_view"):
                self.rules_view.setPlainText("")
            if hasattr(self, "_update_buttons"):
                self._update_buttons()
            self._refresh_dm_roster()

    def _campaign_show_page(self, index):
        # Preserve the final compact Phase 6 wizard organization, but page 2 is
        # now the DM roster instead of the player character-sharing page.
        index = max(0, min(2, int(index)))
        self._campaign_page_index = index
        self.campaign_pages.setCurrentIndex(index)

        names = ("Campaign", "Characters", "Creation Rules")
        self.campaign_step_label.setText(
            f"Step {index + 1} of 3  •  {names[index]}"
        )
        self.campaign_back_btn.setVisible(index > 0)
        self.campaign_next_btn.setVisible(index < 2)

        if index == 1:
            self._refresh_dm_roster()

        # Use the refined adaptive proportions instead of forcing every page to
        # the tallest page's footprint.
        page_heights = (250, 390, 385)
        window_heights = (470, 590, 610)
        try:
            self.campaign_pages.setFixedHeight(page_heights[index])
            self.resize(self.width(), window_heights[index])
        except Exception:
            pass

    def _refresh_dm_roster(self):
        layout = getattr(self, "dm_roster_layout", None)
        if layout is None:
            return

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child is not None:
                while child.count():
                    nested = child.takeAt(0)
                    if nested.widget() is not None:
                        nested.widget().deleteLater()

        if not isinstance(self.current_campaign, dict) or self.client is None:
            label = QLabel("Select a campaign to see its characters.")
            label.setObjectName("Muted")
            layout.addWidget(label)
            return

        try:
            rows = self.client.list_campaign_characters(
                self.current_campaign.get("id")
            )
        except Exception as error:
            label = QLabel(f"Could not load campaign characters: {error}")
            label.setWordWrap(True)
            layout.addWidget(label)
            return

        if not rows:
            label = QLabel("No characters are currently connected to this campaign.")
            label.setObjectName("Muted")
            layout.addWidget(label)
            return

        for row in rows:
            state = _state_from_character_row(row)
            name = str(
                state.get("name")
                or row.get("display_name")
                or "Unnamed Character"
            )
            species = str(state.get("species") or "").strip()
            try:
                level = int(state.get("level") or 1)
            except Exception:
                level = 1

            card = QFrame()
            card.setObjectName("DMRosterCard")
            card.setStyleSheet(
                "QFrame#DMRosterCard { background-color:#fffdf7; "
                "border:1px solid #e0c68f; border-radius:9px; }"
            )
            grid = QGridLayout(card)
            grid.setContentsMargins(13, 9, 13, 9)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(4)

            name_label = QLabel(name)
            name_label.setStyleSheet("font-size:14px; font-weight:900;")
            subtitle_parts = []
            if species:
                subtitle_parts.append(species)
            subtitle_parts.append(f"Level {level}")
            subtitle = QLabel(" • ".join(subtitle_parts))
            subtitle.setObjectName("Muted")

            hp = QLabel(f"HP  {_hp_text(state)}")
            at = QLabel(f"AT  {_at_text(state)}")
            hp.setStyleSheet("font-weight:800;")
            at.setStyleSheet("font-weight:800;")

            remove = QPushButton("Remove from Campaign")
            remove.setObjectName("DangerButton")
            _fit_button(remove)
            remove.clicked.connect(
                lambda _checked=False,
                character_id=row.get("id"),
                display_name=name: self.remove_campaign_character(
                    character_id, display_name
                )
            )

            grid.addWidget(name_label, 0, 0, 1, 3)
            grid.addWidget(subtitle, 1, 0, 1, 3)
            grid.addWidget(hp, 2, 0)
            grid.addWidget(at, 2, 1)
            grid.addWidget(remove, 0, 3, 3, 1)
            grid.setColumnStretch(2, 1)
            layout.addWidget(card)

    def remove_campaign_character(self, campaign_character_id, display_name):
        if self.client is None or not campaign_character_id:
            return
        answer = QMessageBox.question(
            self,
            "Remove Character from Campaign",
            f"Remove {display_name} from this campaign?\n\n"
            "The player's local character file will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.client._request_json(
                "POST",
                "/rest/v1/rpc/did_remove_campaign_character",
                body={"p_campaign_character_id": str(campaign_character_id)},
            )
            if result is False:
                raise CampaignCloudError("The character could not be removed")
        except Exception as error:
            QMessageBox.warning(self, "Remove Character Failed", str(error))
            return
        self._refresh_dm_roster()

    def open_party_dashboard(self):
        if not isinstance(self.current_campaign, dict) or self.client is None:
            return
        try:
            launch_party_dashboard(
                self.client,
                self.current_campaign.get("id"),
                app_dir=Path(__file__).resolve().parent,
            )
        except Exception as error:
            QMessageBox.warning(self, "Open Party Dashboard Failed", str(error))
'''


def replace_once(text, old, new, label):
    if new in text:
        return text, False
    if old not in text:
        raise RuntimeError(f"Could not safely locate {label} in campaign_role_ui.py")
    return text.replace(old, new, 1), True


def repair(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original
    changes = []

    text, changed = replace_once(text, IMPORT_OLD, IMPORT_NEW, "campaign_ui import")
    changes.append(("Refined CampaignManager import", changed))

    text, changed = replace_once(text, FIT_OLD, FIT_NEW, "button fitting helper")
    changes.append(("Button text clipping", changed))

    text, changed = replace_once(text, PREFS_OLD, PREFS_NEW, "player privacy initialization")
    changes.append(("Player privacy initialization", changed))

    text, changed = replace_once(text, LOAD_PREFS_OLD, LOAD_PREFS_NEW, "empty campaign privacy state")
    changes.append(("No-campaign privacy state", changed))

    if "class PreservedDMCampaignManagerDialog" not in text:
        marker = "\ndef open_dm_campaign_manager(window):\n"
        if marker not in text:
            raise RuntimeError("Could not locate open_dm_campaign_manager")
        text = text.replace(marker, PRESERVED_DM_CLASS + marker, 1)
        changes.append(("Phase 6 Campaign UI preserved", True))
    else:
        changes.append(("Phase 6 Campaign UI preserved", False))

    text, changed = replace_once(text, OPEN_DM_OLD, OPEN_DM_NEW, "DM Campaign opener")
    changes.append(("DM Campaign opener", changed))

    required = (
        "CampaignManagerDialog",
        "class PreservedDMCampaignManagerDialog",
        "self._dm_prefs = normalize_privacy_preferences()",
        "text_width = button.fontMetrics().horizontalAdvance(button.text())",
        "Remove from Campaign",
        "Open Party Dashboard",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError("Phase 7 regression repair verification failed: " + ", ".join(missing))

    if text != original:
        backup = path.with_name(path.name + ".before_phase7_regression_repair")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    return changes


def main():
    here = Path(__file__).resolve().parent
    path = here / "campaign_role_ui.py"
    if not path.is_file():
        raise FileNotFoundError("campaign_role_ui.py must be beside this repair script")

    changes = repair(path)
    for label, changed in changes:
        print(f"{label}: {'PASS' if changed else 'already fixed'}")
    print("Campaign Manager previous refinements: PRESERVED")
    print("DM-only character roster: PASS")
    print("Player _dm_prefs crash: FIXED")
    print("Button clipping: FIXED")
    print("Compile: PASS")


if __name__ == "__main__":
    main()
