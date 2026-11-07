"""Local code-only follow-up regression tests; no PySide6/Windows dependency."""
import importlib.util
from pathlib import Path
import unittest

THIS = Path(__file__).resolve()
ROOT = THIS.parents[1]
SPEC = importlib.util.spec_from_file_location('did114_ui_polish', ROOT/'apply_did_1_0_14_ui_polish.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class FollowupTests(unittest.TestCase):
    def test_idempotency_on_installed_source(self):
        source = (ROOT/'campaign_role_ui.py').read_text('utf8')
        self.assertEqual(MOD.patch_role(source),source)

    def test_button_text_sizing(self):
        s=(ROOT/'campaign_role_ui.py').read_text('utf8')
        self.assertIn('def _resize_campaign_tabs(self)',s)
        self.assertIn('button.fontMetrics().horizontalAdvance(button.text()) + 30',s)
        self.assertNotIn('tabs_host.setFixedWidth(280)',s)

    def test_unlinked_character_has_add_action(self):
        s=(ROOT/'campaign_role_ui.py').read_text('utf8')
        self.assertIn('No character added to this campaign',s)
        self.assertIn('self.player_add_character_btn.setVisible(True)',s)
        self.assertIn('self._show_player_character_page',s)

    def test_rules_summary_hidden_but_owned(self):
        s=(ROOT/'campaign_role_ui.py').read_text('utf8')
        self.assertIn('player_content_layout.addWidget(rules_section)\n        rules_section.setVisible(False)',s)

    def test_scrollbar_matches_sheet(self):
        s=(ROOT/'campaign_role_ui.py').read_text('utf8')
        self.assertIn('DID114_CAMPAIGN_SCROLLBAR',s)
        self.assertIn('background: #d9bd82; border-radius: 4px',s)

    def test_version_remains_1_0_14(self):
        s=(ROOT/'DID_Character_Sheet_Installer_with_icon.iss').read_text('utf8')
        self.assertIn('#define MyAppVersion "1.0.14"',s)

if __name__=='__main__':unittest.main()
