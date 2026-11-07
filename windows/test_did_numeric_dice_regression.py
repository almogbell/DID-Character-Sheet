"""Targeted tests for the numeric-input and dice-initialization repair.

Run: python -m unittest test_did_numeric_dice_regression -v
The UI tests require PySide6 (set QT_QPA_PLATFORM=offscreen for headless Qt).
"""
import os
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from dice_asset_server import start_dice_asset_server

ROOT = Path(__file__).resolve().parent


class DiceAssetSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_js_stub = b'function QWebChannel(transport, callback) {}'
        cls.server, cls.url = start_dice_asset_server(
            ROOT, webchannel_js=cls.qt_js_stub
        )
        cls.base = cls.url.rsplit('/', 1)[0]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_dice_module_and_html_are_served(self):
        for name in ('dice.html', 'dice_libs/dice-box/dice-box.es.min.js'):
            with self.subTest(asset=name), urlopen(f'{self.base}/{name}', timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read(30))

    def test_webchannel_client_is_served_from_same_origin(self):
        with urlopen(f'{self.base}/qtwebchannel/qwebchannel.js', timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), self.qt_js_stub)
            self.assertIn('javascript', response.headers['Content-Type'])
        html = (ROOT / 'dice.html').read_text(encoding='utf-8')
        self.assertIn('src="./qtwebchannel/qwebchannel.js"', html)
        self.assertNotIn('src="qrc:///qtwebchannel/qwebchannel.js"', html)

    def test_only_exact_qt_script_path_is_public(self):
        for name in ('qtwebchannel/other.js', 'qtwebchannel/../../backend_2_1.py',
                     'qtwebchannel/qtwebchannel.js.txt'):
            with self.subTest(filename=name):
                with self.assertRaises(HTTPError) as captured:
                    urlopen(f'{self.base}/{name}', timeout=3)
                self.assertEqual(captured.exception.code, 404)

    def test_non_dice_project_files_are_not_served(self):
        for name in ('character_API.py', '.env', 'node_modules/.package-lock.json'):
            with self.subTest(filename=name):
                with self.assertRaises(HTTPError) as captured:
                    urlopen(f'{self.base}/{name}', timeout=3)
                self.assertEqual(captured.exception.code, 404)

    def test_dice_api_exists_without_module(self):
        html = (ROOT / 'dice.html').read_text(encoding='utf-8')
        bootstrap = html.split('<script>', 1)[1].split('</script>', 1)[0]
        self.assertIn('window.rollDicePlan = function', bootstrap)
        self.assertIn('window.clearDiceDisplay = function', bootstrap)
        self.assertIn('window.hideDiceResult = function', bootstrap)
        self.assertIn('window.didDiceState.roll = async function', html)
        self.assertIn("await import('./dice_libs/dice-box/dice-box.es.min.js')", html)


class RealQtWebChannelResourceTests(unittest.TestCase):
    def test_pyside6_qt_resource_when_installed(self):
        try:
            from PySide6 import QtWebChannel
        except ImportError:
            self.skipTest('PySide6 is not installed in this environment')
        from dice_asset_server import qt_webchannel_javascript
        script = qt_webchannel_javascript()
        self.assertIn(b'QWebChannel', script)
        self.assertGreater(len(script), 1000)


class NumericEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        try:
            from PySide6.QtWidgets import QApplication
            from ui_widgets import NumericEntry
        except ImportError as error:
            raise unittest.SkipTest(f'PySide6 unavailable: {error}')
        cls.qt_app = QApplication.instance() or QApplication([])
        cls.widget_type = NumericEntry

    def test_range_values_and_editability(self):
        widget = self.widget_type()
        widget.setRange(7, 9999)
        widget.setValue(50)
        self.assertEqual(widget.text(), '50')
        self.assertEqual(widget.value(), 50)
        widget.selectAll()
        widget.insert('125')
        self.assertEqual(widget.value(), 125)
        widget.setValue(10000)
        self.assertEqual(widget.value(), 9999)
        widget.deleteLater()

    def test_value_changed_for_dice_counts(self):
        widget = self.widget_type()
        events = []
        widget.valueChanged.connect(events.append)
        widget.setRange(0, 20)
        widget.setValue(3)
        self.assertEqual(events[-1], 3)
        widget.setText('8')
        self.assertEqual(events[-1], 8)
        widget.deleteLater()


if __name__ == '__main__':
    unittest.main()
