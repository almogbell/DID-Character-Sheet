# Windows 1.0.13 — Manual acceptance checklist

## Install source update
1. Close DID Character Sheet and back up the source folder and the regular character/settings files before proceeding. **Do not delete or clear app data**.
2. Extract the **Windows update ZIP** into `C:\Users\almog\Desktop\DIDCharacterSheet\current code` if that is still your current source folder, **or your actual current 1.0.13 Windows project root** (the folder containing `frontend_2_8.py`). Choose replace existing files. Preserve the ZIP's nested `DID_Important_Tests\` path.
3. Run the existing application using your normal Python/PySide6 virtual environment. Keep a backup copy of the original source so you can roll back code without touching user data.
4. To test built distribution, rebuild with the existing PyInstaller/Inno Setup workflow, then run the installed build separately. This update has **not** itself been built into an installer.

## Desktop status and synchronization
1. Launch Aurora Lockwood; check the redesigned header has Saved and an empty reserved phone slot before pairing.
2. Open Tools > Mobile Companion. Confirm the dialog is compact and Start pairing, Cancel pairing and Copy code remain visible. The inactive QR area must be navy, not bright white.
3. Start pairing. Existing Pocket DID should scan the **legacy JSON QR** by default; alternatively copy pairing JSON to the phone.
4. After live connection, verify `● Phone connected` appears beside the **redesigned** Saved widget and `Connected` appears inside the dialog.
5. On Windows change Aurora Lockwood AT; verify Android AT updates within a short time and the saved value survives restart. On Android change a supported value and verify Windows validation, save and canonical state are returned.
6. Disconnect Wi-Fi on Android. Confirm the Windows badge clears and paired phone shows Paired but offline. Reconnect; confirm badge returns without a duplicate connected count.
7. Rename phone and reconnect: confirm the Windows name survives. Click Remove Phone then Cancel (must retain); then remove via Remove Phone (must revoke pairing).
8. Keep both devices connected long enough to observe possible reconnection flapping; collect server/Android logs and any repeated requests.

## Layout
1. Verify the dialog at light/dark and Windows scaling 100% / 125% / 150% / 200%; QR never covers directions or buttons. Shrink window until minimum.
2. Expand/collapse inventory card with a long multi-line name/long description. The delete button must not overlap; description must render completely.
3. Confirm the three-part quantity pill remains constant 34×54 pixels (Qt logical pixels), centered vertically even while card height changes; collapse should restore a compact row.
4. Switch screen tabs and Notes and resize Windows. Record any sideways/vertical movement; inventory/improvement scrollbars now reserve their width.
5. Open Campaigns > How to Use / Help. Check Player and DM tabs, scrolling, returning to the original campaign tab, and no interference with inline rules editing.

## Browser-first QR (staged; requires Android V8 source changes)
1. Host the companion landing files on HTTPS and implement/register `didcharactersheet://pair` in the **current** Android V8 activity (not V7).
2. Confirm the current Pocket DID build can handle the deep link from a normal browser and the existing JSON scanner still works.
3. Only then set `DID_PAIRING_LANDING_URL=https://almogbell.github.io/DID-Character-Sheet/pair/` in the launching environment and restart Windows DID.
4. Start pairing and scan with the phone camera: installed app opens after tapping Open Pocket DID, parses temporary code, pairs and shows Done; with no app installed the page offers GitHub APK release. Let token expire and confirm rejection.
5. For auto-opening **without user tapping a button**, deploy verified App Links on a controlled domain with Android `assetlinks.json`; GitHub Releases or a project GitHub Pages path alone cannot verify links.
6. Build Android using **release application ID and compatible signing key**. If Android Studio installs a second app, do not uninstall or clear either copy. Fix package/signing first.

## Automated checks run on this update
- `python -m compileall -q` on all changed Python source files: PASS.
- `python -m unittest -v test_mobile_pairing_link.py`: 3/3 PASS.
- `python DID_Important_Tests/mobile_protocol_smoke_1013.py`: 3/3 PASS with fake Qt transport.
- PySide6 Qt UI, live socket tests, Android Gradle build, physical-device and packaged-installer tests: **NOT RUN** because PySide6 and Android source/build are not present in this environment.
