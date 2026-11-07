from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

from dashboard_runtime import prepare_dashboard_dir, config_root, server_command, start_frozen_dashboard, public_config_from_client
from campaign_cloud import CampaignCloudError, load_campaign_cloud_config


PARTY_DASHBOARD_PORT = 18766
PARTY_DASHBOARD_DIRNAME = "party_dashboard"


def _app_dir(app_dir=None):
    return Path(app_dir or Path(__file__).resolve().parent)


def prepare_party_dashboard_config(app_dir=None, cloud_config=None):
    root = _app_dir(app_dir)
    dashboard_dir = prepare_dashboard_dir("party", app_dir=root)
    config = cloud_config if cloud_config is not None else load_campaign_cloud_config(config_root(root))
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


def _free_party_dashboard_port():
    # Reserve an available loopback port, avoiding stale servers and unrelated
    # processes occupying the previous fixed 18766 port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def launch_party_dashboard_server(access_code="", app_dir=None, cloud_config=None):
    root = _app_dir(app_dir)
    prepare_party_dashboard_config(root, cloud_config=cloud_config)

    code = str(access_code or "").strip()
    port = _free_party_dashboard_port()
    base_url = f"http://127.0.0.1:{port}/"
    url = base_url
    if code:
        url += "#code=" + urllib.parse.quote(code, safe="")

    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )

    web_dir = prepare_dashboard_dir("party", app_dir=root)
    if getattr(sys, "frozen", False):
        start_frozen_dashboard(web_dir, port, url)
        return url

    command = server_command("party", port, url, web_dir, app_dir=root)
    subprocess.Popen(
        command,
        cwd=str(config_root(root)),
        creationflags=creationflags,
        close_fds=(os.name != "nt"),
    )
    return url


def open_party_dashboard(client, campaign_id, app_dir=None):
    access = create_party_dashboard_access(client, campaign_id)
    access["url"] = launch_party_dashboard_server(
        access["code"],
        app_dir=app_dir,
        cloud_config=public_config_from_client(client),
    )
    return access
