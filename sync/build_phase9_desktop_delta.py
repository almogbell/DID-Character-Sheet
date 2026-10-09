from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"

FILES = (
    "mobile_sync_frontend_adapter.py",
)

README = """DID Character Sheet - Phase 9 desktop delta

Use this only after the Phase 8 Windows companion is already working.

1. Close the Windows DID app.
2. Replace mobile_sync_frontend_adapter.py in the same current-code test folder
   with the file from this ZIP.
3. Start DID normally. You do NOT need to patch frontend_2_8.py again.

This adds authoritative mobile commands for ordinary character name/backstory
text and Inventory add/edit/delete. Windows still validates, autosaves and
broadcasts the canonical state. Improvement/species/note rules are not copied
into Android.
"""


def build(output: Path) -> Path:
    missing = [name for name in FILES if not (WINDOWS / name).is_file()]
    if missing:
        raise SystemExit(f"Missing Phase 9 delta files: {missing}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.write(WINDOWS / name, arcname=name)
        zf.writestr("PHASE9_README.txt", README)

    with zipfile.ZipFile(output) as zf:
        if zf.testzip() is not None:
            raise AssertionError("Created Phase 9 ZIP failed CRC validation")

    print(f"Created {output} ({output.stat().st_size} bytes)")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "DID_Phase9_Desktop_Delta.zip",
    )
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
