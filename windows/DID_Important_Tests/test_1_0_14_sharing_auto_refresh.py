"""1.0.14 sharing/auto-refresh regression tests for deployed dashboard variants.
Tests the actual behavior contract, not one particular local variable name.
"""
import ast
import importlib.util
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('did114_patch',ROOT/'patch_did114_sharing_refresh.py')
PATCH=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

class SharingRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.role=(ROOT/'campaign_role_ui.py').read_text(encoding='utf-8-sig')
        cls.party=(ROOT/'party_dashboard'/'app.js').read_text(encoding='utf-8-sig')
        cls.dm=(ROOT/'dm_dashboard'/'app.js').read_text(encoding='utf-8-sig')

    def test_patch_idempotence_and_python_syntax(self):
        self.assertEqual(self.role,PATCH.patch_role(self.role))
        ast.parse(self.role)

    def test_visible_checkbox_edges_and_left_padding(self):
        self.assertIn('QCheckBox::indicator:unchecked',self.role)
        self.assertIn('"#ffffff" if dark',self.role)
        self.assertIn('grid.setContentsMargins(24, 12, 18, 12)',self.role)

    def test_selected_tab_has_same_background(self):
        self.assertRegex(self.role,r'QPushButton#CampaignRoleTab:checked\s*\{\s*background:#fffdf7')
        self.assertIn('border:2px solid #b98322',self.role)

    def test_roll_toggle_is_actionable_but_server_flag_is_shared(self):
        self.assertIn('Session dice rolls (shared)',self.role)
        self.assertIn('self.roll_share_box.setEnabled(True)',self.role)
        self.assertIn('self.party_roll_share_box.setEnabled(True)',self.role)
        self.assertIn('self.session_service.set_roll_sharing(',self.role)
        self.assertIn('self._did114_pending_roll_key',self.role)
        self.assertIn('self._did114_pending_roll_share = enabled',self.role)

    def test_removed_characters_have_add_character_screen(self):
        self.assertIn('No character added to this campaign',self.role)
        self.assertIn('self.player_add_character_btn.setVisible(True)',self.role)

    def test_dashboard_quiet_poll_with_safe_existing_guards(self):
        for name,src in [('party',self.party),('dm',self.dm)]:
            with self.subTest(name=name):
                self.assertEqual(src,PATCH.patch_js(src,dashboard=name))
                self.assertIn('async function loadCurrentCampaign(quiet = false)',src)
                self.assertIn('if (!quiet) setConnection("Refreshing…", "neutral")',src)
                self.assertIn('did114RefreshBusy',src)
                self.assertIn('document.hidden',src)
                self.assertIn('loadCurrentCampaign(true)',src)
                self.assertIn('}, 20000);',src)
                self.assertEqual(src.count('let campaignLoadSerial = 0;'),1)
                self.assertEqual(src.count('let subscribedCampaignId = "";'),1)
                self.assertRegex(src,r'\b(?:serial|sequence)\s*!==\s*campaignLoadSerial')
                self.assertIn('realtimeChannel && subscribedCampaignId === currentCampaignId',src)

    def test_missing_serial_guard_is_rejected(self):
        src=self.party.replace('if (serial !== campaignLoadSerial', 'if (serial !== retiredSerial')
        # Existing marker intentionally means already-patched sources are stable.
        # Test a fresh copy (not the patched result) for missing safeguards.
        orig=self.party.replace('  // DID114_SHARING_AUTO_REFRESH_V1:', '  // TEST_REMOVED_MARKER:')
        orig=orig.replace('async function loadCurrentCampaign(quiet = false)', 'async function loadCurrentCampaign()')
        orig=orig.replace('if (!quiet) setConnection("Refreshing…", "neutral");', 'setConnection("Refreshing…", "neutral");')
        orig=orig[:orig.find('  // TEST_REMOVED_MARKER:')] + '  boot();\n})();\n'
        orig=orig.replace('if (serial !== campaignLoadSerial','if (serial !== retiredSerial')
        with self.assertRaises(PATCH.StopPatch):PATCH.patch_js(orig,dashboard='party')

if __name__=='__main__':unittest.main()
