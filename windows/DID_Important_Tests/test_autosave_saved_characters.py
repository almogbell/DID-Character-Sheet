"""Problem 4 follow-up: source-level Windows autosave invariants.

Runs without PySide6: python -m unittest discover -s DID_Important_Tests
    -p test_autosave_saved_characters.py -v
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend_2_8.py"
DISPLAY = ROOT / "character_display_ui.py"


def load_autosave_class():
    module = ast.parse(FRONTEND.read_text(encoding="utf-8"))
    base = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == 'BaseMainWindow')
    method_names = {'mark_dirty', 'schedule_auto_save', 'auto_save_character'}
    methods = [node for node in base.body if isinstance(node, ast.FunctionDef) and node.name in method_names]
    assert len(methods) == len(method_names)
    code = ast.Module(body=[ast.ClassDef(name='AutosaveMethods', bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
    namespace = {'schedule_campaign_state_sync': lambda window: setattr(window, 'campaign_sync', window.campaign_sync + 1)}
    exec(compile(ast.fix_missing_locations(code), '<autosave_methods>', 'exec'), namespace)
    return namespace['AutosaveMethods']


class FakeTimer:
    def __init__(self):
        self.starts = 0
    def start(self):
        self.starts += 1


class TestHarness(load_autosave_class()):
    def __init__(self, *, path='saved.didchar', readonly=False, restored=False):
        self.character = type('Character', (), {'name': 'Aurora'})()
        self.current_character_filepath = path
        self.readonly = readonly
        self._history_restore_pending = restored
        self.unsaved_changes = False
        self.supress_dirty = False
        self._auto_save_in_progress = False
        self._auto_save_timer = FakeTimer()
        self.campaign_sync = 0
        self.saves = []
        self.save_status_label = type('Label', (), {'setText': lambda obj, t: setattr(obj, 'text', t), 'setToolTip': lambda obj, t: setattr(obj, 'tooltip', t)})()
    def is_readonly_character(self):
        return self.readonly
    def _record_undo_state(self):
        pass
    def setWindowModified(self, _):
        pass
    def schedule_recovery_write(self):
        pass
    def save_character_from_ui(self, quiet=False):
        self.saves.append(quiet)
        self.unsaved_changes = False


class AutosaveTests(unittest.TestCase):
    def test_default_mark_dirty_schedules(self):
        w = TestHarness()
        w.mark_dirty()
        self.assertEqual(w._auto_save_timer.starts, 1)
        self.assertEqual(w.save_status_label.text, 'Unsaved')
        self.assertEqual(w.saves, [])
        w.auto_save_character()
        self.assertEqual(w.saves, [True])
    def test_explicit_autosave_is_coalesced(self):
        w = TestHarness()
        w.mark_dirty(auto_save=True)
        self.assertEqual(w.saves, [])
        self.assertEqual(w._auto_save_timer.starts, 1)
    def test_hp_and_at_have_dirty_hooks(self):
        src = DISPLAY.read_text(encoding='utf-8')
        self.assertIn('class HeartsPanel', src)
        self.assertIn('class ATWidget', src)
        self.assertIn('window.mark_dirty()', src[src.index('class HeartsPanel'):src.index('class ATWidget')])
        self.assertIn('window.mark_dirty()', src[src.index('class ATWidget'):src.index('class CharacterDisplayMixin')])
    def test_new_character_needs_first_save(self):
        w = TestHarness(path=None)
        w.mark_dirty()
        self.assertEqual(w._auto_save_timer.starts, 0)
        w.auto_save_character()
        self.assertEqual(w.saves, [])
    def test_readonly_cannot_autosave(self):
        w = TestHarness(readonly=True)
        w.mark_dirty()
        self.assertEqual(w._auto_save_timer.starts, 0)
        w.auto_save_character()
        self.assertEqual(w.saves, [])
    def test_restored_history_is_not_overwritten(self):
        w = TestHarness(restored=True)
        w.mark_dirty()
        self.assertEqual(w._auto_save_timer.starts, 0)
        w.auto_save_character()
        self.assertEqual(w.saves, [])
    def test_cleared_dirty_flag_skips_stale_timer(self):
        w = TestHarness()
        w.mark_dirty()
        w.unsaved_changes = False
        w.auto_save_character()
        self.assertEqual(w.saves, [])
    def test_name_required_for_background_save(self):
        w = TestHarness()
        w.character.name = ''
        w.mark_dirty()
        w.auto_save_character()
        self.assertEqual(w.saves, [])
    def test_autosave_does_not_repeat_reentrant_request(self):
        w = TestHarness()
        w.mark_dirty()
        w._auto_save_in_progress = True
        w.auto_save_character()
        self.assertEqual(w.saves, [])
        self.assertEqual(w._auto_save_timer.starts, 2)
    def test_initialization_and_quiet_save_are_wired(self):
        src = FRONTEND.read_text(encoding='utf-8')
        self.assertIn('self._auto_save_timer.timeout.connect(self.auto_save_character)', src)
        self.assertIn('self._auto_save_timer.setSingleShot(True)', src)
        self.assertIn('def save_character_from_ui(self, quiet=False)', src)
        self.assertIn('self.save_character_from_ui(quiet=True)', src)
        self.assertIn('self.save_status_label.setText("Saved")', src)


if __name__ == '__main__':
    unittest.main()
