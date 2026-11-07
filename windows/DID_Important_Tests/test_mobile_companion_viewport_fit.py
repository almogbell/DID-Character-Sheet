"""Structural + dependency-free layout checks for Mobile Companion fitting.

A real visual test is still required on Windows with PySide6 installed.
"""
import ast
from pathlib import Path
import types
import unittest

SRC = (Path(__file__).resolve().parents[1] / 'mobile_companion_dialog.py').read_text(encoding='utf-8')
TREE = ast.parse(SRC)
DIALOG = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
              and n.name == 'MobileCompanionDialog')
FIT = next(n for n in DIALOG.body if isinstance(n, ast.FunctionDef)
           and n.name == '_fit_qr_to_viewport')
ns = {}
exec(compile(ast.Module(body=[FIT], type_ignores=[]), '<layout-only>', 'exec'), ns)


class Rect:
    def __init__(self, height=0):
        self._height = height
    def height(self):
        return self._height
    def updateGeometry(self):
        self.updated = True

class Margin:
    def top(self): return 2
    def bottom(self): return 2

class Label:
    def __init__(self, side): self.side=side
    def minimumHeight(self): return self.side
    def width(self): return self.side
    def setFixedSize(self, w, h):
        assert w == h
        self.side = w

class Scroll:
    def __init__(self, height):
        self._vp = Rect(height)
        self._body = Rect()
    def viewport(self): return self._vp
    def widget(self): return self._body

class Fake:
    QR_DISPLAY_SIZE = 212
    QR_FRAME_PADDING = 16
    MIN_QR_FRAME_SIZE = 184
    def __init__(self, width, viewport):
        self._width=width
        self._qr_fit_scheduled=True
        self.qr_label=Label(228)
        self.content_scroll=Scroll(viewport)
        self.content_layout=types.SimpleNamespace(contentsMargins=lambda: Margin())
        self.qr_column=types.SimpleNamespace(sizeHint=lambda: Rect(124+self.qr_label.side))
        self.pixmap_refreshes=0
    def width(self): return self._width
    def isVisible(self): return True
    def _update_qr_pixmap_size(self): self.pixmap_refreshes += 1

class MobileCompanionViewportTests(unittest.TestCase):
    def fit(self, width, height):
        f = Fake(width, height)
        ns['_fit_qr_to_viewport'](f)
        return f

    def test_default_window_preserves_full_size_qr(self):
        f = self.fit(760, 370)
        self.assertEqual(228, f.qr_label.side)

    def test_shorter_side_by_side_window_shrinks_qr_instead_of_scroll(self):
        f = self.fit(760, 335)
        self.assertEqual(204, f.qr_label.side)
        self.assertEqual(1, f.pixmap_refreshes)

    def test_small_height_caps_minimum_qr_for_scannability(self):
        f = self.fit(760, 260)
        self.assertEqual(184, f.qr_label.side)

    def test_narrow_stack_uses_normal_qr_and_may_scroll(self):
        f = self.fit(600, 260)
        self.assertEqual(228, f.qr_label.side)

    def test_middle_scroll_as_needed_not_forced(self):
        self.assertIn('self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)', SRC)
        self.assertIn('self.content_scroll.viewport().installEventFilter(self)', SRC)
        self.assertIn('QEvent.Type.Resize', SRC)
        self.assertIn('target_w, target_h = 760, 570', SRC)

    def test_original_qr_remains_for_resizing(self):
        self.assertIn('self._qr_original_pixmap = pixmap', SRC)
        self.assertIn('self._update_qr_pixmap_size()', SRC)
        self.assertIn('self._qr_original_pixmap = None', SRC)
        self.assertIn('Qt.TransformationMode.FastTransformation', SRC)

    def test_all_actions_stay_outside_outer_scroll(self):
        self.assertLess(SRC.index('outer.addWidget(self.content_scroll, 1)'),
                        SRC.index('outer.addLayout(actions)'))
        for label in ('Paired phones','Phone connection network','Copy pairing code',
                      'Remove Phone','Rename','New pairing code'):
            self.assertIn(label, SRC)

if __name__ == '__main__':
    unittest.main()
