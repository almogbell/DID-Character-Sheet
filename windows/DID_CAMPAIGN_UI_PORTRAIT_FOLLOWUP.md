# DID Campaign UI / Portrait Follow-up — 2026-11-07

Changes in this patch:
- Replaced the system-style Remove Campaign Character confirmation with a themed dialog, Cancel left and Remove right.
- Replaced the system-style pending-approval warning in both main save paths with a readable themed dialog.
- Sharing checkboxes now use a consistently sized, theme-matched square and checkmark, including read-only DM-required fields.
- Character Sharing is hidden until an approved character exists; Add Character opens a character selection / creation screen instead.
- My Character card is hidden while Character Sharing or Campaign Info is shown and restored when returning to overview.
- Portrait add/remove/arrows/count controls appear only while the cursor is over a populated portrait. The add button uses a full-width plus sign.

Important: Creation Rules are still enforced. Existing characters without the campaign's creation-template metadata still require DM approval, even when other attributes match. This cannot safely be bypassed by changing only the UI. The app's local character file is not deleted when withdrawing a campaign link.

Validation: Python syntax compiled; 9 campaign access/replacement tests passed. Qt UI rendering and live Supabase interactions require Windows verification.
