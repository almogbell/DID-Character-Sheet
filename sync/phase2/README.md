# DID Campaign Cloud — Phase 2

Phase 2 adds the secure Supabase foundation for campaigns. It does **not** change the character-sheet UI yet.

It adds:

- Supabase Anonymous Auth support (no player email/password required)
- campaign creation
- join-by-invite-code
- DM/player membership with RLS
- per-character campaign links
- DM-safe character-state upload
- structured roll-event upload
- DM read access to campaign characters and rolls
- local unit tests
- a real end-to-end Supabase smoke test

## Files

- `campaign_cloud.py` — stdlib-only Supabase client
- `campaign_supabase.sql` — tables, functions, grants and RLS
- `test_campaign_cloud.py` — offline unit tests
- `campaign_cloud_smoke_test.py` — real Supabase end-to-end test
- `apply_phase2_patch.py` — copies the Phase 2 files into the current Windows project and runs the offline tests

## Install into the current project

Copy all Phase 2 files into:

`C:\Users\almog\Desktop\current code`

Then run:

```bat
cd /d "C:\Users\almog\Desktop\current code"
python apply_phase2_patch.py
```

The local tests should pass before touching Supabase.

## Supabase setup

Use the same Supabase project already used by the Improvement suggestion system.

### 1. Enable anonymous sign-ins

In the Supabase dashboard open **Authentication → Providers / Sign In Methods** and enable **Anonymous Sign-Ins**.

Anonymous users still receive a unique authenticated user ID. The campaign RLS rules use that ID; the desktop app never receives a service-role/secret key.

### 2. Run the SQL

Open **SQL Editor**, paste the complete contents of `campaign_supabase.sql`, and run it once.

It creates:

- `campaigns`
- `campaign_members`
- `campaign_characters`
- `character_state`
- `campaign_rolls`

It also installs the join-by-code RPC and the RLS policies.

### 3. Supabase configuration

`campaign_cloud.py` first looks for `campaign_config.json`. If none exists, it reuses `suggestions_config.json` from the existing Improvement-suggestion feature.

Supported keys include `supabase_url` / `url` and `supabase_anon_key` / `publishable_key` / `anon_key`.

Never put a Supabase `service_role` or `sb_secret_...` key in the desktop app. The client explicitly rejects those keys.

If a separate config is ever needed, copy `campaign_config.example.json` to `campaign_config.json` and insert the same public project URL and publishable/anon key.

## Real end-to-end test

After Anonymous Sign-Ins are enabled and the SQL has run:

```bat
cd /d "C:\Users\almog\Desktop\current code"
python campaign_cloud_smoke_test.py
```

The smoke test intentionally exercises the real security model. It:

1. creates two temporary anonymous users;
2. creates a temporary campaign as the DM;
3. joins it as a second player;
4. links a temporary character;
5. uploads its safe character state;
6. uploads a structured roll event;
7. verifies the DM can read that character and roll;
8. verifies the player sees only their own character data;
9. removes the temporary campaign.

Expected final line:

`PHASE 2 SUPABASE SMOKE TEST: PASS`

Once that passes, the cloud foundation is ready for the first in-app **Create Campaign / Join Campaign** UI and then the browser DM dashboard.
