# Phase 7 — DM / Player split + Party Dashboard

This phase separates campaign use by role instead of forcing DM and player controls into one window.

## Desktop entry points

**Campaign Manager...** is for campaigns you DM:
- campaign selector and invite code
- DM Dashboard and Party Dashboard
- live campaign character roster
- DM can remove a character from the live campaign without deleting the player's local `.didchar`
- clean read/edit Creation Rules summary

**My Campaigns...** is for campaigns you joined as a player:
- join/select player campaigns
- create a campaign-rules character, edit it normally on the sheet, then Save to Campaign
- integrated DM sharing controls (no separate Sharing & Privacy window)
- separate Party sharing controls
- Party Dashboard access
- read-only Creation Rules

Backstory sharing is removed because the character sheet does not own a Backstory field.

## Dashboard changes

The DM Dashboard uses **HP** rather than Hearts for the numeric resource display and safely renders the basic rich-text formatting in shared notes instead of showing literal `<b>` / `<br>` tags.

The **Party Dashboard** is visible to campaign members through a one-time browser pairing code. It reads only player-controlled Party payloads for character information. Party sharing defaults to name/identity only; HP, AT, abilities, Improvements, portrait, inventory and notes are opt-in.

The Party Dashboard also has a **Live Play** panel:
- active session / no active session status
- recent session rolls in newest-first order
- Realtime updates when session state or shared rolls change
- rolls appear only while a session is active
- the existing player setting **Share my dice rolls during active sessions** is authoritative; when disabled, that player's roll never enters the Party feed

## Install

1. Keep the whole `phase7` folder together inside your current code folder.
2. Run the final installer:

```bat
python phase7\install_phase7_final.py
```

The installer keeps the pre-v5 Campaign/My Campaigns visual state, installs the live Party Dashboard assets, compiles the Python files, and runs the local Phase 7 checks.

3. If you have already run `campaign_supabase_phase7.sql`, run the new incremental migration:

```text
campaign_supabase_phase7_live.sql
```

If this is a fresh Phase 7 install, run `campaign_supabase_phase7.sql` first and then `campaign_supabase_phase7_live.sql`.

4. Restart the app:

```bat
python frontend_2_8.py
```

5. Test both menu entries under **Tools -> Campaign & Templates**.

## End-to-end cloud smoke test

After both Phase 7 SQL files are installed, run:

```bat
python phase7_party_smoke_test.py
```

The smoke test uses two temporary anonymous Supabase users and removes its temporary campaign afterward. It verifies:
- create/join campaign
- link character
- Party sharing payload
- Party Dashboard pairing RPC
- active session visibility
- shared session roll reaches Party feed
- disabling roll sharing keeps the next roll private
- ending the session clears active-session status
- DM Remove from Campaign removes the Party state without deleting any local `.didchar`

A successful run ends with:

```text
PHASE 7 PARTY DASHBOARD SMOKE TEST: PASS
```

## Important

The SQL migrations are required for:
- DM Remove from Campaign
- Party Dashboard state
- Party Dashboard browser pairing
- Party Dashboard live session roll feed

Until the live SQL migration is installed, the normal character sync and Party character cards still work, but the Party Dashboard live roll feed will not.
