from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path


CONFIG_FILENAME = "discord_integration.json"
PID_FILENAME = "discord_bot.pid"
LOG_FILENAME = "discord_bot.log"
SCHEMA_VERSION = 2


def default_user_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "DID Character Sheet"
    return Path.home() / ".did_character_sheet"


def config_path(user_data_dir=None) -> Path:
    root = Path(user_data_dir or default_user_data_dir())
    return root / CONFIG_FILENAME


def pid_path(user_data_dir=None) -> Path:
    root = Path(user_data_dir or default_user_data_dir())
    return root / PID_FILENAME


def log_path(user_data_dir=None) -> Path:
    root = Path(user_data_dir or default_user_data_dir())
    return root / LOG_FILENAME


def _read_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temp.replace(path)


def empty_config():
    return {
        "schema_version": SCHEMA_VERSION,
        "bot_token": "",
        "application_id": "",
        "campaigns": {},
    }


def normalize_config(raw=None):
    result = empty_config()
    if isinstance(raw, dict):
        result["bot_token"] = str(raw.get("bot_token") or "").strip()
        result["application_id"] = str(raw.get("application_id") or "").strip()
        campaigns = raw.get("campaigns") if isinstance(raw.get("campaigns"), dict) else {}
        clean = {}
        for campaign_id, entry in campaigns.items():
            campaign_id = str(campaign_id or "").strip()
            if not campaign_id or not isinstance(entry, dict):
                continue
            clean[campaign_id] = normalize_binding(entry)
        result["campaigns"] = clean
    result["schema_version"] = SCHEMA_VERSION
    return result


ROLL_NOTIFICATION_MODES = ("off", "important", "all")


def normalize_roll_notification_mode(value, legacy_announce_rolls=False):
    mode = str(value or "").strip().lower()
    if mode in ROLL_NOTIFICATION_MODES:
        return mode
    return "all" if legacy_announce_rolls else "off"


def normalize_binding(value=None):
    value = value if isinstance(value, dict) else {}
    roll_mode = normalize_roll_notification_mode(
        value.get("roll_notifications"),
        legacy_announce_rolls=bool(value.get("announce_rolls", False)),
    )
    return {
        "campaign_name": str(value.get("campaign_name") or "Campaign").strip() or "Campaign",
        "guild_id": str(value.get("guild_id") or "").strip(),
        "channel_id": str(value.get("channel_id") or "").strip(),
        "dm_role_id": str(value.get("dm_role_id") or "").strip(),
        "dashboard_url": str(value.get("dashboard_url") or "").strip(),
        "announce_sessions": bool(value.get("announce_sessions", True)),
        "announce_campaign_reveals": bool(value.get("announce_campaign_reveals", False)),
        "announce_effect_changes": bool(value.get("announce_effect_changes", False)),
        "roll_notifications": roll_mode,
        # Kept as a compatibility mirror for older local builds. New code uses
        # roll_notifications so all three Phase 6 modes survive round-trips.
        "announce_rolls": roll_mode == "all",
        "pending_dashboard_code": str(value.get("pending_dashboard_code") or "").strip(),
        # Temporary per-session Discord destination. This is local routing
        # metadata only; the authoritative session itself remains in Supabase.
        "session_channel_id": str(value.get("session_channel_id") or "").strip(),
        "session_channel_session_id": str(value.get("session_channel_session_id") or "").strip(),
    }


def load_config(user_data_dir=None):
    return normalize_config(_read_json(config_path(user_data_dir), {}))


def save_config(config, user_data_dir=None):
    clean = validate_channel_mappings(config)
    clean = validate_dm_role_mappings(clean)
    _write_json(config_path(user_data_dir), clean)
    return clean


def get_binding(config, campaign_id):
    config = normalize_config(config)
    return normalize_binding(config["campaigns"].get(str(campaign_id or "").strip()))


