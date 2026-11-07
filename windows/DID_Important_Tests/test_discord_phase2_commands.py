from __future__ import annotations

from pathlib import Path

from discord_integration import (
    query_visible_campaign_entries,
    query_visible_campaign_npcs,
)


class FakeClient:
    def __init__(self, response=None):
        self.response = [] if response is None else response
        self.calls = []

    def _request_json(self, method, path, body=None, query=None, authenticated=True, prefer=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "query": dict(query or {}),
                "authenticated": authenticated,
                "prefer": prefer,
            }
        )
        return self.response


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_visible_campaign_entries_query():
    client = FakeClient([{"title": "Clue"}])
    rows = query_visible_campaign_entries(client, "campaign-a", 12)
    check(rows == [{"title": "Clue"}], "Visible campaign-entry rows were not returned")
    call = client.calls[-1]
    check(call["path"] == "/rest/v1/campaign_entries", "Wrong campaign-entry endpoint")
    check(call["query"].get("campaign_id") == "eq.campaign-a", "Campaign isolation filter missing")
    check(call["query"].get("visible_to_players") == "eq.true", "Player visibility filter missing")
    select = call["query"].get("select", "")
    check("gm_notes" not in select and "created_by" not in select, "DM/private fields must not be selected")
    check(call["query"].get("limit") == "12", "Campaign-entry limit mismatch")


def test_visible_npc_query():
    client = FakeClient([{"name": "Guide"}])
    rows = query_visible_campaign_npcs(client, "campaign-b", 9)
    check(rows == [{"name": "Guide"}], "Visible NPC rows were not returned")
    call = client.calls[-1]
    check(call["path"] == "/rest/v1/campaign_npcs", "Wrong NPC endpoint")
    check(call["query"].get("campaign_id") == "eq.campaign-b", "NPC campaign isolation filter missing")
    check(call["query"].get("visible_to_players") == "eq.true", "NPC visibility filter missing")
    select = call["query"].get("select", "")
    check("gm_notes" not in select, "NPC gm_notes must never be selected")
    check(call["query"].get("limit") == "9", "NPC limit mismatch")


def test_bot_command_surface():
    source = (Path(__file__).resolve().parent.parent / "did_discord_bot.py").read_text(encoding="utf-8")
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in source, f"/{command} command missing")
    check('@character.autocomplete("name")' in source, "/character autocomplete missing")
    check("query_visible_campaign_entries" in source, "/campaign is not using the visible-only query")
    check("query_visible_campaign_npcs" in source, "/npcs is not using the visible-only query")
    check("party_session_rolls" not in source, "Bot should use the shared-roll helper instead of a direct roll-table query")
    check("/rest/v1/character_state" not in source, "Discord bot must not query full character state")
    check("/rest/v1/campaign_characters" not in source, "Discord bot must not query raw campaign character rows")


def main():
    tests = [
        test_visible_campaign_entries_query,
        test_visible_npc_query,
        test_bot_command_surface,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
