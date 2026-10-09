from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "updates" / "android.json"
REPOSITORY = "almogbell/DID-Character-Sheet"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    version = args.version.strip().removeprefix("android-v").removeprefix("v")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("version") != version:
        raise SystemExit(
            f"Manifest version {data.get('version')!r} does not match release version {version!r}"
        )

    tag = f"android-v{version}"
    filename = f"DID_Character_Sheet_Android_{version}.apk"
    data["tag"] = tag
    data["download_url"] = (
        f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}"
    )
    data["release_url"] = f"https://github.com/{REPOSITORY}/releases/tag/{tag}"

    MANIFEST.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Finalized Android {version} manifest for {tag}")


if __name__ == "__main__":
    main()
