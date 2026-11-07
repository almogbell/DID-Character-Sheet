"""Resolve the DID application folder without depending on stale absolute paths."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = (
    "frontend_2_8.py",
    "backend_2_1.py",
    "character_API.py",
    "notes_ui.py",
    "improvements_ui.py",
)


def _is_app_dir(path: Path) -> bool:
    return all((path / name).is_file() for name in REQUIRED)


def _normalise_app_path(value: str, *, relative_to: Path = HERE) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip().strip('"')))
    path = Path(expanded)
    if not path.is_absolute():
        path = relative_to / path
    path = path.resolve()
    if path.is_file() and path.name.lower() == "frontend_2_8.py":
        path = path.parent
    return path


def app_dir() -> Path:
    """Return the app folder used by the tests.

    Priority:
      1. DID_APP_DIR / --app: explicit caller override.
      2. The parent of DID_Important_Tests: normal portable project layout.
      3. app_path.txt: fallback for tests stored somewhere else.

    This prevents an old absolute path in app_path.txt from silently making the
    tests exercise a different copy of the DID application.
    """
    explicit = os.environ.get("DID_APP_DIR", "").strip()
    if explicit:
        path = _normalise_app_path(explicit)
    else:
        local_app = HERE.parent.resolve()
        if _is_app_dir(local_app):
            path = local_app
        else:
            config = HERE / "app_path.txt"
            configured = (
                config.read_text(encoding="utf-8-sig").strip()
                if config.exists() else ""
            )
            if not configured:
                raise RuntimeError(
                    "Could not find the DID app beside DID_Important_Tests. "
                    "Move the test folder inside the app folder, set DID_APP_DIR, "
                    "use --app, or put the app path in app_path.txt."
                )
            path = _normalise_app_path(configured, relative_to=HERE)

    missing = [name for name in REQUIRED if not (path / name).is_file()]
    if missing:
        raise RuntimeError(f"Wrong app folder {path}; missing {', '.join(missing)}")

    # Always put the chosen app first. If it was already present later in
    # sys.path, move it to the front so another project copy cannot win imports.
    app_text = str(path)
    sys.path[:] = [entry for entry in sys.path if entry != app_text]
    sys.path.insert(0, app_text)
    return path


def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
