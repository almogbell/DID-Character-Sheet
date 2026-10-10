# Phase 9 real-device acceptance

Run this only after Phase 8 Windows↔Android pairing already works.

## Current test setup

1. Keep the working Phase 9 Windows sync adapter already installed. V5 is Android-only.
2. Install/update the `DID Phase 9 Test 2` APK.
3. Reconnect or pair only if Android requires it.

The Windows adapter adds a mobile-only `_mobile_ui.icons` block to snapshots. It reads the actual SVG artwork from the running desktop installation (`icons/*.svg` and `icons/defenses/*.svg`). This data is never written into `.didchar` files.

## V5 visual / interaction checks

- Character name is larger and has no Edit button. Double-tapping the name opens the rename dialog.
- The portrait gallery uses larger cards and does not mark any image as selected/current.
- Hearts have no `HP 16/16` heading, are larger, remain four-quarter controls, and update visually immediately when tapped while Windows remains authoritative.
- Adversity diamonds have no `Adversity Tokens` heading, are larger, remain directly tappable, and update visually immediately when tapped.
- BDV / DR and ability icons continue using the artwork supplied by the desktop installation.
- Character / Equipment / Notes use DID-style sheet, inventory-bag, and notes-book symbols rather than placeholder glyphs.
- The Android launcher has a DID-style app symbol.
- Inventory has only one destructive path: Delete in the three-dot menu. The Edit dialog no longer repeats Delete.
- Inventory quantity remains a circular number badge.
- Improvement-linked notes open with their note color, border/background, pin state, and DID rich-text formatting.
- Notes page uses the same rich-text rendering and note colors.

## Bidirectional sync regression

- Change HP on Windows and confirm Android updates.
- Tap Heart quarters on Android and confirm the phone responds immediately, then Windows receives/saves the canonical change.
- Tap Adversity diamonds on Android and confirm the phone responds immediately, then Windows receives/saves the canonical change.
- Switch active character on Windows and confirm Android follows it, including all portraits and lists.
- Disconnect Wi-Fi: Android becomes read-only and does not queue mutations. Reconnect and confirm canonical resync.

## Phase 9 direct edits

- Double-tap the character name on Android, rename it, and confirm Windows updates/saves.
- Add an Inventory item from Android. Confirm it appears on Windows with the same name/description/quantity.
- Edit that Inventory item on Android. Confirm Windows updates.
- Delete that Inventory item from the three-dot menu. Confirm Windows removes it.
- Verify a read-only desktop character rejects all mutations.

## Deliberately deferred

Do not treat missing mobile editing for Notes, Improvements/Empowerments, species rules or creation rules as a Phase 9 failure. Those features require explicit reuse of the desktop rule/system-note paths before Android exposes destructive editing.
