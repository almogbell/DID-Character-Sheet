"""Problem 4: regression tests for actual controller badge methods without Qt.

Run: python DID_Important_Tests/test_problem04_phone_indicator.py
These test the methods extracted from current source, but do not replace a
Windows + Android device test or assert that actual Qt painting succeeded.
"""
from __future__ import annotations

import ast
import types
import unittest
from pathlib import Path

SOURCE_PATH = Path(__file__).resolve().parents[1] / 'mobile_companion_controller.py'


def load_methods():
    tree = ast.parse(SOURCE_PATH.read_text(encoding='utf-8-sig'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'MobileCompanionController')
    functions = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'_refresh_phone_status', '_update_phone_status'}]
    assert len(functions) == 2
    isolated = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {}
    exec(compile(isolated, str(SOURCE_PATH), 'exec'), namespace)
    return namespace


METHODS = load_methods()


class Label:
    def __init__(self):
        self.text_value = ''
        self.tooltip = ''
        self.hidden = True
        self.changes = 0

    def text(self):
        return self.text_value

    def toolTip(self):
        return self.tooltip

    def isHidden(self):
        return self.hidden

    def setText(self, value):
        self.text_value = value
        self.changes += 1

    def setToolTip(self, value):
        self.tooltip = value

    def setVisible(self, yes):
        self.hidden = not yes


class Server:
    def __init__(self):
        self.connected = set()
        self.paired = {'old-phone', 'new-phone'}

    def connected_device_ids(self):
        return set(self.connected)


class Controller:
    _refresh_phone_status = METHODS['_refresh_phone_status']
    _update_phone_status = METHODS['_update_phone_status']

    def __init__(self):
        self.server = Server()
        self.window = types.SimpleNamespace(phone_connection_label=Label())
        self._shutdown = False
        self._last_phone_count = None
        self._last_phone_devices = frozenset()
        self._last_phone_label = None


class PhoneIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.c = Controller()

    def test_only_authenticated_live_device_ids_count(self):
        # Stored pairing records do not constitute a live phone session.
        self.c._refresh_phone_status()
        self.assertEqual(self.c._last_phone_count, 0)
        self.assertEqual(self.c.window.phone_connection_label.text(), '')
        self.assertFalse(self.c.window.phone_connection_label.isHidden())
        self.assertIn('paired phones may be offline',
                      self.c.window.phone_connection_label.toolTip())
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status(1)
        self.assertIn('Phone connected', self.c.window.phone_connection_label.text())
        self.assertEqual(self.c._last_phone_count, 1)

    def test_disconnect_and_reconnect_restore_badge(self):
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status()
        self.c.server.connected.clear()
        self.c._refresh_phone_status(1)  # stale signal arg is ignored
        self.assertEqual(self.c.window.phone_connection_label.text(), '')
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status()
        self.assertIn('Phone connected', self.c.window.phone_connection_label.text())

    def test_rebuilt_header_badge_is_rebound_at_same_count(self):
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status()
        self.c.window.phone_connection_label = Label()
        self.c._refresh_phone_status()
        self.assertEqual(self.c._last_phone_count, 1)
        self.assertIn('Phone connected', self.c.window.phone_connection_label.text())
        self.assertFalse(self.c.window.phone_connection_label.isHidden())

    def test_replaced_device_at_same_count_rebinds(self):
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status()
        self.c.server.connected = {'new-phone'}
        self.c._refresh_phone_status()
        self.assertEqual(self.c._last_phone_devices, frozenset({'new-phone'}))

    def test_duplicate_connection_identity_is_counted_once(self):
        self.c.server.connected = {'old-phone', 'new-phone'}
        self.c._refresh_phone_status()
        self.assertEqual(self.c._last_phone_count, 2)
        self.assertIn('2 phones', self.c.window.phone_connection_label.text())

    def test_no_extra_widget_writes_when_state_unchanged(self):
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status()
        before = self.c.window.phone_connection_label.changes
        self.c._refresh_phone_status()
        self.assertEqual(self.c.window.phone_connection_label.changes, before)
        # But recover if the label is externally overwritten.
        self.c.window.phone_connection_label.setText('')
        self.c._refresh_phone_status()
        self.assertIn('Phone connected', self.c.window.phone_connection_label.text())

    def test_stale_direct_count_argument_cannot_invent_live_phone(self):
        self.c._update_phone_status(17)
        self.assertEqual(self.c._last_phone_count, 0)
        self.assertEqual(self.c.window.phone_connection_label.text(), '')

    def test_no_update_during_shutdown(self):
        self.c._shutdown = True
        self.c.server.connected = {'old-phone'}
        self.c._refresh_phone_status()
        self.assertEqual(self.c.window.phone_connection_label.text(), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
