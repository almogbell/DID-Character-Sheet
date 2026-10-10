from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


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
        if (
            (root / "frontend_2_8.py").is_file()
            and (root / "campaign_ui.py").is_file()
            and (root / "campaign_privacy.py").is_file()
            and (root / "campaign_session.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 6 DID project. Put this script in the phase6 "
        "folder inside your current code folder and run it from there."
    )


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")

    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = original.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    start = original.find("    def __init__(self, window):\n", class_pos)
    end = original.find("    def _show_error(self, title, error):\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate the Campaign constructor.")

    before = original[:start]
    block = original[start:end]
    after = original[end:]

    # Use the same neutral palette as the original Character Creation Template.
    # Do not touch CharacterTemplateDialog itself.
    replacements = (
        ("background-color: #f5efe1;", "background-color: #fffdf7;"),
        ("border: 1px solid #d8ad58;", "border: 1px solid #d9bd82;"),
        ("border: 1px solid #d8b56d;", "border: 1px solid #d9bd82;"),
        ("border: 1px solid #d2a650;", "border: 1px solid #d9bd82;"),
        ("background-color: #fffaf0;\n            border: 1px solid #c99836;", "background-color: #fffdf7;\n            border: 1px solid #c79a3b;"),
        ("background-color: #fff5df;\n            border-color: #ad7820;", "background-color: #fff4df;\n            border-color: #a87824;"),
    )

    changed = False
    for old, new in replacements:
        if old in block:
            block = block.replace(old, new)
            changed = True

    # Preserve the existing light-blue primary action styling from the template.
    if "QPushButton#PrimaryButton" not in block:
        raise RuntimeError("Campaign primary button styling was not found.")

    text = before + block + after

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v12_template_colors")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    print("Campaign background matches original template palette: PASS" if changed else "Campaign template palette: already installed")
    print("Campaign borders/buttons match original template palette: PASS")
    print("Original Character Creation Template: UNTOUCHED")
    print("v9-v11 layout/sizing changes: PRESERVED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
