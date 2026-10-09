# DID Character Sheet — Phase 5: Session Mode

Phase 5 builds on the verified Phase 4 DM Dashboard.

## What it adds

- DM **Start Session / End Session** controls in the browser dashboard.
- Only one active session per campaign.
- Rolls made during an active session are automatically attached to that session.
- Automatic read-only character snapshots at **session start** and **session end**.
- Archived sessions keep their rolls and snapshots after the session ends.
- The dashboard can switch between the current session, archived sessions, and campaign-wide recent rolls.
- **View Snapshots** shows the captured start/end character state for an archived or live session.
- Players get a desktop Campaign checkbox: **Share my dice rolls during active sessions**.
- When that checkbox is off, rolls made during an active session are not stored in the DM session log. Rolls outside sessions are unchanged.
- Existing live presence, safe state sync, campaign rules, and dashboard authorization remain unchanged.

## Install

Copy everything in `sync/phase5` into the current DID project folder, including the `dm_dashboard` folder.

Run:

```bat
python install_phase5.py
```

The installer backs up changed UI/dashboard files, compiles the Python changes, and runs the local Phase 5 tests.

## Supabase migration

Run the whole file below in the same Supabase project after Phase 4:

```text
campaign_supabase_phase5.sql
```

Then run the real cloud test:

```bat
python campaign_session_smoke_test.py
```

Expected final line:

```text
PHASE 5 SESSION MODE SMOKE TEST: PASS
```

The smoke test creates temporary DM/player identities and a temporary campaign, verifies session-start snapshots, session-scoped rolls, player roll privacy, session-end snapshots, archived rolls, DM-only session control, and Session 2 numbering, then removes the temporary campaign.

## Manual check

1. Launch `frontend_2_8.py`.
2. Open a campaign as a player and confirm the session roll-sharing checkbox is visible for the linked character.
3. Open the DM Dashboard.
4. Click **Start Session**.
5. Roll from the player sheet and verify it appears under the live session.
6. Turn player roll sharing off and roll again; that roll should not appear in the active session log.
7. Change Hearts or AT, then click **End Session**.
8. Select the archived session and open **View Snapshots**. The start and end values should remain available.
