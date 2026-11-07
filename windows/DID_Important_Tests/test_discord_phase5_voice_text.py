from __future__ import annotations

from pathlib import Path

from discord_integration import (
    normalize_config,
    resolve_channel_binding,
    set_binding,
    validate_channel_mappings,
)

ROOT = Path(__file__).resolve().parent.parent
BOT = (ROOT / "did_discord_bot.py").read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def base_config():
    return normalize_config({
        "campaigns": {
            "campaign-a": {
                "campaign_name": "Dragon",
                "guild_id": "100",
                "channel_id": "200",
                "session_channel_id": "300",
                "session_channel_session_id": "session-a",
            },
            "campaign-b": {
                "campaign_name": "Space",
                "guild_id": "100",
                "channel_id": "201",
            },
        }
    })


def test_temporary_session_channel_routes_commands():
    config = base_config()
    resolved = resolve_channel_binding(config, "100", "300")
    check(resolved is not None and resolved[0] == "campaign-a", "Active session channel did not route to its campaign")
    home = resolve_channel_binding(config, "100", "200")
    check(home is not None and home[0] == "campaign-a", "Home Channel stopped routing after a session channel was added")


def test_temporary_route_requires_concrete_session():
    config = base_config()
    config["campaigns"]["campaign-a"]["session_channel_session_id"] = ""
    resolved = resolve_channel_binding(config, "100", "300")
    check(resolved is None, "A stale session channel without a session ID must not route commands")


def test_session_channel_cannot_collide_with_another_campaign():
    config = base_config()
    binding = dict(config["campaigns"]["campaign-b"])
    binding["session_channel_id"] = "300"
    binding["session_channel_session_id"] = "session-b"
    try:
        set_binding(config, "campaign-b", binding)
    except ValueError:
        pass
    else:
        raise AssertionError("Two campaigns were allowed to route the same temporary Discord channel")


def test_session_channel_cannot_take_another_home_channel():
    config = base_config()
    binding = dict(config["campaigns"]["campaign-a"])
    binding["session_channel_id"] = "201"
    binding["session_channel_session_id"] = "session-a"
    try:
        set_binding(config, "campaign-a", binding)
    except ValueError:
        pass
    else:
        raise AssertionError("A session channel was allowed to take another campaign's Home Channel")


def test_same_campaign_may_use_home_as_session_channel():
    config = base_config()
    binding = dict(config["campaigns"]["campaign-a"])
    binding["session_channel_id"] = "200"
    binding["session_channel_session_id"] = "session-a"
    updated = set_binding(config, "campaign-a", binding)
    validate_channel_mappings(updated)
    resolved = resolve_channel_binding(updated, "100", "200")
    check(resolved is not None and resolved[0] == "campaign-a", "Home-as-session routing should remain valid")


def test_voice_channel_selector_and_text_only_behavior_exist():
    check("class SessionChannelSelect(discord.ui.ChannelSelect)" in BOT, "DM session channel selector is missing")
    check("discord.ChannelType.voice" in BOT, "Voice channels are not offered as session destinations")
    check("discord.ChannelType.text" in BOT, "Text channels are not offered as session destinations")
    check("voice-channel text chat only" in BOT, "Voice text-only behavior is not communicated")
    forbidden = (
        ".connect(",
        "VoiceClient(",
        "on_voice_state_update",
        "send_audio_packet",
        ".play(",
        "transcribe(",
        "record(",
    )
    for token in forbidden:
        check(token not in BOT, f"Phase 5 must not add voice/audio behavior: found {token}")


def test_stale_temporary_route_is_checked_against_supabase():
    check("_validated_binding_for_interaction" in BOT, "Temporary routes are not validated at interaction time")
    check("routed_session_id == active_id" in BOT, "Temporary route is not matched to the authoritative active session")
    check("_clear_session_channel(campaign_id, routed_session_id)" in BOT, "Stale temporary routing is not cleared")


def test_existing_commands_preserved():
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in BOT, f"/{command} command missing after Phase 5")
    check("class SessionControlView(discord.ui.View)" in BOT, "Phase 4 session controls were regressed")
    check("class DIDMenuView(discord.ui.View)" in BOT, "Phase 3 interactive menu was regressed")


def main():
    tests = [
        test_temporary_session_channel_routes_commands,
        test_temporary_route_requires_concrete_session,
        test_session_channel_cannot_collide_with_another_campaign,
        test_session_channel_cannot_take_another_home_channel,
        test_same_campaign_may_use_home_as_session_channel,
        test_voice_channel_selector_and_text_only_behavior_exist,
        test_stale_temporary_route_is_checked_against_supabase,
        test_existing_commands_preserved,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
