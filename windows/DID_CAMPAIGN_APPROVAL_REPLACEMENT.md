# DID — campaign character replacement and access gating

Target: DID Character Sheet 1.0.14, after the Ability Dice Readability update.

## Changes
- A **Remove / Replace Character** button appears for a selected campaign's approved, pending, or rejected character.
- The previous character remains saved locally. Its campaign approval request is cancelled or its approved campaign link is withdrawn on Supabase before the local association is cleared.
- Once removed, the card presents **Add Character**.
- Party Dashboard and Campaign Info controls are hidden until there is an approved campaign character, regardless of which local character sheet is currently open.
- Party Dashboard launch is also guarded in both the main Campaigns hub and the older Player Campaigns dialog.
- The existing server-side `did_party_access` policy restricts party data to users with an active approved campaign character or authorized DM status. The UI changes are an additional boundary, not a replacement for database RLS.

## Test
1. Join a test campaign, submit an incompatible character, and have the DM reject it.
2. Confirm Party Dashboard and Campaign Info are absent; Character & Sharing remains available.
3. Click **Remove / Replace Character** and confirm. The local character should still be available under Load Character.
4. Check **Add Character** is offered, then create or select a different character.
5. Have the DM approve the replacement; refresh and confirm Party Dashboard and Campaign Info appear.
6. Switch to a different local character: the campaign continues to show its approved linked character.
7. Remove an approved character and confirm dashboard access is withdrawn. Test the party site with a fresh browser session, not an already loaded tab.

## Limitations
- The server-side functions already exist in the connected DID-Suggestions Supabase project; no new SQL migration is required for this patch.
- If a record is locally stale, Supabase may reject withdrawal; the local association is then retained and an error is shown.
- This environment cannot run Windows Qt GUI interactions; verify visually on Windows.
- General campaign metadata remains readable to joined members as required for character creation. The Party Dashboard's underlying data is protected by Supabase access checks.
