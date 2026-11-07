from __future__ import annotations

import json
import secrets
import threading
import hashlib
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QStandardPaths

SUPABASE_URL = "https://pqrvwcaaliccgyuommyq.supabase.co"
SUPABASE_KEY = "sb_publishable_iNGE2WpvTOHKZZjSwELshQ_Bh57P6_X"
RPC_UPSERT = f"{SUPABASE_URL}/rest/v1/rpc/did_sync_upsert"


class MobileCloudSync:
    """Upload latest Windows-authored character snapshots to Supabase.

    The secret is generated once per Windows installation and shared only with
    paired Android clients through the LAN snapshot metadata.
    """

    def __init__(self) -> None:
        self._credentials = self._load_or_create_credentials()
        self._lock = threading.Lock()
        self._last_signature_by_character: dict[str, str] = {}

    def public_config(self) -> dict[str, str]:
        return {
            "url": SUPABASE_URL,
            "key": SUPABASE_KEY,
            "owner": self._credentials["owner"],
            "secret": self._credentials["secret"],
        }

    def upload_async(self, state: Optional[dict]) -> None:
        if not isinstance(state, dict):
            return
        character_id = str(state.get("id") or "").strip()
        if not character_id:
            return

        payload_state = json.loads(json.dumps(state, ensure_ascii=False))
        payload_state.pop("_mobile_cloud", None)
        raw = json.dumps(
            payload_state, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        signature = hashlib.sha256(raw).hexdigest()

        with self._lock:
            if self._last_signature_by_character.get(character_id) == signature:
                return
            self._last_signature_by_character[character_id] = signature

        # Wall-clock milliseconds provide a monotonic-enough version across
        # desktop restarts, unlike the LAN server's in-memory revision counter.
        revision = int(time.time_ns() // 1_000_000)
        body = {
            "p_owner": self._credentials["owner"],
            "p_secret": self._credentials["secret"],
            "p_character_id": character_id,
            "p_character_name": str(state.get("name") or ""),
            "p_revision": revision,
            "p_character": payload_state,
        }
        threading.Thread(
            target=self._upload,
            args=(body,),
            name="did-cloud-sync",
            daemon=True,
        ).start()

    def _upload(self, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            RPC_UPSERT,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            # Cloud sync must never interfere with the desktop character sheet.
            return

    @staticmethod
    def _credentials_path() -> Path:
        root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        path = Path(root or Path.home() / ".did_character_sheet")
        path.mkdir(parents=True, exist_ok=True)
        return path / "mobile_cloud_sync.json"

    @classmethod
    def _load_or_create_credentials(cls) -> dict[str, str]:
        path = cls._credentials_path()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                owner = str(data.get("owner") or "").strip()
                secret = str(data.get("secret") or "").strip()
                uuid.UUID(owner)
                if len(secret) >= 32:
                    return {"owner": owner, "secret": secret}
        except Exception:
            pass

        data = {
            "owner": str(uuid.uuid4()),
            "secret": secrets.token_urlsafe(32),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
        return data
