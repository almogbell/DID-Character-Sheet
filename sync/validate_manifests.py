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


def require_protocol(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AssertionError(f"{field} must be a positive integer")
    return value


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

    windows_protocol = require_protocol(windows.get("sync_protocol"), "windows.sync_protocol")
    android_protocol = require_protocol(android.get("sync_protocol"), "android.sync_protocol")
    if windows_protocol != android_protocol:
        raise AssertionError(
            "Windows and Android manifests must declare the same sync_protocol "
            f"(windows={windows_protocol}, android={android_protocol})"
        )

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

    # A minimum desktop newer than the currently advertised Windows app would make
    # the current Android release impossible to use with the current Windows release.
    def parts(version: str) -> tuple[int, int, int]:
        core = version.split("-", 1)[0].split("+", 1)[0]
        major, minor, patch = core.split(".")
        return int(major), int(minor), int(patch)

    if parts(minimum_desktop) > parts(windows_version):
        raise AssertionError(
            "android.minimum_desktop_version cannot be newer than updates/windows.json"
        )

    print(
        "Update manifests valid: "
        f"Windows {windows_version}, Android {android_version}, protocol {windows_protocol}"
    )


if __name__ == "__main__":
    validate()
