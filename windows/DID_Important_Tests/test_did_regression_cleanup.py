"""Static compatibility checks for the cleaned 1.0.14 desktop sources."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CleanupTests(unittest.TestCase):
    def test_no_overridden_dice_or_recovery_methods(self):
        for file_name, class_name, method_name in (
            ('frontend_2_8.py', 'BaseMainWindow', '_detect_rendered_die_rect'),
            ('backend_2_1.py', 'CharacterStorageSystem', 'list_recovery_files'),
            ('backend_2_1.py', 'CharacterStorageSystem', 'find_saved_character_filepath'),
        ):
            with self.subTest(method=method_name):
                tree = ast.parse((ROOT / file_name).read_text(encoding='utf8'))
                cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == class_name)
                methods = [fn for fn in cls.body if isinstance(fn, ast.FunctionDef) and fn.name == method_name]
                self.assertEqual(len(methods), 1)

    def test_network_operations_scheduled_from_gui(self):
        tree = ast.parse((ROOT / 'campaign_role_ui.py').read_text(encoding='utf8'))
        hub = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == 'CampaignsHubDialog')
        for name in ('_refresh_selected_player_admission', '_decide_dm_character_request',
                     'delete_dm_campaign', 'remove_dm_character', '_inline_rules_saved'):
            with self.subTest(action=name):
                fn = next(f for f in hub.body if isinstance(f, ast.FunctionDef) and f.name == name)
                self.assertTrue(any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                                    and c.func.attr == '_submit_hub_job' for c in ast.walk(fn)))

    def test_default_build_does_not_reapply_old_patches(self):
        text = (ROOT / 'BUILD_DID_1.0.14.ps1').read_text(encoding='utf8')
        self.assertNotIn("Invoke-DidPython -Arguments @('.\\apply_did_1_0_14.py')", text)
        self.assertIn('campaign_roll_outbox.py', text)

if __name__ == '__main__': unittest.main()
