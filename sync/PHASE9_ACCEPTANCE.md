# Phase 9 real-device acceptance

Run this only after Phase 8 Windows↔Android pairing already works.

## Visual parity

- The Android app uses the DID cream/gold/blue sheet treatment rather than the generic Material prototype.
- The current desktop portrait appears in the Android character header when one exists.
- Name, species and backstory are readable without crowding the portrait.
- HP is shown as four-point heart segments; BDV and DR appear beside the heart panel.
- Adversity Tokens and IP/Level match the Windows character.
- Abilities are sorted by die size descending, then bonus descending, then name, matching the finished desktop redesign.
- Improvements show descriptions, choices and purchased empowerments in the desktop-style hierarchy.
- Inventory is a dedicated phone page and Notes retain their desktop note colors and pinned marker.
- Character / Equipment / Notes remains the bottom navigation, with Abilities / Improvements inside Character.

## Bidirectional sync regression

- Change HP on Windows and confirm Android updates.
- Change HP/AT/IP on Android and confirm Windows updates/saves and Android settles on the canonical returned value.
- Switch active character on Windows and confirm Android follows it, including portrait and lists.
- Disconnect Wi-Fi: Android becomes read-only and does not queue mutations. Reconnect and confirm canonical resync.

## Phase 9 direct edits

After applying the Phase 9 Windows delta:

- Rename the character from Android. Confirm Windows updates and saves.
- Edit backstory from Android. Confirm Windows updates and saves.
- Add an Inventory item from Android. Confirm it appears on Windows with the same name/description/quantity.
- Edit that Inventory item on Android. Confirm Windows updates.
- Delete that Inventory item on Android. Confirm Windows removes it.
- Verify a read-only desktop character rejects all of these mutations.

## Deliberately deferred

Do not treat missing mobile editing for Notes, Improvements/Empowerments, species rules or creation rules as a Phase 9 failure. Those features require explicit reuse of the desktop rule/system-note paths before Android exposes destructive editing.
