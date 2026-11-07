# DID 1.0.14 — Mixed d100 sizing and Player Campaigns heading

## Changes

- `d100_physics.js`: During a mixed roll containing exactly one physical d100 and at least one ordinary die, size the d100 by a target projected pixel diameter. Track the actual physical body's 3D position with the camera so the larger view remains in the separate d100 tray without cropping. Solo and two-d100 camera framing is unchanged. No physics parameters or face-number calculations changed.
- `campaign_role_ui.py`: The player campaign name/title and supporting text now occupy a fixed header at the top of the Player Campaigns right panel, outside the scrollable overview. They remain grouped above the Join Campaign form and detail cards.
- `test_did_mixed_d100_player_header_20261107.py`: Adds regressions covering projected sizing and player header layout.
- `test_did_d100_notes_20261106.py`: Updates an obsolete assertion for 160px textures to the already-shipped 192px textures; no runtime behavior changed.

## Verification

- 25 focused Python tests passed (including existing d100, theme, note-color and Enter-key checks).
- JavaScript syntax checked with Node.js; modified Python syntax checked with `py_compile`.
- Qt WebEngine rendering and visual alignment could not be checked here because PySide6 is unavailable. Test the app on Windows before treating this as released.

## Retest

1. Roll one d100 alone, then one d100 with one d8: compare die diameter and number legibility.
2. Roll d100 with two other dice: confirm no overlap, clipping, or result-delivery errors.
3. Open Player Campaigns with a selected campaign, scroll through details, and open/close Join Campaign: the title and its description should stay at the top of the right panel.
4. Switch DM / Player tabs and resize the Campaigns window; ensure headings and controls remain readable.
