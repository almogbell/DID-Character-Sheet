"""Problem 6 behavior tests. No PySide6 runtime is needed for these checks."""
import ast
import copy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parent.parent
UI_SOURCE = (ROOT / 'mobile_companion_dialog.py').read_text(encoding='utf-8')
SERVER_SOURCE = (ROOT / 'mobile_sync_server.py').read_text(encoding='utf-8')


def extract_method(source, class_name, method_name, globals_=None):
    tree = ast.parse(source)
    klass = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == class_name)
    method = copy.deepcopy(next(x for x in klass.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == method_name))
    method.decorator_list = []
    env = dict(globals_ or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<source method>', 'exec'), env)
    return env[method_name]


def extract_function(source, name, globals_=None):
    tree = ast.parse(source)
    fn = copy.deepcopy(next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name))
    env = dict(globals_ or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<source function>', 'exec'), env)
    return env[name]


class FakeSocket:
    def __init__(self):
        self.close_calls = 0
    def close(self):
        self.close_calls += 1


class FakeServer:
    def __init__(self):
        self._settings = {'devices': {
            'device-a': {'device_name': 'One', 'token': 'TOKEN_A', 'last_seen': 500},
            'device-b': {'device_name': 'Two', 'token': 'TOKEN_B', 'last_seen': 400},
        }}
        self.socket_a = FakeSocket()
        self.socket_b = FakeSocket()
        self._clients = {
            10: SimpleNamespace(device_id='device-a', device_name='One', socket=self.socket_a),
            11: SimpleNamespace(device_id='device-b', device_name='Two', socket=self.socket_b),
        }
        self.messages = []
        self.save_count = 0
        self.fail_save = False
        self.emit_count = 0
    def _save_settings(self):
        if self.fail_save:
            raise OSError('disk unavailable')
        self.save_count += 1
    def _send(self, ws, message):
        self.messages.append((ws, message))
    def _emit_client_count(self):
        self.emit_count += 1


class Problem06Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from collections import Counter
        cls.rows_fn = staticmethod(extract_function(UI_SOURCE, '_device_rows', {'Counter': Counter}))
        cls.rename = staticmethod(extract_method(SERVER_SOURCE, 'MobileSyncServer', 'rename_device', {'MAX_DEVICE_NAME_CHARS': 120}))
        cls.revoke = staticmethod(extract_method(SERVER_SOURCE, 'MobileSyncServer', 'revoke_device'))
        cls.count_fn = staticmethod(extract_method(UI_SOURCE, 'MobileCompanionDialog', '_show_client_count'))

    def test_unique_id_duplicate_same_name_is_separate(self):
        phones = [{'device_id': 'aaaaaa', 'device_name': 'Pixel'}, {'device_id': 'bbbbbb', 'device_name': 'Pixel'}]
        rows = self.rows_fn(phones, {'aaaaaa'})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['status'], 'Connected')
        self.assertEqual(rows[1]['status'], 'Paired but offline')
        self.assertNotEqual(rows[0]['display_name'], rows[1]['display_name'])
        self.assertEqual({x['name'] for x in rows}, {'Pixel'})

    def test_duplicate_identical_device_id_collapses(self):
        phones = [{'device_id': 'id1', 'device_name': 'Old', 'last_seen': 100},
                  {'device_id': 'id1', 'device_name': 'New', 'last_seen': 200}]
        rows = self.rows_fn(phones, set())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'New')

    def test_empty_identity_not_rendered(self):
        self.assertEqual(self.rows_fn([{'device_name': 'Unknown'}, {}, None], set()), [])

    def test_rename_preserves_token_and_updates_live_clients(self):
        server = FakeServer()
        self.assertTrue(self.rename(server, 'device-a', '   My Phone  '))
        self.assertEqual(server._settings['devices']['device-a']['device_name'], 'My Phone')
        self.assertEqual(server._settings['devices']['device-a']['token'], 'TOKEN_A')
        self.assertEqual(server._clients[10].device_name, 'My Phone')
        self.assertEqual(server.save_count, 1)

    def test_invalid_rename_does_not_modify_saved_data(self):
        server = FakeServer()
        for value in (' ', 'x'*121, 'Hello\nWorld'):
            self.assertFalse(self.rename(server, 'device-a', value))
        self.assertEqual(server._settings['devices']['device-a']['device_name'], 'One')
        self.assertEqual(server.save_count, 0)

    def test_failed_disk_write_rolls_back_rename(self):
        server = FakeServer()
        server.fail_save = True
        self.assertFalse(self.rename(server, 'device-a', 'New'))
        self.assertEqual(server._settings['devices']['device-a']['device_name'], 'One')
        self.assertEqual(server._clients[10].device_name, 'One')

    def test_remove_connected_device_invalidates_session(self):
        server = FakeServer()
        self.assertTrue(self.revoke(server, 'device-a'))
        self.assertNotIn('device-a', server._settings['devices'])
        self.assertEqual(server.socket_a.close_calls, 1)
        self.assertEqual(server.socket_b.close_calls, 0)
        self.assertNotIn(10, server._clients)
        self.assertIn(11, server._clients)
        self.assertEqual(server.messages[0][1]['code'], 'DEVICE_REVOKED')
        self.assertEqual(server.emit_count, 1)

    def test_remove_unknown_device_does_not_disconnect_others(self):
        server = FakeServer()
        self.assertFalse(self.revoke(server, 'nope'))
        self.assertEqual(len(server._clients), 2)

    def test_failed_disk_write_rolls_back_remove(self):
        server = FakeServer()
        server.fail_save = True
        self.assertFalse(self.revoke(server, 'device-a'))
        self.assertIn('device-a', server._settings['devices'])
        self.assertEqual(server.socket_a.close_calls, 0)
        self.assertEqual(server.emit_count, 0)

    def test_swap_identity_same_count_refreshes_device_list(self):
        class Banner:
            def __init__(self): self.texts = []
            def setText(self, text): self.texts.append(text)
        class LiveServer:
            def __init__(self): self.live = {'device-a'}
            def connected_device_ids(self): return self.live
            def paired_devices(self): return [{'device_id': 'device-a', 'device_name': 'One'},
                                              {'device_id': 'device-b', 'device_name': 'Two'}]
            def pending_connection_count(self): return 0
        dialog = SimpleNamespace(server=LiveServer(), _last_device_status=None, connection_banner=Banner(),
                                 _displayed_count=0)
        recorded = []
        dialog._refresh_devices = lambda devices, live: recorded.append((devices, set(live)))
        self.count_fn(dialog, 1)
        dialog.server.live = {'device-b'}
        self.count_fn(dialog, 1)
        self.assertEqual(len(recorded), 2)
        self.assertEqual(recorded[-1][1], {'device-b'})
        self.assertEqual(dialog._displayed_count, 1)
        self.assertEqual(dialog.connection_banner.texts[-1], '● Connected — 1 live phone')

    def test_stale_count_signal_cannot_falsely_claim_connected(self):
        class Banner:
            def __init__(self): self.current = None
            def setText(self, text): self.current = text
        class LiveServer:
            def connected_device_ids(self): return set()
            def paired_devices(self): return [{'device_id': 'device-a', 'device_name': 'One'}]
            def pending_connection_count(self): return 0
        dialog = SimpleNamespace(server=LiveServer(), _last_device_status=None,
                                 connection_banner=Banner(), _refresh_devices=lambda *_: None)
        self.count_fn(dialog, 1)
        self.assertIn('Paired but offline', dialog.connection_banner.current)

    def test_management_prompts_themed_with_safe_button_order(self):
        self.assertIn("dialog.setObjectName('PhoneManagementDialog')", UI_SOURCE)
        self.assertIn('QDialog#PhoneManagementDialog', UI_SOURCE)
        self.assertIn("cancel = QPushButton('Cancel')", UI_SOURCE)
        self.assertIn('actions.addStretch(1)', UI_SOURCE)
        self.assertIn("remove.setObjectName('RemovePhone')", UI_SOURCE)
        self.assertIn('cancel.setDefault(True)', UI_SOURCE)
        self.assertNotIn('QInputDialog.getText', UI_SOURCE)
        self.assertNotIn('confirm = QMessageBox(self)', UI_SOURCE)

    def test_existing_pairing_and_scroll_untouched(self):
        for text in ('self.server.begin_pairing(host_override=self.address_selector.currentData())', 'self.server.cancel_pairing',
                     'self.content_scroll = QScrollArea(self)',
                     'make_pairing_landing_url(payload, landing)'):
            self.assertIn(text, UI_SOURCE)
        for text in ('def _handle_hello(', 'def _handle_pair(', 'def _handle_command(', 'def _reply_to_discovery('):
            self.assertIn(text, SERVER_SOURCE)


if __name__ == '__main__':
    unittest.main()
