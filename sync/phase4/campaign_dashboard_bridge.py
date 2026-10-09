from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QTimer

from campaign_cloud import CampaignCloudError, load_campaign_cloud_config


DASHBOARD_PORT = 8765
DASHBOARD_DIRNAME = "dm_dashboard"
PRESENCE_INTERVAL_MS = 15000


def _app_dir(app_dir=None):
    return Path(app_dir or Path(__file__).resolve().parent)


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def prepare_dashboard_config(app_dir=None):
    root = _app_dir(app_dir)
    dashboard_dir = root / DASHBOARD_DIRNAME
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    config = load_campaign_cloud_config(root)
    payload = {
        "supabaseUrl": str(config["url"]),
        "supabaseKey": str(config["key"]),
    }
    target = dashboard_dir / "config.js"
    target.write_text(
        "window.DID_DASHBOARD_CONFIG = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    return target


def create_dashboard_access(client, campaign_id):
    campaign_id = str(campaign_id or "").strip()
    if not campaign_id:
        raise CampaignCloudError("Campaign ID is required")

    rows = client._request_json(
        "POST",
        "/rest/v1/rpc/did_create_dashboard_code",
        body={"p_campaign_id": campaign_id},
    )
    if not isinstance(rows, list) or not rows:
        raise CampaignCloudError("Could not create a DM dashboard access code")

    code = str(rows[0].get("dashboard_code") or "").strip()
    if not code:
        raise CampaignCloudError("Supabase returned an empty dashboard access code")

    return {
        "code": code,
        "expires_at": rows[0].get("expires_at"),
    }


def launch_dashboard_server(access_code="", app_dir=None):
    root = _app_dir(app_dir)
    prepare_dashboard_config(root)

    code = str(access_code or "").strip()
    base_url = f"http://127.0.0.1:{DASHBOARD_PORT}/"
    url = base_url
    if code:
        url += "#code=" + urllib.parse.quote(code, safe="")

    server = root / "dashboard_server.py"
    if not server.is_file():
        raise CampaignCloudError("dashboard_server.py is missing")

    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )

    subprocess.Popen(
        [sys.executable, str(server), "--open-url", url],
        cwd=str(root),
        creationflags=creationflags,
        close_fds=(os.name != "nt"),
    )
    return url


def open_dm_dashboard(client, campaign_id, app_dir=None):
    access = create_dashboard_access(client, campaign_id)
    access["url"] = launch_dashboard_server(
        access["code"],
        app_dir=app_dir,
    )
    return access


def touch_character_presence(client, campaign_character_id):
    campaign_character_id = str(campaign_character_id or "").strip()
    if not campaign_character_id:
        return False

    client._request_json(
        "PATCH",
        "/rest/v1/campaign_characters",
        query={"id": f"eq.{campaign_character_id}"},
        body={"last_seen_at": _utc_now_iso()},
        prefer="return=minimal",
    )
    return True


def install_presence_heartbeat(window):
    if getattr(window, "_campaign_presence_timer", None) is not None:
        return

    timer = QTimer(window)
    timer.setInterval(PRESENCE_INTERVAL_MS)

    def heartbeat():
        client = getattr(window, "_campaign_cloud_client", None)
        executor = getattr(window, "_campaign_sync_executor", None)
        character = getattr(window, "character", None)
        character_id = str(getattr(character, "id", "") or "").strip()

        if client is None or executor is None or not character_id:
            return

        try:
            link = client.get_character_link(character_id)
        except Exception:
            return

        if not isinstance(link, dict):
            return

        campaign_character_id = str(
            link.get("campaign_character_id") or ""
        ).strip()
        if not campaign_character_id:
            return

        def job():
            try:
                touch_character_presence(client, campaign_character_id)
            except Exception:
                # Presence is advisory only. Never interrupt character editing.
                return

        executor.submit(job)

    timer.timeout.connect(heartbeat)
    timer.start()
    window._campaign_presence_timer = timer
    QTimer.singleShot(250, heartbeat)
