import ast
import tempfile
import subprocess
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'campaign_role_ui.py'

class PatchAndJoinTests(unittest.TestCase):
    def test_compact_join_dialog_no_native_layout(self):
        s=(ROOT/'campaign_join_ui.py').read_text('utf8')
        ast.parse(s)
        self.assertIn('QDialog(parent)',s)
        self.assertIn('details.setWordWrap(True)',s)
        self.assertIn('setFixedWidth(500)',s)
        self.assertIn('set_themed_stylesheet',s)
        self.assertIn('if not _ask_create(parent)',s)
        self.assertIn('on_created()',s)
        self.assertNotIn('message = QMessageBox(parent)',s)
    def test_patch_is_idempotent_and_does_not_replace_source(self):
        if not SOURCE.is_file():
            self.skipTest('Previous Problem 17 source snapshot not present in test environment')
        with tempfile.TemporaryDirectory() as td:
            here=Path(td)
            shutil.copy2(SOURCE,here/'campaign_role_ui.py')
            before=(here/'campaign_role_ui.py').read_text('utf8')
            cmd=['python',str(ROOT/'patch_campaign_player_link.py')]
            first=subprocess.run(cmd,cwd=here,text=True,capture_output=True)
            self.assertEqual(first.returncode,0,first.stderr)
            after=(here/'campaign_role_ui.py').read_text('utf8')
            self.assertIn('DID_PLAYER_LINK_CHECK_V1',after)
            self.assertIn('_finish_player_link_check',after)
            self.assertIn('self._schedule_player_link_check',after)
            self.assertIn('def _refresh_dm_characters',after)
            self.assertLessEqual(len(list(here.glob('campaign_role_ui.py.backup*'))),1)
            if 'DID_PLAYER_LINK_CHECK_V1' not in before:
                self.assertNotEqual(after,before)
            second=subprocess.run(cmd,cwd=here,text=True,capture_output=True)
            self.assertEqual(second.returncode,0,second.stderr)
            self.assertEqual((here/'campaign_role_ui.py').read_text('utf8'),after)
            self.assertLessEqual(len(list(here.glob('campaign_role_ui.py.backup*'))),1)
    def test_script_refuses_unexpected_source(self):
        with tempfile.TemporaryDirectory() as td:
            here=Path(td)
            (here/'campaign_role_ui.py').write_text('print("another version")',encoding='utf8')
            cmd=['python',str(ROOT/'patch_campaign_player_link.py')]
            out=subprocess.run(cmd,cwd=here,text=True,capture_output=True)
            self.assertNotEqual(out.returncode,0)
            self.assertEqual((here/'campaign_role_ui.py').read_text('utf8'),'print("another version")')

if __name__=='__main__':unittest.main()
