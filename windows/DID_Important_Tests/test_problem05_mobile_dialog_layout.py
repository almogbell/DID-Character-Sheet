"""Problem 5 UI source invariants. Real Qt visual tests still required."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / 'mobile_companion_dialog.py').read_text(encoding='utf-8')
TREE = ast.parse(SRC)

class MobileDialogTests(unittest.TestCase):
    def test_valid_python_and_still_uses_existing_dialog(self):
        self.assertIn('class MobileCompanionDialog(QDialog)', SRC)
    def test_dialog_scrolls_content_not_actions(self):
        self.assertIn('self.content_scroll = QScrollArea(self)', SRC)
        self.assertLess(SRC.index('outer.addWidget(self.content_scroll, 1)'), SRC.index('outer.addLayout(actions)'))
    def test_responsive_switch_below_690(self):
        self.assertIn("compact = self.width() < 690", SRC)
        self.assertIn('QBoxLayout.Direction.TopToBottom', SRC)
        self.assertIn('QBoxLayout.Direction.LeftToRight', SRC)
        self.assertIn('self._update_mobile_layout()', SRC)
    def test_pairing_connection_workflow_untouched(self):
        for expected in ('self.server.begin_pairing(host_override=self.address_selector.currentData())', 'self.server.cancel_pairing',
                         'self.server.paired_devices()', 'self.server.connected_device_ids()',
                         'make_pairing_landing_url(payload, landing)'):
            self.assertIn(expected, SRC)
    def test_dark_placeholder_is_readable(self):
        self.assertIn("dark = ui_theme.CURRENT_THEME == 'dark'", SRC)
        self.assertIn("bg = '#192b3a' if dark else '#fffaf0'", SRC)
        self.assertIn("fg = '#f6f0e4' if dark else '#6c5428'", SRC)
    def test_code_uses_same_bottom_actions(self):
        for text in ('Cancel pairing', 'Copy pairing code', 'Start pairing', 'Remove Phone', 'Rename'):
            self.assertIn(text, SRC)
    def test_qr_still_scannable_on_white(self):
        self.assertIn('background: white; color: #25190f', SRC)
        self.assertIn('Qt.AspectRatioMode.KeepAspectRatio', SRC)
    def test_device_list_visible_in_compact_mode(self):
        self.assertIn('self.devices.setMinimumHeight(145 if compact else 105)', SRC)

if __name__ == '__main__':
    unittest.main()
