from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "did_discord_bot.py").read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_interactive_menu_surface():
    check("class DIDMenuView(discord.ui.View)" in SOURCE, "DID interactive menu view is missing")
    for label in ("Party", "Character", "Campaign", "Recent Rolls", "NPCs", "Session"):
        check(f'label="{label}"' in SOURCE, f"Missing /did button: {label}")
    check('view=DIDMenuView(campaign_id)' in SOURCE, "/did does not attach the interactive view")


def test_character_dropdown():
    check("class CharacterSelect(discord.ui.Select)" in SOURCE, "Character select menu is missing")
    check("class CharacterSelectView(discord.ui.View)" in SOURCE, "Character select view is missing")
    check("Choose a shared character" in SOURCE, "Character selector placeholder is missing")
    check("self.values[0]" in SOURCE, "Character selector does not use the selected value")


def test_phase1_isolation_rechecked_on_click():
    check("_resolved_for_expected_campaign" in SOURCE, "Interactive actions do not re-check campaign routing")
    check("bot._binding_for_interaction(interaction)" in SOURCE, "Interactive actions do not resolve the current channel binding")
    check("str(resolved[0]) != str(expected_campaign_id)" in SOURCE, "Interactive actions do not fail closed on campaign mismatch")


def test_existing_commands_preserved():
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in SOURCE, f"/{command} command missing after Phase 3")
    check('@character.autocomplete("name")' in SOURCE, "/character autocomplete was regressed")


def test_privacy_paths_preserved():
    check("query_visible_campaign_entries" in SOURCE, "Campaign UI is not using visible-only campaign entries")
    check("query_visible_campaign_npcs" in SOURCE, "NPC UI is not using visible-only NPCs")
    check("_fetch_party" in SOURCE, "Party/character UI is not using the Party Dashboard feed")
    check("_fetch_rolls" in SOURCE, "Recent Rolls UI is not using the shared-roll helper")
    check("/rest/v1/character_state" not in SOURCE, "Discord UI must not query full character state")
    check("/rest/v1/campaign_characters" not in SOURCE, "Discord UI must not query raw campaign characters")


def main():
    tests = [
        test_interactive_menu_surface,
        test_character_dropdown,
        test_phase1_isolation_rechecked_on_click,
        test_existing_commands_preserved,
        test_privacy_paths_preserved,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
