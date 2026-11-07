"""Untrusted contributor submissions and authenticated owner inbox for DID.

No service-role keys, passwords, or session tokens are stored on disk.
The publishable key is public; PostgreSQL RLS is the authorization boundary.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_BYTES = 145_000
MAX_OUTBOX = 50


class CloudError(RuntimeError):
    pass


def load_config(path: Path):
    if not path.is_file():
        raise CloudError("Online suggestions are not configured. Ask the owner for suggestions_config.json.")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise CloudError("Invalid suggestions configuration") from exc
    url = str(cfg.get("supabase_url", "")).rstrip("/")
    key = str(cfg.get("publishable_key", ""))
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise CloudError("Supabase URL must be the HTTPS project root, with no path, credentials or query")
    if not key.startswith("sb_publishable_") or len(key) > 1024:
        raise CloudError("Configure a Supabase PUBLISHABLE key (never a secret/service-role key)")
    return {"url": url, "key": key}


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Do not forward an owner JWT to a redirected host.
        return None


class CloudClient:
    def __init__(self, config):
        self.url = config["url"]
        self.key = config["key"]
        self.access_token = None
        self.context = ssl.create_default_context()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.context), _RejectRedirects()
        )

    def _call(self, path, *, method="GET", body=None, auth=False, query=None):
        if auth and not self.access_token:
            raise CloudError("Sign in as the catalog owner first.")
        url = self.url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if data is not None and len(data) > MAX_BYTES:
            raise CloudError("Suggestion is too large (145 KB maximum). Reduce your changes.")
        headers = {"apikey": self.key, "Accept": "application/json", "Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.access_token
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                raw = response.read(MAX_BYTES * 30 + 1)
                if len(raw) > MAX_BYTES * 30:
                    raise CloudError("Server response exceeded the allowed size.")
                return json.loads(raw.decode("utf-8")) if raw.strip() else None
        except urllib.error.HTTPError as exc:
            if auth and exc.code == 401:
                self.access_token = None
            # Never include auth tokens/passwords in error messages.
            try:
                obj = json.loads(exc.read(2000).decode("utf-8"))
                detail = str(obj.get("message") or obj.get("error_description") or obj.get("error") or "")[:250]
            except Exception:
                detail = ""
            raise CloudError(f"Server returned HTTP {exc.code}. {detail}".strip()) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CloudError("Connection failed; suggestion retained locally for retry.") from exc

    def submit(self, item):
        # No SELECT permission is needed for public submissions.
        return self._call("/rest/v1/improvement_suggestions", method="POST", body={
            "id": item["id"], "author": item["author"], "proposal": item["proposal"]
        })

    def login(self, email, password):
        result = self._call("/auth/v1/token", method="POST", query={"grant_type": "password"}, body={
            "email": email, "password": password
        })
        token = result.get("access_token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            raise CloudError("Sign in did not return a valid session.")
        self.access_token = token  # Only in RAM; never persist to disk.
        return True

    def pending(self):
        result = self._call("/rest/v1/improvement_suggestions", auth=True, query={
            "select": "id,created_at,author,proposal,status",
            "status": "eq.pending", "order": "created_at.desc", "limit": "25"
        })
        if not isinstance(result, list):
            raise CloudError("Unexpected response from the suggestions inbox")
        return result

    def update_status(self, suggestion_id, status):
        if status not in {"approved", "rejected"}:
            raise ValueError("Invalid review status")
        return self._call("/rest/v1/improvement_suggestions", auth=True,
                          method="PATCH", query={"id": "eq." + str(uuid.UUID(str(suggestion_id))), "status": "eq.pending"},
                          body={"status": status})


def read_outbox(path):
    try:
        items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, ValueError) as exc:
        raise CloudError("Local suggestion queue is unreadable; it has NOT been overwritten.") from exc
    if not isinstance(items, list):
        raise CloudError("Local suggestion queue has an invalid format")
    return items


def write_outbox(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def enqueue(path, proposal):
    if not isinstance(proposal, dict) or not proposal.get("changes") or proposal.get("errors"):
        raise CloudError("Only nonempty, technically valid suggestions can be sent.")
    size = len(json.dumps(proposal, ensure_ascii=False).encode("utf-8"))
    if size > MAX_BYTES - 1000:
        raise CloudError("Suggestion is too large to send. Reduce the number of edited Improvements.")
    items = read_outbox(path)
    if len(items) >= MAX_OUTBOX:
        raise CloudError("50 suggestions are already queued. Send them before creating more.")
    item = {"id": str(uuid.uuid4()), "author": str(proposal.get("author", "Editor"))[:100], "proposal": copy.deepcopy(proposal)}
    items.append(item)
    write_outbox(path, items)
    return item


def flush_outbox(path, client):
    """Keep stable UUID on retries so an ambiguous HTTP timeout cannot double-submit."""
    items = read_outbox(path)
    sent = 0
    for item in list(items):
        try:
            client.submit(item)
        except CloudError as exc:
            # PostgreSQL duplicate UUID means previous timed-out submission succeeded.
            if "23505" not in str(exc) and "409" not in str(exc):
                return sent, len(items), str(exc)
        items.remove(item)
        write_outbox(path, items)
        sent += 1
    return sent, 0, ""
