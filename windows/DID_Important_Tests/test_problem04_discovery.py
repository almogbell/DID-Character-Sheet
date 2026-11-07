"""Offline regression tests for paired-PC UDP discovery and UI rollback.
Run from the project root with:
    python -m unittest discover -s DID_Important_Tests -p test_problem04_discovery.py -v
No PySide6 or physical phone is required.
"""
import base64
import hashlib
import hmac
import importlib.util
import ipaddress
from pathlib import Path
import sys
import types
import unittest

BASE = Path(__file__).resolve().parents[1]


def source_path(filename):
    """Find the module in the real flat Windows source tree.

    Also accept the older packaging convention with a nested ``windows``
    directory so the offline tests work with both distribution layouts.
    """
    candidates = (BASE / filename, BASE / "windows" / filename)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Cannot locate {filename}; looked in: {searched}")


def load_server():
    qt = types.ModuleType("PySide6")
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.QStandardPaths = type("QStandardPaths", (), {})
    qtcore.QTimer = type("QTimer", (), {})
    qtcore.Signal = lambda *a: None
    qtn = types.ModuleType("PySide6.QtNetwork")
    qtn.QAbstractSocket = type("QAbstractSocket", (), {})

    class Address:
        AnyIPv4 = object()
        def __init__(self, address):
            self.value = str(address)
        def isInSubnet(self, net, prefix):
            return ipaddress.ip_address(self.value) in ipaddress.ip_network(f"{net.value}/{prefix}", strict=False)
    qtn.QHostAddress = Address
    qtw = types.ModuleType("PySide6.QtWebSockets")
    qtw.QWebSocket = type("QWebSocket", (), {})
    qtw.QWebSocketServer = type("QWebSocketServer", (), {})
    names = {"PySide6": qt, "PySide6.QtCore": qtcore, "PySide6.QtNetwork": qtn,
             "PySide6.QtWebSockets": qtw}
    saved = {k: sys.modules.get(k) for k in names}
    sys.modules.update(names)
    try:
        spec = importlib.util.spec_from_file_location("mobile_sync_server_p4_test", source_path("mobile_sync_server.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module, Address
    finally:
        for k, v in saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v


class Incoming:
    def __init__(self, data, sender):
        self._data = data
        self._sender = sender
    def data(self): return self._data
    def senderAddress(self): return self._sender
    def senderPort(self): return 56789


class Udp:
    def __init__(self, incoming):
        self.queue = list(incoming)
        self.out = []
    def hasPendingDatagrams(self): return bool(self.queue)
    def receiveDatagram(self): return self.queue.pop(0)
    def writeDatagram(self, packet, address, port): self.out.append((packet, address, port))


class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod, cls.Address = load_server()

    def make_server(self, payloads):
        obj = object.__new__(self.mod.MobileSyncServer)
        obj._server_id = "8e41ef0d-96f7-4541-9e65-0b701ad6f3c1"
        obj.port = 8765
        obj._settings = {"devices": {"phone-a": {"token": "my-real-permanent-token"}}}
        obj._discovery_socket = Udp(payloads)
        obj.is_listening = lambda: True
        return obj

    def request(self, server, **overrides):
        import json
        value = {"type": "did_discover_v1", "server_id": server._server_id,
                 "device_id": "phone-a", "nonce": "0123456789abcdef0123456789abcdef"}
        value.update(overrides)
        return json.dumps(value).encode()

    def test_known_pair_receives_verified_proof(self):
        import json
        s = self.make_server([])
        s._discovery_socket.queue.append(Incoming(self.request(s), self.Address("192.168.1.30")))
        s._reply_to_discovery()
        self.assertEqual(len(s._discovery_socket.out), 1)
        payload = json.loads(s._discovery_socket.out[0][0])
        self.assertEqual(payload["type"], "did_discover_ok_v1")
        self.assertNotIn("my-real-permanent-token", str(payload))
        value = f"DID_DISCOVER_V1|{s._server_id}|{payload['nonce']}|8765".encode()
        correct = base64.urlsafe_b64encode(hmac.new(b"my-real-permanent-token", value, hashlib.sha256).digest()).decode().rstrip("=")
        self.assertEqual(payload["proof"], correct)

    def test_wrong_identity_never_receives_endpoint(self):
        s=self.make_server([])
        s._discovery_socket.queue.append(Incoming(self.request(s, device_id="unknown"), self.Address("192.168.1.33")))
        s._reply_to_discovery()
        self.assertEqual(s._discovery_socket.out, [])

    def test_wrong_server_never_receives_endpoint(self):
        s=self.make_server([])
        s._discovery_socket.queue.append(Incoming(self.request(s, server_id="other"), self.Address("192.168.1.33")))
        s._reply_to_discovery()
        self.assertEqual(s._discovery_socket.out, [])

    def test_public_network_ignored(self):
        s=self.make_server([])
        s._discovery_socket.queue.append(Incoming(self.request(s), self.Address("8.8.8.8")))
        s._reply_to_discovery()
        self.assertEqual(s._discovery_socket.out, [])

    def test_malformed_request_ignored(self):
        s=self.make_server([])
        s._discovery_socket.queue.append(Incoming(b"invalid!", self.Address("192.168.1.33")))
        s._reply_to_discovery()
        self.assertEqual(s._discovery_socket.out, [])

    def test_windows_pairing_address_selection_preserves_legacy_protocol(self):
        # Byte-for-byte hashes cannot be used when intentionally fixing the UI.
        ui = source_path("mobile_companion_dialog.py").read_text(encoding="utf8")
        self.assertIn('self.server.begin_pairing(host_override=self.address_selector.currentData())', ui)
        self.assertIn('self.server.cancel_pairing()', ui)
        self.assertIn('make_pairing_landing_url(payload, landing)', ui)
        self.assertIn('self.content_scroll = QScrollArea(self)', ui)

if __name__ == '__main__': unittest.main()
