DID Character Sheet 1.0.14 — Ability Dice Numeral Readability Patch

Changes:
* Normal ability dice now use the same improved, high-contrast number texture as Roll Other Dice.
* Advantage, disadvantage, improvements, magic and other special dice retain their per-die colors.
* Exploding ability dice use the improved numeral theme, too.
* If the optional dice theme cannot be loaded, the built-in theme is used to keep rolls working.
* No changes to d100 physics, dice totals, WebChannel, character files or campaign data.

Patch files:
 dice.html
 test_did_readable_theme_loading_20261106.py
 test_did_mixed_dice_readability_20261106.py

Windows install:
  1) Close DID Character Sheet.
  2) Download DID_Ability_Dice_Readability_PATCH.zip into Downloads.
  3) In PowerShell:

$folder = Join-Path ([Environment]::GetFolderPath('Desktop')) "Almog's\DID_1_0_14_Test\current code - Copy"
$zip = Join-Path $HOME 'Downloads\DID_Ability_Dice_Readability_PATCH.zip'
Expand-Archive -LiteralPath $zip -DestinationPath $folder -Force
Set-Location $folder
.\.venv\Scripts\python.exe .\frontend_2_8.py

Verification here: 26 automated groups passed, 0 failed, 4 blocked without PySide6.
Actual 3D rendering must be checked on Windows in light and dark modes.
