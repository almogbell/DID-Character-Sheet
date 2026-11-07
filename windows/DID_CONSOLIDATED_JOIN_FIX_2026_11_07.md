# DID Character Sheet 1.0.14 — Consolidated Campaign Join / Portrait / Roll Dialog Fix

## Included

1. Player Campaigns shows the character linked to the selected campaign regardless of which local sheet is open. Without a link, it offers Add Character. The existing rejection and replacement controls are retained.
2. Normal ability-roll options: Enter / keypad Enter from a numeric editor triggers Roll; typed values are committed first. Cancel is at the left, Roll is at the right.
3. Portrait picker accepts WEBP, TIFF, GIF, JPEG, PNG, BMP, ICO, AVIF and any file Qt/Pillow can decode; imported photos are normalized to PNG for reliable saving and reopening. Actual supported codecs depend on installed Qt/Pillow plugins.
4. Join Campaign opens a dedicated page, with no campaign overview, character card, Party Dashboard or other unrelated widgets.
5. Invite codes use a monospaced font, distinguishing zero from the letter O.
6. After entering a valid invite code, users explicitly choose from local saved characters or create a new character using the campaign template. The currently open character is never published automatically. The character list identifies creation-rule mismatches that may require DM approval. New campaign characters are linked after they have a proper name and are saved (not on the initial unnamed autosave). Account membership is created when the invite code is accepted, before character selection; exiting selection does not remove membership.
7. Approval-pending feedback uses a themed, readable dialog, with a clearer explanation of creation-rule mismatches.
8. Remove/Replace Character remains available for pending, rejected and linked characters. Local files are retained. Party Dashboard and Campaign Info are hidden and guarded in the Windows UI until an approved character is linked. The server's existing Party Dashboard data RLS requires an active character or DM authorization; campaign creation rules remain accessible to joined players for creating a character.

## Creation Rules enabled

This means the character has creation-rule metadata copied from a template when it was created. It is not a checkbox the player should turn on. Older standalone characters usually do not have the template metadata. Such characters can be submitted for DM approval, or a new character can be created directly from the campaign's rules.

## Validation

- Python syntax compilation successful.
- Quick automated runner: 27 pass, 0 fail, 4 blocked by missing PySide6 runtime in this test environment.
- Added 8 focused tests for campaign join stages, approved-link lookup, replacement/access guards, dice Enter key, WEBP import and invite-code readability.
- Windows-only manual verification required for the live Qt screens, real Supabase join/approval, and physical portrait decoding.

## Install

Close DID and extract the patch-only ZIP into the existing `Desktop\Almog's\DID_1_0_14_Test\current code - Copy` directory, overwriting matching source files. Full project ZIP is also provided. Keep a backup of saved character files before first live join testing.
