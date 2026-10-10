# Phase 9 real-device acceptance

Run this only after Phase 8 Windows↔Android pairing already works.

## V3 setup

1. Close Windows DID.
2. Replace `mobile_sync_frontend_adapter.py` with the Phase 9 V3 delta version, then restart DID.
3. Install/update the `DID Phase 9 Test 2` APK.
4. Reconnect or pair the phone if needed.

The V3 Windows adapter adds a mobile-only `_mobile_ui.icons` block to snapshots. It reads the actual SVG artwork from the running desktop installation (`icons/*.svg` and `icons/defenses/*.svg`). This data is never written into `.didchar` files.

## Visual / interaction checks

- HP and Hearts appear together as one resource group.
- Each Heart uses the desktop four-quarter heart shape.
- Tapping a Heart quarter changes HP using the same target-value semantics as Windows.
- Adversity Tokens are gold diamonds and are directly tappable using the same slot semantics as Windows.
- HP and AT no longer need +/- buttons.
- BDV and DR use the actual desktop SVG artwork with the current value over the icon.
- Ability rows use the actual desktop ability SVG artwork and desktop accent colors.
- No extra `Defense: Agility` subtitle and no duplicated `Defense ability` text.
- Portrait uses Fit and is not clipped at the left edge.
- No dedicated Backstory button.
- Improvement and Empowerment descriptions render DID rich text.
- Improvement-linked note icons still open the associated note.
- The linked-note popup renders built-in HTML formatting rather than showing `<b>` / `<br>` markup.
- Inventory has no item-count badge.
- Notes has no note-count badge.
- Inventory quantity is a circular number badge rather than `x1`.
- Inventory row actions use a three-dot menu instead of a large Edit button.

## Bidirectional sync regression

- Change HP on Windows and confirm Android updates.
- Tap a Heart quarter on Android and confirm Windows HP updates/saves and Android settles on the canonical returned value.
- Tap Adversity diamonds on Android and confirm Windows matches the same slot semantics.
- Change IP on Android and confirm Windows updates/saves.
- Switch active character on Windows and confirm Android follows it, including portrait and lists.
- Disconnect Wi-Fi: Android becomes read-only and does not queue mutations. Reconnect and confirm canonical resync.

## Phase 9 direct edits

- Rename the character from Android. Confirm Windows updates and saves.
- Add an Inventory item from Android. Confirm it appears on Windows with the same name/description/quantity.
- Edit that Inventory item from the three-dot menu. Confirm Windows updates.
- Delete that Inventory item from the three-dot menu. Confirm Windows removes it after confirmation.
- Verify a read-only desktop character rejects all mutations.

## Deliberately deferred

Do not treat missing mobile editing for Notes, Improvements/Empowerments, species rules or creation rules as a Phase 9 failure. Those features require explicit reuse of the desktop rule/system-note paths before Android exposes destructive editing.
