from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from windows.integrate_mobile_companion import (
    INSTALL_MARKER,
    patch_frontend_file,
    patch_frontend_text,
)


FINISHED_BOOTSTRAP = '''
APP_VERSION = "1.0.10"

class BaseMainWindow:
    def __init__(self):
        self.setup_keyboard_shortcuts()

        self.refresh_all()
        self.reset_undo_history(
            treat_current_as_clean=True
        )

    def refresh_all(self):
        pass
'''


class IntegrationPatcherTests(unittest.TestCase):
    def test_patches_confirmed_finished_bootstrap_and_version(self):
        patched = patch_frontend_text(FINISHED_BOOTSTRAP)
        self.assertIn('APP_VERSION = "1.0.11"', patched)
        self.assertIn(INSTALL_MARKER, patched)
        self.assertIn("from mobile_companion_controller import install_mobile_companion", patched)
        self.assertIn("CharacterStorageSystem", patched)
        self.assertLess(patched.index("self.reset_undo_history"), patched.index(INSTALL_MARKER))

    def test_patch_is_idempotent(self):
        once = patch_frontend_text(FINISHED_BOOTSTRAP)
        twice = patch_frontend_text(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count(INSTALL_MARKER), 1)

    def test_can_preserve_version_when_requested(self):
        patched = patch_frontend_text(FINISHED_BOOTSTRAP, target_version=None)
        self.assertIn('APP_VERSION = "1.0.10"', patched)
        self.assertIn(INSTALL_MARKER, patched)

    def test_refuses_to_guess_unknown_bootstrap(self):
        with self.assertRaisesRegex(ValueError, "Refusing to guess"):
            patch_frontend_text('APP_VERSION = "1.0.10"\nclass X: pass\n')

    def test_file_patch_creates_one_backup_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frontend_2_8.py"
            path.write_text(FINISHED_BOOTSTRAP, encoding="utf-8")

            self.assertTrue(patch_frontend_file(path))
            backup = path.with_suffix(".py.phase8.bak")
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), FINISHED_BOOTSTRAP)

            self.assertFalse(patch_frontend_file(path))
            self.assertEqual(backup.read_text(encoding="utf-8"), FINISHED_BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