def set_binding(config, campaign_id, binding):
    clean = normalize_config(config)
    campaign_id = str(campaign_id or "").strip()
    if not campaign_id:
        raise ValueError("Campaign ID is required")
    normalized = normalize_binding(binding)
    conflict = _channel_conflict(clean, campaign_id, normalized)
    if conflict:
        other_id, other, channel_id = conflict
        raise ValueError(
            "Discord channel ID "
            f"{channel_id} is already connected to "
            f"{other.get('campaign_name') or other_id}. "
            "A Discord channel can be connected to only one DID campaign at a time."
        )
    role_conflict = _dm_role_conflict(clean, campaign_id, normalized)
    if role_conflict:
        other_id, other, role_id = role_conflict
        raise ValueError(
            "Discord DM Role ID "
            f"{role_id} is already assigned to "
            f"{other.get('campaign_name') or other_id}. "
            "Each DID campaign in a Discord server must use its own DM role."
        )
    clean["campaigns"][campaign_id] = normalized
    return clean


def remove_binding(config, campaign_id):
    clean = normalize_config(config)
    clean["campaigns"].pop(str(campaign_id or "").strip(), None)
    return clean


def _binding_route_ids(binding):
    """Return every Discord channel currently routed to this campaign.

    The Home Channel is permanent. ``session_channel_id`` is temporary and is
    considered a route only while it is associated with a concrete DID session.
    A campaign may intentionally use its Home Channel as the session channel;
    duplicates within the same campaign are collapsed.
    """
    routes = set()
    home = str(binding.get("channel_id") or "").strip()
    if home:
        routes.add(home)
    session_channel = str(binding.get("session_channel_id") or "").strip()
    session_id = str(binding.get("session_channel_session_id") or "").strip()
    if session_channel and session_id:
        routes.add(session_channel)
    return routes


def resolve_channel_binding(config, guild_id, channel_id):
    """Return the one campaign routed to this Discord guild/channel.

    The permanent Home Channel always routes to its campaign. During a live
    session, a temporary session channel (including a voice channel's attached
    text chat) routes to that same campaign as well. Routing remains fail-closed:
    if configuration corruption maps a channel to more than one campaign, no
    campaign is returned.
    """
    clean = normalize_config(config)
    guild_id = str(guild_id or "").strip()
    channel_id = str(channel_id or "").strip()
    if not guild_id or not channel_id:
        return None

    matches = []
    for campaign_id, binding in clean["campaigns"].items():
        if str(binding.get("guild_id") or "").strip() != guild_id:
            continue
        if channel_id in _binding_route_ids(binding):
            matches.append((campaign_id, binding))

    return matches[0] if len(matches) == 1 else None


def _channel_conflict(config, campaign_id, binding):
    guild_id = str(binding.get("guild_id") or "").strip()
    if not guild_id:
        return None
    candidate_routes = _binding_route_ids(binding)
    if not candidate_routes:
        return None
    for other_id, other in config.get("campaigns", {}).items():
        if str(other_id) == str(campaign_id):
            continue
        if str(other.get("guild_id") or "").strip() != guild_id:
            continue
        overlap = candidate_routes.intersection(_binding_route_ids(other))
        if overlap:
            return str(other_id), other, sorted(overlap)[0]
    return None




def _dm_role_conflict(config, campaign_id, binding):
    """Reject reuse of one DM role by multiple campaigns in the same server.

    Phase 7 intentionally makes DM authority campaign-scoped. Reusing a role
    would make membership in Campaign A's DM role silently grant Campaign B's
    DM controls, so the configuration fails closed instead.
    """
    guild_id = str(binding.get("guild_id") or "").strip()
    role_id = str(binding.get("dm_role_id") or "").strip()
    if not guild_id or not role_id:
        return None
    for other_id, other in config.get("campaigns", {}).items():
        if str(other_id) == str(campaign_id):
            continue
        if str(other.get("guild_id") or "").strip() != guild_id:
            continue
        if str(other.get("dm_role_id") or "").strip() == role_id:
            return str(other_id), other, role_id
    return None


