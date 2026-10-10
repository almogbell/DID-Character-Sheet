from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"

FILES = (
    "mobile_sync_frontend_adapter.py",
    "mobile_sync_server.py",
    "mobile_sync_v7.py",
    "mobile_companion_dialog.py",
)

README = """DID Character Sheet - Phase 9 V8 desktop delta

Use this after the Phase 8 Windows companion is already installed and working.

1. Close the Windows DID app.
2. Copy all four Python files from this ZIP into the same current-code folder:
   mobile_sync_frontend_adapter.py
   mobile_sync_server.py
   mobile_sync_v7.py
   mobile_companion_dialog.py
3. Replace the older files when Windows asks.
4. Start DID normally. You do NOT need to patch frontend_2_8.py again.

V8 keeps the authoritative V7 mobile editing/dice actions and adds the pairing QR
fix: the Windows QR is generated with high error correction, displayed larger,
and scaled without smoothing so phone cameras see crisp square modules.
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
