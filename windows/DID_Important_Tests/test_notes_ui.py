"""Focused checks for system-note text, palette controls, and note cards."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_support import app_dir, qt_app
app_dir()
APP = qt_app()

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMenu, QPushButton
import notes_ui
import ui_theme
from backend_2_1 import CharacterNote


class MemorySettings:
    values = {}

    def __init__(self, *_):
        pass

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class NoteTests(unittest.TestCase):
    def setUp(self):
        MemorySettings.values = {}
        self.settings = patch.object(notes_ui, "QSettings", MemorySettings)
        self.settings.start()
        self.original_theme = ui_theme.CURRENT_THEME

    def tearDown(self):
        ui_theme.CURRENT_THEME = self.original_theme
        self.settings.stop()

    def test_palette_replaces_slot_and_tracks_theme(self):
        notes_ui.set_palette_note_color("red", "#804020")
        self.assertEqual(notes_ui.palette_note_color("red"), "#804020")
        ui_theme.CURRENT_THEME = "light"
        light = notes_ui.note_colors_for_theme("red")[0]
        ui_theme.CURRENT_THEME = "dark"
        dark = notes_ui.note_colors_for_theme("red")[0]
        self.assertNotEqual(light, dark)
        notes_ui.set_palette_note_color("red", None)
        self.assertEqual(notes_ui.palette_note_color("red"), notes_ui.NOTE_COLORS["red"])

    def test_color_picker_accepts_rgb_and_changes_original_slot(self):
        picker = notes_ui.NoteColorPicker(QColor("#ff0000"))
        for field, value in zip(picker.rgb_fields, (12, 34, 56)):
            field.setText(str(value))
        picker.update_from_rgb()
        self.assertEqual(picker.selected_color.name(), "#0c2238")
        self.assertEqual(len(picker.rgb_fields), 3)
        picker.slot_selector.setCurrentIndex(notes_ui.NOTE_COLOR_ORDER.index("red"))
        picker.change_quick_palette(False)
        self.assertEqual(notes_ui.palette_note_color("red"), "#0c2238")
        picker.change_quick_palette(True)
        self.assertEqual(notes_ui.palette_note_color("red"), notes_ui.NOTE_COLORS["red"])
        picker.close()

    def test_current_color_is_on_plus_button(self):
        ui_theme.CURRENT_THEME = "light"
        menu = QMenu()
        notes_ui.note_menu(menu, "#123456")
        plus = next(button for button in menu.findChildren(QPushButton)
                    if button.text() == "+")
        style = plus.styleSheet().lower()
        # The + opens the custom picker; it must not look like a color swatch.
        self.assertIn("background:transparent", style)
        self.assertNotIn("background:#123456", style)
        self.assertIn("color:#6f4e22", style)
        self.assertEqual(style.count("{"), style.count("}"))
        menu.close()

    def test_spellcasting_abilities_form_one_list_after_stats(self):
        owned = [SimpleNamespace(catalog_id=key)
                 for key in ("harm_slinger", "expert_enchanter")]
        html = notes_ui.spellcasting_note_html(SimpleNamespace(empowerments=owned))
        self.assertEqual(html.count("&#8226;"), 6)
        self.assertEqual(html.count("<br><br>"), 1)
        self.assertLess(html.index("Knowledge"), html.index("Area harm"))
        formatted = notes_ui.format_system_note_html(html)
        self.assertIn('<p style="margin:0 0 0 15px; text-indent:-15px"><b>Agility:', formatted)
        self.assertIn("text-indent:-15px", formatted)
        self.assertIn("&nbsp;", formatted)

    def test_system_note_read_only_and_full_last_line(self):
        text = notes_ui.spellcasting_note_html(SimpleNamespace(empowerments=[
            SimpleNamespace(catalog_id="harm_slinger"),
            SimpleNamespace(catalog_id="expert_enchanter")]))
        card = notes_ui.NoteCard(CharacterNote(id="spell", title="Spellcasting Verbs", text=text),
                                 lambda: None, lambda *_: None)
        card.show()
        APP.processEvents()
        card.resize_text_edit()
        self.assertTrue(card.title_edit.isReadOnly())
        self.assertIn("Extended duration", card.text_edit.text())
        self.assertGreater(card.text_edit.height(), card.text_edit.fontMetrics().lineSpacing() * 10)
        card.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
