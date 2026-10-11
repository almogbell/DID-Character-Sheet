from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

from campaign_cloud import CampaignCloudError, load_campaign_cloud_config


PARTY_DASHBOARD_PORT = 8766
PARTY_DASHBOARD_DIRNAME = "party_dashboard"


def _app_dir(app_dir=None):
    return Path(app_dir or Path(__file__).resolve().parent)


def prepare_party_dashboard_config(app_dir=None):
    root = _app_dir(app_dir)
    dashboard_dir = root / PARTY_DASHBOARD_DIRNAME
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    config = load_campaign_cloud_config(root)
    payload = {
        "supabaseUrl": str(config["url"]),
        "supabaseKey": str(config["key"]),
    }
    target = dashboard_dir / "config.js"
    target.write_text(
        "window.DID_PARTY_DASHBOARD_CONFIG = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    return target


def create_party_dashboard_access(client, campaign_id):
    campaign_id = str(campaign_id or "").strip()
    if not campaign_id:
        raise CampaignCloudError("Campaign ID is required")
    rows = client._request_json(
        "POST",
        "/rest/v1/rpc/did_create_party_dashboard_code",
        body={"p_campaign_id": campaign_id},
    )
    if not isinstance(rows, list) or not rows:
        raise CampaignCloudError("Could not create a Party Dashboard access code")
    code = str(rows[0].get("dashboard_code") or "").strip()
    if not code:
        raise CampaignCloudError("Supabase returned an empty Party Dashboard access code")
    return {
        "code": code,
        "expires_at": rows[0].get("expires_at"),
    }


def launch_party_dashboard_server(access_code="", app_dir=None):
    root = _app_dir(app_dir)
    prepare_party_dashboard_config(root)

    code = str(access_code or "").strip()
    base_url = f"http://127.0.0.1:{PARTY_DASHBOARD_PORT}/"
    url = base_url
    if code:
        url += "#code=" + urllib.parse.quote(code, safe="")

    server = root / "party_dashboard_server.py"
    if not server.is_file():
        raise CampaignCloudError("party_dashboard_server.py is missing")

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


def open_party_dashboard(client, campaign_id, app_dir=None):
    access = create_party_dashboard_access(client, campaign_id)
    access["url"] = launch_party_dashboard_server(
        access["code"],
        app_dir=app_dir,
    )
    return access
