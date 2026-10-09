# DID Character Sheet — Windows

The Windows app is the authoritative implementation of DID character rules, character storage, Improvements, Inventory, Notes, dice behavior, and mobile-companion synchronization.

## Releases

Windows releases continue to use tags such as `v1.0.10`. Windows and Android have independent version numbers and may be released separately.

`updates/windows.json` is also the compatibility manifest used by the companion-release tooling. Protocol `0` means the published Windows build predates mobile sync. The first planned sync-enabled Windows release is `1.0.11`, which maps to protocol `1` in `sync/windows_protocol_compatibility.json`.

After this branch is merged to `main`, `.github/workflows/windows-release-manifest.yml` automatically updates `updates/windows.json` whenever a normal Windows `vX.Y.Z` GitHub Release with an `.exe` asset is published. Existing Windows update behavior can therefore remain unchanged while Android receives accurate compatibility information.

## Phase 8 mobile companion

Android connects to the running Windows application. The phone does not own or rewrite `.didchar` files.

The Phase 8 desktop layer is split deliberately:

- `mobile_sync_server.py` — authenticated WebSocket transport, pairing and revisions.
- `mobile_sync_frontend_adapter.py` — translates allowed phone commands into the existing desktop character model/save path.
- `mobile_companion_controller.py` — starts the server with Windows, watches canonical desktop state for changes, prevents mobile-originated changes from being double-counted, and injects the Mobile Companion action into the existing Tools menu.
- `mobile_companion_dialog.py` — QR/manual pairing and paired-phone management.
- `integrate_mobile_companion.py` — safe/idempotent finished-frontend patcher.

The controller starts the authenticated server when the desktop application starts, so a previously paired phone can reconnect automatically. Pairing itself still requires the user to explicitly choose Start pairing.

The controller polls the canonical desktop serializer every 500 ms. Existing desktop HP/AT/IP/improvement/inventory/note functions therefore do not need networking calls sprinkled throughout the frontend. A changed serialized state results in a fresh canonical Android snapshot.

## Finished 1.0.10 frontend integration

The finished `frontend_2_8(20261009-160308).py` bootstrap has been inspected. Its main-window startup ends with:

```python
self.setup_keyboard_shortcuts()
self.refresh_all()
self.reset_undo_history(
    treat_current_as_clean=True
)
```

The Phase 8 controller belongs immediately after that sequence. Rather than hand-editing the large frontend, run:

```text
python windows/integrate_mobile_companion.py frontend_2_8.py --version 1.0.11
```

The patcher:

- changes `APP_VERSION` to `1.0.11` by default,
- adds the one controller installation block at the confirmed bootstrap point,
- creates `frontend_2_8.py.phase8.bak` the first time it changes the file,
- is idempotent if run again,
- refuses to modify an unknown frontend layout instead of guessing.

Equivalent inserted code is:

```python
try:
    from mobile_companion_controller import install_mobile_companion
    install_mobile_companion(
        self,
        CharacterStorageSystem,
        APP_VERSION,
    )
except Exception:
    traceback.print_exc()
```

The controller recognizes the finished Tools menu using its stable New Character / Load Character / Edit Abilities actions and inserts `Mobile Companion` before the Dice Roller submenu. It does **not** depend on a permanent `Check for Updates` action, because the finished 1.0.10 frontend only displays its update row when an update actually exists.

No `closeEvent` edit is required: the controller shuts the sync server down from `QApplication.aboutToQuit`.

The controller automatically detects ordinary desktop state changes, including active-character replacement, so existing mutation functions do not need Phase 8-specific edits.

## Additional packaging dependency

Install the QR dependency from `windows/mobile_companion_requirements.txt` before freezing the app:

```text
python -m pip install -r windows/mobile_companion_requirements.txt
```

PySide6 already supplies Qt WebSockets in the desktop runtime; the packaged build must include the imported `PySide6.QtWebSockets` module. Because the integrated frontend contains a normal Python import of `mobile_companion_controller`, PyInstaller can follow the controller → dialog/server/adapter imports during analysis. The release build should still be smoke-tested after freezing to confirm the QR dependency and Qt WebSockets plugins are present.
