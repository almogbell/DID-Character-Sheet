# DID Character Sheet — Phase 4: Live DM Dashboard

Phase 4 adds the first real browser DM dashboard on top of the Phase 1–3 campaign foundation.

## What this phase adds

- Read-only browser dashboard for the DM.
- Live party cards from `campaign_characters` + `character_state`.
- Hearts, AT, BDV, DR, Level, IP remaining and all six abilities.
- Recent structured dice rolls, including exploding chains and Other Dice without a fake combined total.
- Character detail view with shared Improvements.
- Player presence heartbeat (`last_seen_at`).
- Supabase Realtime subscriptions for characters, state and rolls.
- Secure one-time DM dashboard code, valid for 10 minutes.
- Browser session persists after the first claim, so the code is not a permanent secret.
- Dashboard server binds only to `127.0.0.1` in this phase.

## Security model

The browser uses the same Supabase **publishable/anon** key as the desktop app. It never receives a service-role key or the desktop app's refresh token.

`Open DM Dashboard` asks Supabase for a one-time code. A separate anonymous browser user claims that code and receives a DM membership for that campaign. Existing RLS policies then control what the browser may read.

The ordinary player invite code does **not** grant dashboard/DM access.

## Install

Copy everything in this `phase4` folder into the Phase 3 project folder, preserving the `dm_dashboard` subfolder, then run:

```bat
python apply_phase4_patch.py
```

Then run `campaign_supabase_phase4.sql` in the same Supabase project's SQL Editor.

Then run:

```bat
python campaign_dashboard_smoke_test.py
```

Expected ending:

```text
PHASE 4 DM DASHBOARD SMOKE TEST: PASS
```

Then launch the app and use:

`Tools -> Campaign & Templates -> Campaign... -> Open DM Dashboard`

## Current scope

The dashboard is intentionally read-only. DM-written campaign effects, private DM notes, snapshots, session mode and Discord come later.

The shared-state schema currently exposes whether a character has a portrait but deliberately does not upload image bytes, so Phase 4 uses an initials avatar rather than transferring the portrait itself. That preserves the Phase 1 privacy allowlist until portrait storage is added explicitly.
