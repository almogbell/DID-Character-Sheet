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

The controller starts the authenticated server when the desktop application starts, so a previously paired phone can reconnect automatically. Pairing itself still requires the user to explicitly choose Start pairing.

The controller polls the canonical desktop serializer every 500 ms while sync is active. Existing desktop HP/AT/IP/improvement/inventory/note functions therefore do not need networking calls sprinkled throughout the frontend. A changed serialized state results in a fresh canonical Android snapshot.

## Final frontend integration

Once these modules are copied beside the finished desktop source, the final main window only needs to import and instantiate the controller once after `self.character` and the normal UI are ready:

```python
from mobile_companion_controller import install_mobile_companion

self.mobile_companion = install_mobile_companion(
    self,
    CharacterStorageSystem,
    APP_VERSION,
)
```

The controller recognizes the existing DID Tools menu by its normal `Load Character` / `Check for Updates` actions and inserts `Mobile Companion` automatically before `Check for Updates`, so `toggle_tools_menu()` does not need to be rewritten.

A manual shutdown call is optional but clean:

```python
if hasattr(self, "mobile_companion"):
    self.mobile_companion.shutdown()
```

The controller automatically detects ordinary desktop state changes, including active-character replacement, so existing mutation functions do not need Phase 8-specific edits.

## Additional packaging dependency

Install the QR dependency from `windows/mobile_companion_requirements.txt`. PySide6 already supplies Qt WebSockets in the desktop runtime; the packaged build must include the imported `PySide6.QtWebSockets` module.
