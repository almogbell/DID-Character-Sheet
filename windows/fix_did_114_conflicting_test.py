#!/usr/bin/env python3
"""Fix obsolete 1.0.14 layout assertion after responsive Campaigns tab update.

Only changes one outdated unittest assertion block, never application source.
"""
from __future__ import annotations
import ast
from datetime import datetime
from pathlib import Path
import os
import shutil
import sys

OLD = ("        self.assertIn('tabs_host.setFixedWidth(280)', ui)\n"
       "        self.assertIn('root.addWidget(tabs_host, 0, Qt.AlignmentFlag.AlignLeft)', ui)\n")
NEW = ("        # 1.0.14 follow-up: fixed 280px host clipped the campaign labels.\n"
       "        self.assertNotIn('tabs_host.setFixedWidth(280)', ui)\n"
       "        self.assertIn('def _resize_campaign_tabs(self):', ui)\n"
       "        self.assertIn('self._resize_campaign_tabs()', ui)\n"
       "        self.assertIn('root.addWidget(tabs_host, 0, Qt.AlignmentFlag.AlignLeft)', ui)\n")

def fix(root: Path) -> str:
    path = root / 'DID_Important_Tests' / 'test_1_0_14_campaign_reveals.py'
    if not path.is_file():
        raise RuntimeError(f'Missing expected test: {path}; no files changed.')
    orig_bytes = path.read_bytes()
    try:
        source = orig_bytes.decode('utf-8-sig')
    except UnicodeError as exc:
        raise RuntimeError('Test has an unfamiliar encoding; no files changed.') from exc
    normalized = source.replace('\r\n', '\n')
    if NEW in normalized and OLD not in normalized:
        print('PASS: Already fixed. No files changed.')
        return 'unchanged'
    if normalized.count(OLD) != 1:
        raise RuntimeError(f'Expected one outdated 280px test; found {normalized.count(OLD)}. No files changed. Send your build log instead.')
    updated = normalized.replace(OLD, NEW, 1)
    ast.parse(updated, filename=str(path))
    newline = '\r\n' if '\r\n' in source else '\n'
    if newline == '\r\n': updated = updated.replace('\n', '\r\n')
    # Preserve BOM if provided.
    b = (b'\xef\xbb\xbf' if orig_bytes.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
    backup = path.with_name(path.name + '.before_114_test_repair_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.bak')
    shutil.copy2(path, backup)
    temp = path.with_name(path.name + '.114tmp')
    try:
        temp.write_bytes(b)
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()
    print(f'PASS: Updated obsolete test only. Backup: {backup.name}')
    print('No application code, character data, or build configuration was changed.')
    return 'changed'

if __name__ == '__main__':
    try:
        root = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
        fix(root)
    except Exception as exc:
        print(f'STOP: {exc}', file=sys.stderr)
        sys.exit(1)
