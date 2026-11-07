from __future__ import annotations

import tempfile
from pathlib import Path

import discord_integration as integration
from discord_integration import (
    empty_config,
    friendly_runtime_error,
    get_binding,
    launch_bot,
    save_config,
    set_binding,
)

ROOT = Path(__file__).resolve().parent.parent
BOT = (ROOT / "did_discord_bot.py").read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def binding(name="A", guild=10, channel=101, role=501):
    return {
        "campaign_name": name,
        "guild_id": str(guild),
        "channel_id": str(channel),
        "dm_role_id": str(role),
    }


def test_raw_backend_errors_are_not_exposed():
    raw = "Supabase HTTP 500 jwt=very-secret-internal-detail"
    message = friendly_runtime_error(RuntimeError(raw), "load the party")
    check("very-secret" not in message, "Raw backend detail leaked into the user-facing error")
    check("load the party" in message, "Generic friendly error lost the requested action")


def test_permission_error_is_actionable():
    message = friendly_runtime_error(RuntimeError("403 Forbidden: Missing Permissions"), "send a notification")
    check("permission" in message.lower(), "Permission failure does not explain the problem")
    check("Send Messages" in message, "Permission failure does not name the relevant Discord permission")


def test_missing_resource_error_is_actionable():
    message = friendly_runtime_error(RuntimeError("404 Unknown Channel"), "load session status")
    check("could not be found" in message, "Missing/deleted Discord resource does not get a useful message")
    check("mapping" in message, "Missing resource message does not mention stale Discord mapping")


def test_immediate_bot_startup_failure_is_detected():
    with tempfile.TemporaryDirectory() as app_tmp, tempfile.TemporaryDirectory() as data_tmp:
        app_dir = Path(app_tmp)
        user_data = Path(data_tmp)
        (app_dir / "did_discord_bot.py").write_text("raise RuntimeError('intentional startup crash')\n", encoding="utf-8")

        config = empty_config()
        config["bot_token"] = "test-token"
        config["application_id"] = "1000"
        config = set_binding(config, "campaign-a", binding())
        save_config(config, user_data)

        original = integration.discord_library_available
        integration.discord_library_available = lambda: True
        try:
            try:
                launch_bot(app_dir, user_data)
            except RuntimeError as error:
                check("stopped during startup" in str(error), "Immediate bot crash was not detected")
            else:
                raise AssertionError("launch_bot reported success for a process that immediately crashed")
        finally:
            integration.discord_library_available = original

        check(not integration.pid_path(user_data).exists(), "Dead startup process left a stale PID file")


def test_unhandled_commands_have_a_final_response_guard():
    check("@bot.tree.error" in BOT, "No global application-command error handler is installed")
    check("_send_ephemeral" in BOT, "Global command error path does not use the safe response helper")
    check('"The application did not respond"' in BOT, "Phase 8 guard is not documented around Discord timeout handling")


def test_notification_permission_failures_do_not_break_polling():
    check("async def _safe_channel_send" in BOT, "Automatic notifications do not use a protected send path")
    check("except discord.Forbidden" in BOT, "Missing Discord permissions are not handled")
    check(BOT.count("await channel.send(") == 1, "Automatic notifications still bypass the safe send helper")
    check("await self._safe_channel_send" in BOT, "Polling notifications are not routed through the safe sender")


def test_command_sync_failure_is_isolated_per_server():
    setup_start = BOT.index("    async def setup_hook(self):")
    setup_end = BOT.index("\n    async def on_ready", setup_start)
    setup = BOT[setup_start:setup_end]
    check("except discord.Forbidden" in setup, "One server's missing permissions can still abort command synchronization")
    check("except discord.HTTPException" in setup, "Discord command sync HTTP failure is not isolated")


def test_removed_campaign_runtime_state_is_pruned():
    check("def _prune_removed_campaign_state" in BOT, "Removed campaigns keep stale in-memory bot state")
    check("self._prune_removed_campaign_state(self.config[\"campaigns\"].keys())" in BOT, "Polling does not prune deleted campaign state")


def test_one_stale_campaign_authorization_does_not_stop_all_campaigns():
    claim_start = BOT.index("    async def _claim_pending_campaigns(self):")
    claim_end = BOT.index("\n    def _binding_for_interaction", claim_start)
    claim = BOT[claim_start:claim_end]
    check("continue" in claim, "A stale campaign claim can still abort startup for every campaign")
    check("Could not authorize Discord cloud access" in claim, "Failed campaign authorization is not logged clearly")


def test_existing_phase_surface_and_reconnect_are_preserved():
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in BOT, f"/{command} disappeared during Phase 8")
    check("reconnect=True" in BOT, "Discord reconnect behavior was removed")
    check("class SessionChannelSelect(discord.ui.ChannelSelect)" in BOT, "Voice/text session channel picker regressed")
    check("manage_guild" not in BOT[BOT.index("    def _is_dm"):BOT.index("    async def _fetch_party")], "Campaign-specific DM permissions regressed")


def main():
    tests = [
        test_raw_backend_errors_are_not_exposed,
        test_permission_error_is_actionable,
        test_missing_resource_error_is_actionable,
        test_immediate_bot_startup_failure_is_detected,
        test_unhandled_commands_have_a_final_response_guard,
        test_notification_permission_failures_do_not_break_polling,
        test_command_sync_failure_is_isolated_per_server,
        test_removed_campaign_runtime_state_is_pruned,
        test_one_stale_campaign_authorization_does_not_stop_all_campaigns,
        test_existing_phase_surface_and_reconnect_are_preserved,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
