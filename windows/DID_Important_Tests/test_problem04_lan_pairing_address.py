"""Problem 4 follow-up: LAN QR address selection without requiring real PySide6.

Run: python DID_Important_Tests/test_problem04_lan_pairing_address.py
These are offline contract tests. They do not test a real phone or firewall.
"""
from __future__ import annotations

import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mobile_protocol_smoke_1013 as smoke
SERVER = smoke.SERVER


class Addr:
    def __init__(self, ip): self.ip_value = ip
    def ip(self): return self
    def toString(self): return self.ip_value


class Interface:
    def __init__(self, name, ips, up=True):
        self.display = name
        self.ips = ips
        self.up = up
    def flags(self): return 1 if self.up else 0
    def humanReadableName(self): return self.display
    def name(self): return self.display
    def addressEntries(self): return [Addr(ip) for ip in self.ips]


class QNetworkInterface:
    InterfaceFlag = types.SimpleNamespace(IsUp=1)
    all_interfaces = []
    @classmethod
    def allInterfaces(cls): return cls.all_interfaces


class NetworkSelectionTests(smoke.ProtocolSmokeTests):
    # Inherit the original 3 protocol tests, so this suite also runs those.
    def setUp(self):
        super().setUp()
        QNetworkInterface.all_interfaces = [
            Interface('VPN Tunnel', ['172.27.18.83']),
            Interface('Loopback', ['127.0.0.1']),
            Interface('Wi-Fi', ['192.168.1.42']),
            Interface('Disconnected Ethernet', ['192.168.2.3'], up=False),
            Interface('Ethernet', ['10.0.0.15']),
        ]
        net = types.ModuleType('PySide6.QtNetwork')
        net.QNetworkInterface = QNetworkInterface
        self.network_patch = patch.dict(sys.modules, {'PySide6.QtNetwork': net})
        self.network_patch.start()
        self.addCleanup(self.network_patch.stop)

    def test_wifi_is_preferred_over_vpn_without_excluding_legitimate_private_ranges(self):
        addresses = self.server.pairing_lan_addresses()
        self.assertEqual([ip for _name, ip in addresses],
                         ['192.168.1.42', '10.0.0.15', '172.27.18.83'])

    def test_selected_lan_address_is_advertised_without_changing_saved_phones(self):
        before_devices = dict(self.server._settings['devices'])
        qr = self.server.begin_pairing(host_override='192.168.1.42')
        self.assertEqual(qr['host'], '192.168.1.42')
        self.assertEqual(qr['port'], self.server.port)
        self.assertGreater(len(qr['pairing_token']), 20)
        self.assertEqual(before_devices, self.server._settings['devices'])

    def test_stale_or_unlisted_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Selected phone pairing address'):
            self.server.begin_pairing(host_override='192.168.100.99')
        self.assertIsNone(self.server._pairing_token)

    def test_existing_default_pairing_signature_is_unchanged(self):
        with patch.object(self.server, '_best_lan_ip', return_value='192.168.1.42'):
            qr = self.server.begin_pairing()
        self.assertEqual(qr['type'], 'did_pairing')
        self.assertEqual(qr['host'], '192.168.1.42')
        self.assertEqual(qr['protocol'], 1)

    def test_companion_dialog_uses_selected_address(self):
        path = ROOT / 'mobile_companion_dialog.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == 'MobileCompanionDialog')
        f = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                 and x.name == '_start_pairing')
        calls = [x for x in ast.walk(f) if isinstance(x, ast.Call)]
        pair = next(x for x in calls if isinstance(x.func, ast.Attribute)
                    and x.func.attr == 'begin_pairing')
        self.assertIn('host_override', {x.arg for x in pair.keywords})


if __name__ == '__main__':
    unittest.main(verbosity=2)
