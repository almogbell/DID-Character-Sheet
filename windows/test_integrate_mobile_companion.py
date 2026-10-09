from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from windows.integrate_mobile_companion import (
    INSTALL_MARKER,
    MENU_MARKER,
    patch_frontend_file,
    patch_frontend_text,
)


FINISHED_FRONTEND = '''
APP_VERSION = "1.0.10"

class BaseMainWindow:
    def __init__(self):
        self.setup_keyboard_shortcuts()

        self.refresh_all()
        self.reset_undo_history(
            treat_current_as_clean=True
        )

    def toggle_tools_menu(self):
        menu = QMenu(self)

        def add_normal_action(label, callback):
            action = menu.addAction(label)
            action.triggered.connect(callback)
            return action

        add_normal_action(
            "Edit Abilities",
            self.open_ability_editor,
        )

        dice_menu = menu.addMenu("Dice Roller")
        menu.exec()

    def refresh_all(self):
        pass
'''


class IntegrationPatcherTests(unittest.TestCase):
    def test_patches_confirmed_finished_bootstrap_menu_and_version(self):
        patched = patch_frontend_text(FINISHED_FRONTEND)
        self.assertIn('APP_VERSION = "1.0.11"', patched)
        self.assertIn(INSTALL_MARKER, patched)
        self.assertIn(MENU_MARKER, patched)
        self.assertIn("from mobile_companion_controller import install_mobile_companion", patched)
        self.assertIn("CharacterStorageSystem", patched)
        self.assertIn('"Mobile Companion"', patched)
        self.assertIn("companion.show_dialog()", patched)
        self.assertLess(patched.index("self.reset_undo_history"), patched.index(INSTALL_MARKER))
        self.assertLess(patched.index(MENU_MARKER), patched.index('dice_menu = menu.addMenu("Dice Roller")'))

    def test_patch_is_idempotent(self):
        once = patch_frontend_text(FINISHED_FRONTEND)
        twice = patch_frontend_text(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count(INSTALL_MARKER), 1)
        self.assertEqual(twice.count(MENU_MARKER), 1)

    def test_can_upgrade_an_older_phase8_patch_with_visible_menu_entry(self):
        old = patch_frontend_text(FINISHED_FRONTEND)
        # Simulate the earlier Phase 8 patch which installed the controller but
        # relied only on the QMenu event filter for the menu row.
        start = old.index(MENU_MARKER)
        end = old.index('        dice_menu = menu.addMenu("Dice Roller")')
        old = old[:start] + old[end:]
        self.assertIn(INSTALL_MARKER, old)
        self.assertNotIn(MENU_MARKER, old)

        upgraded = patch_frontend_text(old)
        self.assertIn(MENU_MARKER, upgraded)
        self.assertIn('"Mobile Companion"', upgraded)

    def test_can_preserve_version_when_requested(self):
        patched = patch_frontend_text(FINISHED_FRONTEND, target_version=None)
        self.assertIn('APP_VERSION = "1.0.10"', patched)
        self.assertIn(INSTALL_MARKER, patched)
        self.assertIn(MENU_MARKER, patched)

    def test_refuses_to_guess_unknown_bootstrap(self):
        with self.assertRaisesRegex(ValueError, "Refusing to guess"):
            patch_frontend_text('APP_VERSION = "1.0.10"\nclass X: pass\n')

    def test_refuses_success_without_confirmed_tools_menu_anchor(self):
        text = FINISHED_FRONTEND.replace('        dice_menu = menu.addMenu("Dice Roller")\n', '')
        with self.assertRaisesRegex(ValueError, "visible Mobile Companion entry"):
            patch_frontend_text(text)

    def test_file_patch_creates_one_backup_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frontend_2_8.py"
            path.write_text(FINISHED_FRONTEND, encoding="utf-8")

            self.assertTrue(patch_frontend_file(path))
            backup = path.with_suffix(".py.phase8.bak")
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), FINISHED_FRONTEND)

            self.assertFalse(patch_frontend_file(path))
            self.assertEqual(backup.read_text(encoding="utf-8"), FINISHED_FRONTEND)


if __name__ == "__main__":
    unittest.main()
