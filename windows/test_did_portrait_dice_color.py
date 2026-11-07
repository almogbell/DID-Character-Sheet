"""Regression checks for the 1.0.14 portrait sizing and neutral dice colors.

Run: python -m unittest test_did_portrait_dice_color -v
The JavaScript integration check uses Node.js. Qt's live geometry still needs
manual verification on Windows.
"""
import os
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest

ROOT = Path(__file__).resolve().parent


class PortraitSizingTests(unittest.TestCase):
    def test_portrait_uses_all_remaining_column_height(self):
        source = (ROOT / 'frontend_2_8.py').read_text(encoding='utf-8')
        method = source.split('def apply_redesign_height_to_viewport(self):', 1)[1].split(
            'def resizeEvent(self, event):', 1
        )[0]
        self.assertIn('portrait_height = max(\n            120,\n            portrait_height,', method)
        self.assertNotIn('330,\n                portrait_height', method)
        self.assertIn('self.image_frame.setFixedHeight(\n            portrait_height', method)
        self.assertIn('timer.timeout.connect(self.refresh_character_image_after_layout)', method)
        self.assertIn('self.image_frame.setMinimumHeight(120)', source)

    def test_six_ability_rows_fit_the_portrait_budget(self):
        # Real row dimensions and layout margins: 6 * 56px, five 4px gaps,
        # 8px top and bottom margins, 5px gap above the ability group.
        used_by_rows = 6 * 56 + 5 * 4 + 8 + 8 + 5
        for viewport_sheet_height in (500, 592, 735, 820, 1100):
            with self.subTest(height=viewport_sheet_height):
                portrait_height = max(120, viewport_sheet_height - used_by_rows)
                self.assertEqual(portrait_height + used_by_rows, viewport_sheet_height)
                self.assertGreaterEqual(portrait_height, 120)


class DiceColorTests(unittest.TestCase):
    def test_roll_other_dice_uses_one_color_including_physical_d100(self):
        if shutil.which('node') is None:
            self.skipTest('Node.js not available')
        js = r'''
          const fs = require('fs');
          const assert = require('node:assert/strict');
          const html = fs.readFileSync(process.argv[1], 'utf8');
          const start = html.indexOf('function dieVariantColor(');
          const end = html.indexOf('window.didDiceState.hide = function', start);
          assert.ok(start >= 0 && end > start, 'dice functions missing');
          const funcs = html.slice(start, end);
          let standardRequests = [], d100Color = null;
          const diceBox = {
            roll: async (requests) => { standardRequests = requests; return []; },
            add: async () => []
          };
          const d100Engine = async () => ({
            rollPhysicalD100: async (quantity, tray, mixed, color) => {
              d100Color = color;
              return Array(quantity).fill(42);
            }
          });
          // The real page loads the readable dice theme before invoking rolls.
          // Supply that initialized state when extracting the function alone.
          const run = new Function('diceBox', 'd100Engine', 'readBatchResults',
              'sendStatus', 'document', 'readableThemeReady', funcs + '\nreturn rollPlanBatches;')(
            diceBox, d100Engine, (result, requests) => requests.map(() => 2),
            () => {}, {getElementById: () => ({})}, true);
          async function check() {
            const plan = {
              roll_type: 'other_dice',
              ability: {sides:4, kind:'other_die', label:'d4'},
              extras: [
                {sides:6, kind:'other_die', label:'d6'},
                {sides:12, kind:'other_die', label:'d12'},
                {sides:100, kind:'other_die', label:'d100'}
              ]
            };
            const specs = await run(plan, '#a87824');
            assert.equal(specs.length, 4);
            assert.ok(specs.every(spec => spec.color === '#a87824'));
            assert.ok(standardRequests.every(req => req.themeColor === '#a87824'));
            assert.equal(d100Color, '#a87824');
            await run({ability:{sides:8,kind:'ability'}, extras:[
              {sides:6,kind:'advantage'}, {sides:6,kind:'magic'}
            ]}, '#6f8f2c');
            assert.equal(standardRequests[0].themeColor, '#6f8f2c');
            assert.notEqual(standardRequests[1].themeColor, '#6f8f2c');
            assert.notEqual(standardRequests[2].themeColor, '#6f8f2c');
            const d100Source = fs.readFileSync(process.argv[2], 'utf8');
            assert.match(d100Source, /faceColor = '#cb9adb'/);
            assert.match(d100Source, /color:faceColor/);
          }
          check().catch(e => { console.error(e); process.exitCode = 1; });
        '''
        result = subprocess.run(
            ['node', '-e', textwrap.dedent(js), str(ROOT / 'dice.html'),
             str(ROOT / 'd100_physics.js')],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
