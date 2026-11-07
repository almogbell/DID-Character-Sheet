# DID 1.0.14 — Dice Theme Loading Regression Fix (2026-11-06)

## Cause
DiceBox 1.1.4 loads only its initial `default` theme during `init()`. The previous readability patch set `theme: "did-readable"` in `roll()` before the custom theme was loaded, causing a synchronous `themesLoadedData[theme].diceAvailable` lookup on an undefined value.

## Fix
- `dice.html` now explicitly awaits `diceBox.loadTheme("did-readable")` after `diceBox.init()` and before a roll can begin.
- It checks that the theme has the supported ordinary die shapes before selecting it.
- If the optional high-contrast theme fails to load, "Roll Other Dice" uses the default DiceBox theme instead of failing all dice rolls.
- Retains d100 sizing and the previously generated readable-theme texture assets.

## Verification
- JavaScript module syntax: passed (`node --check`).
- Focused appearance/theme regression tests: 10 passed.
- Asset server: confirmed HTTP 200 and correct content types for the readable theme configuration, mesh, and number atlas.
- No Windows Qt WebEngine visual roll was performed. Verify on Windows.

## Apply
Close DID and extract the ZIP into the existing project folder containing `dice.html`, overwriting matching files. Restart with `\.venv\Scripts\python.exe .\frontend_2_8.py`.
