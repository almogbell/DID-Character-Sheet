# Phase 9 — Android desktop parity

Phase 9 builds on Sync Protocol v1 without changing the authoritative model: Windows remains the only owner of DID game state and character persistence.

## Visual parity

The Android companion intentionally adapts the finished desktop redesign instead of copying a three-column desktop layout onto a phone. It uses the desktop cream/gold/blue palette, serif typography, bordered sheet panels, portrait presentation, compact HP/AT/IP resources, BDV/DR, desktop ability sorting, Improvement/Empowerment hierarchy, Inventory styling, and the desktop note-color palette.

Phone navigation remains `Character | Equipment | Notes`; within Character it remains `Abilities | Improvements`.

## Canonical derived values

Android derives the read-only BDV and DR presentation from the canonical desktop snapshot using the same formulas as the desktop model:

- BDV = `max_AT // 2`
- DR = `(defense die size // 2) + defense bonus`
- explicit `selected_defense_stat_name` is honored; otherwise the highest die/bonus stat is used.

These values are display-only on Android. Windows still owns the character model.

## Additive direct-edit commands

Protocol v1 command envelopes are reused. These actions are additive: older Phase 8 clients never send them, and an older desktop which does not recognize one rejects it rather than mutating unknown state.

### Identity

Only fields that are ordinary desktop text data are directly editable from mobile:

```json
{
  "type": "command",
  "request_id": "uuid",
  "base_revision": 12,
  "action": "identity.set",
  "payload": {"field": "name", "value": "Aurora"}
}
```

Supported fields:

- `name`
- `backstory`

`species_name` is deliberately not a free-text mobile mutation because species is Improvement-backed in the finished desktop application.

### Inventory

Add:

```json
{
  "action": "inventory.add",
  "payload": {"name": "Rope", "description": "50 feet", "quantity": 1}
}
```

Update:

```json
{
  "action": "inventory.update",
  "payload": {"id": "item-id", "name": "Silk Rope", "description": "50 feet", "quantity": 2}
}
```

Remove:

```json
{
  "action": "inventory.remove",
  "payload": {"id": "item-id"}
}
```

All of these commands are applied to the current Windows character, validated there, routed through `mark_dirty(auto_save=True)`, refreshed on the desktop, assigned a new sync revision, and then replaced on Android by the canonical snapshot.

## Deliberately not duplicated on Android

Phase 9 does not implement a second Kotlin rules engine for Improvement purchasing, empowerments, species rules, creation rules, or system-note generation. Those flows must call Windows/backend rule paths before mobile editing for them is exposed.

Notes are displayed with desktop color/pin/link metadata, but destructive note editing remains deferred until the permanent/system-note protections from the current desktop Notes implementation are wired explicitly.
