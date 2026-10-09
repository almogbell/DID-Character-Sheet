from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "updates" / "windows.json"
COMPATIBILITY = ROOT / "sync" / "windows_protocol_compatibility.json"


def version_key(value: str) -> tuple[int, int, int]:
    value = value.strip().removeprefix("v")
    core = value.split("-", 1)[0].split("+", 1)[0]
    return tuple(int(part) for part in core.split("."))


def protocol_for(version: str) -> int:
    data = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    selected = 0
    for rule in data.get("protocol_releases", []):
        minimum = str(rule["minimum_windows_version"])
        if version_key(version) >= version_key(minimum):
            selected = max(selected, int(rule["sync_protocol"]))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--release-url", required=True)
    args = parser.parse_args()

    version = args.version.strip().removeprefix("v")
    expected_tag = f"v{version}"
    if args.tag != expected_tag:
        raise SystemExit(f"Expected Windows tag {expected_tag!r}, got {args.tag!r}")
    if not args.download_url.lower().endswith(".exe"):
        raise SystemExit("Windows release manifest must point to an .exe installer")
    if expected_tag not in args.download_url or expected_tag not in args.release_url:
        raise SystemExit("Windows release URLs do not contain the release tag")

    data = {
        "platform": "windows",
        "version": version,
        "tag": expected_tag,
        "sync_protocol": protocol_for(version),
        "download_url": args.download_url,
        "release_url": args.release_url,
    }
    MANIFEST.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Updated Windows manifest to {version} "
        f"(sync protocol {data['sync_protocol']})"
    )


if __name__ == "__main__":
    main()
