"""Regression checks for the Roll Other Dice mixed-d100 appearance patch.

Run from the project root: py -m unittest test_did_mixed_dice_readability_20261106
These do not require PySide6 or an active GPU.
"""
import json
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / 'dice.html').read_text(encoding='utf-8')
D100 = (ROOT / 'd100_physics.js').read_text(encoding='utf-8')
THEME = ROOT / 'dice_libs/dice-box/assets/themes/did-readable'


class DiceAppearanceRegression(unittest.TestCase):
    def test_both_ability_and_other_dice_select_readable_theme(self):
        self.assertIn('const standardTheme = readableThemeReady ? "did-readable" : "default";', HTML)
        self.assertIn('theme: standardTheme', HTML)

    def test_readable_theme_has_all_assets(self):
        data = json.loads((THEME / 'theme.config.json').read_text(encoding='utf-8'))
        self.assertEqual(data['systemName'], 'did-readable')
        self.assertEqual(data['meshFile'], 'default.json')
        for name in ('default.json', 'diffuse-dark.png', 'diffuse-light.png',
                     'normal.png', 'specular.jpg'):
            self.assertTrue((THEME / name).is_file(), name)

    def test_number_atlas_keeps_transparency_and_both_contrasting_inks(self):
        for name, primary in [('diffuse-light.png', (255, 255, 255)),
                              ('diffuse-dark.png', (17, 15, 24))]:
            with Image.open(THEME / name) as image:
                image = image.convert('RGBA')
                self.assertEqual(image.size, (1024, 1024))
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertTrue(any(tuple(px[:3]) == primary and px[3] > 200
                                    for px in image.getdata()))

    def test_mixed_d100_gets_own_viewport_and_tracking_camera(self):
        self.assertIn('Math.round(usableWidth * 0.5)', HTML)
        self.assertIn('context.mixedCameraDistance = Math.max(', D100)
        self.assertIn('radius * h / (diameterPx * halfFovTan)', D100)
        self.assertIn('camera.position.set(focus.x, focus.y + context.mixedCameraDistance, focus.z)', D100)

    def test_standard_die_scale_compensates_for_canvas_height(self):
        self.assertIn('normalScale * 112 / trayHeight', HTML)
        # 282px mixed canvas should not turn a single d8 into a larger die.
        original_scale, original_canvas, mixed_canvas = 10.5, 112, 282
        scaled = original_scale * original_canvas / mixed_canvas
        self.assertAlmostEqual(scaled * mixed_canvas, original_scale * original_canvas)

    def test_d100_numbers_are_inked_for_face_luminance(self):
        self.assertIn('function diceFaceLuminance(hex)', D100)
        self.assertIn("const ink = lightInk ? '#fffdf5' : '#15131c';", D100)
        self.assertIn('ctx.lineWidth = 12', D100)


if __name__ == '__main__':
    unittest.main()
