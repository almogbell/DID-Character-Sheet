# DID Character Sheet — Windows

The Windows app is the authoritative implementation of DID character rules, character storage, Improvements, Inventory, Notes, dice behavior, and mobile-companion synchronization.

## Releases

Windows releases use tags such as `v1.0.10` and the Windows updater reads `updates/windows.json`.

The desktop and Android apps have independent version numbers and may be released separately.

## Phase 8 mobile companion

Android connects to the running Windows application. The phone does not own or rewrite `.didchar` files.

The Phase 8 desktop layer is split deliberately:

- `mobile_sync_server.py` — authenticated WebSocket transport, pairing and revisions.
- `mobile_sync_frontend_adapter.py` — translates allowed phone commands into the existing desktop character model/save path.
- `mobile_companion_controller.py` — starts the server with Windows, watches canonical desktop state for changes, and prevents mobile-originated changes from being double-counted.
- `mobile_companion_dialog.py` — QR pairing and paired-phone management.

The controller starts the authenticated server when the desktop application starts, so a previously paired phone can reconnect automatically. Pairing itself still requires the user to explicitly choose Start pairing.

The controller polls the canonical desktop serializer every 500 ms while sync is active. This means existing desktop HP/AT/IP/improvement/inventory/note code does not need networking calls sprinkled through every mutation function. A changed serialized state results in a fresh canonical Android snapshot.

## Final frontend integration

Once these modules are copied beside the finished desktop source, the final main window only needs to:

1. import `install_mobile_companion`;
2. create it once after the window/character model is initialized;
3. expose `self.mobile_companion.show_dialog` from the existing Tools menu;
4. call `self.mobile_companion.shutdown()` during final application cleanup.

Example:

```python
from mobile_companion_controller import install_mobile_companion

# after self.character / the normal UI are ready
self.mobile_companion = install_mobile_companion(
    self,
    CharacterStorageSystem,
    APP_VERSION,
)
```

Tools action:

```python
("Mobile Companion", self.mobile_companion.show_dialog)
```

The controller automatically detects normal desktop state changes, including active-character replacement, so ordinary desktop mutation functions do not need to be rewritten for Phase 8.

## Additional packaging dependency

Install the QR dependency from `windows/mobile_companion_requirements.txt`. PySide6 already supplies Qt WebSockets in the desktop runtime; the packaged build must include the imported `PySide6.QtWebSockets` module.
