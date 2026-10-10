from __future__ import annotations

import py_compile
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
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_ui.py").is_file():
            return root

    raise FileNotFoundError(
        "Could not find the DID project. Put this script in the phase6 folder "
        "inside your current code folder and run it from there."
    )


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    text = path.read_text(encoding="utf-8")

    if "    QWidget,\n" not in text:
        if "    QTabWidget,\n" in text:
            text = text.replace(
                "    QTabWidget,\n",
                "    QTabWidget,\n    QWidget,\n",
                1,
            )
        elif "    QFrame,\n" in text:
            text = text.replace(
                "    QFrame,\n",
                "    QFrame,\n    QWidget,\n",
                1,
            )
        else:
            raise RuntimeError("Could not locate the PySide6.QtWidgets import block.")

        path.write_text(text, encoding="utf-8")
        print("QWidget import: FIXED")
    else:
        print("QWidget import: already present")

    py_compile.compile(str(path), doraise=True)
    print("Compile: PASS")
    print("Restart frontend_2_8.py and open Campaign again.")


if __name__ == "__main__":
    main()
