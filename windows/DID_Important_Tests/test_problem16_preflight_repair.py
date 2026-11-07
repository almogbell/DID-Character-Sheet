"""Non-UI tests for the release validator and safe dashboard packaging."""
from pathlib import Path
from unittest.mock import patch
import importlib.util
import socket
import sys
import tempfile
import urllib.request
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dashboard_runtime as runtime


class Problem16RepairTests(unittest.TestCase):
    def test_source_mode_dashboard_assets_remain_local(self):
        with patch.object(sys, "frozen", False, create=True):
            for kind in ('dm', 'party'):
                path = runtime.prepare_dashboard_dir(kind, ROOT)
                self.assertTrue((path / 'index.html').is_file())
                self.assertEqual(path, ROOT / f'{kind}_dashboard')

    def test_frozen_mode_assets_are_copied_to_writable_directory(self):
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', str(ROOT), create=True), \
             patch.object(sys, 'executable', str(ROOT / 'DID Character Sheet.exe')):
            self.assertEqual(runtime.config_root(ROOT), ROOT)
            for kind in ('dm', 'party'):
                path = runtime.prepare_dashboard_dir(kind, ROOT)
                self.assertTrue((path / 'index.html').is_file())
                self.assertNotEqual(path, ROOT / f'{kind}_dashboard')
                (path/'config.js').write_text('window.SOURCE_TEST = true;', encoding='utf8')
                self.assertTrue((path/'config.js').is_file())

    def test_frozen_mode_can_serve_dashboard_content_on_loopback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'index.html').write_text('DID DASHBOARD TEST', encoding='utf8')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0))
                port = sock.getsockname()[1]
            with patch.object(runtime.webbrowser, 'open'):
                url = f'http://127.0.0.1:{port}/'
                runtime.start_frozen_dashboard(root, port, url)
                response = urllib.request.urlopen(url, timeout=3)
                self.assertIn(b'DID DASHBOARD TEST', response.read())
                self.assertEqual(response.headers['Cache-Control'],
                                 'no-store, no-cache, must-revalidate, max-age=0')
                server = runtime._SERVERS.pop()
                server.shutdown()
                server.server_close()

    def test_source_command_does_not_execute_app_binary(self):
        with patch.object(sys, 'frozen', False, create=True):
            cmd = runtime.server_command('party', 18766, 'http://127.0.0.1:18766/',
                                         ROOT/'party_dashboard', ROOT)
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith('dashboard_server.py'))
        self.assertIn('party', cmd)

    def test_windows_release_metadata_preserves_stable_identity(self):
        installer = (ROOT/'DID_Character_Sheet_Installer_with_icon.iss').read_text(encoding='utf8')
        self.assertIn('#define MyAppVersion "1.0.14"', installer)
        self.assertIn('0DCE3792-7789-4AE5-B5A7-18AB2A512928', installer)
        spec = (ROOT/'DID_Character_Sheet.spec').read_text(encoding='utf8')
        self.assertIn("('dm_dashboard', 'dm_dashboard')", spec)
        self.assertIn("('party_dashboard', 'party_dashboard')", spec)
        self.assertIn('dashboard_runtime', spec)

    def test_both_bridges_use_frozen_in_process_server(self):
        for name in ('campaign_dashboard_bridge.py', 'campaign_party_bridge.py'):
            code = (ROOT/name).read_text(encoding='utf8')
            self.assertIn('start_frozen_dashboard', code)
            self.assertIn('getattr(sys, "frozen", False)', code)


if __name__=='__main__':
    unittest.main()
