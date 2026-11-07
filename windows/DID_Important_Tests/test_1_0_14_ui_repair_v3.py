"""Structure-only tests; does not require PySide6 or a live Supabase account."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'apply_did_1_0_14_ui_polish.py'
SPEC=importlib.util.spec_from_file_location('did114_ui_v3', P)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class CampaignUIFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'campaign_role_ui.py').read_text(encoding='utf-8-sig')
        cls.hub=cls.source.split('class CampaignsHubDialog(QDialog):',1)[1]

    def test_integration_is_safe_to_rerun(self):
        self.assertEqual(self.source,MOD.patch_role(self.source))

    def test_hooks_are_not_added_to_overview_layout(self):
        # Hooks still load in the background for compatibility; they must not
        # be rendered twice in the overview next to Campaign Info.
        self.assertIn('self.player_shared_hooks = QLabel(',self.hub)
        self.assertNotIn('        reveals_layout.addWidget(self.player_shared_hooks)',self.hub)
        self.assertNotIn('reveals_title = QLabel("Shared by the DM")',self.hub)
        self.assertIn('self.player_campaign_info_btn',self.hub)

    def test_character_specific_effects_remain_visible(self):
        self.assertIn('        reveals_layout.addWidget(self.player_shared_effects)',self.hub)
        self.assertIn('reveals_title = QLabel("Effects on My Character")',self.hub)

    def test_campaign_tab_sizing(self):
        self.assertNotIn('tabs_host.setFixedWidth(280)',self.hub)
        self.assertIn('def _resize_campaign_tabs(self):',self.hub)

    def test_character_file_not_deleted(self):
        self.assertNotIn('unlink(',self.hub)

if __name__=='__main__': unittest.main()
