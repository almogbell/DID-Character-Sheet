"""Safely update ONLY dialogs.BuddyStatCard; back up the original dialogs.py."""
from pathlib import Path
from datetime import datetime
import ast
import shutil

REPLACEMENT = 'class BuddyStatCard(QFrame):\n    """\n    Clickable card used for choosing Animal Buddy stats.\n    Cycles through die sizes when clicked.\n    """\n    def __init__(self, stat_name, die_size, click_callback):\n        super().__init__()\n        accent = {"agility": "#6F8F2C", "strength": "#A8453C",\n                  "finesse": "#356FA8", "instinct": "#6B55A6",\n                  "presence": "#2F8792", "knowledge": "#B17828"}.get(stat_name.lower(), "#96662a")\n        self.accent = accent\n        self.stat_name = stat_name\n        self.die_size = die_size\n        self.click_callback = click_callback\n\n        self.setFixedSize(90, 90)\n        self.setCursor(Qt.CursorShape.PointingHandCursor)\n        set_themed_stylesheet(self, f"""\n            QFrame {{\n                background-color: #fffdf8;\n                border: 2px solid {accent};\n                border-radius: 14px;\n            }}\n        """)\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(6, 6, 6, 6)\n        layout.setSpacing(2)\n\n        self.die_label = QLabel()\n        self.die_label.setAlignment(Qt.AlignmentFlag.AlignCenter)\n        set_themed_stylesheet(self.die_label, f"""\n            QLabel {{\n                border: none;\n                background: transparent;\n                font-size: 28px;\n                font-weight: 900;\n                color: {accent};\n            }}\n        """)\n\n        self.name_label = QLabel(stat_name.title())\n        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)\n        set_themed_stylesheet(self.name_label, f"""\n            QLabel {{\n                border: none;\n                background: transparent;\n                font-size: 13px;\n                font-weight: 900;\n                color: {accent};\n            }}\n        """)\n\n        layout.addStretch()\n        layout.addWidget(self.die_label)\n        layout.addStretch()\n        layout.addWidget(self.name_label)\n\n        self.refresh()\n\n    def refresh(self):\n        self.die_label.setText(f"d{self.die_size}")\n\n    def mousePressEvent(self, event):\n        self.click_callback(self.stat_name)\n'

def apply(target=None):
    path = Path(target) if target is not None else Path(__file__).resolve().parent / "dialogs.py"
    if not path.is_file():
        raise FileNotFoundError(f"Place this installer alongside your current dialogs.py: {path}")
    original = path.read_text(encoding="utf-8")
    tree = ast.parse(original)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BuddyStatCard"]
    if len(classes) != 1:
        raise RuntimeError("Expected exactly one BuddyStatCard class; no files changed.")
    node = classes[0]
    existing = "\n".join(original.splitlines()[node.lineno-1:node.end_lineno])
    if "self.die_label" not in existing or "self.name_label" not in existing:
        raise RuntimeError("Your BuddyStatCard differs too much; no files changed. Send your current dialogs.py.")
    if existing.strip() == REPLACEMENT.strip():
        print("BuddyStatCard already up to date. Nothing changed.")
        return
    lines = original.splitlines(keepends=True)
    final = "".join(lines[:node.lineno-1]) + REPLACEMENT + "".join(lines[node.end_lineno:])
    compile(final, str(path), "exec")
    backup = path.with_name(f"dialogs.py.before_buddy_colors_{datetime.now():%Y%m%d_%H%M%S}.bak")
    shutil.copy2(path, backup)
    path.write_text(final, encoding="utf-8")
    print(f"Updated only BuddyStatCard in {path.name}. Backup: {backup.name}")

if __name__ == "__main__":
    apply()
