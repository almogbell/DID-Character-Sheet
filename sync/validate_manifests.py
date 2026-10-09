from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATES = ROOT / "updates"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def load(name: str) -> dict:
    path = UPDATES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"{name} must contain a JSON object")
    return data


def require_version(value: object, field: str) -> str:
    if not isinstance(value, str) or not VERSION_RE.match(value):
        raise AssertionError(f"{field} must be a semantic version such as 1.0.10")
    return value


def require_protocol(value: object, field: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise AssertionError(f"{field} must be a {qualifier} integer")
    return value


def extract_android_code_constants() -> tuple[str, int, str]:
    view_model = (ROOT / "android" / "phase8" / "DidCompanionViewModel.kt").read_text(
        encoding="utf-8"
    )
    sync_client = (ROOT / "android" / "phase8" / "DidSyncClient.kt").read_text(
        encoding="utf-8"
    )

    version_match = re.search(r'const\s+val\s+ANDROID_VERSION\s*=\s*"([^"]+)"', view_model)
    minimum_match = re.search(r'const\s+val\s+MINIMUM_DESKTOP_VERSION\s*=\s*"([^"]+)"', view_model)
    protocol_match = re.search(r"const\s+val\s+PROTOCOL\s*=\s*(\d+)", sync_client)
    if not version_match:
        raise AssertionError("Could not find ANDROID_VERSION in DidCompanionViewModel.kt")
    if not minimum_match:
        raise AssertionError("Could not find MINIMUM_DESKTOP_VERSION in DidCompanionViewModel.kt")
    if not protocol_match:
        raise AssertionError("Could not find PROTOCOL in DidSyncClient.kt")
    return version_match.group(1), int(protocol_match.group(1)), minimum_match.group(1)


def version_parts(version: str) -> tuple[int, int, int]:
    core = version.split("-", 1)[0].split("+", 1)[0]
    major, minor, patch = core.split(".")
    return int(major), int(minor), int(patch)


def validate() -> None:
    windows = load("windows.json")
    android = load("android.json")

    assert windows.get("platform") == "windows"
    assert android.get("platform") == "android"

    windows_version = require_version(windows.get("version"), "windows.version")
    android_version = require_version(android.get("version"), "android.version")
    minimum_desktop = require_version(
        android.get("minimum_desktop_version"),
        "android.minimum_desktop_version",
    )

    # Protocol 0 explicitly means a released Windows build predates the mobile
    # companion. Android protocol numbers begin at 1.
    windows_protocol = require_protocol(
        windows.get("sync_protocol"),
        "windows.sync_protocol",
        allow_zero=True,
    )
    android_protocol = require_protocol(android.get("sync_protocol"), "android.sync_protocol")

    expected_windows_tag = f"v{windows_version}"
    if windows.get("tag") != expected_windows_tag:
        raise AssertionError(
            f"windows.tag must be {expected_windows_tag!r} for version {windows_version}"
        )

    expected_android_tag = f"android-v{android_version}"
    if android.get("tag") != expected_android_tag:
        raise AssertionError(
            f"android.tag must be {expected_android_tag!r} for version {android_version}"
        )

    windows_download = windows.get("download_url")
    windows_release = windows.get("release_url")
    if not isinstance(windows_download, str) or expected_windows_tag not in windows_download:
        raise AssertionError("windows.download_url must point at the declared Windows release")
    if not isinstance(windows_release, str) or expected_windows_tag not in windows_release:
        raise AssertionError("windows.release_url must point at the declared Windows release")

    android_download = android.get("download_url")
    android_release = android.get("release_url")
    if (android_download is None) != (android_release is None):
        raise AssertionError(
            "Android download_url and release_url must either both be null before the first release, "
            "or both be populated"
        )
    if android_download is not None:
        if not isinstance(android_download, str) or expected_android_tag not in android_download:
            raise AssertionError("android.download_url must point at the declared Android release")
        if not isinstance(android_release, str) or expected_android_tag not in android_release:
            raise AssertionError("android.release_url must point at the declared Android release")

    windows_is_compatible_release = version_parts(windows_version) >= version_parts(minimum_desktop)
    if windows_is_compatible_release and windows_protocol != android_protocol:
        raise AssertionError(
            "The advertised compatible Windows release must use the Android sync protocol "
            f"(windows={windows_protocol}, android={android_protocol})"
        )

    # During development an unpublished Android build may target the next
    # sync-enabled Windows release. Once Android is actually published, that
    # Windows release must already be advertised and speak the same protocol.
    if android_download is not None:
        if not windows_is_compatible_release:
            raise AssertionError(
                "Published Android release requires a Windows version newer than updates/windows.json"
            )
        if windows_protocol != android_protocol:
            raise AssertionError(
                "Published Android release and advertised Windows release use different sync protocols"
            )

    code_version, code_protocol, code_minimum_desktop = extract_android_code_constants()
    if code_version != android_version:
        raise AssertionError(
            "Android code version and updates/android.json differ "
            f"(code={code_version}, manifest={android_version})"
        )
    if code_protocol != android_protocol:
        raise AssertionError(
            "DidSyncClient.PROTOCOL and updates/android.json differ "
            f"(code={code_protocol}, manifest={android_protocol})"
        )
    if code_minimum_desktop != minimum_desktop:
        raise AssertionError(
            "DidCompanionViewModel.MINIMUM_DESKTOP_VERSION and updates/android.json differ "
            f"(code={code_minimum_desktop}, manifest={minimum_desktop})"
        )

    print(
        "Update manifests valid: "
        f"Windows {windows_version} (protocol {windows_protocol}), "
        f"Android {android_version} (protocol {android_protocol}), "
        f"minimum desktop {minimum_desktop}"
    )


if __name__ == "__main__":
    validate()
