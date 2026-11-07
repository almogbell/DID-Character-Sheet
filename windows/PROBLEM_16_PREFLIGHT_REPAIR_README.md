# DID 1.0.13 — Release Preflight Repair

This corrects **release configuration and packaged-dashboard launching**, not character data.

## What was wrong

The earlier release-preflight ZIP included `release_preflight.py` but **not** the updated `DID_Character_Sheet.spec` / `.iss` configurations it required. Older files can still show version 1.0.12 and omit bundled dashboard assets. In addition, the Problem 14 Party Dashboard source imported `dashboard_runtime.py`, but that module was absent from the delivered patch. Bundled PyInstaller executables cannot use `sys.executable` to run `dashboard_server.py` because `sys.executable` points to the app EXE, not Python.

## Install (Windows source ONLY)

1. CLOSE DID Character Sheet and make a copy of `C:\Users\almog\Desktop\current code` or at least back up the files this ZIP replaces.
2. Extract the files in this ZIP directly into `C:\Users\almog\Desktop\current code`, preserving `DID_Important_Tests` and replacing matching files.
3. Leave `C:\Users\almog\Desktop\DIDAndroid` unchanged. The Problem 16 Android Gradle patch remains required but is not repeated here.
4. Do NOT run any Supabase SQL again. No database changes are part of this repair.

Files updated:
- `DID_Character_Sheet.spec`: bundles DM + Party HTML/JS and dashboard runtime modules.
- `DID_Character_Sheet_Installer_with_icon.iss`: version 1.0.13, same Inno Setup AppId.
- `dashboard_runtime.py`: NEW. Maintains source-mode launching; packaged EXE serves dashboard HTML on loopback using a daemon thread and a writable copy of static assets.
- `campaign_dashboard_bridge.py`, `campaign_party_bridge.py`: use the runtime helper correctly in the packaged app.
- `release_preflight.py`: makes every failure actionable and saves `release_preflight_report.txt`.
- `DID_Important_Tests/test_problem16_preflight_repair.py`: focused source and loopback regression tests.

## Run

In PowerShell:

```powershell
cd 'C:\Users\almog\Desktop\current code'
python release_preflight.py
python -m unittest discover -s DID_Important_Tests -p test_problem16_preflight_repair.py -v
```

Expected from the preflight if your earlier Windows and Android patches are installed: `18/18 source checks passed.`

If a check still fails, attach `release_preflight_report.txt` from the Windows source folder; it identifies the exact path and remediation. Common errors: `DIDAndroid` isn't next to `current code`, the original Gradle file is still present, or the Problem 15 `campaign_cloud.py` update wasn't applied.

For an Android project in a different folder, before running:

```powershell
$env:DID_ANDROID_ROOT = 'C:\path\to\DIDAndroid'
python release_preflight.py
```

## Scope and limitations

This is *source verification*, not a Windows installer or Android APK build. Neither digital signing nor an upgrade from 1.0.12 is tested here. The dashboard runtime was exercised locally using an HTTP loopback test, not yet in a real PyInstaller executable. Do not publish the release before the final device and two-computer integration tests.
