from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import threading
import time
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
DEFAULT_PORTS = {
    "dm": 8765,
    "party": 18766,
}
DASHBOARD_DIRS = {
    "dm": "dm_dashboard",
    "party": "party_dashboard",
}


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        return


class ReusableThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", choices=sorted(DASHBOARD_DIRS), default="dm")
    parser.add_argument("--port", type=int)
    parser.add_argument("--open-url")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="If the requested port is already in use, open the URL and exit instead of failing.",
    )
    args = parser.parse_args()

    port = args.port or DEFAULT_PORTS[args.dashboard]
    open_url = args.open_url or f"http://{HOST}:{port}/"
    dashboard_dir = Path(__file__).resolve().parent / DASHBOARD_DIRS[args.dashboard]
    label = "DM dashboard" if args.dashboard == "dm" else "Party Dashboard"

    if not (dashboard_dir / "index.html").is_file():
        raise FileNotFoundError(f"{label} files are missing from {dashboard_dir}")

    handler = functools.partial(NoCacheHandler, directory=str(dashboard_dir))

    try:
        server = ReusableThreadingHTTPServer((HOST, port), handler)
    except OSError as exc:
        if args.reuse_existing:
            webbrowser.open(open_url)
            return
        raise RuntimeError(f"Could not start {label} server on port {port}") from exc

    def open_later():
        time.sleep(0.35)
        webbrowser.open(open_url)

    threading.Thread(target=open_later, daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
