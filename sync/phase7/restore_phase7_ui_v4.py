from __future__ import annotations

import py_compile
from pathlib import Path


FIT_V4 = '''def _fit_button(button):
    # Match the Character Creation Template buttons while leaving enough room
    # for bold Georgia text on Windows DPI scaling. The button wraps snugly
    # around the whole label instead of clipping its first/last characters.
    button.ensurePolished()
    text_width = button.fontMetrics().horizontalAdvance(button.text())
    button.setMinimumHeight(40)
    button.setFixedWidth(max(78, text_width + 56))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

CHECKBOX_V3 = '''def _prepare_sharing_checkbox(box, *, locked=False):
    # Restore the pre-v5 sharing checkbox geometry.
    box.setFixedSize(28, 28)
    box.setStyleSheet(
        "QCheckBox { padding:0px; margin:0px; min-height:28px; }"
        "QCheckBox::indicator { width:18px; height:18px; }"
    )
    if locked:
        box.setChecked(True)
        box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    else:
        box.setCursor(Qt.CursorShape.PointingHandCursor)
    return box
'''


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])
    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_role_ui.py").is_file():
            return root
    raise FileNotFoundError(
        "Could not find the installed Phase 7 DID project. Keep the phase7 folder "
        "inside the current code folder and run this script from there."
    )


def replace_top_level_function(text: str, signature: str, replacement: str, next_name: str):
    start = text.find(f"def {signature}")
    if start < 0:
        raise RuntimeError(f"Could not locate {signature}")
    end = text.find(f"\n\ndef {next_name}", start)
    if end < 0:
        raise RuntimeError(f"Could not locate function after {signature}")
    return text[:start] + replacement.rstrip("\n") + text[end:]


def patch(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    # Restore the exact v4 button geometry.
    start = text.find("def _fit_button(button):\n")
    if start < 0:
        raise RuntimeError("Could not locate _fit_button")
    end = text.find("\n\ndef _prepare_sharing_checkbox", start)
    if end < 0:
        end = text.find("\n\ndef _campaign_rules_rows", start)
    if end < 0:
        raise RuntimeError("Could not locate end of _fit_button")
    text = text[:start] + FIT_V4.rstrip("\n") + text[end:]

    # Restore the checkbox helper used immediately before v5.
    if "def _prepare_sharing_checkbox" not in text:
        raise RuntimeError("Could not locate _prepare_sharing_checkbox")
    text = replace_top_level_function(
        text,
        "_prepare_sharing_checkbox(box, *, locked=False):",
        CHECKBOX_V3,
        "_confirm_character_removal",
    )

    # Preserve the functional crash guards added before the v5 visual change.
    required = (
        "button.setMinimumHeight(40)",
        "button.setFixedWidth(max(78, text_width + 56))",
        "box.setFixedSize(28, 28)",
        "QCheckBox::indicator { width:18px; height:18px; }",
        'self._dm_prefs = normalize_privacy_preferences()',
        'if not hasattr(self, "_dm_prefs"):',
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("Phase 7 v4 restore verification failed: " + ", ".join(missing))

    if text != original:
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)


def main():
    root = find_project_root()
    patch(root / "campaign_role_ui.py")
    print("Pre-v5 button sizing restored: PASS")
    print("Pre-v5 sharing checkbox sizing restored: PASS")
    print("Player sharing crash guards preserved: PASS")
    print("Compile: PASS")


if __name__ == "__main__":
    main()
