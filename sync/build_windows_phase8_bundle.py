from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"

FILES = (
    "mobile_sync_server.py",
    "mobile_sync_frontend_adapter.py",
    "mobile_companion_controller.py",
    "mobile_companion_dialog.py",
    "integrate_mobile_companion.py",
    "mobile_companion_requirements.txt",
    "phase8_apply.bat",
    "phase8_revert.bat",
)

README = """DID Character Sheet - Phase 8 Windows test package

This package is for the first Windows <-> Android companion test.

SAFE TEST METHOD
1. Make a COPY of your finished DID 'current code' folder.
2. Extract every file from this ZIP directly into that copied folder.
3. Double-click phase8_apply.bat.
4. Start DID normally from the copied folder.
5. Tools will contain Mobile Companion.

phase8_apply.bat installs the QR dependency and patches frontend_2_8.py to the
first sync-enabled Windows version (1.0.11). The patcher creates
frontend_2_8.py.phase8.bak before modifying the frontend.

Double-click phase8_revert.bat to restore that backup.

Do not publish Windows 1.0.11 or Android 0.8.0 until the real-device acceptance
test has passed.
"""


def build(output: Path) -> Path:
    missing = [name for name in FILES if not (WINDOWS / name).is_file()]
    if missing:
        raise SystemExit(f"Missing bundle input files: {missing}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.write(WINDOWS / name, arcname=name)
        zf.writestr("PHASE8_README.txt", README)

    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
        expected = set(FILES) | {"PHASE8_README.txt"}
        if names != expected:
            raise AssertionError(f"Unexpected bundle contents: {sorted(names ^ expected)}")
        if zf.testzip() is not None:
            raise AssertionError("Created ZIP failed CRC validation")

    print(f"Created {output} ({output.stat().st_size} bytes)")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "DID_Phase8_Windows_Integration.zip",
    )
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
