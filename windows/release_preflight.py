"""DID 1.0.13 release SOURCE preflight, with actionable failure explanations.

Run from the Windows project (beside frontend_2_8.py):
    python release_preflight.py

Only inspects source files. Does not build or publish, change data or keys.
Outputs release_preflight_report.txt to make follow-up diagnosis easy.
"""
from __future__ import annotations
from pathlib import Path
import os
import re
import sys

ROOT = Path(__file__).resolve().parent
RESULTS: list[tuple[bool,str,str]] = []


def test(label: str, valid: bool, on_failure: str = "") -> None:
    RESULTS.append((bool(valid), label, on_failure))


def source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ""


def android_candidates() -> list[Path]:
    roots = []
    explicit = os.getenv("DID_ANDROID_ROOT")
    if explicit:
        roots.append(Path(explicit))
    roots += [ROOT.parent / "DIDAndroid", ROOT.parent / "DIDAndroid (2)", ROOT]
    return [p / "app" / "build.gradle.kts" for p in roots]


def run() -> int:
    windows = ROOT / 'frontend_2_8.py'
    spec = ROOT / 'DID_Character_Sheet.spec'
    installer = ROOT / 'DID_Character_Sheet_Installer_with_icon.iss'
    test('Windows project directory', windows.is_file(),
         f'Move release_preflight.py beside frontend_2_8.py (this script is in {ROOT}).')
    test('Windows PyInstaller spec', spec.is_file(),
         'Extract the repaired DID_Character_Sheet.spec into the Windows project folder.')
    test('Windows Inno Setup installer configuration', installer.is_file(),
         'Extract the repaired DID_Character_Sheet_Installer_with_icon.iss into the Windows project folder.')

    s = source(spec)
    test('Both dashboards bundled in EXE',
         all(item in s for item in ("('dm_dashboard', 'dm_dashboard')", "('party_dashboard', 'party_dashboard')")),
         'The old .spec lacks the dashboard assets; install the updated .spec in this repair ZIP.')
    test('Dashboard Python modules bundled',
         "'dashboard_server'" in s and "'dashboard_runtime'" in s,
         'Install the updated .spec (includes both dashboard hidden imports).')
    iss = source(installer)
    test('Windows installer version 1.0.13',
         bool(re.search(r'^#define\s+MyAppVersion\s+"1\.0\.13"\s*$', iss, re.M)),
         'The old installer reports 1.0.12; install the updated .iss.')
    test('Windows installer stable AppId',
         '0DCE3792-7789-4AE5-B5A7-18AB2A512928' in iss,
         'Do not change the AppId from the existing released application.')

    test('DM Dashboard assets present', (ROOT/'dm_dashboard'/'index.html').is_file(),
         'Keep the existing dm_dashboard folder intact.')
    test('Party Dashboard assets present', (ROOT/'party_dashboard'/'index.html').is_file(),
         'Keep the existing party_dashboard folder intact.')
    test('Dashboard server source present', (ROOT/'dashboard_server.py').is_file(),
         'dashboard_server.py should already be in your Windows project.')
    runtime = ROOT/'dashboard_runtime.py'
    test('Packaged dashboard runtime helper present', runtime.is_file(),
         'Extract dashboard_runtime.py from this repair ZIP.')
    test('Packaged dashboard server can run inside the EXE',
         'start_frozen_dashboard' in source(ROOT/'campaign_dashboard_bridge.py')
         and 'start_frozen_dashboard' in source(ROOT/'campaign_party_bridge.py'),
         'Extract BOTH campaign_dashboard_bridge.py and campaign_party_bridge.py from this repair ZIP.')

    android_file = next((p for p in android_candidates() if p.is_file()), None)
    test('Android Gradle configuration found', android_file is not None,
         'Expected a sibling DIDAndroid\\app\\build.gradle.kts. If elsewhere, set DID_ANDROID_ROOT to the Android project folder.')
    gradle = source(android_file) if android_file else ''
    test('Android production app package unchanged',
         bool(re.search(r'applicationId\s*=\s*"com\.did\.charactersheet"', gradle)),
         'Install the updated app/build.gradle.kts from Problem 16 into DIDAndroid/app.')
    test('Android versionName 1.0.13 / versionCode 17',
         bool(re.search(r'versionName\s*=\s*"1\.0\.13"', gradle))
         and bool(re.search(r'versionCode\s*=\s*17\b', gradle)),
         'Install the updated app/build.gradle.kts from Problem 16.')
    test('Debug APK remains separate', 'applicationIdSuffix = ".phase9test2"' in gradle,
         'Keep the separate test/debug application ID in app/build.gradle.kts.')
    test('Production signing required', 'verifyPocketDidReleaseSigning' in gradle,
         'Install the updated app/build.gradle.kts; this check does not require signing credentials.')

    cloud = source(ROOT/'campaign_cloud.py')
    test('Server-side admission RPC used by Windows client',
         '/rest/v1/rpc/did_admit_compliant_character' in cloud,
         'Install campaign_cloud.py from the Problem 15 admission patch.')

    okay = sum(ok for ok, _, _ in RESULTS)
    lines = [f'DID 1.0.13 source preflight', f'Windows root: {ROOT}',
             f'Android file: {android_file or "NOT FOUND"}', '']
    for ok, label, fix in RESULTS:
        lines.append(f'{"PASS" if ok else "FAIL"}  {label}')
        if not ok and fix:
            lines.append(f'      Fix: {fix}')
    lines += ['', f'{okay}/{len(RESULTS)} source checks passed.',
              'Not verified: signed Android release/update, PyInstaller build,',
              'Windows installer upgrade, real two-computer campaign workflows.']
    report = '\n'.join(lines) + '\n'
    print(report)
    try:
        (ROOT/'release_preflight_report.txt').write_text(report, encoding='utf-8')
        print('Saved: release_preflight_report.txt')
    except OSError:
        print('Could not save report; copy console output if you need assistance.')
    return 0 if okay == len(RESULTS) else 1

if __name__ == '__main__':
    sys.exit(run())
