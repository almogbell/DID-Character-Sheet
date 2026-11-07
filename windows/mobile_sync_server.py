"""LAN sync server used by DID Character Sheet's Android companion.

Both Windows and Android keep independent local character data.  This module is
only the authenticated transport: character validation and persistence remain in
mobile_sync_frontend_adapter.py.
"""
from __future__ import annotations

import json
import base64
import hashlib
import hmac
import ipaddress
import re
import os
import secrets
import shutil
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, QStandardPaths, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QHostAddress
from PySide6.QtWebSockets import QWebSocket, QWebSocketServer

SYNC_PROTOCOL = 1
DEFAULT_PORT = 8765
FALLBACK_PORT_SPAN = 10
PAIRING_TTL_SECONDS = 300
HEARTBEAT_INTERVAL_MS = 5000
# UDP discovery only advertises the server's temporary LAN endpoint. The
# device token is NEVER transmitted over UDP. WebSocket authentication is
# still mandatory and is unchanged.
DISCOVERY_PORT = 8764
DISCOVERY_CHALLENGE = "DID_DISCOVER_V1"
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
        self._pairing_payload: Optional[dict] = None
        self._pairing_last_end_reason = ""

        self._settings_path = self._stable_settings_path()
        self._migrate_legacy_settings_if_needed()
        self._settings = self._load_settings()
        server_id = self._settings.get("server_id")
        if not isinstance(server_id, str) or not server_id.strip():
            server_id = str(uuid.uuid4())
            self._settings["server_id"] = server_id
        self._server_id = server_id
        if not isinstance(self._settings.get("devices"), dict):
            self._settings["devices"] = {}
        self._save_settings()

        self._discovery_socket = None
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._heartbeat_clients)
        self._heartbeat_timer.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> bool:
        if self._server.isListening():
            self._start_discovery()
            return True

        # Android discovers the fixed 8765-8775 range. A previous fallback
        # must not shift the next restart outside that discovery range.
        preferred_port = (DEFAULT_PORT if DEFAULT_PORT <= self.port <= DEFAULT_PORT + FALLBACK_PORT_SPAN else int(self.port))
        final_port = min(65535, preferred_port + FALLBACK_PORT_SPAN)
        for candidate_port in range(preferred_port, final_port + 1):
            try:
                ok = self._server.listen(QHostAddress.AnyIPv4, candidate_port)
            except RuntimeError:
                ok = False
            if not ok:
                continue

            self.port = candidate_port
            self._start_discovery()
            if candidate_port == preferred_port:
                self.statusChanged.emit(
                    f"Mobile companion listening on port {candidate_port}"
                )
            else:
                self.statusChanged.emit(
                    "Mobile companion listening on fallback port "
                    f"{candidate_port} because {preferred_port} is already in use"
                )
            return True

        self.statusChanged.emit(
            f"Could not start mobile companion on ports {preferred_port}-{final_port}"
        )
        return False

    def stop(self) -> None:
        if self._discovery_socket is not None:
            try:
                self._discovery_socket.close()
                self._discovery_socket.deleteLater()
            except RuntimeError:
                pass
            self._discovery_socket = None
        self._heartbeat_timer.stop()
        for client in list(self._clients.values()):
            try:
                client.socket.close()
            except RuntimeError:
                pass
        self._clients.clear()
        try:
            self._server.close()
        except RuntimeError:
            pass
        self._emit_client_count()
        try:
            self.statusChanged.emit("Mobile companion stopped")
        except RuntimeError:
            pass

    def _start_discovery(self) -> None:
        """Allow a previously paired phone to find a PC after a DHCP change.

        LAN discovery is best-effort: some Windows firewalls block UDP. It
        never weakens the existing authenticated WebSocket pairing protocol.
        """
        if self._discovery_socket is not None:
            return
        try:
            # Lazy import preserves existing lightweight PySide6 test doubles.
            from PySide6.QtNetwork import QUdpSocket
            discovery = QUdpSocket(self)
            if not discovery.bind(QHostAddress.AnyIPv4, DISCOVERY_PORT):
                discovery.deleteLater()
                return
            discovery.readyRead.connect(self._reply_to_discovery)
            self._discovery_socket = discovery
        except (ImportError, RuntimeError, AttributeError):
            self._discovery_socket = None

    def _reply_to_discovery(self) -> None:
        discovery = self._discovery_socket
        if discovery is None or not self.is_listening():
            return
        while discovery.hasPendingDatagrams():
            incoming = discovery.receiveDatagram()
            try:
                address = incoming.senderAddress()
                if not address or not address.isInSubnet(QHostAddress("10.0.0.0"), 8) and not (
                    address.isInSubnet(QHostAddress("172.16.0.0"), 12) or
                    address.isInSubnet(QHostAddress("192.168.0.0"), 16) or
                    address.isInSubnet(QHostAddress("169.254.0.0"), 16)
                ):
                    continue
                body = bytes(incoming.data())
                if len(body) > 1024:
                    continue
                request = json.loads(body.decode("utf-8"))
                if not isinstance(request, dict) or request.get("type") != "did_discover_v1":
                    continue
                if request.get("server_id") != self._server_id:
                    continue
                device_id = str(request.get("device_id") or "")
                nonce = str(request.get("nonce") or "")
                if not re.fullmatch(r"[0-9a-f]{32}", nonce):
                    continue
                device = self._settings.get("devices", {}).get(device_id)
                if not isinstance(device, dict) or not device.get("token"):
                    continue
                # The responder proves it holds the phone's existing device
                # credential. A spoofed UDP response must not trick Android
                # into sending its credential to a hostile WebSocket endpoint.
                message = f"{DISCOVERY_CHALLENGE}|{self._server_id}|{nonce}|{self.port}"
                proof = base64.urlsafe_b64encode(hmac.new(
                    str(device["token"]).encode("utf-8"), message.encode("utf-8"), hashlib.sha256
                ).digest()).decode("ascii").rstrip("=")
                reply = json.dumps({"type": "did_discover_ok_v1", "server_id": self._server_id,
                                    "port": self.port, "nonce": nonce, "proof": proof},
                                   separators=(",", ":")).encode("utf-8")
                discovery.writeDatagram(reply, address, incoming.senderPort())
            except (RuntimeError, ValueError, TypeError):
                continue

    def is_listening(self) -> bool:
        try:
            return bool(self._server.isListening())
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # Pairing / devices
    # ------------------------------------------------------------------
    def begin_pairing(
        self, ttl_seconds: int = PAIRING_TTL_SECONDS, *, host_override: Optional[str] = None
    ) -> dict:
        if not self.start():
            raise RuntimeError("Mobile companion server could not start")
        # The address advertised in the QR must be reachable by the phone.
        # On VPN-equipped PCs the default outbound route may be a tunnel,
        # so the dialog lets users explicitly select their Wi-Fi/LAN NIC.
        candidates = {ip for _label, ip in self.pairing_lan_addresses()}
        if host_override is not None and str(host_override) not in candidates:
            raise ValueError("Selected phone pairing address is no longer an active LAN address. Refresh the list.")
        pairing_host = str(host_override) if host_override is not None else self._best_lan_ip()
        self._pairing_token = secrets.token_urlsafe(24)
        self._pairing_expires_at = time.time() + max(30, int(ttl_seconds))
        self._pairing_last_end_reason = ""
        payload = {
            "type": "did_pairing",
            "protocol": SYNC_PROTOCOL,
            "host": pairing_host,
            "port": self.port,
            "pairing_token": self._pairing_token,
            "expires_at": int(self._pairing_expires_at),
            "server_id": self._server_id,
        }
        # Only this in-memory temporary code is exposed by the dialog; it is
        # never saved with the trusted devices or their permanent credentials.
        self._pairing_payload = dict(payload)
        self.pairingChanged.emit(dict(payload))
        return payload

    def active_pairing_payload(self) -> Optional[dict]:
        """Return a still-valid QR payload when Mobile Companion is reopened."""
        if not self._pairing_token:
            return None
        if time.time() >= self._pairing_expires_at:
            self.cancel_pairing(reason='expired')
            return None
        return dict(self._pairing_payload) if self._pairing_payload else None

    def cancel_pairing(self, *, reason: str = 'cancelled') -> None:
        """Revoke the temporary code; existing authenticated devices stay connected."""
        self._pairing_token = None
        self._pairing_expires_at = 0.0
        self._pairing_payload = None
        self._pairing_last_end_reason = reason
        self.pairingChanged.emit(None)

    def paired_devices(self) -> list[dict]:
        result = []
        for device_id, data in self._settings.get("devices", {}).items():
            if not isinstance(data, dict):
                continue
            result.append(
                {
                    "device_id": str(device_id),
                    "device_name": data.get("device_name", "Phone"),
                    "created_at": data.get("created_at"),
                    "last_seen": data.get("last_seen"),
                }
            )
        return sorted(
            result,
            key=lambda item: str(item.get("device_name", "")).lower(),
        )

    def connected_device_ids(self) -> set[str]:
        connected: set[str] = set()
        dead_keys: list[int] = []
        for key, client in list(self._clients.items()):
            try:
                live = (
                    client.authenticated
                    and client.socket.isValid()
                    and client.socket.state()
                    == QAbstractSocket.SocketState.ConnectedState
                )
            except RuntimeError:
                live = False
            if live and client.device_id:
                connected.add(str(client.device_id))
            elif client.authenticated:
                dead_keys.append(key)
        for key in dead_keys:
            self._clients.pop(key, None)
        return connected

    def rename_device(self, device_id: str, new_name: str) -> bool:
        """Rename a paired phone without changing its authentication token."""
        devices = self._settings.get("devices", {})
        if device_id not in devices or not isinstance(devices[device_id], dict):
            return False
        name = str(new_name).strip()
        if not name or len(name) > MAX_DEVICE_NAME_CHARS or any(ord(c) < 32 for c in name):
            return False
        previous_name = devices[device_id].get('device_name', 'Phone')
        devices[device_id]['device_name'] = name
        try:
            self._save_settings()
        except OSError:
            devices[device_id]['device_name'] = previous_name
            return False
        for client in self._clients.values():
            if client.device_id == device_id:
                client.device_name = name
        return True

    def pending_connection_count(self) -> int:
        """Sockets connected but not authenticated (not counted as phones)."""
        return sum(1 for client in self._clients.values() if not client.authenticated)

    def _disconnect_previous_sessions(self, device_id: str, current_socket: QWebSocket) -> None:
        """Only one session per device identity; don't count zombie sockets."""
        for client in list(self._clients.values()):
            if client.device_id == device_id and client.socket is not current_socket:
                try:
                    client.socket.close()
                except RuntimeError:
                    pass
                self._clients.pop(id(client.socket), None)

    def revoke_device(self, device_id: str, *, phone_initiated: bool = False) -> bool:
        devices = self._settings.get("devices", {})
        if device_id not in devices:
            return False
        previous_record = devices.pop(device_id)
        try:
            self._save_settings()
        except OSError:
            devices[device_id] = previous_record
            return False
        # Invalidate the in-memory session immediately. Closing a socket is
        # asynchronous; do not allow more commands after explicit revocation.
        for key, client in list(self._clients.items()):
            if client.device_id == device_id:
                self._clients.pop(key, None)
                try:
                    # A phone-initiated removal gets an explicit acknowledgement
                    # before the WebSocket closes. The record is already saved
                    # as deleted, and any old token has been invalidated.
                    notice = (
                        {"type": "forget_ok", "device_id": device_id}
                        if phone_initiated else
                        {"type": "error", "code": "DEVICE_REVOKED",
                         "message": "This phone was removed from the Windows app."}
                    )
                    self._send(client.socket, notice)
                    client.socket.close()
                except RuntimeError:
                    pass
        self._emit_client_count()
        return True

    # ------------------------------------------------------------------
    # State broadcasting
    # ------------------------------------------------------------------
    @property
    def revision(self) -> int:
        return self._revision

    def notify_desktop_change(self) -> None:
        self._revision += 1
        self.broadcast_state()

    def notify_active_character_changed(self) -> None:
        self._revision += 1
        state_message = self._state_message()
        state = (
            state_message.get("character")
            if state_message.get("type") == "state"
            else None
        )
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
            ws.textMessageReceived.connect(
                lambda text, sock=ws: self._on_text(sock, text)
            )
            ws.disconnected.connect(
                lambda sock=ws: self._on_disconnected(sock)
            )
        self._emit_client_count()

    def _on_disconnected(self, ws: QWebSocket) -> None:
        self._clients.pop(id(ws), None)
        self._emit_client_count()
        try:
            ws.deleteLater()
        except RuntimeError:
            pass

    def _on_text(self, ws: QWebSocket, text: str) -> None:
        client = self._clients.get(id(ws))
        if client is None:
            try:
                ws.close()
            except RuntimeError:
                pass
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

        msg_type = str(message.get("type") or "")
        if msg_type == "pair":
            self._handle_pair(client, message)
            return
        if msg_type == "hello":
            self._handle_hello(client, message)
            return
        if not client.authenticated:
            self._send(ws, {"type": "error", "code": "AUTH_REQUIRED"})
            return

        if msg_type == "forget_device":
            # Only the authenticated device may delete its own record.
            # Do not accept a device_id from the incoming JSON.
            if not self.revoke_device(client.device_id, phone_initiated=True):
                self._send(ws, {"type": "forget_error", "message":
                                "Windows could not remove this phone. Remove it manually in Mobile Companion."})
        elif msg_type == "command":
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
            self._send(
                client.socket,
                {"type": "pair_error", "code": "PAIRING_EXPIRED_OR_INVALID"},
            )
            return

        device_id = self._bounded_text(
            message.get("device_id"),
            MAX_DEVICE_ID_CHARS,
        ) or str(uuid.uuid4())
        device_name = self._bounded_text(
            message.get("device_name") or "Phone",
            MAX_DEVICE_NAME_CHARS,
        )
        android_version = self._bounded_text(
            message.get("android_version"),
            MAX_VERSION_CHARS,
        )
        permanent_token = secrets.token_urlsafe(32)
        now = int(time.time())
        self._settings["devices"][device_id] = {
            "device_name": device_name,
            "token": permanent_token,
            "created_at": now,
            "last_seen": now,
        }
        self._save_settings()
        self.cancel_pairing(reason="completed")

        self._disconnect_previous_sessions(device_id, client.socket)
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
        self._emit_client_count()

    def _handle_hello(self, client: ConnectedClient, message: dict) -> None:
        if not self._protocol_matches(message):
            self._send(client.socket, self._protocol_error())
            client.socket.close()
            return
        device_id = self._bounded_text(
            message.get("device_id"),
            MAX_DEVICE_ID_CHARS,
        )
        supplied = str(message.get("device_token", ""))
        saved = self._settings.get("devices", {}).get(device_id)
        if (
            not isinstance(saved, dict)
            or not supplied
            or not secrets.compare_digest(
                supplied,
                str(saved.get("token", "")),
            )
        ):
            self._send(
                client.socket,
                {"type": "hello_error", "code": "NOT_PAIRED"},
            )
            return

        self._disconnect_previous_sessions(device_id, client.socket)
        client.authenticated = True
        client.device_id = device_id
        # A custom Windows-side name must survive future Android reconnects.
        client.device_name = self._bounded_text(
            saved.get("device_name") or message.get("device_name") or "Phone",
            MAX_DEVICE_NAME_CHARS,
        )
        client.android_version = self._bounded_text(
            message.get("android_version"),
            MAX_VERSION_CHARS,
        )
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
        self._emit_client_count()

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
                    "message": (
                        "The character changed on another device. "
                        "Refreshing state."
                    ),
                    "revision": self._revision,
                },
            )
            self._send(client.socket, self._state_message())
            return

        action = self._bounded_text(
            message.get("action"),
            MAX_ACTION_CHARS,
        )
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        try:
            command_result = self.command_handler(
                action,
                payload,
                base_revision,
                request_id,
            )
        except Exception as exc:
            message_text = str(exc) or exc.__class__.__name__
            code = (
                "SYNC_CONFLICT"
                if message_text.startswith("SYNC_CONFLICT:")
                else "VALIDATION_ERROR"
            )
            try:
                self.commandRejected.emit(message_text)
            except RuntimeError:
                pass
            self._send(
                client.socket,
                {
                    "type": "command_error",
                    "request_id": request_id,
                    "code": code,
                    "message": message_text,
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
    def _heartbeat_clients(self) -> None:
        # Expire the QR even if the Mobile Companion dialog is closed.
        if self._pairing_token:
            self.active_pairing_payload()
        changed = False
        for key, client in list(self._clients.items()):
            try:
                live = (
                    client.socket.isValid()
                    and client.socket.state()
                    == QAbstractSocket.SocketState.ConnectedState
                )
            except RuntimeError:
                live = False
            if not live:
                self._clients.pop(key, None)
                changed = True
                continue
            try:
                client.socket.ping()
            except RuntimeError:
                self._clients.pop(key, None)
                changed = True
        if changed:
            self._emit_client_count()

    def _state_message(self) -> dict:
        try:
            character = self._safe_state()
        except Exception as exc:
            try:
                self.statusChanged.emit(
                    f"Mobile companion state unavailable: {exc}"
                )
            except RuntimeError:
                pass
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
        return json.loads(json.dumps(state, ensure_ascii=False))

    def _broadcast(self, message: dict) -> None:
        for client in list(self._clients.values()):
            if client.authenticated:
                try:
                    self._send(client.socket, message)
                except RuntimeError:
                    pass

    @staticmethod
    def _send(ws: QWebSocket, message: dict) -> None:
        ws.sendTextMessage(
            json.dumps(
                message,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

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
        return len(self.connected_device_ids())

    def _emit_client_count(self) -> None:
        try:
            self.clientCountChanged.emit(self._authenticated_client_count())
        except RuntimeError:
            pass

    @staticmethod
    def pairing_lan_addresses() -> list[tuple[str, str]]:
        """Active local IPv4 addresses for selecting a phone-reachable NIC.

        Keep VPN/virtual interfaces in the list as fallbacks, but order actual
        Wi-Fi and Ethernet interfaces first. No hard-coded private subnet is
        assumed: a valid home network can use 10/8 or 172.16/12 as well.
        """
        result: list[tuple[int, str, str]] = []
        seen: set[str] = set()
        try:
            # Import only during QR address enumeration so lightweight Qt
            # transport stubs and older integration tests keep working.
            from PySide6.QtNetwork import QNetworkInterface
            interfaces = QNetworkInterface.allInterfaces()
        except (ImportError, RuntimeError):
            return []
        for interface in interfaces:
            try:
                if not (interface.flags() & QNetworkInterface.InterfaceFlag.IsUp):
                    continue
                name = (interface.humanReadableName() or interface.name() or "Network").strip()
                descriptor = (name + " " + interface.name()).lower()
                for entry in interface.addressEntries():
                    address = entry.ip().toString().split('%', 1)[0]
                    try:
                        ip = ipaddress.IPv4Address(address)
                    except ipaddress.AddressValueError:
                        continue
                    if not ip.is_private or ip.is_loopback or ip.is_link_local or address in seen:
                        continue
                    seen.add(address)
                    if any(token in descriptor for token in ("vpn", "virtual", "vEthernet".lower(),
                                                              "tailscale", "wireguard", "zerotier", "wintun", "tun", "tap", "docker")):
                        priority = 3
                    elif any(token in descriptor for token in ("wi-fi", "wifi", "wireless", "wlan")):
                        priority = 0
                    elif any(token in descriptor for token in ("ethernet", "local area", "lan")):
                        priority = 1
                    else:
                        priority = 2
                    result.append((priority, name, address))
            except RuntimeError:
                continue
        return [(f"{name} — {ip}", ip) for _priority, name, ip in sorted(result)]

    @staticmethod
    def _best_lan_ip() -> str:
        # A connected VPN can replace the system's default route without
        # becoming reachable from a phone on the Wi-Fi. Prefer the actual
        # local Wi-Fi/Ethernet NICs exposed by Qt before route guessing.
        candidates = MobileSyncServer.pairing_lan_addresses()
        if candidates:
            return candidates[0][1]
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
    def _stable_settings_path() -> Path:
        appdata_text = os.environ.get("APPDATA", "").strip()
        if appdata_text:
            appdata_root = Path(appdata_text)
        else:
            generic = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.GenericDataLocation
            )
            appdata_root = (
                Path(generic)
                if generic
                else Path.home() / ".did_character_sheet"
            )

        stable_dir = appdata_root / "DIDCharacterSheet"
        stable_dir.mkdir(parents=True, exist_ok=True)
        return stable_dir / "mobile_companion.json"

    def _migrate_legacy_settings_if_needed(self) -> None:
        if self._settings_path.exists():
            return

        appdata_text = os.environ.get("APPDATA", "").strip()
        appdata_root = Path(appdata_text) if appdata_text else None
        candidates: list[Path] = []

        try:
            current_root = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            if current_root:
                candidates.append(Path(current_root) / "mobile_companion.json")
        except Exception:
            pass

        if appdata_root is not None:
            for pattern_text in (
                "*/mobile_companion.json",
                "*/*/mobile_companion.json",
            ):
                try:
                    candidates.extend(appdata_root.glob(pattern_text))
                except OSError:
                    pass

        best_path: Optional[Path] = None
        best_score = (-1, -1)
        seen: set[str] = set()

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate

            key = str(resolved).lower()
            if (
                key in seen
                or candidate == self._settings_path
                or not candidate.is_file()
            ):
                continue
            seen.add(key)

            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue

            devices = data.get("devices")
            if not isinstance(devices, dict):
                devices = {}

            last_seen = 0
            for device in devices.values():
                if not isinstance(device, dict):
                    continue
                try:
                    last_seen = max(
                        last_seen,
                        int(device.get("last_seen") or 0),
                    )
                except (TypeError, ValueError):
                    pass

            score = (len(devices), last_seen)
            if score > best_score:
                best_score = score
                best_path = candidate

        if best_path is not None:
            try:
                shutil.copy2(best_path, self._settings_path)
            except OSError:
                pass

    def _load_settings(self) -> dict:
        try:
            if self._settings_path.exists():
                data = json.loads(
                    self._settings_path.read_text(encoding="utf-8")
                )
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_settings(self) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._settings_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._settings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self._settings_path)
