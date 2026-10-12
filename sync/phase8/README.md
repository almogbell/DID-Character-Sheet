# Phase 8 — DM Campaign Layer

Phase 8 adds campaign-only information that lives in Supabase and does **not** modify or extend player `.didchar` files.

## What is included

The DM Dashboard gains a **DM Workspace** with four areas:

- **DM Notes** — private campaign notes, never readable by players.
- **NPCs** — name, status, description, DM notes, optional portrait URL, and reveal-to-players flag.
- **NPC Relationships** — NPC → NPC or NPC → player-character relationships, with DM notes.
- **Hooks & Clues** — hooks, secrets, clues, quests, objectives, and messages. Each item can remain DM-only or be explicitly revealed to campaign players.
- **Character Effects** — campaign-layer effects/statuses attached to a campaign character. They remain DM-only unless the DM explicitly reveals them to the affected player.

The player's **My Campaigns** window also gains a fourth page, **Campaign Info**. It shows only data the current player is allowed to read under Supabase RLS:

- campaign entries explicitly revealed to players;
- NPCs explicitly revealed to players;
- character effects explicitly revealed to the owner of the affected character.

Private DM notes, hidden NPCs, secrets, hidden effects, and relationship notes do not appear there.

The desktop character sheet remains authoritative for character state. Phase 8 effects do not overwrite HP, AT, abilities, Improvements, inventory, notes, or any other `.didchar` field.

## Install

1. Put the whole `phase8` folder inside the current DID project folder.
2. Run:

```bat
python phase8\install_phase8.py
```

3. In the Supabase SQL Editor run the complete contents of:

```text
campaign_supabase_phase8.sql
```

4. Run the real cloud smoke test:

```bat
python phase8_cloud_smoke_test.py
```

A successful run ends with:

```text
PHASE 8 CLOUD SMOKE TEST: PASS
```

5. Restart:

```bat
python frontend_2_8.py
```

For the DM, open **Campaign Manager -> Open DM Dashboard**. The new **DM Workspace** appears between the live party section and the roll history.

For a player, open **My Campaigns** and move to **Campaign Info**.

## Security model

- DM notes: DM-only.
- NPCs: DM-only by default; optional campaign-player visibility.
- Relationships: DM-only in this phase. The visibility flag is stored for later relationship presentation, but relationship rows are not currently readable by players.
- Campaign entries: DM-only by default; optional campaign-player visibility.
- Character effects: DM-only by default; when revealed, only the owner of the affected campaign character can read the effect.
- All writes require the campaign DM under RLS. A paired DM browser can manage existing campaign-layer records even when a different DM identity originally created them.

No secret/service-role Supabase key is used by the desktop app or dashboard.
