# Phase 8 — DM Campaign Layer

Phase 8 adds campaign-only information that lives in Supabase and does **not** modify or extend player `.didchar` files.

## What is included

The DM Dashboard gains a **DM Workspace** with four areas:

- **DM Notes** — private campaign notes, never readable by players.
- **NPCs** — name, status, description, DM notes, optional portrait URL, and reveal-to-players flag.
- **NPC Relationships** — NPC → NPC or NPC → player-character relationships, with DM notes.
- **Hooks & Clues** — hooks, secrets, clues, quests, objectives, and messages. Each item can remain DM-only or be explicitly revealed to campaign players.
- **Character Effects** — campaign-layer effects/statuses attached to a campaign character. They remain DM-only unless the DM explicitly reveals them to the affected player.

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

Open **Campaign Manager -> Open DM Dashboard**. The new **DM Workspace** appears between the live party section and the roll history.

## Security model

- DM notes: DM-only.
- NPCs: DM-only by default; optional campaign-player visibility.
- Relationships: DM-only in this phase. A future player UI can use the stored visibility flag.
- Campaign entries: DM-only by default; optional campaign-player visibility.
- Character effects: DM-only by default; when revealed, only the owner of the affected campaign character can read the effect.
- All writes require the campaign DM under RLS.

No secret/service-role Supabase key is used by the desktop app or dashboard.
