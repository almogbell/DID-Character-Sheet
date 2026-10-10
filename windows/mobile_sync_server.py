"""DID Character Sheet mobile companion sync server.

Phase 8 foundation. The desktop application is authoritative: Android sends
commands, Windows validates/mutates/saves via callbacks, and this server then
broadcasts a canonical state snapshot.

This module intentionally does not know the DID character rules. It is wired to
those rules by the desktop frontend through ``state_provider`` and
``command_handler`` callbacks.
"""

from __future__ import annotations

import json
import secrets
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, QStandardPaths, Signal
from PySide6.QtNetwork import QHostAddress
from PySide6.QtWebSockets import QWebSocket, QWebSocketServer

SYNC_PROTOCOL = 1
DEFAULT_PORT = 8765
PAIRING_TTL_SECONDS = 300
MAX_INBOUND_MESSAGE_BYTES = 12 * 1024 * 1024
MAX_DEVICE_ID_CHARS = 128
MAX_DEVICE_NAME_CHARS = 120
MAX_VERSION_CHARS = 64
MAX_REQUEST_ID_CHARS = 128
MAX_ACTION_CHARS = 96

StateProvider = Callable[[], Optional[dict]]
CommandHandler = Callable[[str, dict, int, str], Optional[dict]]


@dataclass
class ConnectedClient:
    socket: QWebSocket
    authenticated: bool = False
    device_id: str = ""
    device_name: str = ""
    android_version: str = ""


