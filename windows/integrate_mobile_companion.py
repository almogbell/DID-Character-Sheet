"""Safely integrate the Phase 8 mobile companion into the finished frontend.

The patcher makes two deliberately small, idempotent changes against the
finished 1.0.10 frontend:

1. Install MobileCompanionController after the confirmed BaseMainWindow startup
   sequence.
2. Add an explicit Mobile Companion row to the existing Tools menu immediately
   before Dice Roller.

The explicit menu row is intentional. The controller still has its event-filter
fallback, but the finished frontend should not depend on a QMenu Show event for
its primary entry point. If startup integration fails, the row remains visible
and shows the captured startup traceback instead of silently disappearing.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

INSTALL_MARKER = "# Phase 8: Windows <-> Android mobile companion"
MENU_MARKER = "# Phase 8: Mobile Companion Tools action"

# Match only the confirmed end-of-BaseMainWindow startup sequence, while
# tolerating blank lines and both LF/CRLF source files. Keeping this anchor
# intentionally narrow is safer than searching for a generic refresh_all().
BOOTSTRAP_RE = re.compile(
    r"(?P<indent>^[ \t]+)self\.setup_keyboard_shortcuts\(\)[ \t]*\r?\n"
    r"(?:[ \t]*\r?\n)*"
    r"(?P=indent)self\.refresh_all\(\)[ \t]*\r?\n"
    r"(?:[ \t]*\r?\n)*"
    r"(?P=indent)self\.reset_undo_history\([ \t]*\r?\n"
    r"(?P=indent)[ \t]+treat_current_as_clean=True[ \t]*\r?\n"
    r"(?P=indent)\)",
    re.MULTILINE,
)

# The finished Tools menu creates the Dice Roller submenu immediately after
# Edit Abilities. Insert our row immediately before that stable anchor.
MENU_ANCHOR_RE = re.compile(
    r'(?P<indent>^[ \t]+)dice_menu\s*=\s*menu\.addMenu\("Dice Roller"\)',
    re.MULTILINE,
)

VERSION_RE = re.compile(
    r'(?m)^(?P<prefix>\s*APP_VERSION\s*=\s*["\'])'
    r'(?P<version>\d+\.\d+\.\d+)'
    r'(?P<suffix>["\']\s*)$'
)


def integration_block(indent: str) -> str:
    inner = indent + "    "
    return (
        f"\n\n{indent}{INSTALL_MARKER}\n"
        f"{indent}self._mobile_companion_startup_error = None\n"
        f"{indent}try:\n"
        f"{inner}from mobile_companion_controller import install_mobile_companion\n"
        f"{inner}install_mobile_companion(\n"
        f"{inner}    self,\n"
        f"{inner}    CharacterStorageSystem,\n"
        f"{inner}    APP_VERSION,\n"
        f"{inner})\n"
        f"{indent}except Exception:\n"
        f"{inner}# Mobile support must never prevent the desktop sheet from opening.\n"
        f"{inner}self._mobile_companion_startup_error = traceback.format_exc()\n"
        f"{inner}traceback.print_exc()"
    )


def menu_block(indent: str) -> str:
    inner = indent + "    "
    return (
        f"{indent}{MENU_MARKER}\n"
        f"{indent}def open_mobile_companion_from_tools():\n"
        f"{inner}companion = getattr(self, \"mobile_companion\", None)\n"
        f"{inner}if companion is not None:\n"
        f"{inner}    companion.show_dialog()\n"
        f"{inner}    return\n"
        f"{inner}detail = getattr(self, \"_mobile_companion_startup_error\", None)\n"
        f"{inner}message = \"Mobile Companion did not initialize.\"\n"
        f"{inner}if detail:\n"
        f"{inner}    message += \"\\n\\n\" + str(detail)\n"
        f"{inner}QMessageBox.warning(self, \"Mobile Companion\", message)\n"
        f"\n"
        f"{indent}add_normal_action(\n"
        f"{inner}\"Mobile Companion\",\n"
        f"{inner}open_mobile_companion_from_tools,\n"
        f"{indent})\n\n"
    )


def patch_frontend_text(text: str, *, target_version: str | None = "1.0.11") -> str:
    """Return patched frontend text; safe to call repeatedly and on older Phase 8 patches."""
    if target_version is not None:
        match = VERSION_RE.search(text)
        if not match:
            raise ValueError("Could not find APP_VERSION assignment in frontend")
        text = VERSION_RE.sub(
            lambda m: m.group("prefix") + target_version + m.group("suffix"),
            text,
            count=1,
        )

    if INSTALL_MARKER not in text:
        match = BOOTSTRAP_RE.search(text)
        if not match:
            raise ValueError(
                "Could not find the confirmed BaseMainWindow startup anchor. "
                "Refusing to guess an insertion point."
            )
        text = text[: match.end()] + integration_block(match.group("indent")) + text[match.end() :]

    if MENU_MARKER not in text:
        menu_match = MENU_ANCHOR_RE.search(text)
        if not menu_match:
            raise ValueError(
                "Could not find the confirmed Dice Roller Tools-menu anchor. "
                "Refusing to report a successful integration without a visible Mobile Companion entry."
            )
        text = text[: menu_match.start()] + menu_block(menu_match.group("indent")) + text[menu_match.start() :]

    return text


def patch_frontend_file(
    path: Path,
    *,
    target_version: str | None = "1.0.11",
    backup: bool = True,
) -> bool:
    """Patch a frontend file in place. Returns True only when bytes changed."""
    original = path.read_text(encoding="utf-8")
    patched = patch_frontend_text(original, target_version=target_version)
    if patched == original:
        return False

    if backup:
        backup_path = path.with_suffix(path.suffix + ".phase8.bak")
        if not backup_path.exists():
            backup_path.write_text(original, encoding="utf-8")

    path.write_text(patched, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Integrate DID Phase 8 mobile companion")
    parser.add_argument("frontend", type=Path, help="Path to frontend_2_8.py")
    parser.add_argument(
        "--version",
        default="1.0.11",
        help="Sync-enabled Windows version (default: 1.0.11)",
    )
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    changed = patch_frontend_file(
        args.frontend,
        target_version=args.version,
        backup=not args.no_backup,
    )
    print("Phase 8 integration applied." if changed else "Phase 8 integration already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
