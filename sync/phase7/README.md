# Phase 7 — DM / Player split + Party Dashboard

This phase separates campaign use by role instead of forcing DM and player controls into one window.

## Desktop entry points

**Campaign Manager...** is for campaigns you DM:
- campaign selector and invite code
- DM Dashboard and Party Dashboard
- live campaign character roster
- DM can remove a character from the live campaign without deleting the player's local `.didchar`
- elegant read/edit Creation Rules summary

**My Campaigns...** is for campaigns you joined as a player:
- join/select player campaigns
- create a campaign-rules character, edit it normally on the sheet, then Save to Campaign
- integrated DM sharing controls (no separate Sharing & Privacy window)
- separate Party sharing controls
- Party Dashboard access
- read-only Creation Rules

Backstory sharing is removed because the character sheet does not own a Backstory field.

## Dashboard changes

The DM Dashboard now uses **HP** rather than Hearts for the numeric resource display and safely renders the basic rich-text formatting in shared notes instead of showing literal `<b>` / `<br>` tags.

The new **Party Dashboard** is visible to campaign members through a one-time browser pairing code. It reads only `party_character_state`, which is a separate player-controlled payload. Party sharing defaults to name/identity only; HP, AT, abilities, Improvements, portrait, inventory and notes are opt-in.

## Install

1. Keep the whole `phase7` folder together inside your current code folder.
2. Run the final installer:

```bat
python phase7\install_phase7_final.py
```

The final installer applies a packaged UI preflight repair first, then runs the normal Phase 7 installer, Python compilation checks and local Phase 7 tests.

3. In Supabase SQL Editor run the full contents of:

```text
campaign_supabase_phase7.sql
```

4. Restart the app:

```bat
python frontend_2_8.py
```

5. Test both menu entries under **Tools -> Campaign & Templates**.

## Important

The SQL migration is required for:
- DM Remove from Campaign
- Party Dashboard state
- Party Dashboard browser pairing

Until the SQL is installed, the normal DM-safe character sync continues working, but those new Phase 7 cloud features will not.
