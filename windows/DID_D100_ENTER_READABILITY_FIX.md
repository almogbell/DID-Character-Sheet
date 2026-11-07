# DID Character Sheet 1.0.14 — d100 numbers + Enter-to-roll patch

This is a small follow-up to `DID_Dice_Theme_Load_Fix_FULL.zip`.

## Fixed

- **d100 face numbers:** Increased the number-plane size from 91% to 97% of its safe face width; upgraded the number textures from 160x160 to 192x192; replaced small serif labels with taller high-contrast sans-serif digits. Two-/three-digit values are fitted **horizontally** so they remain large vertically without overflowing a physical face. Both light and dark dice colors retain contrasting numerals and keylines. Dice physics, face numbering, mixed-roll scaling and result reporting are unchanged.
- **Roll Other Dice — Enter:** The Roll button is the dialog's default action. Enter and numpad Enter in any quantity field now submit a **valid** roll. Pressing Enter with zero dice or over 30 dice does not dismiss the dialog. Escape and Cancel still cancel.

## Install

1. Close DID Character Sheet.
2. Download the PATCH ZIP to Downloads.
3. In PowerShell, from your existing installation:

```powershell
$folder = "$HOME\Desktop\DID_1_0_14_Test\current code - Copy"
$zip = "$HOME\Downloads\DID_D100_Readable_Enter_PATCH.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $folder -Force
Set-Location $folder
.\.venv\Scripts\python.exe .\frontend_2_8.py
```

## Retest

1. Open `Roll Other Dice`, enter 1 in d100 quantity, and press **Enter** from the field. The dialog should close **and roll**.
2. Repeat with numpad Enter (if available), then d8 + d100 in the same roll.
3. Open `Roll Other Dice` with **zero** selected and press Enter: dialog stays open.
4. Check that the d100 labels are legible on gold dice and other supported dice colors in both light and dark modes; 6 and 9 should remain distinguishable by underline.
5. Check that normal ability dice still roll and display totals and Previous Rolls updates.

## Tests run in the patch environment

- Python compile and JavaScript syntax: passed.
- 19 focused Python regression tests: passed (Qt shim tests rather than interactive PySide6).
- Canvas label fitting test for 1, 6, 9, 10, 25, 66, 99, and 100: passed.

Not yet verified in an actual Windows Qt WebEngine / GPU session; please confirm visually.
