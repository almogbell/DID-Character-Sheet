from __future__ import annotations

from pathlib import Path
import shutil
import sys

path = Path(__file__).with_name("mobile_sync_server.py")
if not path.is_file():
    raise SystemExit(f"Could not find {path.name} beside this patch script.")

text = path.read_text(encoding="utf-8")
original = text

if "import ipaddress\n" not in text:
    text = text.replace("import json\n", "import json\nimport ipaddress\n", 1)
if "import subprocess\n" not in text:
    text = text.replace("import socket\n", "import socket\nimport subprocess\nimport sys\n", 1)

old = '''        payload = {\n            "type": "did_pairing",\n            "protocol": SYNC_PROTOCOL,\n            "host": self._best_lan_ip(),\n            "port": self.port,\n            "pairing_token": self._pairing_token,\n            "expires_at": int(self._pairing_expires_at),\n            "server_id": self._server_id,\n        }\n'''
new = '''        hosts = self._candidate_ipv4_addresses()\n        payload = {\n            "type": "did_pairing",\n            "protocol": SYNC_PROTOCOL,\n            "host": hosts[0] if hosts else self._best_lan_ip(),\n            "hosts": hosts,\n            "port": self.port,\n            "pairing_token": self._pairing_token,\n            "expires_at": int(self._pairing_expires_at),\n            "server_id": self._server_id,\n        }\n'''
if old in text:
    text = text.replace(old, new, 1)
elif '"hosts": hosts,' not in text:
    raise SystemExit("Could not locate begin_pairing payload. No changes made.")

# Advertise updated LAN/Tailscale addresses on both authenticated handshakes.
needle = '                "desktop_version": self.desktop_version,\n'
if '"hosts": self._candidate_ipv4_addresses(),' not in text:
    pos = 0
    replaced = 0
    while replaced < 2:
        idx = text.find(needle, pos)
        if idx < 0:
            raise SystemExit("Could not locate both handshake responses. No changes made.")
        end = idx + len(needle)
        text = text[:end] + '                "hosts": self._candidate_ipv4_addresses(),\n' + text[end:]
        pos = end + 70
        replaced += 1

helper_marker = '''    @staticmethod\n    def _best_lan_ip() -> str:\n'''
helper = r'''    @staticmethod
    def _is_supported_peer_ipv4(value: str) -> bool:
        try:
            ip = ipaddress.ip_address(str(value).strip())
        except ValueError:
            return False
        if ip.version != 4 or ip.is_unspecified or ip.is_multicast:
            return False
        octets = [int(part) for part in str(ip).split(".")]
        a, b = octets[0], octets[1]
        tailscale = a == 100 and 64 <= b <= 127
        lan = (
            a == 10
            or (a == 172 and 16 <= b <= 31)
            or (a == 192 and b == 168)
            or (a == 169 and b == 254)
            or a == 127
        )
        return lan or tailscale

    @classmethod
    def _candidate_ipv4_addresses(cls) -> list[str]:
        """Return reconnect candidates, preferring the active LAN then Tailscale.

        The pairing token/device credential still authenticates the phone. The
        address list only lets an already paired phone reach the same server
        whether it is on the local Wi-Fi or on the user's Tailscale network.
        """
        values: list[str] = []

        def add(value) -> None:
            candidate = str(value or "").strip()
            if cls._is_supported_peer_ipv4(candidate) and candidate not in values:
                values.append(candidate)

        add(cls._best_lan_ip())

        try:
            for value in socket.gethostbyname_ex(socket.gethostname())[2]:
                add(value)
        except OSError:
            pass

        try:
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                add(item[4][0])
        except OSError:
            pass

        # Windows hostname resolution often omits virtual adapters. PowerShell's
        # Get-NetIPAddress reliably exposes the Tailscale 100.64.0.0/10 address.
        if sys.platform.startswith("win"):
            creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=creationflags,
                    check=False,
                )
                for line in result.stdout.splitlines():
                    add(line)
            except (OSError, subprocess.SubprocessError):
                pass

        # Keep loopback last; prefer actual LAN, then Tailscale, then other
        # supported adapters. _best_lan_ip() remains first when valid.
        first = values[:1]
        rest = values[1:]
        rest.sort(
            key=lambda value: (
                2 if value.startswith("127.") else
                1 if value.startswith("100.") else
                0,
                value,
            )
        )
        return first + rest

'''
if helper not in text:
    if helper_marker not in text:
        raise SystemExit("Could not locate _best_lan_ip helper. No changes made.")
    text = text.replace(helper_marker, helper + helper_marker, 1)

if text == original:
    print("mobile_sync_server.py already has the reliability update.")
    raise SystemExit(0)

backup = path.with_suffix(path.suffix + ".before_sync_reliability")
if not backup.exists():
    shutil.copy2(path, backup)

path.write_text(text, encoding="utf-8")
print("Updated mobile_sync_server.py")
print(f"Backup: {backup.name}")