def validate_dm_role_mappings(config):
    clean = normalize_config(config)
    seen = {}
    for campaign_id, binding in clean["campaigns"].items():
        guild_id = str(binding.get("guild_id") or "").strip()
        role_id = str(binding.get("dm_role_id") or "").strip()
        if not guild_id or not role_id:
            continue
        key = (guild_id, role_id)
        if key in seen and seen[key] != campaign_id:
            other_id = seen[key]
            other = clean["campaigns"].get(other_id, {})
            raise ValueError(
                "Discord DM Role ID "
                f"{role_id} is already assigned to "
                f"{other.get('campaign_name') or other_id}. "
                "Each DID campaign in a Discord server must use its own DM role."
            )
        seen[key] = campaign_id
    return clean

def validate_channel_mappings(config):
    clean = normalize_config(config)
    seen = {}
    for campaign_id, binding in clean["campaigns"].items():
        guild_id = str(binding.get("guild_id") or "").strip()
        if not guild_id:
            continue
        for channel_id in _binding_route_ids(binding):
            key = (guild_id, channel_id)
            if key in seen and seen[key] != campaign_id:
                other_id = seen[key]
                other = clean["campaigns"].get(other_id, {})
                raise ValueError(
                    "Discord channel ID "
                    f"{channel_id} is already connected to "
                    f"{other.get('campaign_name') or other_id}. "
                    "A Discord channel can be connected to only one DID campaign at a time."
                )
            seen[key] = campaign_id
    return clean

def _numeric_id(value, label, required=False):
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValueError(f"{label} is required")
        return ""
    if not text.isdigit():
        raise ValueError(f"{label} must contain only numbers")
    return text


def validate_config_for_start(config):
    config = validate_channel_mappings(config)
    config = validate_dm_role_mappings(config)
    if not config["bot_token"]:
        raise ValueError("Discord Bot Token is required")
    _numeric_id(config["application_id"], "Discord Application ID", required=True)
    enabled = 0
    for campaign_id, binding in config["campaigns"].items():
        if not str(campaign_id).strip():
            continue
        if binding.get("guild_id"):
            _numeric_id(binding["guild_id"], "Discord Server ID", required=True)
            _numeric_id(binding.get("channel_id"), "Discord Home Channel ID", required=True)
            # DM authority is not configured with a Discord role. The connected
            # Discord account (the owner of this bot application) is the DM for
            # campaigns configured from the DM Campaigns side of DID.
            # dm_role_id is retained only as legacy config for old installs.
            enabled += 1
    if not enabled:
        raise ValueError("Configure at least one campaign with a Discord Server ID and Home Channel ID")
    return config


def invite_url(application_id, guild_id=""):
    application_id = _numeric_id(application_id, "Discord Application ID", required=True)
    guild_id = _numeric_id(guild_id, "Discord Server ID", required=False)
    query = {
        "client_id": application_id,
        "scope": "bot applications.commands",
        # View Channel + Send Messages + Embed Links. No message-content permission.
        "permissions": str(1024 + 2048 + 16384),
    }
    if guild_id:
        query["guild_id"] = guild_id
        query["disable_guild_select"] = "true"
    return "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(query)


def open_invite_url(application_id, guild_id=""):
    url = invite_url(application_id, guild_id)
    webbrowser.open(url)
    return url


def friendly_runtime_error(error, action="complete that request"):
    """Return a short user-facing message without exposing technical internals.

    Full exception details belong in discord_bot.log. Discord/UI surfaces get an
    actionable explanation instead of raw HTTP, Supabase, traceback, or token
    information.
    """
    text = str(error or "").strip()
    lowered = text.casefold()
    action = str(action or "complete that request").strip() or "complete that request"

    if any(marker in lowered for marker in ("401", "unauthorized", "invalid token", "improper token")):
        return "Discord authentication failed. Recheck the Bot Token and restart the bot from Campaign Manager → Discord."
    if any(marker in lowered for marker in ("403", "forbidden", "missing permissions", "missing access")):
        return "The Discord bot does not have permission to do that in this channel. Check View Channel, Send Messages, and Embed Links permissions."
    if any(marker in lowered for marker in ("404", "not found", "unknown channel", "unknown guild")):
        return "The Discord server, channel, campaign, or item could not be found. It may have been removed or the saved Discord mapping may be outdated."
    if any(marker in lowered for marker in ("timeout", "timed out", "connection", "network", "temporarily unavailable", "service unavailable")):
        return f"DID couldn't {action} because the connection is temporarily unavailable. Try again in a moment."
    return f"DID couldn't {action} right now. Check discord_bot.log if the problem continues."


