# -*- mode: python ; coding: utf-8 -*-

# Stable release build.
# The executable name no longer changes with every version.
#
# Put this file in the same folder as:
#   frontend_2_8.py
#   icons\
#
# Build with:
#   pyinstaller --clean --noconfirm DID_Character_Sheet.spec

a = Analysis(
    ['frontend_2_8.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dashboard_server.py', '.'),
        ('icons', 'icons'),
        ('app_icon.ico', '.'),
        ('character_catalog.json', '.'),
        ('suggestions_config.json', '.'),
        ('dice.html', '.'),
        ('d100_physics.js', '.'),
        ('d100_geometry.js', '.'),
        ('dice_libs', 'dice_libs'),
        # Required by DM / Party Dashboard in the single-file installer.
        ('dm_dashboard', 'dm_dashboard'),
        ('party_dashboard', 'party_dashboard'),
    ],
    hiddenimports=['dashboard_server', 'dashboard_runtime'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DID Character Sheet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)
