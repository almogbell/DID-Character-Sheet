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


def version_key(value: str) -> tuple[int, int, int]:
    core = value.strip().removeprefix("v").split("-", 1)[0].split("+", 1)[0]
    return tuple(int(part) for part in core.split("."))


def protocol_from_table(table: dict, version: str) -> int:
    selected = 0
    previous_minimum = None
    previous_protocol = -1
    for rule in table.get("protocol_releases", []):
        minimum = str(rule["minimum_windows_version"])
        protocol = int(rule["sync_protocol"])
        if protocol < 1:
            raise AssertionError("Compatibility-table protocols must start at 1")
        if previous_minimum is not None and version_key(minimum) <= version_key(previous_minimum):
            raise AssertionError("Windows protocol compatibility rules must be ordered by version")
        if protocol <= previous_protocol:
            raise AssertionError("Windows protocol compatibility numbers must increase")
        if version_key(version) >= version_key(minimum):
            selected = protocol
        previous_minimum = minimum
        previous_protocol = protocol
    return selected


def validate() -> None:
    windows_manifest = json.loads(read("updates/windows.json"))
    android_manifest = json.loads(read("updates/android.json"))
    vectors = json.loads(read("sync/test-vectors.json"))
    compatibility = json.loads(read("sync/windows_protocol_compatibility.json"))

    server = read("windows/mobile_sync_server.py")
    client = read("android/phase8/DidSyncClient.kt")
    view_model = read("android/phase8/DidCompanionViewModel.kt")
    protocol_doc = read("sync/protocol-v1.md")

    server_protocol = extract_int(r"SYNC_PROTOCOL\s*=\s*(\d+)", server, "Windows SYNC_PROTOCOL")
    client_protocol = extract_int(r"const\s+val\s+PROTOCOL\s*=\s*(\d+)", client, "Android PROTOCOL")

    active_contract = {
        "android manifest": int(android_manifest["sync_protocol"]),
        "test vectors": int(vectors["protocol"]),
        "Windows Phase 8 server": server_protocol,
        "Android client": client_protocol,
    }
    if len(set(active_contract.values())) != 1:
        raise AssertionError(f"Sync protocol drift detected: {active_contract}")

    protocol = server_protocol
    windows_release_protocol = int(windows_manifest["sync_protocol"])
    windows_version = str(windows_manifest["version"])
    minimum_desktop = str(android_manifest["minimum_desktop_version"])

    table_release_protocol = protocol_from_table(compatibility, windows_version)
    if table_release_protocol != windows_release_protocol:
        raise AssertionError(
            "updates/windows.json does not match windows_protocol_compatibility.json "
            f"(manifest={windows_release_protocol}, table={table_release_protocol})"
        )

    required_protocol_at_android_minimum = protocol_from_table(compatibility, minimum_desktop)
    if required_protocol_at_android_minimum != protocol:
        raise AssertionError(
            "Android minimum_desktop_version does not map to its active sync protocol "
            f"(minimum={minimum_desktop}, table={required_protocol_at_android_minimum}, code={protocol})"
        )

    if version_key(windows_version) >= version_key(minimum_desktop):
        if windows_release_protocol != protocol:
            raise AssertionError(
                "Advertised compatible Windows release does not match the Phase 8 protocol "
                f"(release={windows_release_protocol}, code={protocol})"
            )
    elif windows_release_protocol != 0:
        raise AssertionError(
            "A Windows release older than Android minimum_desktop_version must advertise "
            "sync_protocol 0 rather than claiming Phase 8 compatibility"
        )

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
    }
    missing_client = sorted(token for token in required_client_messages if token not in client)
    if missing_client:
        raise AssertionError(f"Android client contract tokens missing: {missing_client}")

    # Protocol v1 still supports the original relative resource.change vector,
    # but the current Android UI deliberately uses absolute resource.set commands
    # so rapid Heart/AT taps cannot be applied against stale values.
    if '"resource.set"' not in view_model:
        raise AssertionError("Current Android companion must use absolute resource.set commands")

    resource_vector = vectors.get("messages", {}).get("resource_change", {})
    if resource_vector.get("type") != "command":
        raise AssertionError("resource_change test vector must be a command")
    if resource_vector.get("action") != "resource.change":
        raise AssertionError("resource_change test vector action drifted")
    payload = resource_vector.get("payload", {})
    if payload.get("resource") not in {"HP", "Adversity", "IP"}:
        raise AssertionError("resource_change test vector uses an unsupported Phase 8 resource")

    print(
        f"Sync Protocol v{protocol} contract valid; Windows {windows_version} "
        f"correctly advertises release protocol {windows_release_protocol}"
    )


if __name__ == "__main__":
    validate()
