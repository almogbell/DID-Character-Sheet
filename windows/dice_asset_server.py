"""Restricted loopback asset origin for the embedded 3D dice page.

Chromium blocks or inconsistently executes ES module imports and worker scripts
from file:// documents.  Serve only bundled, public dice assets over localhost;
never expose saved characters, credentials, configuration or the project tree.
"""
from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from threading import Thread
import sys
from urllib.parse import unquote, urlsplit


WEBCHANNEL_SCRIPT_PATH = '/qtwebchannel/qwebchannel.js'


def qt_webchannel_javascript():
    """Read the JavaScript client from Qt's bundled resource on the UI thread.

    The dice page has a localhost origin, so Chromium disallows loading a
    qrc:/// script directly. Serving *only this public resource* at the same
    origin preserves the WebChannel bridge without exposing app data.
    """
    from PySide6.QtCore import QFile, QIODevice
    # Importing QtWebChannel registers this resource in Qt's resource system.
    import PySide6.QtWebChannel  # noqa: F401

    resource = QFile(':/qtwebchannel/qwebchannel.js')
    if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError(
            'Qt WebChannel JavaScript is missing from PySide6: '
            ':/qtwebchannel/qwebchannel.js. '
            'Reinstall PySide6 with QtWebChannel support. '
            + resource.errorString()
        )
    try:
        data = bytes(resource.readAll())
    finally:
        resource.close()
    if b'QWebChannel' not in data:
        raise RuntimeError('Qt WebChannel JavaScript resource is empty or invalid')
    return data


class DiceAssetHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory, webchannel_js, **kwargs):
        self._webchannel_js = webchannel_js
        super().__init__(*args, directory=directory, **kwargs)

    def _serve_qt_webchannel_js(self, send_body):
        # Exact path only. Never expose arbitrary qrc: paths or Qt resources.
        if urlsplit(self.path).path != WEBCHANNEL_SCRIPT_PATH:
            return False
        body = self._webchannel_js
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if send_body:
            self.wfile.write(body)
        return True

    def _allowed(self):
        root = Path(self.directory).resolve()
        raw = unquote(urlsplit(self.path).path).lstrip('/')
        path = PurePosixPath(raw)
        if not raw or '\\' in raw or '..' in path.parts or path.is_absolute():
            return False
        is_asset = (
            raw in {'dice.html', 'd100_physics.js', 'd100_geometry.js'}
            or raw.startswith('dice_libs/')
        )
        if not is_asset or any(part.startswith('.') for part in path.parts):
            return False
        candidate = (root / str(path)).resolve()
        return candidate.is_file() and candidate.is_relative_to(root)

    def do_GET(self):
        if self._serve_qt_webchannel_js(send_body=True):
            return
        if not self._allowed():
            self.send_error(404, 'Dice asset not found')
            return
        super().do_GET()

    def do_HEAD(self):
        if self._serve_qt_webchannel_js(send_body=False):
            return
        if not self._allowed():
            self.send_error(404, 'Dice asset not found')
            return
        super().do_HEAD()

    def log_message(self, format, *args):
        # Worker and model asset requests are very frequent; avoid flooding
        # the desktop PowerShell console.
        pass


class _QuietDiceServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # Chromium can cancel asset requests during a new dice roll or while
        # a page reloads. That is normal, not an application error.
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


def start_dice_asset_server(app_directory, *, webchannel_js=None):
    # The real app reads the Qt resource in its GUI thread, before starting
    # the HTTP worker. Tests may pass a stub script without installing Qt.
    if webchannel_js is None:
        webchannel_js = qt_webchannel_javascript()
    if not isinstance(webchannel_js, bytes) or not webchannel_js:
        raise ValueError('webchannel_js must be nonempty bytes')
    root = Path(app_directory).resolve()
    if not (root / 'dice.html').is_file():
        raise FileNotFoundError(root / 'dice.html')

    def handler(*args, **kwargs):
        return DiceAssetHandler(
            *args, directory=str(root), webchannel_js=webchannel_js, **kwargs
        )

    server = _QuietDiceServer(('127.0.0.1', 0), handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, name='DID-DiceAssets', daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}/dice.html'
