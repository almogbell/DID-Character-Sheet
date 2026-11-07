from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

# Works when launched from either the app root or DID_Important_Tests.
ROOT = Path(__file__).resolve().parent
if not (ROOT / "did_discord_bot.py").is_file():
    ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discord_integration import (
    end_campaign_session,
    empty_config,
    get_binding,
    load_config,
    save_config,
    set_binding,
    normalize_binding,
    start_campaign_session,
)

BOT = (ROOT / "did_discord_bot.py").read_text(encoding="utf-8")
INTEGRATION = (ROOT / "discord_integration.py").read_text(encoding="utf-8")
UI = (ROOT / "discord_integration_ui.py").read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


class FakeClient:
    def __init__(self):
        self.calls = []

    def _request_json(self, method, path, query=None, body=None, prefer=None):
        self.calls.append({"method": method, "path": path, "query": query, "body": body, "prefer": prefer})
        if path.endswith("did_start_session"):
            return [{"id": "session-1", "campaign_id": "campaign-1", "session_number": 12}]
        if path.endswith("did_end_session"):
            return [{"id": "session-1", "campaign_id": "campaign-1", "session_number": 12}]
        return []


def test_authoritative_supabase_rpcs():
    client = FakeClient()
    started = start_campaign_session(client, "campaign-1")
    ended = end_campaign_session(client, "campaign-1")
    check(started["id"] == "session-1", "start helper did not return the authoritative session row")
    check(ended["id"] == "session-1", "end helper did not return the authoritative session row")
    check(client.calls[0]["path"] == "/rest/v1/rpc/did_start_session", "Discord start must use did_start_session RPC")
    check(client.calls[0]["body"] == {"p_campaign_id": "campaign-1"}, "Start RPC campaign ID is wrong")
    check(client.calls[1]["path"] == "/rest/v1/rpc/did_end_session", "Discord end must use did_end_session RPC")
    check(client.calls[1]["body"] == {"p_campaign_id": "campaign-1"}, "End RPC campaign ID is wrong")


def test_dm_control_surface():
    check("class SessionControlView(discord.ui.View)" in BOT, "DM session control view is missing")
    for label in ("Start Session", "Start Session Here", "End Session", "Use This Channel"):
        check(f'label="{label}"' in BOT, f"Missing DM session control: {label}")
    check("view=SessionControlView(campaign_id)" in BOT, "/session does not attach DM controls")


def test_players_status_only():
    check("if not is_dm:" in BOT, "/session does not separate players from DMs")
    check("Players get status only" in BOT, "Player-only status branch is missing")
    player_branch = BOT.split("if not is_dm:", 1)[1].split("try:", 1)[0]
    check("SessionControlView" not in player_branch, "Players must not receive DM session controls")


def test_temporary_channel_routing_is_separate_from_home():
    binding = normalize_binding({
        "campaign_name": "Test",
        "guild_id": "10",
        "channel_id": "20",
        "session_channel_id": "30",
        "session_channel_session_id": "session-1",
    })
    check(binding["channel_id"] == "20", "Home Channel was changed by temporary routing")
    check(binding["session_channel_id"] == "30", "Temporary session channel was not preserved")
    check(binding["session_channel_session_id"] == "session-1", "Temporary session ID was not preserved")
    check("_set_session_channel" in BOT and "_clear_session_channel" in BOT, "Temporary session routing helpers are missing")
    check('raw = str(binding.get("channel_id")' in BOT, "Home Channel fallback is missing")


def test_phase1_routing_rechecked_for_controls():
    check("_resolved_for_expected_campaign" in BOT, "Session controls do not re-check Phase 1 routing")
    control_section = BOT.split("class SessionControlView", 1)[1].split("class CharacterSelect", 1)[0]
    check("_resolved_for_expected_campaign" in control_section, "DM buttons are not re-checking current campaign binding")
    check("bot._is_dm(interaction, binding)" in control_section, "DM buttons do not enforce DM permission")


def test_visible_config_save_preserves_internal_route():
    # The hosted connection dialog does not edit local channel mappings.
    # Exercise the real normalization, save and reload path instead of
    # searching for a legacy UI implementation detail.
    check("class DiscordIntegrationDialog" in UI, "Hosted connection dialog missing")
    check("save_config(" not in UI, "Hosted dialog unexpectedly writes legacy bot configuration")
    config = set_binding(empty_config(), "campaign-1", {
        "campaign_name": "Test",
        "guild_id": "10",
        "channel_id": "20",
        "session_channel_id": "30",
        "session_channel_session_id": "session-1",
    })
    with TemporaryDirectory() as directory:
        saved = save_config(config, user_data_dir=directory)
        loaded = load_config(user_data_dir=directory)
    for value in (saved, loaded):
        route = get_binding(value, "campaign-1")
        check(route["channel_id"] == "20", "Save changed the permanent home channel")
        check(route["session_channel_id"] == "30", "Save erased the active session channel")
        check(route["session_channel_session_id"] == "session-1", "Save erased the active session ID")


def test_existing_phase_commands_preserved():
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in BOT, f"/{command} command missing after Phase 4")
    check("class DIDMenuView(discord.ui.View)" in BOT, "Phase 3 /did interactive menu was regressed")
    check('@character.autocomplete("name")' in BOT, "Phase 2 /character autocomplete was regressed")


def main():
    tests = [
        test_authoritative_supabase_rpcs,
        test_dm_control_surface,
        test_players_status_only,
        test_temporary_channel_routing_is_separate_from_home,
        test_phase1_routing_rechecked_for_controls,
        test_visible_config_save_preserves_internal_route,
        test_existing_phase_commands_preserved,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
