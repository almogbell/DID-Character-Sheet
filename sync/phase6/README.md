# DID Character Sheet — Phase 6: Privacy & Sharing Controls

Phase 6 builds on the verified Phase 5 Session Mode.

## What it adds

- A **Sharing & Privacy...** control in the Campaign window for a linked character.
- Core tactical data remains required for campaign play:
  - identity and level
  - Hearts
  - AT
  - IP
  - abilities
  - defense
- Optional player-controlled categories:
  - Improvements
  - portrait
  - backstory
  - selected inventory items
  - selected notes
- Improvements default to shared to preserve the behavior from earlier campaign phases.
- Portrait, backstory, inventory and notes default to **private**.
- Inventory and notes are selected item-by-item; enabling the category does not silently share everything.
- Preferences are stored locally in `%APPDATA%\DID Character Sheet\campaign_privacy.json`, keyed by campaign + character. They are not written into `.didchar` files.
- Turning a category off causes the next live-state upload to omit it, replacing the cloud state so that value is no longer present in the current shared character state.
- The DM dashboard renders only optional fields the player currently shares.
- A shared portrait is rendered on the dashboard when its current display image fits the safe JSON payload size limit; otherwise the dashboard keeps the initials avatar.
- Existing archived Session snapshots remain read-only historical records of what was explicitly shared at the time they were captured.

The current DID backend has no persisted general **conditions/statuses** model, so Phase 6 does not invent or fake one. When such a model exists, it can be added as another optional category using the same privacy mechanism.

## Install

Copy the whole `sync/phase6` folder into the current DID project folder. You should have:

```text
C:\Users\almog\Desktop\current code - new features\phase6\install_phase6.py
```

Run:

```bat
cd /d "C:\Users\almog\Desktop\current code - new features"
python phase6\install_phase6.py
```

The installer backs up changed files, installs the privacy modules, patches Campaign automatic state sync and the dashboard, compiles the Python files, and runs the offline privacy tests.

## Supabase

**No SQL migration is required for Phase 6.** Optional sharing is stored inside the existing `character_state.state` JSON object and remains protected by the same Phase 2–5 RLS rules.

Run the real cloud test:

```bat
python campaign_privacy_smoke_test.py
```

Expected final line:

```text
PHASE 6 PRIVACY & SHARING SMOKE TEST: PASS
```

## Manual check

1. Launch `frontend_2_8.py`.
2. Open **Tools → Campaign & Templates → Campaign...**.
3. Select a campaign to which the current character is linked.
4. Click **Sharing & Privacy...**.
5. Leave Backstory/Inventory/Notes off and confirm the DM dashboard cannot see them.
6. Enable Backstory, select one inventory item and one note, save, and wait for sync.
7. Confirm only those selected values appear in the DM dashboard character details.
8. Turn them off again and confirm they disappear from the live dashboard.