class MobileSyncServer(QObject):
    """LAN WebSocket server for the DID Android companion app.

    All callbacks are invoked from the Qt GUI thread because QWebSocketServer is
    owned by that thread. This is deliberate: the desktop UI and character model
    can be accessed without crossing Python/Qt threads.
    """

    statusChanged = Signal(str)
    pairingChanged = Signal(object)
    clientCountChanged = Signal(int)
    commandRejected = Signal(str)

    def __init__(
        self,
        *,
        desktop_version: str,
        state_provider: StateProvider,
        command_handler: CommandHandler,
        port: int = DEFAULT_PORT,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.desktop_version = str(desktop_version)[:MAX_VERSION_CHARS]
        self.state_provider = state_provider
        self.command_handler = command_handler
        self.port = int(port)

        self._server = QWebSocketServer(
            "DID Character Sheet Mobile Companion",
            QWebSocketServer.SslMode.NonSecureMode,
            self,
        )
        self._server.newConnection.connect(self._on_new_connection)

        self._clients: Dict[int, ConnectedClient] = {}
        self._revision = 0
        self._pairing_token: Optional[str] = None
        self._pairing_expires_at = 0.0

        self._settings_path = self._default_settings_path()
        self._settings = self._load_settings()
        server_id = self._settings.get("server_id")
        if not isinstance(server_id, str) or not server_id.strip():
            server_id = str(uuid.uuid4())
            self._settings["server_id"] = server_id
        self._server_id = server_id
        if not isinstance(self._settings.get("devices"), dict):
            self._settings["devices"] = {}
        self._save_settings()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> bool:
        if self._server.isListening():
            return True
        ok = self._server.listen(QHostAddress.AnyIPv4, self.port)
        if ok:
            self.statusChanged.emit(f"Mobile companion listening on port {self.port}")
        else:
            self.statusChanged.emit(f"Could not start mobile companion on port {self.port}")
        return bool(ok)

    def stop(self) -> None:
        for client in list(self._clients.values()):
            try:
                client.socket.close()
            except RuntimeError:
                pass
        self._clients.clear()
        self._server.close()
        self.clientCountChanged.emit(0)
        self.statusChanged.emit("Mobile companion stopped")

    def is_listening(self) -> bool:
        return bool(self._server.isListening())

    # ------------------------------------------------------------------
    # Pairing / devices
    # ------------------------------------------------------------------
    def begin_pairing(self, ttl_seconds: int = PAIRING_TTL_SECONDS) -> dict:
        if not self.start():
            raise RuntimeError("Mobile companion server could not start")
        self._pairing_token = secrets.token_urlsafe(24)
        self._pairing_expires_at = time.time() + max(30, int(ttl_seconds))
        payload = {
            "type": "did_pairing",
            "protocol": SYNC_PROTOCOL,
            "host": self._best_lan_ip(),
            "port": self.port,
            "pairing_token": self._pairing_token,
            "expires_at": int(self._pairing_expires_at),
            "server_id": self._server_id,
        }
        self.pairingChanged.emit(payload)
        return payload

    def cancel_pairing(self) -> None:
        self._pairing_token = None
        self._pairing_expires_at = 0.0
        self.pairingChanged.emit(None)

    def paired_devices(self) -> list[dict]:
        result = []
        for device_id, data in self._settings.get("devices", {}).items():
            if not isinstance(data, dict):
                continue
            result.append(
                {
                    "device_id": device_id,
                    "device_name": data.get("device_name", "Phone"),
                    "created_at": data.get("created_at"),
                    "last_seen": data.get("last_seen"),
                }
            )
        return sorted(result, key=lambda item: str(item.get("device_name", "")).lower())

    def revoke_device(self, device_id: str) -> bool:
        devices = self._settings.get("devices", {})
        if device_id not in devices:
            return False
        del devices[device_id]
        self._save_settings()
        for client in list(self._clients.values()):
            if client.device_id == device_id:
                self._send(client.socket, {"type": "error", "code": "DEVICE_REVOKED"})
                client.socket.close()
        return True

    # ------------------------------------------------------------------
    # State broadcasting
    # ------------------------------------------------------------------
    @property
    def revision(self) -> int:
        return self._revision

    def notify_desktop_change(self) -> None:
        """Call after a desktop-originated mutation has been saved."""
        self._revision += 1
        self.broadcast_state()

    def notify_active_character_changed(self) -> None:
        self._revision += 1
        state_message = self._state_message()
        state = state_message.get("character") if state_message.get("type") == "state" else None
        char_id = state.get("id") if isinstance(state, dict) else None
        self._broadcast(
            {
                "type": "active_character_changed",
                "protocol": SYNC_PROTOCOL,
                "character_id": char_id,
            }
        )
        self._broadcast(state_message)

    def broadcast_state(self) -> None:
        self._broadcast(self._state_message())

    # ------------------------------------------------------------------
    # WebSocket handling
    # ------------------------------------------------------------------
    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            ws = self._server.nextPendingConnection()
            if ws is None:
                return
            key = id(ws)
            self._clients[key] = ConnectedClient(socket=ws)
            ws.textMessageReceived.connect(lambda text, sock=ws: self._on_text(sock, text))
            ws.disconnected.connect(lambda sock=ws: self._on_disconnected(sock))
            self.clientCountChanged.emit(self._authenticated_client_count())

    def _on_disconnected(self, ws: QWebSocket) -> None:
        self._clients.pop(id(ws), None)
        self.clientCountChanged.emit(self._authenticated_client_count())
        try:
            ws.deleteLater()
        except RuntimeError:
            pass

    def _on_text(self, ws: QWebSocket, text: str) -> None:
        client = self._clients.get(id(ws))
        if client is None:
            ws.close()
            return

        if len(text.encode("utf-8")) > MAX_INBOUND_MESSAGE_BYTES:
            self._send(ws, {"type": "error", "code": "MESSAGE_TOO_LARGE"})
            ws.close()
            return

        try:
            message = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            self._send(ws, {"type": "error", "code": "INVALID_JSON"})
            return
        if not isinstance(message, dict):
            self._send(ws, {"type": "error", "code": "INVALID_MESSAGE"})
            return

        msg_type = message.get("type")
        if msg_type == "pair":
            self._handle_pair(client, message)
            return
        if msg_type == "hello":
            self._handle_hello(client, message)
            return
        if not client.authenticated:
            self._send(ws, {"type": "error", "code": "AUTH_REQUIRED"})
            return
        if msg_type == "command":
            self._handle_command(client, message)
        elif msg_type == "get_state":
            self._send(ws, self._state_message())
        elif msg_type == "ping":
            self._send(ws, {"type": "pong", "protocol": SYNC_PROTOCOL})
        else:
            self._send(ws, {"type": "error", "code": "UNKNOWN_MESSAGE"})

    def _handle_pair(self, client: ConnectedClient, message: dict) -> None:
        if not self._protocol_matches(message):
            self._send(client.socket, self._protocol_error())
            client.socket.close()
            return
        token = str(message.get("pairing_token", ""))
        if (
            not self._pairing_token
            or time.time() >= self._pairing_expires_at
            or not secrets.compare_digest(token, self._pairing_token)
        ):
            self._send(client.socket, {"type": "pair_error", "code": "PAIRING_EXPIRED_OR_INVALID"})
            return

        device_id = self._bounded_text(message.get("device_id"), MAX_DEVICE_ID_CHARS)
        if not device_id:
            device_id = str(uuid.uuid4())
        device_name = self._bounded_text(message.get("device_name") or "Phone", MAX_DEVICE_NAME_CHARS)
        android_version = self._bounded_text(message.get("android_version"), MAX_VERSION_CHARS)
        permanent_token = secrets.token_urlsafe(32)
        now = int(time.time())
        self._settings["devices"][device_id] = {
            "device_name": device_name,
            "token": permanent_token,
            "created_at": now,
            "last_seen": now,
        }
        self._save_settings()
        self.cancel_pairing()

        client.authenticated = True
        client.device_id = device_id
        client.device_name = device_name
        client.android_version = android_version
        self._send(
            client.socket,
            {
                "type": "pair_ok",
                "protocol": SYNC_PROTOCOL,
                "device_id": device_id,
                "device_token": permanent_token,
                "server_id": self._server_id,
                "desktop_version": self.desktop_version,
            },
        )
        self._send(client.socket, self._state_message())
        self.clientCountChanged.emit(self._authenticated_client_count())

    def _handle_hello(self, client: ConnectedClient, message: dict) -> None:
        if not self._protocol_matches(message):
            self._send(client.socket, self._protocol_error())
            client.socket.close()
            return
        device_id = self._bounded_text(message.get("device_id"), MAX_DEVICE_ID_CHARS)
        supplied = str(message.get("device_token", ""))
        saved = self._settings.get("devices", {}).get(device_id)
        if (
            not isinstance(saved, dict)
            or not supplied
            or not secrets.compare_digest(supplied, str(saved.get("token", "")))
        ):
            self._send(client.socket, {"type": "hello_error", "code": "NOT_PAIRED"})
            return

        client.authenticated = True
        client.device_id = device_id
        client.device_name = self._bounded_text(
            message.get("device_name") or saved.get("device_name") or "Phone",
            MAX_DEVICE_NAME_CHARS,
        )
        client.android_version = self._bounded_text(message.get("android_version"), MAX_VERSION_CHARS)
        saved["device_name"] = client.device_name
        saved["last_seen"] = int(time.time())
        self._save_settings()
        self._send(
            client.socket,
            {
                "type": "hello_ok",
                "protocol": SYNC_PROTOCOL,
                "desktop_version": self.desktop_version,
                "server_id": self._server_id,
                "revision": self._revision,
            },
        )
        self._send(client.socket, self._state_message())
        self.clientCountChanged.emit(self._authenticated_client_count())

    def _handle_command(self, client: ConnectedClient, message: dict) -> None:
        request_id = self._bounded_text(
            message.get("request_id") or uuid.uuid4(),
            MAX_REQUEST_ID_CHARS,
        )
        try:
            base_revision = int(message.get("base_revision", -1))
        except (TypeError, ValueError, OverflowError):
            base_revision = -1
        if base_revision != self._revision:
            self._send(
                client.socket,
                {
                    "type": "command_error",
                    "request_id": request_id,
                    "code": "STALE_REVISION",
                    "message": "The character changed on another device. Refreshing state.",
                    "revision": self._revision,
                },
            )
            self._send(client.socket, self._state_message())
            return

        action = self._bounded_text(message.get("action"), MAX_ACTION_CHARS)
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        try:
            # This callback MUST perform the desktop's normal validation and save.
            command_result = self.command_handler(action, payload, base_revision, request_id)
        except Exception as exc:  # surface desktop validation without crashing server
            self.commandRejected.emit(str(exc))
            self._send(
                client.socket,
                {
                    "type": "command_error",
                    "request_id": request_id,
                    "code": "VALIDATION_ERROR",
                    "message": str(exc) or exc.__class__.__name__,
                    "revision": self._revision,
                },
            )
            return

        self._revision += 1
        response = {
            "type": "command_ok",
            "request_id": request_id,
            "revision": self._revision,
        }
        if isinstance(command_result, dict):
            response["result"] = command_result
        self._send(client.socket, response)
        self.broadcast_state()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _state_message(self) -> dict:
        try:
            character = self._safe_state()
        except Exception as exc:
            self.statusChanged.emit(f"Mobile companion state unavailable: {exc}")
            return {
                "type": "error",
                "code": "STATE_UNAVAILABLE",
                "protocol": SYNC_PROTOCOL,
                "revision": self._revision,
                "message": "Desktop character state is temporarily unavailable.",
            }
        return {
            "type": "state",
            "protocol": SYNC_PROTOCOL,
            "revision": self._revision,
            "character": character,
        }

    def _safe_state(self) -> Optional[dict]:
        state = self.state_provider()
        if state is None:
            return None
        if not isinstance(state, dict):
            raise TypeError("state_provider must return dict or None")
        # Force JSON-serializability now, so a bad state cannot break a client
        # halfway through a message.
        return json.loads(json.dumps(state, ensure_ascii=False))

    def _broadcast(self, message: dict) -> None:
        for client in list(self._clients.values()):
            if client.authenticated:
                self._send(client.socket, message)

    @staticmethod
    def _send(ws: QWebSocket, message: dict) -> None:
        ws.sendTextMessage(json.dumps(message, ensure_ascii=False, separators=(",", ":")))

    def _protocol_error(self) -> dict:
        return {
            "type": "error",
            "code": "PROTOCOL_MISMATCH",
            "protocol": SYNC_PROTOCOL,
            "desktop_version": self.desktop_version,
        }

    @staticmethod
    def _protocol_matches(message: dict) -> bool:
        try:
            return int(message.get("protocol", -1)) == SYNC_PROTOCOL
        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _bounded_text(value: Any, limit: int) -> str:
        return str(value if value is not None else "")[: max(0, int(limit))]

    def _authenticated_client_count(self) -> int:
        return sum(1 for client in self._clients.values() if client.authenticated)

    @staticmethod
    def _best_lan_ip() -> str:
        # UDP connect does not send application data; it asks the OS which local
        # interface would be used. Fall back gracefully when offline.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            try:
                return socket.gethostbyname(socket.gethostname())
            except OSError:
                return "127.0.0.1"
        finally:
            sock.close()

    @staticmethod
    def _default_settings_path() -> Path:
        root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        path = Path(root or Path.home() / ".did_character_sheet")
        path.mkdir(parents=True, exist_ok=True)
        return path / "mobile_companion.json"

    def _load_settings(self) -> dict:
        try:
            if self._settings_path.exists():
                data = json.loads(self._settings_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_settings(self) -> None:
        tmp = self._settings_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._settings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self._settings_path)
