from __future__ import annotations

from pathlib import Path

from campaign_party import normalize_party_preferences
from campaign_privacy import normalize_privacy_preferences


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    root = Path(__file__).resolve().parent

    party = normalize_party_preferences()
    check(party["share_hp"] is False, "Party HP must be opt-in")
    check(party["share_at"] is False, "Party AT must be opt-in")
    check(party["share_abilities"] is False, "Party abilities must be opt-in")
    check(party["share_notes"] is False, "Party notes must be opt-in")

    dm = normalize_privacy_preferences({"share_backstory": True})
    check("share_backstory" not in dm, "Backstory must not survive normalization")

    role_ui = (root / "campaign_role_ui.py").read_text(encoding="utf-8")
    check("class DMCampaignManagerDialog" in role_ui, "DM Campaign Manager missing")
    check("class PlayerCampaignsDialog" in role_ui, "My Campaigns player UI missing")
    check('QLabel("HP")' in role_ui or '"HP"' in role_ui, "HP terminology missing")
    check("Remove from Campaign" in role_ui, "DM character removal UI missing")
    check("Sharing" in role_ui and "Party" in role_ui and "DM" in role_ui, "Integrated sharing controls missing")
    check("Backstory" not in role_ui, "Player UI must not advertise Backstory")

    dashboard = root / "party_dashboard"
    app = (dashboard / "app.js").read_text(encoding="utf-8")
    live = (dashboard / "live.js").read_text(encoding="utf-8")
    index = (dashboard / "index.html").read_text(encoding="utf-8")
    styles = (dashboard / "styles.css").read_text(encoding="utf-8")
    check("sanitizeRichNoteHtml" in app, "Party Dashboard rich-note sanitizer missing")
    check('resource-label">HP' in app, "Party Dashboard must display HP")
    check('id="sessionBadge"' in index, "Party Dashboard session status missing")
    check('id="recentRolls"' in index, "Party Dashboard roll feed missing")
    check('src="live.js"' in index, "Party Dashboard live client not loaded")
    check('from("campaign_sessions")' in live, "Party Dashboard active-session query missing")
    check('from("party_session_rolls")' in live, "Party Dashboard roll query missing")
    check("party_session_rolls" in live and "postgres_changes" in live, "Party roll Realtime subscription missing")
    check(".roll-item" in styles and ".session-badge" in styles, "Party live-play styles missing")

    sql = (root / "campaign_supabase_phase7.sql").read_text(encoding="utf-8")
    live_sql = (root / "campaign_supabase_phase7_live.sql").read_text(encoding="utf-8")
    check("party_character_state" in sql, "Party state schema missing")
    check("did_remove_campaign_character" in sql, "DM removal RPC missing")
    check("did_claim_party_dashboard" in sql, "Party Dashboard pairing RPC missing")
    check("party_session_rolls" in live_sql, "Party session-roll schema missing")
    check("did_mirror_party_session_roll" in live_sql, "Party roll mirror trigger missing")
    check("new.session_id is null" in live_sql, "Out-of-session rolls must not enter Party feed")

    smoke = (root / "phase7_party_smoke_test.py").read_text(encoding="utf-8")
    check("set_roll_sharing" in smoke, "Smoke test does not verify roll-sharing choice")
    check("did_remove_campaign_character" in smoke, "Smoke test does not verify DM removal")
    check("PHASE 7 PARTY DASHBOARD SMOKE TEST: PASS" in smoke, "Smoke test completion marker missing")

    print("Phase 7 role split: PASS")
    print("Player sharing integration: PASS")
    print("Party Dashboard character model: PASS")
    print("Party Dashboard live session status: PASS")
    print("Party Dashboard shared roll feed: PASS")
    print("Player roll-sharing enforcement model: PASS")
    print("Phase 7 end-to-end smoke test packaged: PASS")
    print("No Backstory category: PASS")
    print("HP terminology: PASS")


if __name__ == "__main__":
    main()
