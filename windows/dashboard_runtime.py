"""Source and PyInstaller-safe dashboard asset paths / loopback servers.

Packaged single-file EXEs cannot launch dashboard_server.py with sys.executable:
that executable is DID Character Sheet.exe, not the Python interpreter.
For a frozen app we therefore serve copied dashboard assets from a daemon
thread in the current process; source builds keep their original subprocess.
"""
from __future__ import annotations

import atexit
import functools
import http.server
import os
from pathlib import Path
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import webbrowser

_DASHBOARD_DIRS = {"dm": "dm_dashboard", "party": "party_dashboard"}
_ASSET_DIRS: dict[str, Path] = {}
_SERVERS: list[http.server.HTTPServer] = []
_TEMP_DIRS: list[Path] = []


def config_root(app_dir=None) -> Path:
    """Find a usable Supabase configuration in source or frozen builds.

    With PyInstaller --onefile, data files from the .spec are extracted into
    ``sys._MEIPASS`` rather than beside the EXE.  Before installation the
    executable is commonly run directly from ``dist``, which has no external
    suggestions_config.json.  Prefer an explicitly installed configuration
    when one exists; otherwise fall back to the bundled *public* config.

    Do not copy a service-role/secret key into the bundle.  The campaign config
    loader itself rejects those credentials.
    """
    if not getattr(sys, "frozen", False):
        return Path(app_dir or Path(__file__).resolve().parent)

    executable_dir = Path(sys.executable).resolve().parent
    bundled_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    names = ("campaign_config.json", "suggestions_config.json")
    for directory in (executable_dir, bundled_dir):
        if any((directory / name).is_file() for name in names):
            return directory
    # Preserve an actionable "configuration not found" error from the loader.
    return executable_dir



def public_config_from_client(client):
    """Reuse the authenticated CampaignCloudClient's validated public settings.

    Dashboard launchers already have a working client (they just requested a
    one-time dashboard code).  Re-reading a JSON config from the executable
    directory fails for PyInstaller single-file deployments, where that file
    may exist only in the temporary extraction directory.  Do not depend on a
    second filesystem lookup in the ordinary launch path.

    Return None for older test clients without config so the existing
    file-based fallback remains available. Never expose service-role keys.
    """
    if client is None:
        return None
    url = getattr(client, "url", None)
    key = getattr(client, "key", None)
    fallback = getattr(client, "config", None)
    if isinstance(fallback, dict):
        url = url or fallback.get("url")
        key = key or fallback.get("key")
    if not url or not key:
        return None
    from campaign_cloud import CampaignCloudError, _validate_public_key
    url = str(url).strip().rstrip("/")
    if not url.startswith("https://"):
        raise CampaignCloudError("Dashboard Supabase URL must start with https://")
    return {"url": url, "key": _validate_public_key(key)}

def prepare_dashboard_dir(kind: str, app_dir=None) -> Path:
    if kind not in _DASHBOARD_DIRS:
        raise ValueError(f"Unsupported dashboard type: {kind}")
    root = Path(app_dir or Path(__file__).resolve().parent)
    name = _DASHBOARD_DIRS[kind]
    if not getattr(sys, "frozen", False):
        folder = root / name
        if not (folder / "index.html").is_file():
            raise FileNotFoundError(f"Missing dashboard assets: {folder}")
        return folder

    if kind not in _ASSET_DIRS:
        bundled_root = Path(getattr(sys, "_MEIPASS", root))
        source = bundled_root / name
        if not (source / "index.html").is_file():
            raise FileNotFoundError(f"Dashboard was not bundled: {source}")
        dest = Path(tempfile.mkdtemp(prefix=f"did-{kind}-dashboard-"))
        shutil.copytree(source, dest, dirs_exist_ok=True)
        _TEMP_DIRS.append(dest)
        _ASSET_DIRS[kind] = dest
    return _ASSET_DIRS[kind]


def server_command(kind: str, port: int, url: str, web_dir: Path, app_dir=None) -> list[str]:
    """Source-mode subprocess; never try to run a .py via a frozen EXE."""
    if getattr(sys, "frozen", False):
        raise RuntimeError("Use start_frozen_dashboard for a packaged application")
    root = Path(app_dir or Path(__file__).resolve().parent)
    server = root / "dashboard_server.py"
    if not server.is_file():
        raise FileNotFoundError(f"Missing dashboard server script: {server}")
    return [sys.executable, str(server), "--dashboard", kind,
            "--port", str(port), "--open-url", url]


class _NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


class _LoopbackServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_frozen_dashboard(web_dir: Path, port: int, url: str):
    """Keep a dashboard HTTP server alive until DID Character Sheet exits."""
    folder = Path(web_dir)
    if not (folder / "index.html").is_file():
        raise FileNotFoundError(f"Cannot serve missing dashboard assets: {folder}")
    handler = functools.partial(_NoCacheHandler, directory=str(folder))
    server = _LoopbackServer(("127.0.0.1", int(port)), handler)
    _SERVERS.append(server)
    threading.Thread(target=server.serve_forever, daemon=True,
                     name="DID Dashboard HTTP").start()

    def show():
        time.sleep(0.20)
        webbrowser.open(url)

    threading.Thread(target=show, daemon=True, name="DID Dashboard Browser").start()
    return url


def _cleanup():
    for server in _SERVERS:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
    for folder in _TEMP_DIRS:
        shutil.rmtree(folder, ignore_errors=True)


atexit.register(_cleanup)
