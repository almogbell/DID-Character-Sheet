import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'windows' / 'mobile_sync_frontend_adapter.py'
spec = importlib.util.spec_from_file_location('mobile_adapter', SOURCE)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class TombstoneTests(unittest.TestCase):
    def test_persist_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter = module.DesktopSyncAdapter(SimpleNamespace(), SimpleNamespace(SAVE_DIR=folder))
            adapter._record_mobile_tombstone('character-123')
            fresh = module.DesktopSyncAdapter(SimpleNamespace(), SimpleNamespace(SAVE_DIR=folder))
            self.assertIn('character-123', fresh._mobile_tombstones())
            self.assertIsInstance(json.loads((Path(folder) / '_mobile_deleted_characters.json').read_text()), dict)

    def test_stale_upsert_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter = module.DesktopSyncAdapter(SimpleNamespace(), SimpleNamespace(SAVE_DIR=folder))
            adapter._record_mobile_tombstone('character-123')
            with self.assertRaisesRegex(module.MobileSyncValidationError, 'SYNC_CONFLICT'):
                adapter._save_phone_snapshot({'character': {'id': 'character-123'}})

if __name__ == '__main__':
    unittest.main()
