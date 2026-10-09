# DID Sync Protocol v1

Protocol version: `1`

The Windows desktop application is authoritative. Android sends commands; Windows validates, mutates, saves through the existing desktop path, and broadcasts canonical state.

The first planned released Windows build which speaks this protocol is `1.0.11`. Earlier Windows builds explicitly advertise sync protocol `0` in `updates/windows.json`.

## Transport

Phase 8 uses a LAN WebSocket connection on TCP port `8765` by default.

The same WebSocket endpoint is used for first-time pairing and normal authenticated synchronization. The Windows companion server starts with the desktop application so already-paired phones can reconnect without opening the pairing dialog first.

The server must not be exposed directly to the public internet. Remote/Tailscale support can be added later as a separate transport decision.

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

The Android client accepts Phase 8 pairing/reconnect addresses only in private/link-local IPv4 ranges. It also rejects a pairing QR/pasted code whose `expires_at` has already passed.

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
  "desktop_version": "1.0.11"
}
```

The temporary pairing token expires and is invalidated after a successful pairing. It is never used as the permanent credential.

## Authentication / reconnect

Android stores the paired computer address/identity and its device token in private app storage. On later connections it sends:

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
  "desktop_version": "1.0.11",
  "server_id": "stable-random-server-id",
  "revision": 42
}
```

Unknown or revoked credentials are rejected. Incompatible protocol versions are rejected with a clear `PROTOCOL_MISMATCH` error. Android also rejects mutation access when the connected Windows version is older than `minimum_desktop_version` in `updates/android.json`.

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
    "improvements": {"list_of_taken_improvements": []},
    "inventory": {"list_of_items": []},
    "notes": {"list_of_notes": []},
    "image": {"images": []}
  }
}
```

The exact `character` payload is produced from the current desktop model/serializer. Android must not redefine or round-trip-save the character schema independently. The typed Android snapshot layer is a read-only view over this canonical data and preserves Improvement/Empowerment `choices` for features which depend on them.

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
- Improvement Points (`IP`)

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

Read-only desktop characters reject all mobile mutations.

## Desktop-originated changes

The desktop companion controller watches the canonical serialized desktop state. When the desktop application changes HP, AT, IP, improvements, inventory, notes, identity, portrait data, or another serialized field, the watcher detects the new state and broadcasts a fresh canonical snapshot. Existing desktop mutation functions therefore do not each need custom networking code.

The controller records the post-command signature before the server broadcasts a mobile-originated mutation, preventing the watcher from counting the same change twice.

## Character switching

Phase 8 synchronizes the character currently active in the Windows application. When the active character ID changes, Windows sends:

```json
{
  "type": "active_character_changed",
  "character_id": "..."
}
```

followed by a complete `state` snapshot.

## Disconnect behavior

Android may retain the last received state for display, but disconnected state is read-only. Gameplay mutations are not queued. On reconnect Android requests and receives a fresh state from Windows.

## Security requirements

- Pairing is explicitly initiated from Windows.
- Pairing tokens are random, short-lived and one-time.
- Android rejects expired pairing codes before attempting a connection.
- Android Phase 8 accepts only local/private IPv4 pairing/reconnect hosts.
- Permanent device tokens are random and revocable.
- Character-changing commands require authentication.
- Read-only desktop characters reject mobile mutation commands.
- Device credentials are stored only in private application storage.
- Permanent credentials are never placed in GitHub manifests or QR codes after pairing.
- Android update links must be HTTPS GitHub/GitHubusercontent links.
- The Phase 8 server is LAN-only in intended deployment; do not port-forward it to the public internet.

## Update compatibility

`updates/windows.json` describes the **currently published Windows release**, not the code merely under development. A pre-sync release uses protocol `0`.

`updates/android.json` declares Android's protocol and its minimum compatible Windows version. `sync/windows_protocol_compatibility.json` maps Windows release thresholds to protocol versions. GitHub Actions cross-check the server/client constants, manifests, compatibility table, protocol documentation and test vectors.

A signed Android GitHub release is blocked until the currently advertised Windows release is at least Android's `minimum_desktop_version` and advertises the same protocol.
