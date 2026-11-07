"""Source regression guard for compact quantity controls (no Qt dependency)."""
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "inventory_ui.py"

class CompactQuantityTests(unittest.TestCase):
    def test_constructor_and_refresh_keep_old_compact_geometry(self):
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "InventoryRow")
        targets = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        for method_name in ("__init__", "apply_expanded_geometry"):
            method = targets[method_name]
            sizes = {}
            for n in ast.walk(method):
                if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute) or n.func.attr != "setFixedSize":
                    continue
                obj = n.func.value
                if not isinstance(obj, ast.Attribute) or not isinstance(obj.value, ast.Name) or obj.value.id != "self":
                    continue
                if len(n.args) != 2 or not all(isinstance(a, ast.Constant) for a in n.args):
                    continue
                sizes[obj.attr] = tuple(a.value for a in n.args)
            self.assertEqual(sizes.get("quantity_box"), (34, 38), method_name)
            self.assertEqual(sizes.get("plus_btn"), (24, 10), method_name)
            self.assertEqual(sizes.get("quantity_label"), (24, 14), method_name)
            self.assertEqual(sizes.get("minus_btn"), (24, 10), method_name)

    def test_quantity_is_centered_not_stretched(self):
        content = SRC.read_text(encoding="utf-8")
        self.assertIn("outer.addWidget(self.quantity_box, 0, Qt.AlignmentFlag.AlignVCenter)", content)
        self.assertIn("self.quantity_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)", content)
        self.assertIn("return max(self.quantity_box.height(), main_height)", content)

if __name__ == "__main__":
    unittest.main()
