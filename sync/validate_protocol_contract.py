from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def extract_int(pattern: str, text: str, label: str) -> int:
    match = re.search(pattern, text)
    if not match:
        raise AssertionError(f"Could not find {label}")
    return int(match.group(1))


def validate() -> None:
    windows_manifest = json.loads(read("updates/windows.json"))
    android_manifest = json.loads(read("updates/android.json"))
    vectors = json.loads(read("sync/test-vectors.json"))

    server = read("windows/mobile_sync_server.py")
    client = read("android/phase8/DidSyncClient.kt")
    protocol_doc = read("sync/protocol-v1.md")

    server_protocol = extract_int(r"SYNC_PROTOCOL\s*=\s*(\d+)", server, "Windows SYNC_PROTOCOL")
    client_protocol = extract_int(r"const\s+val\s+PROTOCOL\s*=\s*(\d+)", client, "Android PROTOCOL")

    declared = {
        "windows manifest": int(windows_manifest["sync_protocol"]),
        "android manifest": int(android_manifest["sync_protocol"]),
        "test vectors": int(vectors["protocol"]),
        "Windows server": server_protocol,
        "Android client": client_protocol,
    }
    if len(set(declared.values())) != 1:
        raise AssertionError(f"Sync protocol drift detected: {declared}")

    protocol = server_protocol
    if f"Protocol version: `{protocol}`" not in protocol_doc:
        raise AssertionError("Protocol document version does not match code")

    required_server_messages = {
        'message.get("type")',
        '"pair"',
        '"hello"',
        '"command"',
        '"get_state"',
        '"state"',
        '"command_ok"',
        '"command_error"',
        '"PROTOCOL_MISMATCH"',
        '"STALE_REVISION"',
    }
    missing_server = sorted(token for token in required_server_messages if token not in server)
    if missing_server:
        raise AssertionError(f"Windows server contract tokens missing: {missing_server}")

    required_client_messages = {
        '"pair_ok"',
        '"hello_ok"',
        '"state"',
        '"command_ok"',
        '"command_error"',
        '"PROTOCOL_MISMATCH"',
        '"resource.change"',
    }
    missing_client = sorted(token for token in required_client_messages if token not in client)
    if missing_client:
        raise AssertionError(f"Android client contract tokens missing: {missing_client}")

    resource_vector = vectors.get("messages", {}).get("resource_change", {})
    if resource_vector.get("type") != "command":
        raise AssertionError("resource_change test vector must be a command")
    if resource_vector.get("action") != "resource.change":
        raise AssertionError("resource_change test vector action drifted")
    payload = resource_vector.get("payload", {})
    if payload.get("resource") not in {"HP", "Adversity", "IP"}:
        raise AssertionError("resource_change test vector uses an unsupported Phase 8 resource")

    print(f"Sync Protocol v{protocol} contract valid across manifests, code, docs and vectors")


if __name__ == "__main__":
    validate()
