# DID 1.0.14 — Mixed dice sizing and number contrast patch

Based on `DID_Notes_d100_Full_Project.zip` (November 6, 2026). Apply **after** the Notes+d100 patch, or use the accompanying complete project ZIP.

## Changes

- Mixed d100 + ordinary die rolls now divide the arena evenly between the two independent renderers, instead of giving the ordinary die 56% and the d100 44% of the usable width.
- DiceBox ordinary die scale in mixed rolls compensates for the much taller mixed-roll canvas. This targets the d8 becoming unusually large, without changing standalone ability rolls or the physics outcome.
- A single d100 in a mixed roll is enlarged by adjusting its renderer camera (not its rigid body or result calculation). The camera framing for two d100 dice is unchanged.
- Added a separate `did-readable` DiceBox theme for **Roll Other Dice** with thicker, contrasting black/white numeral outlines for the d4/d6/d8/d10/d12/d20 dice. Ability dice keep the original `default` theme and special-die colors.
- Physical d100 numeral textures now select dark or light ink from the face luminance, with an opposite-tone outline. This applies to d100 rolls both inside and outside Roll Other Dice.

## Test locally on Windows

1. Roll a d8 alone, then d8 + d100. The d8 should not grow dramatically in the mixed roll, and the d100 should no longer appear tiny.
2. Roll d100 alone, 2 d100, and 2 d100 + d8; check neither clipping nor overlap occurs and the result arrives.
3. Roll d8, d12, d20 via Roll Other Dice in both Light and Dark mode. The outlined digits should stay readable.
4. Roll normal abilities with advantage/disadvantage to confirm their established colors are preserved.
5. Ensure Previous Rolls and result display still update.

Automated checks validate the assets, basic sizing calculation and JavaScript syntax; the rendered size/contrast requires testing inside the Qt WebEngine Windows app. Browser-level validation is unavailable in this container because local HTTP access is blocked by the browser policy.