def discord_library_available():
    try:
        import discord  # noqa: F401
        return True
    except Exception:
        return False


def _read_pid(user_data_dir=None):
    try:
        text = pid_path(user_data_dir).read_text(encoding="utf-8").strip()
        return int(text) if text.isdigit() else None
    except OSError:
        return None


def _write_pid(pid, user_data_dir=None):
    path = pid_path(user_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(int(pid)), encoding="utf-8")


def _clear_pid(user_data_dir=None):
    try:
        pid_path(user_data_dir).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def pid_is_running(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def bot_status(user_data_dir=None):
    pid = _read_pid(user_data_dir)
    if pid and pid_is_running(pid):
        return {"running": True, "pid": pid, "log": str(log_path(user_data_dir))}
    if pid:
        _clear_pid(user_data_dir)
    return {"running": False, "pid": None, "log": str(log_path(user_data_dir))}


def stop_bot(user_data_dir=None):
    status = bot_status(user_data_dir)
    pid = status.get("pid")
    if not pid:
        return False
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    finally:
        _clear_pid(user_data_dir)
    return True


def launch_bot(app_dir, user_data_dir=None):
    root = Path(app_dir).resolve()
    script = root / "did_discord_bot.py"
    if not script.is_file():
        raise FileNotFoundError("did_discord_bot.py is missing from the DID project folder")
    config = validate_config_for_start(load_config(user_data_dir))
    if not discord_library_available():
        raise RuntimeError(
            "discord.py is not installed. Run: python -m pip install -U \"discord.py>=2.7,<3\""
        )

    stop_bot(user_data_dir)
    log = log_path(user_data_dir)
    log.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log.open("a", encoding="utf-8")

    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    try:
        process = subprocess.Popen(
            [sys.executable, str(script), "--app-dir", str(root)],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            close_fds=(os.name != "nt"),
        )
    finally:
        log_handle.close()

    _write_pid(process.pid, user_data_dir)

    # Catch immediate startup failures (bad token, import/config crash, etc.)
    # instead of telling the user a dead process "started" merely because Popen
    # returned a PID. A healthy Discord connection may take longer than this,
    # but a process that has already exited is definitely not healthy.
    deadline = time.monotonic() + 2.0
    exit_code = process.poll()
    while exit_code is None and time.monotonic() < deadline:
        time.sleep(0.1)
        exit_code = process.poll()
    if exit_code is not None:
        _clear_pid(user_data_dir)
        raise RuntimeError(
            f"Discord bot stopped during startup (exit code {exit_code}). "
            f"Check the bot log for details: {log}"
        )

    return {"pid": process.pid, "log": str(log), "campaign_count": len(config["campaigns"])}


def query_campaign_exists(client, campaign_id):
    """Return True only when the campaign is still visible to the DID identity.

    A deleted campaign returns an empty list through Supabase/PostgREST. Network
    or authentication failures are allowed to raise so callers do not prune a
    valid Discord binding on a transient error.
    """
    campaign_id = str(campaign_id or "").strip()
    if not campaign_id:
        return False
    rows = client._request_json(
        "GET",
        "/rest/v1/campaigns",
        query={
            "id": f"eq.{campaign_id}",
            "select": "id",
            "limit": "1",
        },
    )
    return bool(rows) if isinstance(rows, list) else False


def query_party_state(client, campaign_id):
    rows = client._request_json(
        "GET",
        "/rest/v1/party_character_state",
        query={
            "campaign_id": f"eq.{str(campaign_id)}",
            "select": "campaign_character_id,campaign_id,state,updated_at",
            "order": "updated_at.desc",
        },
    )
    return rows if isinstance(rows, list) else []


def query_active_session(client, campaign_id):
    rows = client._request_json(
        "GET",
        "/rest/v1/campaign_sessions",
        query={
            "campaign_id": f"eq.{str(campaign_id)}",
            "ended_at": "is.null",
            "select": "*",
            "order": "started_at.desc",
            "limit": "1",
        },
    )
    return rows[0] if isinstance(rows, list) and rows else None



def start_campaign_session(client, campaign_id):
    """Start the authoritative DID campaign session through the existing RPC."""
    campaign_id = str(campaign_id or "").strip()
    if not campaign_id:
        raise ValueError("Campaign ID is required")
    rows = client._request_json(
        "POST",
        "/rest/v1/rpc/did_start_session",
        body={"p_campaign_id": campaign_id},
    )
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("The session could not be started")
    return rows[0]


def end_campaign_session(client, campaign_id):
    """End the authoritative DID campaign session through the existing RPC."""
    campaign_id = str(campaign_id or "").strip()
    if not campaign_id:
        raise ValueError("Campaign ID is required")
    rows = client._request_json(
        "POST",
        "/rest/v1/rpc/did_end_session",
        body={"p_campaign_id": campaign_id},
    )
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("The session could not be ended")
    return rows[0]

def query_party_rolls(client, campaign_id, session_id, limit=30):
    if not session_id:
        return []
    rows = client._request_json(
        "GET",
        "/rest/v1/party_session_rolls",
        query={
            "campaign_id": f"eq.{str(campaign_id)}",
            "session_id": f"eq.{str(session_id)}",
            "select": "event_id,campaign_id,session_id,campaign_character_id,rolled_at,event",
            "order": "rolled_at.desc",
            "limit": str(max(1, min(100, int(limit)))),
        },
    )
    return rows if isinstance(rows, list) else []


def query_visible_campaign_entries(client, campaign_id, limit=20):
    """Return only campaign entries explicitly revealed to players.

    The Discord bot intentionally asks PostgREST for player-visible rows and a
    restricted column set. It never downloads hidden campaign entries and then
    filters them locally.
    """
    rows = client._request_json(
        "GET",
        "/rest/v1/campaign_entries",
        query={
            "campaign_id": f"eq.{str(campaign_id)}",
            "visible_to_players": "eq.true",
            "select": "id,entry_type,title,body,status,updated_at",
            "order": "updated_at.desc",
            "limit": str(max(1, min(100, int(limit)))),
        },
    )
    return rows if isinstance(rows, list) else []


def query_visible_campaign_npcs(client, campaign_id, limit=25):
    """Return only NPCs explicitly revealed to campaign players.

    DM-only fields such as gm_notes are not selected at all.
    """
    rows = client._request_json(
        "GET",
        "/rest/v1/campaign_npcs",
        query={
            "campaign_id": f"eq.{str(campaign_id)}",
            "visible_to_players": "eq.true",
            "select": "id,name,status,description,portrait_url",
            "order": "name.asc",
            "limit": str(max(1, min(100, int(limit)))),
        },
    )
    return rows if isinstance(rows, list) else []




def query_visible_character_effects(client, campaign_id, limit=100):
    """Return only character effects explicitly visible to players.

    Discord never selects hidden effects and does not select any DM-private
    fields. Character display names are resolved separately from the existing
    Party Dashboard-safe character state.
    """
    rows = client._request_json(
        "GET",
        "/rest/v1/campaign_character_effects",
        query={
            "campaign_id": f"eq.{str(campaign_id)}",
            "visible_to_player": "eq.true",
            "select": "id,campaign_character_id,name,description,status,updated_at",
            "order": "updated_at.desc",
            "limit": str(max(1, min(200, int(limit)))),
        },
    )
    return rows if isinstance(rows, list) else []


def roll_is_important(event):
    """Return whether a shared roll qualifies for Important-only notices.

    The shared roll schema currently exposes one explicit exceptional outcome:
    a successful Deed. Future producers may set ``important`` directly without
    changing Discord. Ordinary rolls and failed/non-Deed rolls stay quiet.
    """
    event = event if isinstance(event, dict) else {}
    return event.get("important") is True or event.get("deed_success") is True


def ability_die_text(value):
    value = value if isinstance(value, dict) else {}
    try:
        die = max(0, int(value.get("die_size") or 0))
    except (TypeError, ValueError):
        die = 0
    try:
        bonus = int(value.get("bonus") or 0)
    except (TypeError, ValueError):
        bonus = 0
    result = f"d{die}" if die else "—"
    if bonus > 0:
        result += f"+{bonus}"
    elif bonus < 0:
        result += str(bonus)
    return result


def character_summary(state, include_details=True):
    state = state if isinstance(state, dict) else {}
    name = str(state.get("name") or "Unnamed Character")
    species = str(state.get("species") or "").strip()
    level = state.get("level")
    subtitle = " • ".join(x for x in (species, f"Level {level}" if level else "") if x)
    lines = [subtitle] if subtitle else []
    sharing = state.get("sharing") if isinstance(state.get("sharing"), dict) else {}

    if sharing.get("hp") and isinstance(state.get("hp"), dict):
        hp = state["hp"]
        lines.append(f"HP {int(hp.get('current') or 0)} / {int(hp.get('max') or 0)}")
    if sharing.get("at") and isinstance(state.get("at"), dict):
        at = state["at"]
        lines.append(f"AT {int(at.get('current') or 0)} / {int(at.get('max') or 0)}")
    if sharing.get("abilities") and isinstance(state.get("abilities"), dict):
        order = ("agility", "strength", "finesse", "instinct", "presence", "knowledge")
        chunks = []
        for ability in order:
            if ability in state["abilities"]:
                chunks.append(f"{ability.title()} {ability_die_text(state['abilities'][ability])}")
        if chunks:
            lines.append(" • ".join(chunks))

    if include_details and sharing.get("improvements"):
        items = state.get("improvements") if isinstance(state.get("improvements"), list) else []
        names = [str(item.get("name") or item.get("catalog_id") or "Improvement") for item in items if isinstance(item, dict)]
        if names:
            lines.append("Improvements: " + ", ".join(names[:10]))

    return name, "\n".join(lines) if lines else "Name only"


def roll_title(event):
    event = event if isinstance(event, dict) else {}
    name = str(event.get("character_name") or "Character")
    ability = str(event.get("ability_name") or "").strip()
    roll_type = str(event.get("roll_type") or "ability")
    if roll_type == "other_dice":
        return f"{name} • Other Dice"
    return f"{name} • {ability}" if ability else f"{name} • Roll"


def _die_groups(event):
    event = event if isinstance(event, dict) else {}
    groups = event.get("groups") if isinstance(event.get("groups"), list) else []
    if groups:
        parts = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            sides = int(group.get("sides") or 0)
            values = group.get("values") if isinstance(group.get("values"), list) else []
            parts.append(f"d{sides}: {', '.join(str(v) for v in values)}")
        return " • ".join(parts)
    dice = event.get("dice") if isinstance(event.get("dice"), list) else []
    parts = []
    for term in dice:
        if not isinstance(term, dict):
            continue
        sides = int(term.get("sides") or 0)
        values = term.get("values") if isinstance(term.get("values"), list) else []
        parts.append(f"d{sides}: {'→'.join(str(v) for v in values)}")
    return " • ".join(parts)


def roll_result(event):
    event = event if isinstance(event, dict) else {}
    details = _die_groups(event)
    if event.get("individual_only") or event.get("total") is None:
        return details or "Individual dice"
    result = str(event.get("total"))
    if details:
        result += f" ({details})"
    if event.get("deed_success") is True:
        result += " • Deed success"
    elif event.get("deed_success") is False:
        result += " • Deed failed"
    return result
