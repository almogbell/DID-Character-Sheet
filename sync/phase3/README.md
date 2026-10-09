# DID Campaign + Creation Rules — Phase 3

Phase 3 makes **Campaign** the online container for the existing Creation Rules / template system.

A campaign now stores the same `CharacterTemplate` data used by `.didtemplate` files. There is no second campaign-rules implementation.

## What changes

- DM can create a campaign and design its Creation Rules immediately.
- DM can create a campaign from an existing `.didtemplate`.
- Players join with the campaign invite code and receive the campaign's rules.
- Players can create a new character directly from those campaign rules.
- Existing characters can still be shared; mismatches are shown as a warning and the character is never silently rewritten.
- DM can edit campaign rules later; existing characters are not silently changed.
- A linked character's safe state syncs automatically after edits.
- Structured dice rolls sync automatically.
- If the connection drops, the sheet remains usable offline and retries pending state/roll sync later.
- Standalone `.didtemplate` files remain available as reusable presets.

## Install

Copy all files from this `sync/phase3` folder into your current DID code folder, then run:

```bat
python apply_phase3_patch.py
```

The patcher:

1. copies the Phase 3 modules into the app folder;
2. backs up `frontend_2_8.py` as `frontend_2_8.py.before_phase3` before changing it;
3. adds the Campaign & Templates menu and live-sync hooks;
4. compiles the changed Python files;
5. runs the offline Phase 3 tests.

## Supabase migration

After the local tests pass, open the existing DID Supabase project -> SQL Editor and run the entire file:

`campaign_supabase_phase3.sql`

This adds `campaigns.character_template` and grants only the operations needed by the authenticated desktop users. Existing Phase 2 campaigns receive a normal default ruleset.

Then run:

```bat
python campaign_template_smoke_test.py
```

Expected final line:

`PHASE 3 CAMPAIGN + CREATION RULES SMOKE TEST: PASS`

## Use

Launch the normal app:

```bat
python frontend_2_8.py
```

Open:

**Tools -> Campaign & Templates -> Campaign...**

From there you can:

- Create Campaign
- Join Campaign
- Edit Campaign Rules (DM only)
- Create & Share New Character
- Share Current Character
- Unlink Current Character

The old standalone-template workflow is still available in the same **Campaign & Templates** submenu.
