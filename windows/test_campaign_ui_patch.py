"""Checks patching the historical Campaigns Hub source safely.

The real Qt rendering and current Windows source still require testing locally.
"""
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
from shutil import copy2
import ast
import unittest
from fix_campaign_player_pages import patch

SAMPLE = Path(__file__).with_name('campaign_role_ui.py').read_text(encoding='utf-8')

class CampaignUiPatchTests(unittest.TestCase):
    def test_patched_python_compiles(self):
        ast.parse(patch(SAMPLE))
    def test_button_widths_are_equalized(self):
        src = patch(SAMPLE)
        self.assertIn('help_button.setFixedSize(width, height)',src)
        self.assertIn('refresh.setFixedSize(width, height)',src)
    def test_character_page_reparented_and_revealed(self):
        src = patch(SAMPLE)
        self.assertIn('character_page.setParent(character_host)',src)
        self.assertIn('_did_1013_reveal_embedded_page(self, "_did_1013_character_content")',src)
    def test_info_page_reparented_and_revealed(self):
        src = patch(SAMPLE)
        self.assertIn('info_page.setParent(info_host)',src)
        self.assertIn('_did_1013_reveal_embedded_page(self, "_did_1013_info_content")',src)
    def test_no_double_patch(self):
        first=patch(SAMPLE)
        self.assertEqual(patch(first),first)
    def test_guarded_unknown_layout(self):
        with self.assertRaises(ValueError):patch('class CampaignsHubDialog: pass')
    def test_preserves_backend_logic(self):
        src = patch(SAMPLE)
        self.assertEqual(src.count('update_campaign_template('),SAMPLE.count('update_campaign_template('))
        self.assertEqual(src.count('link_character('),SAMPLE.count('link_character('))

if __name__=='__main__':unittest.main()
