from __future__ import annotations

from pathlib import Path

from discord_integration import (
    normalize_binding,
    query_visible_character_effects,
    roll_is_important,
)

ROOT = Path(__file__).resolve().parent.parent
BOT = (ROOT / "did_discord_bot.py").read_text(encoding="utf-8")
UI = (ROOT / "discord_integration_ui.py").read_text(encoding="utf-8")
INTEGRATION = (ROOT / "discord_integration.py").read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


class FakeClient:
    def __init__(self):
        self.calls = []

    def _request_json(self, method, path, query=None, body=None):
        self.calls.append({"method": method, "path": path, "query": query or {}, "body": body})
        return []


def test_legacy_roll_setting_migrates_without_losing_behavior():
    old_on = normalize_binding({"announce_rolls": True})
    old_off = normalize_binding({"announce_rolls": False})
    check(old_on["roll_notifications"] == "all", "Legacy announce_rolls=True must migrate to every shared roll")
    check(old_off["roll_notifications"] == "off", "Legacy announce_rolls=False must migrate to Off")


def test_three_roll_modes_normalize_safely():
    for mode in ("off", "important", "all"):
        binding = normalize_binding({"roll_notifications": mode})
        check(binding["roll_notifications"] == mode, f"Roll mode {mode} was not preserved")
    invalid = normalize_binding({"roll_notifications": "surprise"})
    check(invalid["roll_notifications"] == "off", "Unknown roll modes must fail safe to Off")


def test_visible_effect_query_filters_at_source():
    client = FakeClient()
    query_visible_character_effects(client, "campaign-a")
    check(len(client.calls) == 1, "Visible-effect query made an unexpected number of requests")
    call = client.calls[0]
    check(call["path"] == "/rest/v1/campaign_character_effects", "Wrong table used for visible effects")
    check(call["query"].get("visible_to_player") == "eq.true", "Visible-effect query does not filter at Supabase")
    selected = call["query"].get("select", "")
    check("gm_notes" not in selected and "private" not in selected, "Visible-effect query selected a private field")


def test_important_roll_mode_uses_explicit_shared_signal():
    check(roll_is_important({"deed_success": True}), "Successful Deed should be important")
    check(roll_is_important({"important": True}), "Future explicit important marker should be honored")
    check(not roll_is_important({"deed_success": False}), "Ordinary/failed Deed roll should not be Important-only")
    check(not roll_is_important({"total": 12}), "Ordinary shared roll should not be Important-only")


def test_hosted_ui_keeps_notification_settings_out_of_connection_flow():
    # The hosted connection dialog is not the legacy per-campaign bot settings
    # editor. Notification configuration remains in normalized bot bindings.
    for marker in (
        "class DiscordIntegrationDialog(QDialog)",
        "create_discord_connect_code",
        "disconnect_discord_campaign",
    ):
        check(marker in UI, f"Hosted Discord connection action missing: {marker}")
    for legacy_label in (
        "Session start/end announcements",
        "Campaign reveal announcements",
        "Visible character-effect changes",
    ):
        check(legacy_label not in UI, f"Legacy notification editor unexpectedly exposed: {legacy_label}")
    for key in (
        '"announce_sessions"',
        '"announce_campaign_reveals"',
        '"announce_effect_changes"',
        '"roll_notifications"',
    ):
        check(key in INTEGRATION, f"Notification configuration no longer supported: {key}")
    for key in (
        'binding.get("announce_sessions")',
        'binding.get("announce_campaign_reveals")',
        'binding.get("announce_effect_changes")',
        'binding.get("roll_notifications")',
    ):
        check(key in BOT, f"Bot no longer consumes notification setting: {key}")


def test_reveal_notifications_are_player_filtered_and_nonretroactive():
    check("_reveal_notifications_initialized" in BOT, "Reveal notification baseline state is missing")
    check("_seen_campaign_reveals" in BOT, "Reveal deduplication state is missing")
    check("query_visible_campaign_entries" in BOT and "query_visible_campaign_npcs" in BOT, "Reveal notices do not use player-visible queries")
    check("current_keys" in BOT and "new_keys" in BOT, "Reveal notices are not differential")


def test_effect_notifications_do_not_leak_hidden_disappearances():
    check("_visible_effect_snapshots" in BOT, "Effect snapshot tracking is missing")
    check("_fetch_visible_effects" in BOT, "Visible effect fetch is missing")
    check("Disappearing rows are intentionally silent" in BOT, "Hidden/deleted effect disappearance privacy rule is missing")
    check("party_names" in BOT and "_fetch_party" in BOT, "Effect character names are not resolved through Party Dashboard-safe state")


def test_roll_notifications_still_use_shared_roll_view_and_active_channel():
    check("query_party_rolls" in BOT, "Roll notifications no longer use the shared roll view")
    check('roll_mode = str(binding.get("roll_notifications") or "off")' in BOT, "Roll mode is not applied by polling")
    check('if roll_mode == "important" and not roll_is_important(event):' in BOT, "Important-only filtering is missing")
    check("_notification_channel(binding, active_id or previous_id)" in BOT, "Automatic notices do not use active-session/Home Channel routing")


def test_prior_discord_surface_preserved():
    for command in ("did", "party", "character", "rolls", "campaign", "npcs", "session", "dashboard"):
        check(f'name="{command}"' in BOT, f"/{command} command missing after Phase 6")
    check("class SessionChannelSelect(discord.ui.ChannelSelect)" in BOT, "Phase 5 voice/text session picker regressed")
    check("class DIDMenuView(discord.ui.View)" in BOT, "Phase 3 interactive menu regressed")


def main():
    tests = [
        test_legacy_roll_setting_migrates_without_losing_behavior,
        test_three_roll_modes_normalize_safely,
        test_visible_effect_query_filters_at_source,
        test_important_roll_mode_uses_explicit_shared_signal,
        test_hosted_ui_keeps_notification_settings_out_of_connection_flow,
        test_reveal_notifications_are_player_filtered_and_nonretroactive,
        test_effect_notifications_do_not_leak_hidden_disappearances,
        test_roll_notifications_still_use_shared_roll_view_and_active_channel,
        test_prior_discord_surface_preserved,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"Ran {len(tests)} tests")
    print("OK")


if __name__ == "__main__":
    main()
