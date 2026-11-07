# DID 1.0.14 — Portrait and Dice Color Fix

This patch follows `DID_Fixed_Project_WebChannel.zip` (the project that already
includes the working 3D dice animation and WebChannel results bridge).

## Changes

- Roll Other Dice: d4/d6/d8/d10/d12/d20 use one matching gold material,
  rather than individually varied colors. Physical d100 uses the same gold
  material when selected in this mode.
- Character ability rolls: existing distinct shades for advantage,
  disadvantage, and improvements remain unchanged. Physical d100 retains
  its purple default outside Roll Other Dice.
- Left-column responsive layout: removes the 330px portrait-height cap and
  expands the portrait to use the actual remaining space. The six fixed
  ability rows remain 56px tall, separated by 4px gaps, and Strength sits
  against the bottom content margin of the left frame.
- Compact viewport support: portrait minimum reduced to 120px so smaller
  viewports can fit the six ability rows.
- Added a debounced recrop on portrait height changes so uploaded photos
  fill the newly expanded frame.

## Windows installation (patch only)

Close the app, download `DID_Portrait_Dice_Color_Patch.zip`, then run:

```powershell
$folder = "$HOME\Desktop\DID_1_0_14_Test\current code - Copy"
$zip = "$HOME\Downloads\DID_Portrait_Dice_Color_Patch.zip"
Test-Path $zip
Test-Path "$folder\frontend_2_8.py"
Expand-Archive -LiteralPath $zip -DestinationPath $folder -Force
Set-Location $folder
.\.venv\Scripts\python.exe .\frontend_2_8.py
```

If either Test-Path returns False, check the Downloads filename or the
application folder before expanding the patch.

## Validation

- `python -m py_compile frontend_2_8.py`: passed.
- Dice HTML inline and module JavaScript syntax: passed with Node.js.
- `node --check d100_physics.js`: passed.
- `python -m unittest test_did_numeric_dice_regression test_did_portrait_dice_color -v`:
  9 tests, 7 passed and 2 skipped (PySide6 unavailable in this environment).
- Node integration test verifies one color for an ordinary mixed-dice pool
  (including d100) and retains different colors for ability roll extras.

Qt GUI resizing and dice material appearance must still be verified on
Windows. Neither a Windows installer nor a live Qt rendering was run here.
