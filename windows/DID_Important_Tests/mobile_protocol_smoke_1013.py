"""Offline 1.0.13 protocol smoke checks without PySide6 runtime.

Run: python DID_Important_Tests/mobile_protocol_smoke_1013.py
This tests real MobileSyncServer pairing/auth/message code against minimal Qt
transport stubs; it is not a replacement for Windows/Android device testing.
"""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class Signal:
    def connect(self, callback):
        pass
    def emit(self, *args):
        pass

class QObject:
    def __init__(self, *args, **kwargs):
        pass

class Timer:
    def __init__(self, *_):
        self.timeout = Signal()
    def setInterval(self, *_):
        pass
    def start(self):
        pass
    def stop(self):
        pass

class Socket:
    def __init__(self):
        self.messages = []
        self.alive = True
    def isValid(self):
        return self.alive
    def state(self):
        return 1 if self.alive else 0
    def close(self):
        self.alive = False
    def sendTextMessage(self, raw):
        self.messages.append(json.loads(raw))
    def ping(self):
        pass

class ServerSocket:
    SslMode = types.SimpleNamespace(NonSecureMode=0)
    def __init__(self, *args):
        self.newConnection = Signal()
        self.listening = False
    def listen(self, *args):
        self.listening = True
        return True
    def isListening(self):
        return self.listening
    def close(self):
        self.listening = False
    def hasPendingConnections(self):
        return False


def import_server():
    mods = {'PySide6': types.ModuleType('PySide6')}
    core = types.ModuleType('PySide6.QtCore')
    core.QObject = QObject
    core.QTimer = Timer
    core.Signal = lambda *a: Signal()
    core.QStandardPaths = types.SimpleNamespace(
        StandardLocation=types.SimpleNamespace(GenericDataLocation=0),
        writableLocation=lambda *_: str(ROOT / '_not_used'),
    )
    net = types.ModuleType('PySide6.QtNetwork')
    net.QAbstractSocket = types.SimpleNamespace(SocketState=types.SimpleNamespace(ConnectedState=1))
    net.QHostAddress = types.SimpleNamespace(AnyIPv4=0)
    ws = types.ModuleType('PySide6.QtWebSockets')
    ws.QWebSocket = Socket
    ws.QWebSocketServer = ServerSocket
    mods.update({'PySide6.QtCore': core, 'PySide6.QtNetwork': net,
                 'PySide6.QtWebSockets': ws})
    with patch.dict(sys.modules, mods):
        spec = importlib.util.spec_from_file_location('_did1013_mockserver', ROOT / 'mobile_sync_server.py')
        module = importlib.util.module_from_spec(spec)
        # dataclasses use sys.modules to resolve type definitions
        with patch.dict(sys.modules, {spec.name: module}):
            spec.loader.exec_module(module)
        return module

SERVER = import_server()


class ProtocolSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.character = {'id': 'aurora', 'AT': {'current': 3}, 'name': 'Aurora'}
        with patch.object(SERVER.MobileSyncServer, '_stable_settings_path',
                          return_value=Path(self.tmp.name) / 'devices.json'):
            self.server = SERVER.MobileSyncServer(
                desktop_version='1.0.13', state_provider=lambda: self.character,
                command_handler=lambda *args: None)
        self.addCleanup(self.server.stop)

    def pair(self, device_id='phone-1'):
        payload = self.server.begin_pairing()
        socket = Socket()
        client = SERVER.ConnectedClient(socket=socket)
        self.server._clients[id(socket)] = client
        self.server._handle_pair(client, {
            'type': 'pair', 'protocol': 1, 'pairing_token': payload['pairing_token'],
            'device_id': device_id, 'device_name': 'Pocket DID', 'android_version': '1.0.13'})
        return payload, socket, client

    def test_legacy_pairing_and_reconnect_messages(self):
        payload, sock, client = self.pair()
        self.assertEqual(payload['type'], 'did_pairing')
        self.assertEqual([m['type'] for m in sock.messages], ['pair_ok', 'state'])
        self.assertEqual(sock.messages[1]['character']['AT']['current'], 3)
        token = sock.messages[0]['device_token']
        self.assertNotEqual(payload['pairing_token'], token)
        self.assertIsNone(self.server._pairing_token)
        new_socket = Socket()
        new_client = SERVER.ConnectedClient(socket=new_socket)
        self.server._clients[id(new_socket)] = new_client
        self.server._handle_hello(new_client, {
            'type': 'hello', 'protocol': 1, 'device_id': 'phone-1',
            'device_token': token, 'device_name': 'Pocket DID'})
        self.assertEqual([m['type'] for m in new_socket.messages], ['hello_ok', 'state'])
        self.assertEqual(self.server.connected_device_ids(), {'phone-1'})
        self.assertFalse(sock.alive, 'new connection should close stale socket')
        self.assertEqual(len(self.server._clients), 1)
        self.character['AT']['current'] = 4
        self.server.notify_desktop_change()
        self.assertEqual(new_socket.messages[-1]['character']['AT']['current'], 4)
        self.server._on_text(new_socket, json.dumps({'type': 'get_state', 'protocol': 1}))
        self.assertEqual(new_socket.messages[-1]['type'], 'state')

    def test_device_rename_survives_hello(self):
        _, sock, _ = self.pair()
        saved_token = sock.messages[0]['device_token']
        self.assertTrue(self.server.rename_device('phone-1', 'Travel Phone'))
        new_socket = Socket()
        new_client = SERVER.ConnectedClient(socket=new_socket)
        self.server._clients[id(new_socket)] = new_client
        self.server._handle_hello(new_client, {'type': 'hello', 'protocol': 1,
             'device_id': 'phone-1', 'device_token': saved_token, 'device_name': 'Original Android Name'})
        self.assertEqual(new_client.device_name, 'Travel Phone')
        self.assertEqual(self.server.paired_devices()[0]['device_name'], 'Travel Phone')

    def test_invalid_token_rejected(self):
        self.pair()
        new_sock = Socket()
        bad = SERVER.ConnectedClient(socket=new_sock)
        self.server._handle_hello(bad, {'type': 'hello', 'protocol': 1,
            'device_id': 'phone-1', 'device_token': 'wrong'})
        self.assertEqual(new_sock.messages[-1]['type'], 'hello_error')
        self.assertFalse(bad.authenticated)


if __name__ == '__main__':
    unittest.main(verbosity=2)
