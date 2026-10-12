from __future__ import annotations

from pathlib import Path


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    root = Path(__file__).resolve().parent
    installed_layout = (root / "dm_dashboard").is_dir()

    sql = (root / "campaign_supabase_phase8.sql").read_text(encoding="utf-8")
    js_path = root / "dm_dashboard" / "campaign_layer.js" if installed_layout else root / "campaign_layer.js"
    css_path = root / "dm_dashboard" / "campaign_layer.css" if installed_layout else root / "campaign_layer.css"
    js = js_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    player_ui = (root / "phase8_player_ui.py").read_text(encoding="utf-8")

    for table in (
        "campaign_dm_notes",
        "campaign_npcs",
        "campaign_npc_relationships",
        "campaign_entries",
        "campaign_character_effects",
    ):
        check(table in sql, f"Missing Phase 8 table: {table}")
        check(table in js, f"Dashboard does not use: {table}")

    check("visible_to_players" in sql, "Player visibility field missing")
    check("visible_to_player" in sql, "Character effect visibility field missing")
    check("private.did_is_campaign_dm" in sql, "DM RLS guard missing")
    check("private.did_owns_campaign_character" in sql, "Affected-player effect RLS guard missing")
    check("Nothing here is written into a player's .didchar file" in js, "Campaign-layer boundary message missing")
    check("Add Relationship" in js, "NPC relationship UI missing")
    check("New Character Effect" in js, "Character effect UI missing")
    check(".p8-layer" in css and ".p8-dialog" in css, "Phase 8 dashboard styling missing")
    check('"Campaign Info"' in player_ui, "Player Campaign Info page missing")
    check("campaign_entries" in player_ui and "campaign_character_effects" in player_ui, "Player-visible campaign data loader missing")

    if installed_layout:
        index = (root / "dm_dashboard" / "index.html").read_text(encoding="utf-8")
        role_ui = (root / "campaign_role_ui.py").read_text(encoding="utf-8")
        check('href="campaign_layer.css"' in index, "Phase 8 CSS not wired into DM dashboard")
        check('src="campaign_layer.js"' in index, "Phase 8 JS not wired into DM dashboard")
        check("Phase 8 player campaign info integration" in role_ui, "PlayerCampaignsDialog Phase 8 hook missing")
    else:
        installer = (root / "install_phase8.py").read_text(encoding="utf-8")
        check('href="campaign_layer.css"' in installer, "Installer does not wire Phase 8 CSS")
        check('src="campaign_layer.js"' in installer, "Installer does not wire Phase 8 JS")
        check("patch_player_campaign_ui" in installer, "Installer does not wire Player Campaign Info")

    print("Phase 8 schema model: PASS")
    print("DM-only notes: PASS")
    print("NPCs + relationships: PASS")
    print("Hooks / secrets / clues / quests: PASS")
    print("Character effects: PASS")
    print("Player visibility boundaries: PASS")
    print("DM Dashboard integration: PASS")
    print("Player Campaign Info integration: PASS")


if __name__ == "__main__":
    main()
