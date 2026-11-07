"""Force DID Character Sheet's main Windows window to stay maximized.

Target: frontend_2_8.py (1.0.14). Edits only this file, after validation.
No character files, other windows, campaign state or startup settings are edited.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


SENTINEL = "DID 1.0.14: keep the main character window maximized"
CLASS_PATTERN = re.compile(r"(?m)^class MainWindow\(BaseMainWindow\):\s*$")
STARTUP_PATTERN = re.compile(
    r'(?m)^(?P<indent>[ \t]*)if startup_settings\.value\('  # saved setting
    r'\s*["\']window_maximized["\']\s*,\s*True\s*,\s*type\s*=\s*bool\s*\)\s*:\s*\n'
    r'(?P=indent)[ \t]+win\.showMaximized\(\)\s*\n'
    r'(?P=indent)else\s*:\s*\n'
    r'(?P=indent)[ \t]+win\.show\(\)[ \t]*(?=\n|$)'
)

METHODS = '''    # DID 1.0.14: keep the main character window maximized.
    # Minimize is still allowed, and dialogs keep their normal sizes.
    def changeEvent(self, event):
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.WindowStateChange
            and getattr(self, "_did_keep_main_window_maximized", False)
            and self.isVisible()
            and not self.isMinimized()
            and not self.isMaximized()
        ):
            QTimer.singleShot(0, self._did_remaximize_main_window)

    def _did_remaximize_main_window(self):
        if self.isVisible() and not self.isMinimized() and not self.isMaximized():
            self.showMaximized()

'''


class PatchStop(Exception):
    pass


def patch_source(original: str) -> tuple[str, bool]:
    """Return (new source, changed). Never partially accept a source variant."""
    if SENTINEL in original:
        if original.count(SENTINEL) != 1 or original.count('_did_keep_main_window_maximized = True') != 1:
            raise PatchStop('Incomplete or duplicated maximized-window patch; source was not changed.')
        compile(original, 'frontend_2_8.py', 'exec')
        return original, False

    classes = list(CLASS_PATTERN.finditer(original))
    if len(classes) != 1:
        raise PatchStop(f'Expected one MainWindow class, found {len(classes)}. No files changed.')

    startups = list(STARTUP_PATTERN.finditer(original))
    if len(startups) != 1:
        raise PatchStop(
            'Could not find the saved window_maximized startup branch. '
            'Your frontend_2_8.py differs from the supported 1.0.14 versions. '
            'No files changed; please provide that file.'
        )

    # Place the event handler only on the top-level character-sheet window;
    # the campaign pages, picker dialogs and notes windows remain unchanged.
    class_match = classes[0]
    patched = (original[:class_match.end()] + '\n\n' + METHODS + original[class_match.end():])
    startup = STARTUP_PATTERN.search(patched)
    assert startup
    indent = startup.group('indent')
    replacement = (
        f'{indent}# Always open the character sheet maximized, regardless of an older saved state.\n'
        f'{indent}win.showMaximized()\n'
        f'{indent}win._did_keep_main_window_maximized = True'
    )
    patched = patched[:startup.start()] + replacement + patched[startup.end():]
    try:
        compile(patched, 'frontend_2_8.py', 'exec')
    except SyntaxError as exc:
        raise PatchStop(f'Python syntax check failed: {exc}. No files changed.') from exc
    return patched, True


def main() -> int:
    path = Path(__file__).resolve().parent / 'frontend_2_8.py'
    if not path.is_file():
        print(f'STOP: Could not find {path}; put this script in the Windows current code folder.')
        return 1
    try:
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        patched, changed = patch_source(text)
        if not changed:
            print('OK: Main window maximize behavior is already patched; no files changed.')
            return 0
        # Write safely: preserve UTF-8 BOM, if one exists, and line-ending style.
        if b'\r\n' in raw:
            patched = patched.replace('\r\n', '\n').replace('\n', '\r\n')
        payload = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + patched.encode('utf-8')
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = path.with_name(f'{path.name}.before_maximized_114_{timestamp}.bak')
        counter = 1
        while backup.exists():
            backup = path.with_name(f'{path.name}.before_maximized_114_{timestamp}_{counter}.bak')
            counter += 1
        shutil.copy2(path, backup)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile('wb', dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as f:
                tmp_name = f.name
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
        print(f'OK: Main DID window now always opens and stays maximized. Backup: {backup.name}')
        return 0
    except PatchStop as exc:
        print(f'STOP: {exc}')
        return 1
    except (OSError, UnicodeError) as exc:
        print(f'STOP: {exc}. No source changes applied unless backup already created.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
