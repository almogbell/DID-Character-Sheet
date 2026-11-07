"""Focused tests for d100 label sizing and Roll Other Dice Enter behavior.

Runs without PySide6; tests dialog submission methods in an isolated Qt shim.
Run: python -m unittest -v test_did_d100_enter_readability_20261107
"""
import ast
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parent
PY_SOURCE = (ROOT / "frontend_2_8.py").read_text(encoding="utf-8")
D100_SOURCE = (ROOT / "d100_physics.js").read_text(encoding="utf-8")

class _Base:
    def accept(self):
        self.accepted = getattr(self, 'accepted', 0) + 1

    def eventFilter(self, watched, event):
        return False

    def keyPressEvent(self, event):
        self.other_keys = getattr(self, 'other_keys', 0) + 1

class _Button:
    def __init__(self): self.enabled = False
    def setEnabled(self, value): self.enabled = bool(value)
    def isEnabled(self): return self.enabled

class _Label:
    def setText(self, value): self.text = value

class _Count:
    def __init__(self, number): self.number = number
    def value(self): return self.number

class _Event:
    def __init__(self, key, event_type=6): self._key = key; self._event_type = event_type; self.handled=False
    def key(self): return self._key
    def type(self): return self._event_type
    def accept(self): self.handled=True

def get_dialog_class():
    root = ast.parse(PY_SOURCE)
    node = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == 'FantasyOtherDiceDialog')
    names = {'_submit_roll', 'accept', 'eventFilter', 'keyPressEvent', 'selected_counts', '_update_selection'}
    methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in names]
    copy_node = ast.ClassDef(name='TestOtherDiceDialog', bases=[ast.Name(id='_Base',ctx=ast.Load())], keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[copy_node],type_ignores=[]))
    qt = types.SimpleNamespace(Key=types.SimpleNamespace(Key_Return=13,Key_Enter=10))
    event = types.SimpleNamespace(Type=types.SimpleNamespace(KeyPress=6))
    ns = {'_Base':_Base, 'Qt':qt, 'QEvent':event}
    exec(compile(module,'<extracted FantasyOtherDiceDialog methods>','exec'),ns)
    return ns['TestOtherDiceDialog']

class EnterDialogTests(unittest.TestCase):
    def setUp(self):
        self.dialog = get_dialog_class()()
        self.dialog.dice_counts = {8: _Count(0), 100: _Count(0)}
        self.dialog.roll_button = _Button()
        self.dialog.selection_label = _Label()
        self.dialog._update_selection()

    def test_enter_in_numeric_field_rolls_once(self):
        self.dialog.dice_counts[8].number=2
        self.dialog._update_selection()
        event = _Event(13)
        self.assertTrue(self.dialog.eventFilter(self.dialog.dice_counts[8],event))
        self.assertEqual(self.dialog.accepted,1)

    def test_keypad_enter_in_numeric_field_rolls(self):
        self.dialog.dice_counts[100].number=1
        self.dialog._update_selection()
        self.assertTrue(self.dialog.eventFilter(self.dialog.dice_counts[100],_Event(10)))
        self.assertEqual(self.dialog.accepted,1)

    def test_enter_with_no_dice_keeps_dialog_open(self):
        self.assertTrue(self.dialog.eventFilter(self.dialog.dice_counts[8],_Event(13)))
        self.assertEqual(getattr(self.dialog,'accepted',0),0)

    def test_enter_over_limit_keeps_dialog_open(self):
        self.dialog.dice_counts[8].number=31
        self.dialog._update_selection()
        self.dialog.keyPressEvent(_Event(13))
        self.assertEqual(getattr(self.dialog,'accepted',0),0)

    def test_enter_with_dialog_focus_rolls(self):
        self.dialog.dice_counts[8].number=1
        self.dialog._update_selection()
        event = _Event(13)
        self.dialog.keyPressEvent(event)
        self.assertTrue(event.handled)
        self.assertEqual(self.dialog.accepted,1)

    def test_escape_delegates_to_standard_qt_dialog(self):
        self.dialog.keyPressEvent(_Event(27))
        self.assertEqual(self.dialog.other_keys,1)

    def test_roll_button_is_default_and_installs_event_filters(self):
        dialog = PY_SOURCE.split('class FantasyOtherDiceDialog(QDialog):',1)[1].split('class FantasyDiceOptionsDialog',1)[0]
        self.assertIn('counter.installEventFilter(self)', dialog)
        self.assertIn('self.roll_button.setDefault(True)', dialog)
        self.assertIn('cancel.clicked.connect(self.reject)', dialog)

class D100NumeralTests(unittest.TestCase):
    def test_higher_resolution_with_font_fit_and_contrast(self):
        self.assertIn('canvas.width = canvas.height = 192;', D100_SOURCE)
        self.assertIn('const horizontalFit = Math.min(1, 220 / Math.max(1, measuredWidth));', D100_SOURCE)
        self.assertIn('ctx.scale(horizontalFit, 1);', D100_SOURCE)
        self.assertIn("const ink = lightInk ? '#fffdf5' : '#15131c';", D100_SOURCE)
        self.assertIn('ctx.strokeText(text, 0, 0);', D100_SOURCE)

    def test_label_geometry_enlarged_without_changing_physics(self):
        self.assertIn('const side=inradius*Math.SQRT2*.97;', D100_SOURCE)
        self.assertIn('linearDamping:.50,angularDamping:.75', D100_SOURCE)
        self.assertIn('instance.value=candidate.value;', D100_SOURCE)

if __name__=='__main__': unittest.main()
