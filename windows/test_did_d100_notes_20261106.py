"""DID 1.0.14 regression checks for d100 mixed rolls and adaptive note HEX colors.

Run with: python -m unittest test_did_d100_notes_20261106 -v
These tests do not require Qt. Full Qt WebEngine rendering still needs Windows testing.
"""
import ast
import colorsys
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import unittest

ROOT = Path(__file__).resolve().parent


class DiceMixedRollTests(unittest.TestCase):
    def test_d100_has_its_own_sibling_canvas_region(self):
        html = (ROOT / 'dice.html').read_text(encoding='utf-8')
        physics = (ROOT / 'd100_physics.js').read_text(encoding='utf-8')
        self.assertRegex(html, r'<div id="dice-box"></div>\s*<div id="d100-tray"')
        self.assertIn("document.getElementById('d100-tray')", html)
        self.assertIn('const mixedPhysicalRoll = physicalD100Count > 0 && ordinaryDiceCount > 0;', html)
        self.assertIn('ordinaryTray.style.width = ordinaryWidth + "px"', html)
        self.assertIn('d100Tray.style.left = (margin + ordinaryWidth + gap) + "px"', html)
        self.assertIn('d100Tray.style.width = physicalWidth + "px"', html)
        self.assertIn("layer.style.cssText = 'position:absolute;inset:0;width:100%;height:100%", physics)
        self.assertNotIn("mixed ? '56%' : '100%'", physics)

    def test_physics_bounds_are_merged_for_mixed_roll_results(self):
        html = (ROOT / 'dice.html').read_text(encoding='utf-8')
        self.assertIn('const dieBounds = physicalBounds && ordinaryBounds ?', html)
        self.assertIn('hasOrdinaryDice = terms.some', html)
        self.assertIn('Dice roll failed — please try again', html)

    def test_d100_renders_one_body_mesh_and_reuses_material(self):
        physics = (ROOT / 'd100_physics.js').read_text(encoding='utf-8')
        self.assertIn('group.add(new THREE.Mesh(solidGeometry, solidMaterial));', physics)
        self.assertIn('new THREE.Mesh(labelGeometries[f],labelMaterials[f])', physics)
        self.assertIn('const geometries = new Set(), materials = new Set()', physics)
        self.assertIn('ctx.scale(192 / 256, 192 / 256)', physics)
        self.assertIn('sleepSpeedLimit:.22,sleepTimeLimit:.7', physics)

    def test_js_syntax(self):
        if not shutil.which('node'):
            self.skipTest('Node.js unavailable')
        html = (ROOT / 'dice.html').read_text(encoding='utf-8')
        inline = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', html, re.S)
        for index, source in enumerate(inline):
            with self.subTest(script=index):
                result = subprocess.run(['node', '--check', '--input-type=module'],
                    input=source, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(['node', '--check', str(ROOT / 'd100_physics.js')],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


class FakeColor:
    def __init__(self, value):
        if isinstance(value, str) and re.fullmatch('#[0-9a-fA-F]{6}', value):
            self.rgb = tuple(int(value[i:i+2], 16)/255 for i in (1, 3, 5))
        else:
            self.rgb = (0, 0, 0)

    def isValid(self):
        return True

    def hslSaturation(self):
        return round(colorsys.rgb_to_hls(*self.rgb)[2] * 255)

    def hslHue(self):
        h, l, s = colorsys.rgb_to_hls(*self.rgb)
        return round(h * 360) % 360 if s else -1

    def lightness(self):
        return round(colorsys.rgb_to_hls(*self.rgb)[1] * 255)

    def name(self):
        return '#' + ''.join(f'{round(v * 255):02x}' for v in self.rgb)

    @staticmethod
    def fromHsl(h, s, l, alpha=255):
        rgb = colorsys.hls_to_rgb(h/360, l/255, s/255)
        return FakeColor('#' + ''.join(f'{round(v * 255):02x}' for v in rgb))


class NoteColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'notes_ui.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and
                 n.name in ('random_note_hex_color', '_custom_note_colors_for_theme')]
        import random
        namespace = {'QColor': FakeColor, 'random': random}
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                     '<notes_color_functions>', 'exec'), namespace)
        cls.random_color = staticmethod(namespace['random_note_hex_color'])
        cls.theme_color = staticmethod(namespace['_custom_note_colors_for_theme'])

    def test_random_note_colors_are_colorful_legal_hex(self):
        colors=[]
        for _ in range(150):
            color = self.random_color(colors)
            self.assertRegex(color, r'^#[0-9a-f]{6}$')
            self.assertGreaterEqual(FakeColor(color).hslSaturation(), 150)
            hue = FakeColor(color).hslHue()
            self.assertFalse(18 <= hue <= 47)
            colors.append(color)
        self.assertGreater(len(set(colors)), 120)

    def test_color_light_dark_projection_retains_original_hue(self):
        for color in ['#e98dce', '#7bb7e9', '#8de6ae', '#cb8afa']:
            light = self.theme_color(color, False)
            dark = self.theme_color(color, True)
            self.assertNotEqual(light, dark)
            self.assertLess(FakeColor(dark[0]).lightness(), FakeColor(light[0]).lightness())
            self.assertLess(FakeColor(dark[1]).lightness(), FakeColor(light[1]).lightness())
            self.assertLessEqual(abs(FakeColor(light[0]).hslHue() - FakeColor(dark[0]).hslHue()), 2)

    def test_notes_save_original_hex_and_use_in_previews(self):
        notes = (ROOT / 'notes_ui.py').read_text(encoding='utf-8')
        front = (ROOT / 'frontend_2_8.py').read_text(encoding='utf-8')
        self.assertIn('color=random_note_hex_color()', notes)
        self.assertIn('new_color = random_note_hex_color(', notes)
        self.assertIn('color=new_color,', notes)
        self.assertIn('outer_color, body_color = note_colors_for_theme(color_name)', front)
        self.assertIn('outer_color, body_color = note_colors_for_theme(color_key)', front)
        from backend_2_1 import CharacterNote
        note = CharacterNote('example', color='#89adfa')
        note.validate()
        self.assertEqual(note.color, '#89adfa')


if __name__ == '__main__':
    unittest.main()
