"""Campaign species rules, duplicate prevention, and idle save regressions.

These tests use the actual backend and structurally inspect the Qt UI path
without requiring a running desktop, internet, or personal character files.
"""
from pathlib import Path
from types import SimpleNamespace
import ast
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend_2_1 import Character, ImprovementSystem
from species_ui_policy import is_species_required, species_field_visible, species_tool_visible

FRONTEND = (ROOT / 'frontend_2_8.py').read_text(encoding='utf-8')
DISPLAY = (ROOT / 'character_display_ui.py').read_text(encoding='utf-8')

class SpeciesRulesTests(unittest.TestCase):
    def character(self, mode=None):
        c = Character(id='species-test')
        if mode is not None:
            c.creation_rules_active = True
            c.creation_species_mode = mode
        return c

    def test_standalone_character_can_choose_species(self):
        c = self.character()
        self.assertTrue(species_tool_visible(c))
        self.assertFalse(species_field_visible(c))
        self.assertGreater(len(ImprovementSystem.get_species_options(c)), 0)

    def test_required_campaign_reveals_field_and_tool_before_selection(self):
        c = self.character('required')
        self.assertTrue(is_species_required(c))
        self.assertTrue(species_tool_visible(c))
        self.assertTrue(species_field_visible(c))

    def test_normal_and_disabled_campaign_hide_add_tool(self):
        for mode in ('normal', 'disabled'):
            with self.subTest(mode=mode):
                c = self.character(mode)
                self.assertFalse(species_tool_visible(c))
                self.assertFalse(species_field_visible(c))

    def test_changed_campaign_rules_update_visibility(self):
        c = self.character('normal')
        self.assertFalse(species_tool_visible(c))
        c.creation_species_mode = 'required'
        self.assertTrue(species_tool_visible(c))
        c.creation_species_mode = 'disabled'
        self.assertFalse(species_tool_visible(c))

    def test_owned_improvement_not_offered_as_species(self):
        c = self.character('required')
        candidates = ImprovementSystem.get_species_options(c)
        one = candidates[0]
        self.assertTrue(ImprovementSystem.add_from_catalog(c, one['catalog_id'], source='ip'))
        offered = {x['catalog_id'] for x in ImprovementSystem.get_species_options(c)}
        self.assertNotIn(one['catalog_id'], offered)
        self.assertFalse(ImprovementSystem.add_from_catalog(c, one['catalog_id'], source='species'))

    def test_species_selection_cannot_be_repeated(self):
        c = self.character('required')
        one = ImprovementSystem.get_species_options(c)[0]
        self.assertTrue(ImprovementSystem.add_from_catalog(c, one['catalog_id'], source='species'))
        self.assertFalse(ImprovementSystem.add_from_catalog(c, one['catalog_id'], source='species'))
        self.assertEqual([], ImprovementSystem.get_species_options(c))
        self.assertFalse(species_tool_visible(c))
        self.assertTrue(species_field_visible(c))
        c.creation_species_mode = 'disabled'
        self.assertTrue(species_field_visible(c), 'preserve previously selected species')

    def test_disabled_campaign_backend_picker_empty(self):
        c = self.character('disabled')
        self.assertEqual([], ImprovementSystem.get_species_options(c))

class UiWiringTests(unittest.TestCase):
    def test_species_field_opens_actual_picker(self):
        self.assertIn('class SpeciesSelectionField(QLineEdit)', FRONTEND)
        self.assertIn('self.species_label.activated.connect(self.choose_species_from_sheet)', FRONTEND)
        self.assertIn('self.species_label.setText(species_name)', FRONTEND)
        self.assertIn('species_field_visible(self.character)', FRONTEND)
        self.assertIn('species_tool_visible(self.character)', FRONTEND)
        self.assertIn('picker = ImprovementPickerDialog(options, self)', DISPLAY)
        self.assertIn('source="species"', DISPLAY)

    def test_idle_timer_does_not_replace_fast_autosave(self):
        self.assertIn('self._auto_save_timer.setInterval(1100)', FRONTEND)
        self.assertIn('self._idle_save_timer.setInterval(60_000)', FRONTEND)
        self.assertIn('self._idle_save_timer.timeout.connect(self.auto_save_character)', FRONTEND)

    def test_scheduling_resets_both_timers_for_existing_saves(self):
        tree=ast.parse(FRONTEND)
        owner=next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='BaseMainWindow')
        fn=next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name=='schedule_auto_save')
        namespace={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<autosave>', 'exec'), namespace)
        class Timer:
            count=0
            def start(self): self.count+=1
        f=SimpleNamespace(supress_dirty=False, _restoring_undo_redo=False,
                          _history_restore_pending=False,unsaved_changes=True,
                          current_character_filepath='saved-character.didchar',
                          _auto_save_timer=Timer(), _idle_save_timer=Timer(),
                          is_readonly_character=lambda: False)
        namespace['schedule_auto_save'](f)
        self.assertEqual(1, f._auto_save_timer.count)
        self.assertEqual(1, f._idle_save_timer.count)
        f.unsaved_changes=False
        namespace['schedule_auto_save'](f)
        self.assertEqual(1, f._auto_save_timer.count)
        self.assertEqual(1, f._idle_save_timer.count)

if __name__=='__main__': unittest.main()
