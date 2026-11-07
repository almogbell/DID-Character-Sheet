"""Qt-free geometry contract tests for InventoryRow.required_height.

Run with: python -m unittest test_problem02_inventory_geometry.py -v
These tests simulate the sizing calculation; they do not replace a Qt visual test.
"""
from __future__ import annotations
import ast
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent.parent

def load_sizing_function():
    tree = ast.parse((HERE / "inventory_ui.py").read_text(encoding="utf-8"))
    row = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "InventoryRow")
    method = next(n for n in row.body if isinstance(n, ast.FunctionDef) and n.name == "required_height")
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, "InventoryRow.required_height", "exec"), ns)
    return ns["required_height"]


class Margins:
    def __init__(self, l=0, t=0, r=0, b=0):
        self.l, self.t, self.r, self.b = l, t, r, b
    def left(self): return self.l
    def right(self): return self.r
    def top(self): return self.t
    def bottom(self): return self.b


class Widget:
    def __init__(self, text="", width=0, height=0):
        self._text, self._width, self._height = text, width, height
        self.visible = True
    def width(self): return self._width
    def height(self): return self._height
    def setFixedWidth(self, value): self._width = value
    def setFixedHeight(self, value): self._height = value
    def minimumWidth(self): return self._width
    def sizeHint(self): return self
    def text(self): return self._text
    def setVisible(self, v): self.visible = v


class Layout:
    def __init__(self, widgets=(), margins=None, spacing=0):
        self.items = list(widgets)
        self._margins = margins or Margins()
        self._spacing = spacing
    def contentsMargins(self): return self._margins
    def spacing(self): return self._spacing
    def count(self): return len(self.items)
    def itemAt(self, i): return Item(self.items[i])


class Item:
    def __init__(self, widget): self._widget = widget
    def widget(self): return self._widget


class Container(Widget):
    def __init__(self, layout, **kwargs):
        super().__init__(**kwargs)
        self._layout = layout
    def layout(self): return self._layout


class FakeRow:
    required_height = load_sizing_function()
    def __init__(self, title, description, expanded=False, linked_icons=0):
        self.item = type("ItemModel", (), {"expanded": expanded})()
        self.arrow_btn = Widget(width=18, height=18)
        self.name_label = Widget(text=title)
        self.remove_btn = Widget(width=16, height=16)
        icons = [Widget(width=22, height=22) for _ in range(linked_icons)]
        header = Layout([self.arrow_btn, self.name_label, *icons, self.remove_btn], spacing=5)
        self.header_widget = Container(header)
        self.description_label = Widget(text=description, height=80)
        self.main_box = Container(Layout([self.header_widget, self.description_label],
                                         Margins(12, 4, 6, 4), spacing=0))
        self.quantity_box = Widget(width=34, height=38)
        self._outer = Layout([self.main_box, self.quantity_box], spacing=5)
    def layout(self): return self._outer
    @staticmethod
    def _wrapped_text_height(label, width):
        if not label.text(): return 0
        # A predictable fake wrapped-font model; Qt text measurement is tested on Windows.
        lines = sum(max(1, (len(chunk) * 8 + width - 1) // max(1, width))
                    for chunk in label.text().split("\n"))
        return lines * 17


class InventoryGeometryTests(unittest.TestCase):
    def test_quantity_stays_fixed_centerable(self):
        row = FakeRow("Healing potion", "A very long description " * 25, True)
        self.assertGreater(row.required_height(310), 38)
        self.assertEqual((row.quantity_box.width(), row.quantity_box.height()), (34, 38))
        row.item.expanded = False
        self.assertEqual(row.required_height(310), 38)
        self.assertEqual(row.description_label.height(), 0)
        self.assertFalse(row.description_label.visible)
        self.assertEqual((row.quantity_box.width(), row.quantity_box.height()), (34, 38))

    def test_linked_note_icons_reduce_name_width(self):
        plain = FakeRow("Very long inventory name needing two or more wrapped lines", "")
        linked = FakeRow("Very long inventory name needing two or more wrapped lines", "", linked_icons=3)
        plain.required_height(310)
        linked.required_height(310)
        self.assertLess(linked.name_label.width(), plain.name_label.width())
        self.assertGreaterEqual(linked.header_widget.height(), 22)
        available = 310 - 34 - 5 - 12 - 6
        controls = 18 + 16 + 3 * 22
        gaps = 5 * 5  # five header widgets total = four gaps? name + 5 controls = 5 gaps
        self.assertLessEqual(linked.name_label.width() + controls + gaps, available)

    def test_expanded_newlines_are_measured(self):
        row = FakeRow("Potion", "Line one\nLine two\nLine three", True)
        height = row.required_height(260)
        self.assertGreater(height, 38)
        self.assertTrue(row.description_label.visible)
        row.item.expanded = False
        self.assertEqual(row.required_height(260), 38)


if __name__ == "__main__":
    unittest.main()
