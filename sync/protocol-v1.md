# DID Sync Protocol v1

Protocol version: `1`

The desktop application is authoritative. Android sends commands; Windows validates, mutates, saves, and broadcasts canonical state.

## Transport

Phase 8 uses the local network first.

- HTTP is used for pairing and basic discovery/health endpoints.
- WebSocket is used for authenticated live synchronization.
- Remote/Tailscale support may be added later without changing the character-state contract.

## Pairing

The Windows app starts a temporary pairing session and shows a QR code containing:

```json
{
  "type": "did_pairing",
  "protocol": 1,
  "host": "192.168.1.20",
  "port": 8765,
  "pairing_token": "short-lived-random-token"
}
```

The pairing token must expire and must not be reused as the permanent device credential.

Android exchanges it for a persistent random device token and stores the paired computer identity locally.

## Authentication

Every WebSocket connection must authenticate using the paired device token. Unknown/revoked tokens are rejected.

Windows must provide a UI to revoke paired devices.

## Connection hello

Android sends:

```json
{
  "type": "hello",
  "protocol": 1,
  "android_version": "0.8.0",
  "device_id": "stable-random-device-id",
  "device_name": "Phone"
}
```

Windows replies:

```json
{
  "type": "hello_ok",
  "protocol": 1,
  "desktop_version": "1.0.10",
  "server_id": "stable-random-server-id"
}
```

If protocol versions are incompatible, Windows returns an error and closes the connection.

## Canonical state

After authentication, Windows sends a full state snapshot:

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

The exact `character` payload should be produced from the current desktop model, not redefined independently by Android.

`revision` increases after every accepted mutation. Android replaces its displayed model from server state rather than treating its speculative local state as authoritative.

## Commands

A command envelope is:

```json
{
  "type": "command",
  "request_id": "uuid",
  "base_revision": 42,
  "action": "resource.change",
  "payload": {}
}
```

### Phase 8 actions

#### Change HP

```json
{
  "action": "resource.change",
  "payload": {
    "resource": "HP",
    "delta": -1
  }
}
```

#### Change Adversity Tokens

```json
{
  "action": "resource.change",
  "payload": {
    "resource": "Adversity",
    "delta": 1
  }
}
```

#### Change Improvement Points

The exact desktop-supported IP mutation semantics must be used. Android must not bypass desktop validation.

## Accepted command

Windows applies the command using the desktop model, saves through the normal desktop persistence path, increments the revision, and broadcasts canonical state.

Optionally, it may first send:

```json
{
  "type": "command_ok",
  "request_id": "uuid",
  "revision": 43
}
```

The subsequent `state` message remains authoritative.

## Rejected command

```json
{
  "type": "command_error",
  "request_id": "uuid",
  "code": "VALIDATION_ERROR",
  "message": "Human-readable explanation",
  "revision": 42
}
```

Android must revert any temporary visual change and use the latest server state.

## Desktop-originated changes

When the user changes the character in the Windows UI, the desktop sync service broadcasts a new `state` message to all authenticated companion clients.

Android therefore does not need to poll for character changes.

## Character switching

Phase 8 may initially synchronize the single character currently active in the Windows application.

When the desktop active character changes, Windows broadcasts:

```json
{
  "type": "active_character_changed",
  "character_id": "..."
}
```

followed by a full `state` snapshot.

Multi-character independent mobile sessions can be added in a later protocol version if desired.

## Disconnect behavior

Android may retain the last state for display, but while disconnected it is read-only. It must not queue gameplay edits which could create two competing character histories.

On reconnect, Android requests and displays a fresh full state from Windows.

## Security requirements

- Server binds only as broadly as required for LAN access.
- Pairing must be explicitly initiated from Windows.
- Pairing tokens expire quickly.
- Permanent device tokens are random and revocable.
- Character-changing commands require authentication.
- Never place permanent credentials in GitHub update manifests.
- Do not expose the desktop server directly to the public internet in Phase 8.

## Update compatibility

`updates/windows.json` and `updates/android.json` declare their supported sync protocol. Android also declares the minimum supported Windows application version.

If protocol versions are incompatible, the connection is refused with a clear update message rather than attempting partial synchronization.
