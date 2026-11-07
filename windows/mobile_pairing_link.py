"""Optional browser-first pairing QR. Keep legacy JSON until Android V8 supports links.

The pairing secret lives only in the URL fragment, which is not sent in
HTTP requests. Never add credentials to URL query strings or paths.
"""
from __future__ import annotations

import base64
import json
from urllib.parse import urlsplit, urlunsplit


def make_pairing_landing_url(payload: dict, landing_url: str) -> str:
    parsed = urlsplit(str(landing_url).strip())
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('Pairing landing page requires a valid HTTPS URL')
    if parsed.query or parsed.fragment:
        raise ValueError('Pairing landing URL must not contain a query or fragment')
    if payload.get('type') != 'did_pairing' or not payload.get('pairing_token'):
        raise ValueError('Expected a temporary DID pairing payload')
    raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    encoded = base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', 'did=' + encoded))
