# DID Character Sheet 1.0.14 — Species, autosave, and regression updates

This patch is based on `DID_Mobile_Companion_Scroll_Full_Project.zip` (the latest complete source at the time of these edits). It includes all earlier dice, UI, notes, and mobile layout changes. No user's saved characters or cloud data were edited.

## Changes

- In campaign characters whose creation rules require a Species, always show the Species chooser at the top of the sheet, even if none has been selected. Clicking it (or pressing Enter or Space while focused) opens the actual species-improvement picker or existing species editor.
- The Tools > Add Species action is hidden for campaign characters whose Species mode is optional/normal or disabled, and reappears if the active creation rules later require Species. Standalone characters retain the normal Add Species action. Existing Species selections remain visible if rules change, avoiding loss of data.
- The species picker excludes improvements already owned by the character. The backend also rejects attempts to add an already-owned catalog improvement as a Species improvement, even if requests bypass the UI.
- Saved characters still autosave shortly after an edit (existing 1.1-second debounce), and now also have a 60-second inactivity safety timer for pending unsaved edits. New, unnamed, readonly, and history-restoration characters preserve existing safety gates.
- Two older dice tests now check the actual camera-tracking implementation and initialized readable-theme state rather than obsolete code.
- Adds a standalone PowerShell automated test runner. It tests against a disposable copy, with a temporary home and outbound Python network blocked, and produces HTML and plain-text reports. It deliberately cannot automatically confirm real phone pairing, cloud interactions, or 3D visual appearance.

## Install and test on Windows

1. Close DID Character Sheet and download `DID_Species_Autosave_AutoTests_PATCH.zip` to Downloads.
2. In PowerShell run:

```powershell
$folder = "$HOME\Desktop\DID_1_0_14_Test\current code - Copy"
$zip = "$HOME\Downloads\DID_Species_Autosave_AutoTests_PATCH.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $folder -Force
Set-Location $folder
powershell -NoProfile -ExecutionPolicy Bypass -File .\Run-DID-Automatic-Tests.ps1 -Quick
```

For the full test suite, omit `-Quick`. The script opens the HTML report and saves its files to `Desktop\DID_Test_Reports` by default.

After automated tests, start the application as before:

```powershell
.\.venv\Scripts\python.exe .\frontend_2_8.py
```

## Test status on Linux source-only environment

Quick runner: **25 check groups passed; 0 failed; 4 blocked** (PySide6 Qt modules unavailable). New dedicated backend and structural species/autosave tests: **10 passed**. There are no claims that real GUI layouts or phone/online workflows were verified here.

## Screenshot-specific UI requests

The most recent two additional screenshots were not accessible as source files in the review runtime. No undocumented visual guesses were applied to those particular screens. Those exact visual adjustments remain to be verified separately.
