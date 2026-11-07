# Linked Character Sharing Fix
- Character Sharing resolves the selected campaign's approved character, not the open sheet.
- Inventory, notes, and sharing preferences use that character ID.
- Apply Sharing uploads the resolved character's state, never the unrelated open sheet.
- Save to Campaign is blocked when another character is open.
- No approved link or missing local file cannot fall back to the open character.
- Preserves Effects visibility changes from the previous patch.
- Live Qt and Supabase verification is required.
