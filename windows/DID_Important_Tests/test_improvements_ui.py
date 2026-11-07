"""Check land detail rows and compact empowerment controls in both themes."""
import unittest
from types import SimpleNamespace

from test_support import app_dir, qt_app
app_dir()
APP = qt_app()

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
import ui_theme
import improvements_ui
import backend_2_1 as backend


class ImprovementVisualTests(unittest.TestCase):
    def setUp(self):
        self.theme = ui_theme.CURRENT_THEME

    def tearDown(self):
        ui_theme.CURRENT_THEME = self.theme

    def test_land_name_and_detail_stay_in_one_row_in_both_themes(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                ui_theme.CURRENT_THEME = theme
                host = QWidget()
                layout = QVBoxLayout(host)
                improvement = backend.Improvement(
                    id="land", catalog_id="born_of_soil", name="Born of Soil",
                    cost=2, description="", choices={})
                improvements_ui.ImprovementRow.add_removable_choice_row(
                    SimpleNamespace(), layout, "Forest", improvement,
                    description="A quiet woodland")
                host.show()
                APP.processEvents()
                labels = [label for label in host.findChildren(QLabel)
                          if "Forest" in label.text()]
                self.assertEqual(len(labels), 1)
                self.assertIn("A quiet woodland", labels[0].text())
                self.assertTrue(labels[0].property("compact_choice_line"))
                if theme == "dark":
                    self.assertIn("#d8d0bf", labels[0].text())
                host.close()

    def test_empowerment_rows_have_top_aligned_remove_controls(self):
        character = backend.Character.create_new_character("Empowerments")
        item = backend.Improvement(id="spell", catalog_id="spellcasting",
                                   name="Spellcasting", cost=2, description="",
                                   expanded=True,
                                   choices={"magic_school": "Arcane"})
        for key, name in (("harm_slinger", "Harm Slinger"),
                          ("expert_enchanter", "Expert Enchanter")):
            item.empowerments.append(backend.TakenEmpowerment(
                id=key, group_id=key, catalog_id=key, name=name,
                cost=2, description=""))
        character.improvements.list_of_taken_improvements.append(item)
        row = improvements_ui.ImprovementRow(
            character, item, lambda *_: None,
            remove_empowerment_callback=lambda *_: None)
        row.show()
        APP.processEvents()
        labels = [label for label in row.findChildren(QLabel)
                  if label.property("compact_improvement_line")]
        self.assertEqual(len(labels), 2)
        # Remove controls are LineRemoveButton widgets.  The widget itself is
        # 22 px high so it has room to track the target label, while its custom
        # paintEvent draws the normal × control into a 15 px rectangle aligned
        # with the label's first text line.  Do not require the whole widget to
        # be 15 px high; that was the pre-LineRemoveButton implementation.
        removes = row.findChildren(improvements_ui.LineRemoveButton)
        self.assertEqual(len(removes), 2)
        for button in removes:
            self.assertEqual(button.text(), "×")
            self.assertEqual(button.height(), 22)
            self.assertIsNotNone(button.target_label)
            self.assertTrue(button.target_label.property("compact_improvement_line"))
        row.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
