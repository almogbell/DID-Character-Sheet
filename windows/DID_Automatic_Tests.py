#!/usr/bin/env python3
"""Read-only DID Character Sheet source/asset checks plus sandboxed offline regression runs.

Designed for Windows PowerShell. Tests run from a disposable copy of the
application, with a temporary home and outbound Python network access blocked.
No live Supabase, Discord or mobile-device mutation is attempted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

SUITE_TIMEOUT = 25
STRESS_TIMEOUT = 120
SKIP_DIRS = {
    '.venv', 'venv', '.git', '.idea', '.vscode', '__pycache__',
    'node_modules', 'build', 'dist', 'reports', 'Saved_Characters',
    'Saved_characters', 'Saved Characters', 'Recovery', 'character_backups',
    'user_data', 'user-data', '.pytest_cache', 'DID_Test_Reports',
}
SKIP_FILE_PATTERNS = (
    '.didchar', '.didbackup', '.pyc', '.pyo', '.log', '.bak', '.old',
    '.sqlite', '.sqlite3', '.db', '.db-journal', '.lock', '.env',
    '.pem', '.p12', '.pfx', '.key',
)
SKIP_PREFIXES = ('crash_log', 'DID_1.0.14_build', 'DID114_patch_error')
QUICK_NAMES = {
    'test_did_campaign_progression_policy.py',
    'test_did_join_and_dialog_regressions_20261107.py',
    'test_did_d100_enter_readability_20261107.py',
    'test_did_mixed_d100_player_header_20261107.py',
    'test_did_mixed_dice_readability_20261106.py',
    'test_did_readable_theme_loading_20261106.py',
    'test_did_d100_notes_20261106.py',
    'test_did_portrait_dice_color.py',
    'test_did_numeric_dice_regression.py',
    'test_campaign_roll_outbox.py',
    'test_problem02_inventory_compact_quantity.py',
    'test_problem02_inventory_geometry.py',
    'test_problem04_lan_pairing_address.py',
    'test_problem05_mobile_dialog_layout.py',
    'test_mobile_companion_viewport_fit.py',
    'test_autosave_saved_characters.py',
    'test_species_idle_autosave_20261107.py',
    'test_mobile_sync_contract.py',
    'test_core.py',
    'test_did_regression_cleanup.py',
}
MANUAL = [
    'Actual Windows window layout at different sizes (including player heading and Mobile Companion scrollbar)',
    '3D die appearance, d100 scale, number readability, color, physics and displayed results',
    'Actual Enter key interaction with the Roll Other Dice dialog',
    'Real phone QR-code pairing and reconnecting over local Wi-Fi',
    'Live campaign creation, invitations, permissions, and two-account synchronization',
    'Offline roll persistence/reconnection with a real cloud account',
    'Installed .exe/installer, Windows shortcuts and long-term stability',
]


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def announce(message):
    print(message, flush=True)


def category(path):
    n = path.name.lower()
    if 'dice' in n or 'd100' in n or 'heightened' in n:
        return 'Dice and d100'
    if any(k in n for k in ('mobile', 'phone', 'pairing', 'sync', 'android', 'device')):
        return 'Mobile and sync'
    if 'campaign' in n or 'admission' in n or 'dashboard' in n or 'join_' in n or 'party' in n:
        return 'Campaigns and cloud'
    if 'discord' in n:
        return 'Discord'
    if any(k in n for k in ('notes', 'note_', 'portrait', 'inventory', 'improvement', 'ui_', 'layout', 'viewport', 'theme', 'player_polish', 'redesign')):
        return 'UI, notes, inventory'
    return 'Core, saves and safety'


def add(results, title, status, detail='', group='Preflight', seconds=0, log=None, count=None):
    record = dict(name=title, status=status, group=group, detail=detail,
                  duration_seconds=round(seconds, 2))
    if log:
        record['log'] = str(log).replace('\\', '/')
    if count is not None:
        record['reported_tests'] = count
    results.append(record)
    prefix = {'PASS':'PASS', 'FAIL':'FAIL', 'SKIP':'SKIP', 'BLOCKED':'BLOCKED'}[status]
    announce(f'[{prefix}] {title}' + (f' — {detail[:165]}' if detail else ''))


def copy_project(source, destination):
    """Exclude personal save folders, environments and build output."""
    def ignored(_folder, names):
        skipped = []
        for name in names:
            n = name.casefold()
            p = Path(_folder) / name
            if p.is_symlink():
                skipped.append(name)
            elif p.is_dir() and (n in {x.casefold() for x in SKIP_DIRS} or
                                 n.startswith('backup_')):
                skipped.append(name)
            elif p.is_file() and (n.endswith(SKIP_FILE_PATTERNS) or
                                  n.startswith(tuple(x.casefold() for x in SKIP_PREFIXES)) or
                                  n.endswith('.didtemplate.bak') or
                                  n.endswith('.zip')):
                skipped.append(name)
        return skipped
    shutil.copytree(source, destination, ignore=ignored)


def restrict_python_network(folder):
    """Loaded automatically by test subprocesses through PYTHONPATH."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'sitecustomize.py').write_text(r'''# DID automated test network guard: allow loopback only.
