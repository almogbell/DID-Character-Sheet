"""Exercise the actual MainWindow portrait upload method without opening a window."""
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import app_dir, qt_app
app_dir()
APP = qt_app()

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
import backend_2_1 as backend
import frontend_2_8 as frontend
import ui_theme


class WindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.character = backend.Character.create_new_character("Portrait test")
        self.saves = self.refreshes = 0

    def block_if_readonly(self):
        return False

    def mark_dirty(self, auto_save=False):
        assert auto_save
        self.saves += 1

    def refresh_character_image(self):
        self.refreshes += 1


class PortraitTests(unittest.TestCase):
    def make_picture(self, folder, name, format, color):
        path = Path(folder) / name
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        image.fill(color)
        self.assertTrue(image.save(str(path), format))
        return str(path)

    def test_multiple_selection_and_original_alpha(self):
        with tempfile.TemporaryDirectory() as folder:
            clear = self.make_picture(folder, "clear.png", "PNG", Qt.GlobalColor.transparent)
            red = self.make_picture(folder, "red.png", "PNG", QColor("#db4437"))
            window = WindowStub()
            with patch.object(frontend.QFileDialog, "getOpenFileNames",
                              return_value=([clear, red], "")):
                frontend.MainWindow.add_character_image_from_ui(window)
            self.assertEqual((window.saves, window.refreshes), (1, 1))
            self.assertEqual(len(window.character.image.images), 2)
            self.assertEqual(window.character.image.current_index, 1)
            first = window.character.image.images[0].image_data
            self.assertTrue(first.startswith("data:image/png;base64,"))
            pixels = QImage.fromData(base64.b64decode(first.split(",", 1)[1]))
            self.assertEqual(pixels.pixelColor(0, 0).alpha(), 0)
            restored = backend.CharacterStorageSystem.character_from_dict(
                backend.CharacterStorageSystem.character_to_dict(window.character))
            self.assertEqual(len(restored.image.images), 2)

    def test_jpeg_is_accepted_without_fake_transparency(self):
        with tempfile.TemporaryDirectory() as folder:
            jpg = self.make_picture(folder, "opaque.jpg", "JPG", Qt.GlobalColor.white)
            window = WindowStub()
            with patch.object(frontend.QFileDialog, "getOpenFileNames",
                              return_value=([jpg], "")):
                frontend.MainWindow.add_character_image_from_ui(window)
            encoded = window.character.image.current_image()
            self.assertTrue(encoded.startswith("data:image/jpeg;base64,"))
            self.assertEqual(QImage.fromData(base64.b64decode(encoded.split(",", 1)[1]))
                             .pixelColor(0, 0).alpha(), 255)

    def test_dark_mode_keeps_white_pixels(self):
        pixmap = QPixmap(8, 8)
        pixmap.fill(Qt.GlobalColor.white)
        old = ui_theme.CURRENT_THEME
        try:
            ui_theme.CURRENT_THEME = "dark"
            displayed = frontend.portrait_pixmap_for_current_theme(pixmap)
            self.assertEqual(displayed.toImage().pixelColor(0, 0).alpha(), 255)
        finally:
            ui_theme.CURRENT_THEME = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
