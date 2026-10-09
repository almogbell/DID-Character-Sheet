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
PORT = 8765


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
    parser.add_argument("--open-url", default=f"http://{HOST}:{PORT}/")
    args = parser.parse_args()

    dashboard_dir = Path(__file__).resolve().parent / "dm_dashboard"
    if not (dashboard_dir / "index.html").is_file():
        raise FileNotFoundError(f"DM dashboard files are missing from {dashboard_dir}")

    handler = functools.partial(NoCacheHandler, directory=str(dashboard_dir))

    try:
        server = ReusableThreadingHTTPServer((HOST, PORT), handler)
    except OSError:
        # A previous dashboard server is already running. Reuse it.
        webbrowser.open(args.open_url)
        return

    def open_later():
        time.sleep(0.35)
        webbrowser.open(args.open_url)

    threading.Thread(target=open_later, daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
