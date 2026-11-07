import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from mobile_sync_frontend_adapter import DesktopSyncAdapter

with tempfile.TemporaryDirectory() as folder:
    storage = SimpleNamespace(SAVE_DIR=folder)
    DesktopSyncAdapter.record_desktop_deletion(storage, 'offline-uuid')
    data = json.loads((Path(folder) / '_mobile_deleted_characters.json').read_text())
    assert 'offline-uuid' in data
    DesktopSyncAdapter.record_desktop_deletion(storage, 'another-uuid')
    data = json.loads((Path(folder) / '_mobile_deleted_characters.json').read_text())
    assert set(data) == {'offline-uuid', 'another-uuid'}
print('PASS: desktop tombstones persist without a controller')
