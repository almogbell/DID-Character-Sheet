# DID Sync Protocol v1

Protocol version: `1`

The Windows desktop application is authoritative. Android sends commands; Windows validates, mutates, saves through the existing desktop path, and broadcasts canonical state.

## Transport

Phase 8 uses a LAN WebSocket connection on TCP port `8765` by default.

The same WebSocket endpoint is used for first-time pairing and normal authenticated synchronization. This avoids adding a second HTTP server to the desktop application. Discovery/health endpoints may be added later without changing the character-state contract.

The server must not be exposed directly to the public internet. Remote/Tailscale support can be added later.

## Pairing

Pairing must be explicitly started from the Windows app. Windows creates a short-lived one-time token and displays a QR code containing:

```json
{
  "type": "did_pairing",
  "protocol": 1,
  "host": "192.168.1.20",
  "port": 8765,
  "pairing_token": "short-lived-random-token",
  "expires_at": 1791580000,
  "server_id": "stable-random-server-id"
}
```

Android connects to `ws://HOST:PORT` and sends:

```json
{
  "type": "pair",
  "protocol": 1,
  "pairing_token": "short-lived-random-token",
  "device_id": "stable-random-device-id",
  "device_name": "Phone",
  "android_version": "0.8.0"
}
```

Windows exchanges the temporary pairing token for a persistent device token:

```json
{
  "type": "pair_ok",
  "protocol": 1,
  "device_id": "stable-random-device-id",
  "device_token": "persistent-random-device-token",
  "server_id": "stable-random-server-id",
  "desktop_version": "1.0.10"
}
```

The temporary pairing token expires and is invalidated after a successful pairing. It is never used as the permanent credential.

## Authentication / reconnect

Android stores the paired computer identity and its device token in private app storage. On later connections it sends:

```json
{
  "type": "hello",
  "protocol": 1,
  "android_version": "0.8.0",
  "device_id": "stable-random-device-id",
  "device_name": "Phone",
  "device_token": "persistent-random-device-token"
}
```

Windows replies:

```json
{
  "type": "hello_ok",
  "protocol": 1,
  "desktop_version": "1.0.10",
  "server_id": "stable-random-server-id",
  "revision": 42
}
```

Unknown or revoked credentials are rejected. Incompatible protocol versions are rejected with a clear `PROTOCOL_MISMATCH` error.

## Canonical state

After pairing/authentication Windows sends a full snapshot:

```json
{
  "type": "state",
  "protocol": 1,
  "revision": 42,
  "character": {
    "id": "...",
    "name": "Aurora Lockwood",
    "species_name": "...",
    "HP": {},
    "Adversity": {},
    "progression": {},
    "stats": {},
    "improvements": {},
    "inventory": {},
    "notes": []
  }
}
```

The exact `character` payload is produced from the current desktop model/serializer. Android must not redefine the character schema independently.

`revision` increases after every accepted mutation. Android replaces its displayed state from server snapshots instead of treating speculative local edits as authoritative.

## Commands

```json
{
  "type": "command",
  "request_id": "uuid",
  "base_revision": 42,
  "action": "resource.change",
  "payload": {
    "resource": "HP",
    "delta": -1
  }
}
```

Phase 8 initially supports desktop-validated changes for:

- `HP`
- `Adversity`
- Improvement Points, using the exact mutation semantics exposed by the finished desktop application

Android never writes a `.didchar` file directly.

### Accepted command

Windows validates, mutates, saves through the normal desktop persistence code, increments the revision, sends `command_ok`, then broadcasts canonical state:

```json
{
  "type": "command_ok",
  "request_id": "uuid",
  "revision": 43
}
```

### Rejected command

```json
{
  "type": "command_error",
  "request_id": "uuid",
  "code": "VALIDATION_ERROR",
  "message": "Human-readable explanation",
  "revision": 42
}
```

If `base_revision` is stale, Windows returns `STALE_REVISION` and immediately sends the current state.

## Desktop-originated changes

After a desktop-side mutation is saved, the desktop integration calls `notify_desktop_change()`. The sync service increments its revision and broadcasts a new state to all authenticated companion clients.

## Character switching

Phase 8 synchronizes the character currently active in the Windows application. When that character changes, Windows sends:

```json
{
  "type": "active_character_changed",
  "character_id": "..."
}
```

followed by a complete `state` snapshot.

## Disconnect behavior

Android may cache the last received state for display, but disconnected state is read-only. Gameplay mutations are not queued. On reconnect Android receives a fresh state from Windows.

## Security requirements

- Pairing is explicitly initiated from Windows.
- Pairing tokens are random, short-lived and one-time.
- Permanent device tokens are random and revocable.
- Character-changing commands require authentication.
- Device credentials are stored only in private application storage.
- Permanent credentials are never placed in GitHub manifests or QR codes after pairing.
- The Phase 8 server is LAN-only in intended deployment; do not port-forward it to the public internet.

## Update compatibility

`updates/windows.json` and `updates/android.json` declare the supported sync protocol. Android also declares the minimum supported Windows application version. Protocol mismatch produces an update message instead of partial synchronization.