import socket as _s
_orig_connect = _s.socket.connect
_orig_connect_ex = _s.socket.connect_ex
_orig_create_connection = _s.create_connection

def _local(address):
    if not isinstance(address, tuple):
        return True  # AF_UNIX and other non-IP transports
    host = str(address[0]).strip('[]').lower()
    return host in ('127.0.0.1', '::1', 'localhost') or host.startswith('127.')

def _guard_connect(self, address):
    if not _local(address):
        raise OSError('DID TEST SANDBOX: outbound network disabled')
    return _orig_connect(self, address)

def _guard_connect_ex(self, address):
    if not _local(address):
        raise OSError('DID TEST SANDBOX: outbound network disabled')
    return _orig_connect_ex(self, address)

def _guard_create_connection(address, *args, **kwargs):
    if not _local(address):
        raise OSError('DID TEST SANDBOX: outbound network disabled')
    return _orig_create_connection(address, *args, **kwargs)

_s.socket.connect = _guard_connect
_s.socket.connect_ex = _guard_connect_ex
_s.create_connection = _guard_create_connection
''', encoding='utf-8')


def save_log(logs, label, text):
    safe = re.sub(r'[^a-zA-Z0-9._-]+', '_', label).strip('._')[:105]
    target = logs / (safe + '.log')
    target.write_text(text, encoding='utf-8', errors='replace')
    return Path('logs') / target.name


def command_run(args, cwd, env=None, timeout=SUITE_TIMEOUT):
    start = time.monotonic()
    try:
        p = subprocess.run(args, cwd=str(cwd), env=env, capture_output=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        return p.returncode, p.stdout, p.stderr, round(time.monotonic() - start, 2), False
    except subprocess.TimeoutExpired as ex:
        stdout = (ex.stdout or b'')
        stderr = (ex.stderr or b'')
        if isinstance(stdout, bytes): stdout = stdout.decode('utf-8', errors='replace')
        if isinstance(stderr, bytes): stderr = stderr.decode('utf-8', errors='replace')
        return -1, stdout, stderr + f'\nTimeout after {timeout} seconds', round(time.monotonic()-start, 2), True
    except Exception as ex:
        return -1, '', str(ex), round(time.monotonic()-start, 2), False


def static_checks(app, results, logdir, node):
    sources = []
    for folder in (app, app/'DID_Important_Tests'):
        if folder.is_dir():
            sources.extend(p for p in folder.glob('*.py') if p.is_file())
    # Remaining project-owned Python files (not third-party) in auxiliary folders.
    for folder in (app/'problem20_support',):
        if folder.is_dir(): sources.extend(folder.rglob('*.py'))
    failures = []
    for p in sources:
        try:
            compile(p.read_bytes(), str(p), 'exec')
        except Exception as exc:
            failures.append(f'{p.relative_to(app)}: {exc}')
    log = save_log(logdir, 'Python_syntax', '\n'.join(failures) or f'Validated {len(sources)} Python files')
    add(results, 'Python source syntax', 'FAIL' if failures else 'PASS',
        f'{len(sources)} files checked; {len(failures)} errors',
        group='Source and assets', log=log)

    required = (
        'frontend_2_8.py', 'backend_2_1.py', 'character_API.py',
        'notes_ui.py', 'inventory_ui.py', 'improvements_ui.py',
        'campaign_runtime.py', 'campaign_role_ui.py',
        'mobile_companion_dialog.py', 'mobile_sync_server.py',
        'dice.html', 'd100_physics.js',
        'dice_libs/dice-box/dice-box.es.min.js',
        'dice_libs/dice-box/assets/themes/did-readable/theme.config.json',
        'dm_dashboard/index.html', 'party_dashboard/index.html',
    )
    missing = [name for name in required if not (app/name).is_file()]
    add(results, 'Required DID application and dice assets', 'FAIL' if missing else 'PASS',
        f'{len(required)-len(missing)}/{len(required)} files present' +
        (': missing ' + ', '.join(missing) if missing else ''),
        group='Source and assets')

    invalid_json = []
    count=0
    for name in ('character_catalog.json',
                 'dice_libs/dice-box/assets/themes/did-readable/theme.config.json'):
        p = app/name
        if p.is_file():
            count+=1
            try: json.loads(p.read_text(encoding='utf-8-sig'))
            except Exception as exc: invalid_json.append(f'{name}: {exc}')
    add(results, 'Critical JSON configuration files', 'FAIL' if invalid_json else 'PASS',
        f'{count} checked' + ('; '+ '; '.join(invalid_json) if invalid_json else ''),
        group='Source and assets')

    js_files = [p for p in app.glob('*.js') if p.is_file()]
    for folder in ('dm_dashboard', 'party_dashboard', 'public'):
        if (app/folder).is_dir():
            js_files.extend(p for p in (app/folder).glob('*.js') if p.is_file())
    html_scripts = []
    dice_html = app/'dice.html'
    if dice_html.exists():
        content = dice_html.read_text(encoding='utf-8')
        for i, (attrs, source) in enumerate(re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', content,
                                                   flags=re.IGNORECASE | re.DOTALL)):
            if not source.strip() or re.search(r'type\s*=\s*["\']application/(json|ld\+json)',attrs,re.I):
                continue
            path = logdir / f'dice_inline_{i}.mjs'
            path.write_text(source, encoding='utf-8')
            html_scripts.append(path)
    if not node:
        add(results, 'JavaScript syntax (Node.js)', 'SKIP',
            'Node.js is not installed; Python and regression checks continue.', group='Source and assets')
    else:
        problems=[]
        scripts = js_files + html_scripts
        for p in scripts:
            # ES module syntax is valid in either .js/.mjs in a modern Node.
            code, out, err, _, timed = command_run([node, '--check', str(p)], app, timeout=15)
            if code != 0:
                problems.append(f'{p.name}: {(err or out)[-700:]}')
        log = save_log(logdir, 'JavaScript_syntax', '\n\n'.join(problems) or f'{len(scripts)} JS scripts passed')
        add(results, 'JavaScript syntax, including dice HTML', 'FAIL' if problems else 'PASS',
            f'{len(scripts)} scripts checked; {len(problems)} errors', log=log,
            group='Source and assets')


def environment_checks(results, app):
    add(results, 'Python version', 'PASS' if sys.version_info >= (3, 10) else 'FAIL',
        f'{platform.python_version()} ({sys.executable})', group='Environment')
    for name, module in [('Qt Widgets', 'PySide6.QtWidgets'),
                         ('Qt WebEngine', 'PySide6.QtWebEngineWidgets'),
                         ('Qt WebChannel', 'PySide6.QtWebChannel'),
                         ('QR codes', 'qrcode'), ('Pillow', 'PIL')]:
        try:
            found = importlib.util.find_spec(module) is not None
        except (ModuleNotFoundError, ValueError):
            found = False
        add(results, name, 'PASS' if found else 'BLOCKED',
            'Available' if found else f'Missing Python module: {module}', group='Environment')
    for module in ('PySide6.QtCore', 'PySide6.QtWidgets'):
        try:
            __import__(module)
        except (Exception, BaseException) as exc:
            add(results, f'Qt runtime import: {module}', 'BLOCKED', f'{type(exc).__name__}: {exc}', group='Environment')
            break
    else:
        add(results, 'Qt runtime imports', 'PASS', 'Qt Core and Widgets import successfully', group='Environment')


def sandbox_env(app, sandbox, outdir, guard_dir, android):
    child = os.environ.copy()
    homedir = sandbox/'test_home'
    appdata = homedir/'AppData'/'Roaming'
    local = homedir/'AppData'/'Local'
    for p in (homedir, appdata, local, homedir/'tmp'):
        p.mkdir(parents=True, exist_ok=True)
    child.update({
        'HOME': str(homedir), 'USERPROFILE': str(homedir),
        'APPDATA': str(appdata), 'LOCALAPPDATA': str(local),
        'XDG_CONFIG_HOME': str(homedir/'.config'),
        'XDG_DATA_HOME': str(homedir/'.local'/'share'),
        'XDG_CACHE_HOME': str(homedir/'.cache'),
        'TMP': str(homedir/'tmp'), 'TEMP': str(homedir/'tmp'),
        'QT_QPA_PLATFORM': 'offscreen',
        'DID_APP_DIR': str(app),
        'DID_TEST_REPORT_DIR': str(outdir),
        'DID_AUTOMATED_TEST': '1',
        'PYTHONPATH': os.pathsep.join([str(guard_dir), str(app), str(app/'DID_Important_Tests')]),
    })
    if android and android.exists():
        child['DID_ANDROID_PROJECT'] = str(android)
        child['DID_ANDROID_ROOT'] = str(android)
    return child


def run_suite(path, app, env, results, logs, timeout):
    group = category(path)
    title = str(path.relative_to(app)).replace('\\','/')
    code, stdout, stderr, elapsed, timed = command_run([sys.executable, '-B', str(path)],
                                                       cwd=app, env=env, timeout=timeout)
    output = f'$ {sys.executable} -B {title}\nExit: {code}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}'
    log = save_log(logs, title, output)
    combined = stdout + '\n' + stderr
    match = list(re.finditer(r'Ran\s+(\d+)\s+tests?', combined))
    count = int(match[-1].group(1)) if match else None
    if timed:
        status, detail = 'FAIL', f'Test timed out after {timeout}s'
    elif code == 0:
        status, detail = 'PASS', (f'{count} unittest cases' if count is not None else 'Completed without errors')
    elif ('No module named \'PySide6\'' in combined or
          'ModuleNotFoundError: No module named \'PySide6' in combined or
          'No module named \'qrcode\'' in combined or
          'No module named \'PIL\'' in combined):
        status, detail = 'BLOCKED', 'Required Python GUI/QR dependency is missing'
    else:
        status='FAIL'
        excerpt = [line.strip() for line in combined.splitlines() if line.strip()]
        detail = (excerpt[-1] if excerpt else f'Exited with code {code}')[:195]
        # Two older test harnesses target implementations removed by later fixes.
        # Preserve FAIL in the report, while distinguishing the harness mismatch
        # from an observed GUI/physics regression.
        if path.name == 'test_did_mixed_dice_readability_20261106.py' and 'mixed && quantity === 1 ? 1.25 : 1' in combined:
            detail = 'OLDER TEST EXPECTATION: looks for removed 1.25 camera zoom expression; latest d100 uses tracked camera. Update this test.'
        elif path.name == 'test_did_portrait_dice_color.py' and 'readableThemeReady is not defined' in combined:
            detail = 'OLDER TEST HARNESS: extracted roll function without its readableThemeReady closure variable. Update the test harness.'
        elif path.name == 'test_problem07_pairing_lifecycle.py' and '_schedule_qr_fit' in combined:
            detail = 'OLDER TEST HARNESS: FakeDialog lacks _schedule_qr_fit added by responsive QR fix. Update the test harness.'
    add(results, title, status, detail=detail, group=group,
        seconds=elapsed, log=log, count=count)


def reports(outdir, results, original, mode, elapsed, node):
    summary = {s: sum(r['status']==s for r in results) for s in ('PASS','FAIL','BLOCKED','SKIP')}
    rep = {
        'generated_utc': now_utc(), 'project_under_test': str(original),
        'mode': mode, 'elapsed_seconds': round(elapsed, 1),
        'python': sys.version.splitlines()[0], 'node': bool(node),
        'summary_checks': summary, 'results': results,
        'not_automatically_tested': MANUAL,
        'note': 'Offline sandbox test only. PASS does not imply real phone, cloud, Qt 3D renderer or installed EXE verification.',
    }
    (outdir/'DID_Test_Report.json').write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding='utf-8')
    lines = [f'DID CHARACTER SHEET — AUTOMATIC TEST REPORT',
             f'Generated: {rep["generated_utc"]}', f'Project: {original}',
             f'Mode: {mode}', f'Total checks: {len(results)}',
             f'PASS {summary["PASS"]} | FAIL {summary["FAIL"]} | BLOCKED {summary["BLOCKED"]} | SKIP {summary["SKIP"]}',
             '', 'FAILURES / BLOCKED:']
    for r in results:
        if r['status'] in ('FAIL','BLOCKED'):
            lines += [f'  [{r["status"]}] {r["name"]}: {r["detail"]}' +
                      (f' (see {r["log"]})' if r.get('log') else '')]
    if not any(r['status'] in ('FAIL','BLOCKED') for r in results):
        lines.append('  None.')
    lines.extend(['','ALL CHECKS:'])
    for r in results:
        lines.append(f'  [{r["status"]:7}] {r["name"]}: {r["detail"]}')
    lines.extend(['', 'REQUIRES MANUAL TESTING:'])
    for x in MANUAL: lines.append(f'  - {x}')
    lines.append('')
    (outdir/'DID_Test_Report.txt').write_text('\n'.join(lines), encoding='utf-8')
    palette={'PASS':'#18754a','FAIL':'#b42318','BLOCKED':'#a15c08','SKIP':'#65758a'}
    rows=[]
    for r in results:
        status=r['status']; link = (f'<a href="{html.escape(r["log"])}">Details</a>' if r.get('log') else '')
        rows.append('<tr>' + ''.join([
            f'<td><span class="tag" style="background:{palette[status]}">{status}</span></td>',
            f'<td>{html.escape(r["group"])}</td>',
            f'<td>{html.escape(r["name"])}</td>',
            f'<td>{html.escape(str(r["detail"]))}</td>',
            f'<td>{r["duration_seconds"]:.1f}s</td>',
            f'<td>{link}</td>',
        ]) + '</tr>')
    manual = ''.join(f'<li>{html.escape(x)}</li>' for x in MANUAL)
    html_text = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DID Automatic Test Results</title><style>
body{font:15px/1.55 Segoe UI,system-ui,Arial;margin:0 auto;padding:24px;max-width:1300px;background:#f7f8fa;color:#25324b}
h1{margin:0 0 6px}.muted{color:#637083}.summary{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.pill{background:white;border:1px solid #dde3eb;border-radius:10px;padding:12px 20px;font-weight:700}
.panel{background:white;border:1px solid #dce2eb;border-radius:10px;padding:18px;margin:16px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e4e8ed;text-align:left;vertical-align:top}th{background:#eff2f5;position:sticky;top:0}td:nth-child(3){font-weight:600}a{color:#1769a2}.tag{color:white;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:700}li{margin:5px 0}
</style></head><body>'''
    html_text += f'<h1>DID Character Sheet — Automatic Test Report</h1><p class="muted">{html.escape(rep["generated_utc"])} · {html.escape(mode)} mode<br>Project: {html.escape(str(original))}</p>'
    html_text += '<div class="summary">' + ''.join(f'<div class="pill" style="color:{palette[s]}">{s}: {summary[s]}</div>' for s in summary) + '</div>'
    html_text += '<section class="panel"><strong>Scope:</strong> syntax, source assets and offline regression tests in a disposable copy of the project. No real cloud writes or phone pairing. Tests may reveal failures in older test expectations. A pass is not proof of correct visual rendering.</section>'
    html_text += '<section class="panel"><table><thead><tr><th>Status</th><th>Area</th><th>Check</th><th>Result</th><th>Duration</th><th>Log</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></section>'
    html_text += '<section class="panel"><h2>Still requires hands-on checks</h2><ul>' + manual + '</ul></section></body></html>'
    (outdir/'DID_Test_Report.html').write_text(html_text,encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True, type=Path)
    parser.add_argument('--report-dir', required=True, type=Path)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--android-project', type=Path)
    args=parser.parse_args()
    original=args.project_dir.expanduser().resolve()
    outdir=args.report_dir.expanduser().resolve()
    if not (original/'frontend_2_8.py').is_file():
        parser.error(f'Not the DID source folder: {original} (frontend_2_8.py missing)')
    outdir.mkdir(parents=True,exist_ok=True)
    logs=outdir/'logs'; logs.mkdir(exist_ok=True)
    node=shutil.which('node')
    start=time.monotonic()
    results=[]
    announce(f'\nDID AUTOMATIC TESTS — {"QUICK" if args.quick else "FULL"} MODE')
    announce(f'Project: {original}')
    announce(f'Report:  {outdir}')
    announce('Source project is not edited. Running tests in temporary isolated copy.')
    with tempfile.TemporaryDirectory(prefix='DID_Test_') as tmp:
        sandbox=Path(tmp)
        app=sandbox/'DID'
        announce('\n[PREPARING] Copying testable source and assets to sandbox ...')
        copy_project(original, app)
        env=sandbox_env(app, sandbox, outdir, sandbox/'network_guard', args.android_project)
        restrict_python_network(sandbox/'network_guard')
        environment_checks(results, app)
        announce('\n[STATIC] Python / JavaScript / assets')
        static_checks(app, results, logs, node)
        scripts = sorted((app/'DID_Important_Tests').glob('test_*.py')) + sorted(app.glob('test_*.py'))
        scripts = [p for p in scripts if p.name != 'test_support.py']
        if args.quick:
            scripts = [p for p in scripts if p.name in QUICK_NAMES]
        else:
            scripts += sorted((app/'DID_Important_Tests').glob('automated_*_torture_test.py'))
            for name in ('check_campaign_modules.py','mobile_protocol_smoke_1013.py'):
                p=app/'DID_Important_Tests'/name
                if p.exists(): scripts.append(p)
        announce(f'\n[REGRESSIONS] {len(scripts)} existing test scripts selected')
        for i, path in enumerate(scripts, start=1):
            announce(f'[{i}/{len(scripts)}] {path.relative_to(app)}')
            if path.name in ('test_problem20_android_sources.py',
                             'test_problem04_inbound_state_reconciliation.py',
                             'test_problem04_phone_to_windows_sync.py') and not (
                args.android_project and (args.android_project/'phase8'/'DidOfflineStore.kt').is_file()
            ):
                add(results, str(path.relative_to(app)), 'SKIP',
                    'Android source project not provided (use -AndroidProject).', group='Mobile and sync')
                continue
            if not node and ('node' in path.read_text(encoding='utf-8',errors='replace') and
                             ('subprocess.run(' in path.read_text(encoding='utf-8',errors='replace') or
                              'node --check' in path.read_text(encoding='utf-8',errors='replace'))):
                add(results, str(path.relative_to(app)), 'SKIP',
                    'Requires Node.js for a JavaScript integration check.', group=category(path))
                continue
            timeout=STRESS_TIMEOUT if 'torture_test' in path.name else SUITE_TIMEOUT
            run_suite(path, app, env, results, logs, timeout)
        elapsed=time.monotonic()-start
        summary=reports(outdir,results,original,'quick' if args.quick else 'full',elapsed,node)
    announce('\n'+'='*70)
    announce(f'COMPLETED: {summary["PASS"]} PASS | {summary["FAIL"]} FAIL | {summary["BLOCKED"]} BLOCKED | {summary["SKIP"]} SKIP')
    announce(f'Report: {outdir / "DID_Test_Report.html"}')
    announce(f'Share this file for analysis: {outdir / "DID_Test_Report.txt"}')
    announce('Note: Real Windows 3D dice appearance and phone/cloud pairing need manual tests.')
    return 0 if not summary['FAIL'] and not summary['BLOCKED'] else 1


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        announce('\nTests interrupted. Existing app files were not modified.')
        raise SystemExit(130)
    except Exception as exc:
        announce(f'\nFATAL: {type(exc).__name__}: {exc}')
        traceback.print_exc()
        raise SystemExit(2)
