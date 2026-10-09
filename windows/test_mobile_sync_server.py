from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from windows.mobile_sync_server import ConnectedClient, MobileSyncServer, SYNC_PROTOCOL


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.closed = False

    def sendTextMessage(self, text: str) -> int:
        self.messages.append(json.loads(text))
        return len(text)

    def close(self, *args, **kwargs) -> None:
        self.closed = True


class MobileSyncServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = {
            "id": "char-1",
            "name": "Test Character",
            "HP": {"current": 3, "max": 5},
            "Adversity": {"current": 1},
            "progression": {"ip": 2},
        }
        self.commands: list[tuple[str, dict, int, str]] = []

        def state_provider():
            return self.state

        def command_handler(action: str, payload: dict, base_revision: int, request_id: str):
            self.commands.append((action, payload, base_revision, request_id))
            if action != "resource.change":
                raise ValueError("Unsupported command")
            resource = payload.get("resource")
            delta = int(payload.get("delta", 0))
            if resource == "HP":
                current = int(self.state["HP"]["current"])
                maximum = int(self.state["HP"]["max"])
                self.state["HP"]["current"] = max(0, min(maximum, current + delta))
            elif resource == "Adversity":
                self.state["Adversity"]["current"] = max(
                    0, int(self.state["Adversity"]["current"]) + delta
                )
            else:
                raise ValueError("Unsupported resource")

        settings_path = Path(self.tmp.name) / "mobile_companion.json"
        patcher = patch.object(
            MobileSyncServer,
            "_default_settings_path",
            return_value=settings_path,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.server = MobileSyncServer(
            desktop_version="1.0.10",
            state_provider=state_provider,
            command_handler=command_handler,
        )
        self.addCleanup(self.server.stop)

    def test_state_message_is_canonical_copy(self):
        message = self.server._state_message()
        self.assertEqual(message["type"], "state")
        self.assertEqual(message["protocol"], SYNC_PROTOCOL)
        self.assertEqual(message["revision"], 0)
        self.assertEqual(message["character"]["name"], "Test Character")
        message["character"]["name"] = "Mutated copy"
        self.assertEqual(self.state["name"], "Test Character")

    def test_pairing_issues_permanent_device_token_and_consumes_pairing_token(self):
        sock = FakeSocket()
        client = ConnectedClient(socket=sock)  # type: ignore[arg-type]
        self.server._pairing_token = "one-time-token"
        self.server._pairing_expires_at = time.time() + 60

        self.server._handle_pair(
            client,
            {
                "type": "pair",
                "protocol": SYNC_PROTOCOL,
                "pairing_token": "one-time-token",
                "device_id": "phone-1",
                "device_name": "Test Phone",
                "android_version": "0.8.0",
            },
        )

        self.assertTrue(client.authenticated)
        self.assertIsNone(self.server._pairing_token)
        self.assertEqual(sock.messages[0]["type"], "pair_ok")
        self.assertTrue(sock.messages[0]["device_token"])
        self.assertEqual(sock.messages[1]["type"], "state")
        saved = self.server._settings["devices"]["phone-1"]
        self.assertEqual(saved["token"], sock.messages[0]["device_token"])

    def test_invalid_pairing_token_is_rejected(self):
        sock = FakeSocket()
        client = ConnectedClient(socket=sock)  # type: ignore[arg-type]
        self.server._pairing_token = "correct-token"
        self.server._pairing_expires_at = time.time() + 60

        self.server._handle_pair(
            client,
            {
                "protocol": SYNC_PROTOCOL,
                "pairing_token": "wrong-token",
                "device_id": "phone-1",
            },
        )

        self.assertFalse(client.authenticated)
        self.assertEqual(sock.messages[-1]["type"], "pair_error")

    def test_saved_device_can_authenticate_again(self):
        self.server._settings["devices"]["phone-1"] = {
            "device_name": "Test Phone",
            "token": "permanent-token",
            "created_at": int(time.time()),
            "last_seen": int(time.time()),
        }
        sock = FakeSocket()
        client = ConnectedClient(socket=sock)  # type: ignore[arg-type]

        self.server._handle_hello(
            client,
            {
                "type": "hello",
                "protocol": SYNC_PROTOCOL,
                "device_id": "phone-1",
                "device_name": "Test Phone",
                "device_token": "permanent-token",
                "android_version": "0.8.0",
            },
        )

        self.assertTrue(client.authenticated)
        self.assertEqual(sock.messages[0]["type"], "hello_ok")
        self.assertEqual(sock.messages[1]["type"], "state")

    def test_stale_revision_does_not_mutate_character(self):
        sock = FakeSocket()
        client = ConnectedClient(socket=sock, authenticated=True)  # type: ignore[arg-type]
        self.server._revision = 4

        self.server._handle_command(
            client,
            {
                "request_id": "req-stale",
                "base_revision": 3,
                "action": "resource.change",
                "payload": {"resource": "HP", "delta": -1},
            },
        )

        self.assertEqual(self.state["HP"]["current"], 3)
        self.assertEqual(self.commands, [])
        self.assertEqual(sock.messages[0]["type"], "command_error")
        self.assertEqual(sock.messages[0]["code"], "STALE_REVISION")
        self.assertEqual(sock.messages[1]["type"], "state")

    def test_accepted_command_mutates_then_increments_revision(self):
        sock = FakeSocket()
        client = ConnectedClient(socket=sock, authenticated=True)  # type: ignore[arg-type]
        self.server._clients[id(sock)] = client

        self.server._handle_command(
            client,
            {
                "request_id": "req-1",
                "base_revision": 0,
                "action": "resource.change",
                "payload": {"resource": "HP", "delta": -1},
            },
        )

        self.assertEqual(self.state["HP"]["current"], 2)
        self.assertEqual(self.server.revision, 1)
        self.assertEqual(sock.messages[0]["type"], "command_ok")
        self.assertEqual(sock.messages[0]["revision"], 1)
        self.assertEqual(sock.messages[1]["type"], "state")
        self.assertEqual(sock.messages[1]["character"]["HP"]["current"], 2)

    def test_validation_failure_keeps_revision_and_returns_error(self):
        sock = FakeSocket()
        client = ConnectedClient(socket=sock, authenticated=True)  # type: ignore[arg-type]

        self.server._handle_command(
            client,
            {
                "request_id": "req-bad",
                "base_revision": 0,
                "action": "resource.change",
                "payload": {"resource": "Unknown", "delta": 1},
            },
        )

        self.assertEqual(self.server.revision, 0)
        self.assertEqual(sock.messages[-1]["type"], "command_error")
        self.assertEqual(sock.messages[-1]["code"], "VALIDATION_ERROR")

    def test_revoke_device_removes_credentials(self):
        self.server._settings["devices"]["phone-1"] = {
            "device_name": "Test Phone",
            "token": "permanent-token",
        }
        self.assertTrue(self.server.revoke_device("phone-1"))
        self.assertNotIn("phone-1", self.server._settings["devices"])
        self.assertFalse(self.server.revoke_device("phone-1"))


if __name__ == "__main__":
    unittest.main()
