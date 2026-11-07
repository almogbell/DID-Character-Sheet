"""Regression checks for the seven campaign UI changes in DID 1.0.14.
These are source/logic checks; the final Windows UI still requires device testing.
"""
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('player_polish_7', ROOT / 'patch_did114_player_polish.py')
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
SRC = (ROOT / 'campaign_role_ui.py').read_text(encoding='utf-8-sig')


class PlayerPolishSevenTests(unittest.TestCase):
    def test_syntax_and_repeat_application(self):
        ast.parse(SRC)
        self.assertEqual(SRC, PATCH.patch_source(SRC))
        self.assertEqual(SRC.count(PATCH.MARK), 1)

    def test_checked_and_unchecked_have_identical_outer_dimensions(self):
        self.assertIn('QCheckBox::indicator { width:20px; height:20px; }', SRC)
        self.assertIn('indicator:unchecked {{ width:16px; height:16px; border:2px', SRC)
        self.assertEqual(20, 16 + 2 * 2)
        self.assertIn('"#ffffff" if dark', SRC)

    def test_character_sharing_is_not_permanently_highlighted(self):
        self.assertIn('self.player_character_sharing_btn = QPushButton("Character & Sharing")', SRC)
        self.assertNotIn('self.player_character_sharing_btn.setObjectName("HubPrimary")', SRC)
        self.assertIn('self.player_campaign_info_btn = QPushButton("Campaign Info")', SRC)

    def test_info_and_character_render_inside_overview(self):
        self.assertIn('player_content_layout.addWidget(self.player_inline_section)', SRC)
        self.assertIn('self.player_inline_stack.addWidget(character_host)', SRC)
        self.assertIn('self.player_info_stack_index = self.player_inline_stack.addWidget(info_host)', SRC)
        self.assertIn('self.player_inline_section.setVisible(True)', SRC)
        self.assertIn('self.player_inline_section.setVisible(False)', SRC)
        self.assertNotIn('self.player_detail_stack.setCurrentIndex(1)', SRC)
        self.assertNotIn('self.player_detail_stack.setCurrentIndex(index)', SRC)
        self.assertIn('self.player_inline_stack.setFixedHeight(475)', SRC)

    def test_no_campaign_hides_delete(self):
        self.assertIn('self.delete_campaign_btn.setEnabled(bool(campaign))', SRC)
        self.assertIn('self.delete_campaign_btn.setVisible(bool(campaign))', SRC)
        self.assertIn('self.delete_campaign_btn.setVisible(False)  # Hidden until a DM campaign is selected.', SRC)

    def test_help_and_refresh_same_size(self):
        self.assertIn('for button in (self.help_btn, self.refresh_btn):', SRC)
        self.assertIn('button.setFixedSize(help_width, 38)', SRC)
        self.assertIn('self.refresh_btn.setEnabled(False)', SRC)
        self.assertIn('self.refresh_btn.setEnabled(True)', SRC)

    def test_click_opens_the_correct_saved_campaign_character(self):
        self.assertIn('class _CampaignCharacterOpenLabel(QLabel):', SRC)
        self.assertIn('def mouseReleaseEvent(self, event):', SRC)
        self.assertIn('def _open_linked_player_character(self):', SRC)
        self.assertIn('target_id, record = self._campaign_character_record()', SRC)
        self.assertIn('self.window.load_character_from_path(filepath)', SRC)
        self.assertIn('self.window.activateWindow()', SRC)
        self.assertIn('def _find_saved_character_file(self, character_id):', SRC)

    def test_subsequent_campaign_selection_clears_inline_details(self):
        start = SRC.index('    def _player_selection_changed(self, row):')
        end = SRC.index('    def _refresh_dm_details(self):', start)
        self.assertIn('self.player_inline_section.setVisible(False)', SRC[start:end])

    def test_legacy_tests_remain_present(self):
        names = {p.name for p in (ROOT / 'DID_Important_Tests').glob('test_1_0_14*.py')}
        self.assertIn('test_1_0_14_sharing_auto_refresh.py', names)
        self.assertIn('test_1_0_14_ui_followup.py', names)


if __name__ == '__main__':
    unittest.main()
