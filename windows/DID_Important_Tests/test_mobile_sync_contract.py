"""Static contract checks for the currently integrated mobile-sync modules.

These tests intentionally avoid PySide6 so they can run in CI or on a machine
without Qt. They do not replace end-to-end phone/desktop sync tests.
"""
import ast
import unittest
from pathlib import Path
from test_support import app_dir

ROOT = app_dir()

class MobileSyncContractTests(unittest.TestCase):
    def source(self, name):
        path = ROOT / name
        self.assertTrue(path.is_file(), f"Missing Windows sync module: {name}")
        text = path.read_text(encoding="utf-8-sig")
        ast.parse(text, filename=str(path))
        return text

    def test_required_modules_parse(self):
        for name in ("mobile_sync_server.py", "mobile_sync_frontend_adapter.py",
                     "mobile_companion_controller.py", "mobile_companion_dialog.py",
                     "campaign_shared.py", "campaign_runtime.py"):
            with self.subTest(module=name):
                self.source(name)

    def test_fallback_ports_present(self):
        source = self.source("mobile_sync_server.py")
        self.assertIn("FALLBACK_PORT_SPAN", source)
        self.assertIn("8765", source)

    def test_snapshot_upsert_contract(self):
        source = self.source("mobile_sync_frontend_adapter.py")
        self.assertIn("SYNC_CONFLICT", source)
        self.assertIn("character_id", source)

if __name__ == "__main__":
    unittest.main(verbosity=2)
