from __future__ import annotations

from pathlib import Path

from discord_integration import (
    empty_config,
    get_binding,
    set_binding,
    validate_config_for_start,
    validate_dm_role_mappings,
)

ROOT = Path(__file__).resolve().parent.parent
BOT = (ROOT / "did_discord_bot.py").read_text(encoding="utf-8")
UI = (ROOT / "discord_integration_ui.py").read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def binding(name, guild, channel, role):
    return {
        "campaign_name": name,
        "guild_id": str(guild),
        "channel_id": str(channel),
        "dm_role_id": str(role),
    }


def base_config():
    config = empty_config()
    config["bot_token"] = "test-token"
    config["application_id"] = "1000"
    return config


def test_start_allows_roleless_campaign_with_valid_routing():
    config = base_config()
    config = set_binding(config, "campaign-a", binding("A", 10, 101, ""))
    clean = validate_config_for_start(config)
    check(get_binding(clean, "campaign-a")["dm_role_id"] == "", "Roleless hosted configuration changed unexpectedly")
    check(get_binding(clean, "campaign-a")["channel_id"] == "101", "Home routing was lost")


def test_start_rejects_roleless_campaign_without_home_channel():
    config = base_config()
    config = set_binding(config, "campaign-a", binding("A", 10, "", ""))
    try:
        validate_config_for_start(config)
    except ValueError as error:
        check("Home Channel" in str(error), "Missing home channel produced unclear error")
    else:
        raise AssertionError("Enabled campaign started without a home channel")


def test_distinct_roles_in_same_server_are_allowed():
    config = base_config()
    config = set_binding(config, "campaign-a", binding("A", 10, 101, 501))
    config = set_binding(config, "campaign-b", binding("B", 10, 102, 502))
    clean = validate_config_for_start(config)
    check(get_binding(clean, "campaign-a")["dm_role_id"] == "501", "Campaign A role was not preserved")
    check(get_binding(clean, "campaign-b")["dm_role_id"] == "502", "Campaign B role was not preserved")


def test_same_role_cannot_grant_two_campaigns_in_same_server():
    config = base_config()
    config = set_binding(config, "campaign-a", binding("A", 10, 101, 501))
    try:
        set_binding(config, "campaign-b", binding("B", 10, 102, 501))
    except ValueError as error:
        check("Each DID campaign in a Discord server must use its own DM role" in str(error), "Duplicate role error is unclear")
    else:
        raise AssertionError("One Discord role was allowed to grant DM authority to two campaigns")


def test_corrupt_duplicate_role_config_fails_closed():
    config = base_config()
    config["campaigns"] = {
        "campaign-a": binding("A", 10, 101, 501),
        "campaign-b": binding("B", 10, 102, 501),
    }
    try:
        validate_dm_role_mappings(config)
    except ValueError:
        pass
    else:
        raise AssertionError("Corrupt duplicate DM-role mapping did not fail closed")


def _isolated_dm_method():
    """Compile the production method alone so this test needs no live Discord login."""
    import ast
    import types

    source = BOT
    tree = ast.parse(source)
    methods = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_is_dm"]
    check(len(methods) == 1, "Expected exactly one DM authorization method")
    method = methods[0]
    method.decorator_list = []
    method.returns = None
    for arg in method.args.args:
        arg.annotation = None
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    fake_discord = types.SimpleNamespace(Member=type("Member", (), {}))
    scope = {"discord": fake_discord}
    exec(compile(module, "did_discord_bot.py", "exec"), scope)
    return scope["_is_dm"], fake_discord.Member


def test_owner_authorization_and_nonowner_denial():
    from types import SimpleNamespace
    is_dm, Member = _isolated_dm_method()
    bot = SimpleNamespace(application=SimpleNamespace(owner=SimpleNamespace(id=123)))
    owner = SimpleNamespace(user=SimpleNamespace(id=123))
    stranger = SimpleNamespace(user=SimpleNamespace(id=999))
    no_id = SimpleNamespace(user=SimpleNamespace(id=""))
    roleless = binding("A", 10, 101, "")
    check(is_dm(bot, owner, roleless), "Bot application owner was denied for roleless campaign")
    check(not is_dm(bot, stranger, roleless), "Non-owner gained DM authority")
    check(not is_dm(bot, no_id, roleless), "User without Discord ID gained DM authority")
    # Even a matching legacy role must not override a known owner mismatch.
    privileged = Member()
    privileged.id = 999
    privileged.roles = [SimpleNamespace(id=501)]
    check(not is_dm(bot, SimpleNamespace(user=privileged), binding("A", 10, 101, 501)),
          "Legacy role bypassed known application owner")


def test_legacy_role_fallback_fails_closed():
    from types import SimpleNamespace
    is_dm, Member = _isolated_dm_method()
    bot = SimpleNamespace(application=None)
    user = Member()
    user.id = 999
    user.roles = [SimpleNamespace(id=501)]
    check(is_dm(bot, SimpleNamespace(user=user), binding("A", 10, 101, 501)),
          "Existing legacy role authorization was lost")
    check(not is_dm(bot, SimpleNamespace(user=user), binding("A", 10, 101, 502)),
          "Unrelated campaign role authorized a DM")
    check(not is_dm(bot, SimpleNamespace(user=user), binding("A", 10, 101, "")),
          "Missing owner and role did not fail closed")
    check("manage_guild" not in BOT[BOT.index("    def _is_dm("):BOT.index("    async def _fetch_party", BOT.index("    def _is_dm("))],
          "Server-wide Manage Server privilege bypasses campaign DM authorization")


def test_dm_only_surfaces_still_use_campaign_role_gate():
    required_fragments = (
        'if not bot._is_dm(interaction, binding):',
        'name="dashboard"',
        'name="session"',
        'class SessionControlView(discord.ui.View)',
        '_use_selected_channel_control',
        '_use_this_channel_control',
    )
    for fragment in required_fragments:
        check(fragment in BOT, f"DM-only Phase 4/5 surface lost its role gate: {fragment}")


def test_hosted_ui_does_not_require_campaign_dm_role():
    check("DM Role ID (required)" not in UI, "Hosted UI still requires legacy DM role setup")
    check("dm_role_id" not in UI, "Hosted UI exposes legacy campaign-role configuration")
    check("Discord" in UI, "Discord connection UI missing")


def test_prior_discord_surface_preserved():
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in BOT, f"/{command} command missing after Phase 7")
    check("class SessionChannelSelect(discord.ui.ChannelSelect)" in BOT, "Phase 5 voice/text session picker regressed")
    check("roll_notifications" in BOT, "Phase 6 roll notifications regressed")
    check("announce_campaign_reveals" in BOT, "Phase 6 reveal notifications regressed")


def main():
    tests = [
        test_start_allows_roleless_campaign_with_valid_routing,
        test_start_rejects_roleless_campaign_without_home_channel,
        test_distinct_roles_in_same_server_are_allowed,
        test_same_role_cannot_grant_two_campaigns_in_same_server,
        test_corrupt_duplicate_role_config_fails_closed,
        test_owner_authorization_and_nonowner_denial,
        test_legacy_role_fallback_fails_closed,
        test_dm_only_surfaces_still_use_campaign_role_gate,
        test_hosted_ui_does_not_require_campaign_dm_role,
        test_prior_discord_surface_preserved,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
