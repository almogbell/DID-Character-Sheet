"""Problem 03: Qt-free focused tests of the actual methods in the current source.

These test the real method bodies with simple stand-ins for Qt widgets.
They do NOT constitute a rendered Windows UI test.
"""
import ast
import copy
import pathlib
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]


def extract_method(filename, class_name, method_name):
    tree = ast.parse((ROOT / filename).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    method = copy.deepcopy(method)
    method.decorator_list = []
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), filename, 'exec'), namespace)
    return namespace[method_name]


class FakeContent:
    def __init__(self):
        self.visible = None
        self.updates = 0

    def setVisible(self, value):
        self.visible = value

    def updateGeometry(self):
        self.updates += 1


class FakeMainBox:
    def __init__(self):
        self.invalidated = 0

    def layout(self):
        return self

    def invalidate(self):
        self.invalidated += 1


class FakeButton:
    def __init__(self):
        self.label = ''

    def setText(self, label):
        self.label = label


class FakeOwner:
    def __init__(self):
        self.improvement_list_layout = SimpleNamespace(_items=[object()])
        self.remeasured = []
        self.full_refreshes = 0

    def refresh_improvement_scroll_geometry(self, *, changed_widget=None):
        self.remeasured.append(changed_widget)

    def refresh_improvements(self):
        self.full_refreshes += 1


class ImprovementLayoutTests(unittest.TestCase):
    def make_group(self, owner, paid):
        item = SimpleNamespace(expanded=False)
        group = SimpleNamespace(
            expanded=False,
            content_widget=FakeContent(),
            expand_btn=FakeButton(),
            main_box=FakeMainBox(),
            updateGeometry=lambda: None,
        )
        if paid:
            group.owner = owner
            group.purchases = [item]
        else:
            group.window = lambda: owner
            group.skilled_improvements = [item]
        return group, item

    def test_skilled_at_toggle_remeasures_only_clicked_group(self):
        fn = extract_method('improvements_ui.py', 'SkilledAtGroupRow', 'toggle_expanded')
        self.assert_group_toggle(fn, paid=False)

    def test_paid_heightened_toggle_remeasures_only_clicked_group(self):
        fn = extract_method('improvements_ui.py', 'PaidHeightenedAbilityGroup', 'toggle_expanded')
        self.assert_group_toggle(fn, paid=True)

    def assert_group_toggle(self, fn, paid):
        owner = FakeOwner()
        group, item = self.make_group(owner, paid)
        fn(group)
        self.assertTrue(item.expanded)
        self.assertTrue(group.content_widget.visible)
        self.assertEqual(group.expand_btn.label, '▾')
        fn(group)
        self.assertFalse(item.expanded)
        self.assertFalse(group.content_widget.visible)
        self.assertEqual(group.expand_btn.label, '▸')
        self.assertEqual(owner.remeasured, [group, group])
        self.assertEqual(owner.full_refreshes, 0)
        self.assertEqual(group.main_box.invalidated, 2)

    def test_two_column_width_shrinks_without_forcing_old_180_px_min(self):
        tree = ast.parse((ROOT / 'frontend_2_8.py').read_text(encoding='utf-8'))
        helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'improvement_two_column_width')
        fn_namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(helper)], type_ignores=[])), 'frontend_2_8.py', 'exec'), fn_namespace)
        width = fn_namespace['improvement_two_column_width']
        self.assertEqual(width(400, 14), 193)
        self.assertEqual(width(305, 14), 145)
        self.assertEqual(width(100, 14), 43)
        self.assertEqual(width(10, 14), 1)

    def test_scroll_restore_limited_to_same_character(self):
        fn = extract_method('frontend_2_8.py', 'MainWindow', '_restore_improvement_scroll_position')
        class Bar:
            def __init__(self):
                self.value = 0
            def maximum(self):
                return 200
            def setValue(self, value):
                self.value = value
        bar = Bar()
        scroll = SimpleNamespace(verticalScrollBar=lambda: bar)
        owner = SimpleNamespace(character=SimpleNamespace(id='A'), improvement_scroll=scroll, _improvement_scroll_restore_generation=4)
        fn(owner, 'A', 99, 4)
        self.assertEqual(bar.value, 99)
        fn(owner, 'A', 10000, 4)
        self.assertEqual(bar.value, 200)
        owner.character.id = 'B'
        fn(owner, 'A', 10, 4)
        self.assertEqual(bar.value, 200)
        owner.character.id = 'A'
        fn(owner, 'A', 10, 3)  # Stale delayed callback; newer generation is 4.
        self.assertEqual(bar.value, 200)

    def test_hidden_scrollbar_policy_still_present(self):
        text = (ROOT / 'frontend_2_8.py').read_text(encoding='utf-8')
        start = text.index('self.improvement_scroll = QScrollArea()')
        snippet = text[start:start + 1000]
        self.assertIn('Qt.ScrollBarPolicy.ScrollBarAlwaysOff', snippet)


if __name__ == '__main__':
    unittest.main()
