"""Regression tests for eager DiceBox theme loading and safe fallback."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / 'dice.html').read_text(encoding='utf-8')
THEME = ROOT / 'dice_libs/dice-box/assets/themes/did-readable'


class ReadableThemeLoadingTests(unittest.TestCase):
    def test_optional_theme_is_loaded_before_rolls_are_accepted(self):
        init = HTML.index('async function initializeDice()')
        ready = HTML.index('sendStatus("Dice ready")', init)
        load = HTML.index('await diceBox.loadTheme("did-readable")', init)
        self.assertLess(init, load)
        self.assertLess(load, ready)
        self.assertIn('const ready = await diceInitialization;', HTML)

    def test_every_standard_die_uses_preloaded_readable_theme(self):
        self.assertIn('const standardTheme = readableThemeReady ? "did-readable" : "default";', HTML)
        self.assertIn('theme: standardTheme', HTML)
        self.assertNotIn('plan.roll_type === "other_dice" && readableThemeReady', HTML)

    def test_exploding_ability_die_keeps_theme_and_ability_color(self):
        start = HTML.index('let exploding = specs.filter')
        end = HTML.index('return specs;', start)
        wave = HTML[start:end]
        self.assertIn('theme: standardTheme', wave)
        self.assertIn('themeColor: spec.color', wave)
        self.assertIn('diceBox.add(requests', wave)

    def test_theme_error_falls_back_without_breaking_engine(self):
        self.assertIn('readableThemeReady = false;', HTML)
        self.assertIn('High-contrast theme unavailable; using default', HTML)
        self.assertIn('sendStatus("Dice ready")', HTML)

    def test_theme_declares_supported_shapes(self):
        config = json.loads((THEME / 'theme.config.json').read_text(encoding='utf-8'))
        for die in ('d4', 'd6', 'd8', 'd10', 'd12', 'd20'):
            self.assertIn(die, config['diceAvailable'])
        for file in ('theme.config.json', 'default.json', 'diffuse-light.png', 'diffuse-dark.png'):
            self.assertTrue((THEME / file).is_file())


if __name__ == '__main__':
    unittest.main()
