from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks

from campaign_cloud import CampaignCloudClient
from discord_integration import (
    character_summary,
    config_path,
    default_user_data_dir,
    get_binding,
    load_config,
    normalize_config,
    query_active_session,
    query_campaign_exists,
    start_campaign_session,
    end_campaign_session,
    friendly_runtime_error,
    query_party_rolls,
    query_party_state,
    query_visible_campaign_entries,
    query_visible_campaign_npcs,
    query_visible_character_effects,
    resolve_channel_binding,
    roll_is_important,
    roll_result,
    roll_title,
    save_config,
    set_binding,
    remove_binding,
)


POLL_SECONDS = 3.0


def _truncate(text, limit):
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"



def _session_label(session):
    session = session if isinstance(session, dict) else {}
    custom = str(session.get("session_name") or "").strip()
    if custom:
        return custom
    raw = str(session.get("started_at") or "").strip()
    if raw:
        try:
            started = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
            return f"{started.strftime('%b')} {started.day}, {started.year}"
        except (TypeError, ValueError):
            pass
    return "Session"

class DIDDiscordBot(discord.Client):
    def __init__(self, app_dir: Path):
        intents = discord.Intents.none()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.app_dir = Path(app_dir).resolve()
        # Use the same DID/Supabase identity as the desktop application.
        # A separate bot-only anonymous identity can lose campaign membership
        # and then see a configured campaign but not its live session/state.
        self.bot_user_data_dir = default_user_data_dir()
        self.cloud = CampaignCloudClient(app_dir=self.app_dir)
        self.config = normalize_config(load_config())
        self._last_session = {}
        self._seen_rolls = {}
        self._initialized_campaigns = set()
        self._seen_campaign_reveals = {}
        self._reveal_notifications_initialized = set()
        self._visible_effect_snapshots = {}
        self._effect_notifications_initialized = set()

    async def setup_hook(self):
        self.config = normalize_config(load_config())
        await self._claim_pending_campaigns()
        await self._prune_stale_bindings()
        self.config = normalize_config(load_config())
        guild_ids = sorted({
            int(binding["guild_id"])
            for binding in self.config["campaigns"].values()
            if str(binding.get("guild_id") or "").isdigit()
        })
        for guild_id in guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
            except discord.Forbidden:
                logging.error(
                    "Could not synchronize Discord commands to server %s: missing Discord permissions or bot access.",
                    guild_id,
                )
            except discord.HTTPException:
                logging.exception("Could not synchronize Discord commands to server %s", guild_id)

    async def on_ready(self):
        logging.info("Discord bot connected as %s (%s)", self.user, getattr(self.user, "id", ""))
        if not self.poll_campaigns.is_running():
            self.poll_campaigns.start()

    async def _claim_pending_campaigns(self):
        config = normalize_config(load_config())
        changed = False
        for campaign_id, binding in list(config["campaigns"].items()):
            code = str(binding.get("pending_dashboard_code") or "").strip()
            if not code:
                continue
            try:
                rows = await asyncio.to_thread(
                    self.cloud._request_json,
                    "POST",
                    "/rest/v1/rpc/did_claim_dashboard",
                    {"p_dashboard_code": code},
                )
            except Exception:
                # One stale/deleted campaign must not prevent every other
                # configured campaign from bringing the shared bot online.
                logging.exception("Could not authorize Discord cloud access for campaign %s", campaign_id)
                continue
            if not isinstance(rows, list) or not rows:
                logging.error(
                    "Could not authorize Discord cloud access for campaign %s. "
                    "Open Campaigns → Discord Settings and click Save & Start Bot again.",
                    campaign_id,
                )
                continue
            current = get_binding(config, campaign_id)
            current["pending_dashboard_code"] = ""
            config = set_binding(config, campaign_id, current)
            changed = True
            logging.info("Discord Supabase identity authorized for campaign %s", campaign_id)
        if changed:
            save_config(config)

    def _binding_for_interaction(self, interaction: discord.Interaction):
        self.config = normalize_config(load_config())
        return resolve_channel_binding(
            self.config,
            interaction.guild_id,
            interaction.channel_id,
        )

    async def _campaign_exists(self, campaign_id):
        return await asyncio.to_thread(query_campaign_exists, self.cloud, campaign_id)

    def _drop_campaign_binding(self, campaign_id, reason="stale campaign"):
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id:
            return
        config = normalize_config(load_config())
        if campaign_id not in config.get("campaigns", {}):
            return
        config = remove_binding(config, campaign_id)
        self.config = save_config(config)
        self._prune_removed_campaign_state(self.config["campaigns"].keys())
        logging.warning("Removed Discord binding for %s (%s)", campaign_id, reason)

    async def _prune_stale_bindings(self):
        """Remove saved Discord routes whose DID campaign no longer exists.

        Only a definitive empty Supabase result causes pruning. Connection/auth
        failures are logged and leave the binding intact.
        """
        config = normalize_config(load_config())
        changed = False
        for campaign_id in list(config.get("campaigns", {})):
            try:
                exists = await self._campaign_exists(campaign_id)
            except Exception:
                logging.exception("Could not validate saved Discord campaign %s", campaign_id)
                continue
            if exists:
                continue
            config = remove_binding(config, campaign_id)
            changed = True
            logging.warning("Pruned Discord binding for deleted campaign %s", campaign_id)
        if changed:
            self.config = save_config(config)
            self._prune_removed_campaign_state(self.config["campaigns"].keys())
        else:
            self.config = config

    async def _validated_binding_for_interaction(self, interaction: discord.Interaction, resolved=None):
        """Resolve Home or temporary session routing and reject stale routes."""
        resolved = resolved if resolved is not None else self._binding_for_interaction(interaction)
        if not resolved:
            return None
        campaign_id, binding = resolved

        # A saved Discord route must never outlive its DID campaign. This also
        # repairs older installs where a campaign was deleted before Discord
        # binding cleanup was implemented.
        try:
            exists = await self._campaign_exists(campaign_id)
        except Exception:
            logging.exception("Could not validate Discord campaign route for %s", campaign_id)
            return resolved
        if not exists:
            self._drop_campaign_binding(campaign_id, "campaign no longer exists")
            return None

        channel_id = str(interaction.channel_id or "").strip()
        home_id = str(binding.get("channel_id") or "").strip()
        if channel_id == home_id:
            return resolved

        # A non-Home route is a temporary active-session destination. Verify it
        # against the authoritative Supabase session before exposing any data.
        routed_session_id = str(binding.get("session_channel_session_id") or "").strip()
        try:
            active = await self._fetch_session(campaign_id)
        except Exception:
            logging.exception("Could not validate Discord temporary session route for %s", campaign_id)
            return None
        active_id = str((active or {}).get("id") or "").strip()
        if active_id and routed_session_id == active_id:
            return resolved
        self._clear_session_channel(campaign_id, routed_session_id)
        return None

    async def _send_ephemeral(self, interaction, message):
        """Best-effort interaction reply that never leaks a secondary Discord error."""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(str(message), ephemeral=True)
            else:
                await interaction.response.send_message(str(message), ephemeral=True)
            return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logging.exception("Could not send Discord interaction response")
            return False

    async def _safe_channel_send(self, channel, *args, **kwargs):
        """Send an automatic notification without breaking the polling loop."""
        if channel is None:
            return False
        try:
            await channel.send(*args, **kwargs)
            return True
        except discord.Forbidden:
            logging.error(
                "Discord notification skipped for channel %s: missing Send Messages/Embed Links permission.",
                getattr(channel, "id", "unknown"),
            )
            return False
        except discord.NotFound:
            logging.warning(
                "Discord notification skipped because channel %s no longer exists.",
                getattr(channel, "id", "unknown"),
            )
            return False
        except discord.HTTPException:
            logging.exception(
                "Discord notification delivery failed for channel %s",
                getattr(channel, "id", "unknown"),
            )
            return False

    async def _send_binding_error(self, interaction):
        await self._send_ephemeral(
            interaction,
            "This channel isn't connected to a DID campaign.",
        )

    def _is_dm(self, interaction: discord.Interaction, binding):
        """Return DM authority for the one Discord account connected to DID.

        DID no longer asks users to create campaign-specific Discord roles.
        A local Discord configuration is created from the DM side of a DID
        campaign, and the Discord account that owns the configured bot
        application is the DM account for those locally configured campaigns.

        Older installations may still contain a DM role; that is used only as
        a compatibility fallback if Discord does not expose an application
        owner for some reason.
        """
        user = interaction.user
        user_id = str(getattr(user, "id", "") or "").strip()
        if not user_id:
            return False

        application = getattr(self, "application", None)
        owner = getattr(application, "owner", None) if application is not None else None
        owner_id = str(getattr(owner, "id", "") or "").strip()
        if owner_id:
            return user_id == owner_id

        # Compatibility only for old local setups. New setup does not expose
        # or require a DM Role ID.
        role_id = str(binding.get("dm_role_id") or "").strip()
        if role_id and isinstance(user, discord.Member):
            return any(str(role.id) == role_id for role in user.roles)
        return False

    async def _fetch_party(self, campaign_id):
        return await asyncio.to_thread(query_party_state, self.cloud, campaign_id)

    async def _fetch_session(self, campaign_id):
        return await asyncio.to_thread(query_active_session, self.cloud, campaign_id)

    async def _fetch_rolls(self, campaign_id, session_id, limit=30):
        return await asyncio.to_thread(query_party_rolls, self.cloud, campaign_id, session_id, limit)

    async def _fetch_visible_entries(self, campaign_id, limit=100):
        return await asyncio.to_thread(query_visible_campaign_entries, self.cloud, campaign_id, limit)

    async def _fetch_visible_npcs(self, campaign_id, limit=100):
        return await asyncio.to_thread(query_visible_campaign_npcs, self.cloud, campaign_id, limit)

    async def _fetch_visible_effects(self, campaign_id, limit=100):
        return await asyncio.to_thread(query_visible_character_effects, self.cloud, campaign_id, limit)

    async def _notification_channel(self, binding, session_id=""):
        # While a session is active, an explicitly selected temporary session
        # channel takes precedence. The permanent Home Channel remains intact.
        raw = ""
        session_id = str(session_id or "").strip()
        bound_session_id = str(binding.get("session_channel_session_id") or "").strip()
        session_channel_id = str(binding.get("session_channel_id") or "").strip()
        if session_id and session_channel_id and (not bound_session_id or bound_session_id == session_id):
            raw = session_channel_id
        if not raw:
            raw = str(binding.get("channel_id") or "").strip()
        if not raw.isdigit():
            return None
        channel_id = int(raw)
        channel = self.get_channel(channel_id)
        if channel is not None:
            return channel
        try:
            return await self.fetch_channel(channel_id)
        except Exception:
            return None

    def _set_session_channel(self, campaign_id, channel_id, session_id):
        config = normalize_config(load_config())
        binding = get_binding(config, campaign_id)
        binding["session_channel_id"] = str(channel_id or "").strip()
        binding["session_channel_session_id"] = str(session_id or "").strip()
        self.config = save_config(set_binding(config, campaign_id, binding))
        return get_binding(self.config, campaign_id)

    def _clear_session_channel(self, campaign_id, expected_session_id=""):
        config = normalize_config(load_config())
        binding = get_binding(config, campaign_id)
        expected = str(expected_session_id or "").strip()
        current = str(binding.get("session_channel_session_id") or "").strip()
        if expected and current and current != expected:
            return binding
        if not binding.get("session_channel_id") and not binding.get("session_channel_session_id"):
            return binding
        binding["session_channel_id"] = ""
        binding["session_channel_session_id"] = ""
        self.config = save_config(set_binding(config, campaign_id, binding))
        return get_binding(self.config, campaign_id)

    def _prune_removed_campaign_state(self, configured_campaign_ids):
        """Drop only in-memory caches for campaigns removed from local config."""
        keep = {str(value) for value in configured_campaign_ids}
        for mapping in (
            self._last_session,
            self._seen_rolls,
            self._seen_campaign_reveals,
            self._visible_effect_snapshots,
        ):
            for campaign_id in list(mapping):
                if str(campaign_id) not in keep:
                    mapping.pop(campaign_id, None)
        self._initialized_campaigns.intersection_update(keep)
        self._reveal_notifications_initialized.intersection_update(keep)
        self._effect_notifications_initialized.intersection_update(keep)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_campaigns(self):
        try:
            self.config = normalize_config(load_config())
            self._prune_removed_campaign_state(self.config["campaigns"].keys())
            for campaign_id, binding in self.config["campaigns"].items():
                if not binding.get("guild_id"):
                    continue
                try:
                    await self._poll_one(campaign_id, binding)
                except Exception:
                    logging.exception("Discord campaign polling failed for %s", campaign_id)
        except Exception:
            logging.exception("Discord polling loop failed")

    @poll_campaigns.before_loop
    async def before_poll_campaigns(self):
        await self.wait_until_ready()

    async def _poll_one(self, campaign_id, binding):
        active = await self._fetch_session(campaign_id)
        active_id = str((active or {}).get("id") or "")
        previous_id = self._last_session.get(campaign_id, "")
        first = campaign_id not in self._initialized_campaigns

        # Automatic notices use the temporary active-session channel while a
        # session is live, otherwise the campaign's permanent Home Channel.
        channel = await self._notification_channel(binding, active_id or previous_id)

        if first:
            self._initialized_campaigns.add(campaign_id)
            self._last_session[campaign_id] = active_id
            if not active_id and (binding.get("session_channel_id") or binding.get("session_channel_session_id")):
                # Recover cleanly after a bot/DID restart that happened after a
                # session ended but before the previous process cleared routing.
                self._clear_session_channel(campaign_id)
            if active_id:
                rows = await self._fetch_rolls(campaign_id, active_id, 100)
                self._seen_rolls[campaign_id] = {str(row.get("event_id") or "") for row in rows}
            else:
                self._seen_rolls[campaign_id] = set()

        if not first and previous_id != active_id:
            if binding.get("announce_sessions") and channel is not None:
                if previous_id and not active_id:
                    await self._safe_channel_send(channel, f"**{binding.get('campaign_name') or 'Campaign'}:** session ended.")
                elif active_id:
                    await self._safe_channel_send(
                        channel,
                        f"**{binding.get('campaign_name') or 'Campaign'}:** {_session_label(active)} started."
                    )
            self._last_session[campaign_id] = active_id
            self._seen_rolls[campaign_id] = set()
            if previous_id and not active_id:
                self._clear_session_channel(campaign_id, previous_id)
                # The end announcement deliberately used the just-ended session
                # channel. Any persistent notices discovered after the session
                # ended belong back in the permanent Home Channel.
                binding = get_binding(normalize_config(load_config()), campaign_id)
                channel = await self._notification_channel(binding, active_id)

        # Campaign reveals are queried already filtered to player-visible rows.
        # Turning notifications on establishes a baseline first, so old reveals
        # are never dumped into Discord retroactively.
        if binding.get("announce_campaign_reveals"):
            entries, npcs = await asyncio.gather(
                self._fetch_visible_entries(campaign_id, 100),
                self._fetch_visible_npcs(campaign_id, 100),
            )
            current_reveals = {
                f"entry:{row.get('id')}": ("entry", row)
                for row in entries
                if str(row.get("id") or "").strip()
            }
            current_reveals.update({
                f"npc:{row.get('id')}": ("npc", row)
                for row in npcs
                if str(row.get("id") or "").strip()
            })
            current_keys = set(current_reveals)
            if campaign_id not in self._reveal_notifications_initialized:
                self._reveal_notifications_initialized.add(campaign_id)
                self._seen_campaign_reveals[campaign_id] = current_keys
            else:
                seen_reveals = self._seen_campaign_reveals.setdefault(campaign_id, set())
                new_keys = [key for key in current_reveals if key not in seen_reveals]
                if channel is not None:
                    for key in new_keys[-12:]:
                        kind, row = current_reveals[key]
                        if kind == "npc":
                            title = f"NPC revealed: {row.get('name') or 'Unnamed NPC'}"
                            body = str(row.get("description") or "").strip() or str(row.get("status") or "").strip()
                        else:
                            title = f"Campaign reveal: {row.get('title') or 'Untitled'}"
                            body = str(row.get("body") or "").strip()
                        embed = discord.Embed(
                            title=_truncate(title, 256),
                            description=_truncate(body, 4000) if body else None,
                            color=0xC79A3B,
                        )
                        await self._safe_channel_send(channel, embed=embed)
                self._seen_campaign_reveals[campaign_id] = current_keys
        else:
            self._reveal_notifications_initialized.discard(campaign_id)
            self._seen_campaign_reveals.pop(campaign_id, None)

        # Visible character effects use only visible_to_player rows. Names are
        # resolved from Party Dashboard-safe character state, never raw chars.
        if binding.get("announce_effect_changes"):
            effects, party_rows = await asyncio.gather(
                self._fetch_visible_effects(campaign_id, 100),
                self._fetch_party(campaign_id),
            )
            party_names = {}
            for party_row in party_rows:
                state = party_row.get("state") if isinstance(party_row.get("state"), dict) else {}
                cid = str(party_row.get("campaign_character_id") or "").strip()
                if cid:
                    party_names[cid] = str(state.get("name") or "Character")
            current_effects = {}
            current_effect_rows = {}
            for effect in effects:
                effect_id = str(effect.get("id") or "").strip()
                if not effect_id:
                    continue
                signature = (
                    str(effect.get("campaign_character_id") or ""),
                    str(effect.get("name") or ""),
                    str(effect.get("description") or ""),
                    str(effect.get("status") or ""),
                    str(effect.get("updated_at") or ""),
                )
                current_effects[effect_id] = signature
                current_effect_rows[effect_id] = effect
            if campaign_id not in self._effect_notifications_initialized:
                self._effect_notifications_initialized.add(campaign_id)
                self._visible_effect_snapshots[campaign_id] = current_effects
            else:
                previous_effects = self._visible_effect_snapshots.setdefault(campaign_id, {})
                changed_ids = [
                    effect_id for effect_id, signature in current_effects.items()
                    if previous_effects.get(effect_id) != signature
                ]
                if channel is not None:
                    for effect_id in changed_ids[-12:]:
                        effect = current_effect_rows[effect_id]
                        char_id = str(effect.get("campaign_character_id") or "").strip()
                        character_name = party_names.get(char_id, "Character")
                        effect_name = str(effect.get("name") or "Effect")
                        description = str(effect.get("description") or "").strip()
                        status = str(effect.get("status") or "").strip()
                        existed = effect_id in previous_effects
                        label = "Effect updated" if existed else "Effect added"
                        body_parts = [part for part in (status, description) if part]
                        embed = discord.Embed(
                            title=_truncate(f"{label}: {character_name} • {effect_name}", 256),
                            description=_truncate("\n".join(body_parts), 4000) if body_parts else None,
                            color=0xC79A3B,
                        )
                        await self._safe_channel_send(channel, embed=embed)
                # Disappearing rows are intentionally silent: disappearance may
                # mean the DM made an effect private, and Discord must not leak
                # that hidden state.
                self._visible_effect_snapshots[campaign_id] = current_effects
        else:
            self._effect_notifications_initialized.discard(campaign_id)
            self._visible_effect_snapshots.pop(campaign_id, None)

        if not active_id:
            return

        rows = await self._fetch_rolls(campaign_id, active_id, 40)
        seen = self._seen_rolls.setdefault(campaign_id, set())
        new_rows = [row for row in reversed(rows) if str(row.get("event_id") or "") not in seen]
        for row in rows:
            event_id = str(row.get("event_id") or "")
            if event_id:
                seen.add(event_id)

        roll_mode = str(binding.get("roll_notifications") or "off").strip().lower()
        if roll_mode != "off" and channel is not None:
            for row in new_rows[-12:]:
                event = row.get("event") if isinstance(row.get("event"), dict) else {}
                if roll_mode == "important" and not roll_is_important(event):
                    continue
                embed = discord.Embed(
                    title=_truncate(roll_title(event), 256),
                    description=_truncate(roll_result(event), 4000),
                    color=0xC79A3B,
                )
                await self._safe_channel_send(channel, embed=embed)



def install_commands(bot: DIDDiscordBot):
    async def _resolved_or_error(interaction: discord.Interaction):
        base_resolved = bot._binding_for_interaction(interaction)
        resolved = await bot._validated_binding_for_interaction(interaction, base_resolved)
        if not resolved:
            await bot._send_binding_error(interaction)
            return None
        return resolved

    async def _resolved_for_expected_campaign(interaction: discord.Interaction, expected_campaign_id: str):
        base_resolved = bot._binding_for_interaction(interaction)
        resolved = await bot._validated_binding_for_interaction(interaction, base_resolved)
        if not resolved or str(resolved[0]) != str(expected_campaign_id):
            message = "This channel isn't connected to this DID campaign anymore. Run /did again in the campaign's Home Channel."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return None
        return resolved

    async def _party_rows(campaign_id):
        return await bot._fetch_party(campaign_id)

    def _party_state(row):
        return row.get("state") if isinstance(row.get("state"), dict) else {}

    def _party_name(row):
        state = _party_state(row)
        return str(state.get("name") or "Unnamed Character").strip() or "Unnamed Character"

    async def _send_party(interaction: discord.Interaction, campaign_id: str, binding, *, ephemeral=False):
        try:
            rows = await _party_rows(campaign_id)
        except Exception as error:
            logging.exception("Party view failed")
            await interaction.followup.send(friendly_runtime_error(error, "load the party"), ephemeral=True)
            return
        if not rows:
            await interaction.followup.send("No characters are currently sharing with the party.", ephemeral=ephemeral)
            return
        rows = sorted(rows, key=lambda row: _party_name(row).casefold())
        embed = discord.Embed(
            title=_truncate(binding.get("campaign_name") or "Party", 256),
            description=f"{len(rows)} shared character{'s' if len(rows) != 1 else ''}",
            color=0xC79A3B,
        )
        for row in rows[:20]:
            state = _party_state(row)
            name, summary = character_summary(state, include_details=False)
            embed.add_field(name=_truncate(name, 256), value=_truncate(summary, 1000), inline=False)
        if len(rows) > 20:
            embed.add_field(name="More characters", value=f"{len(rows) - 20} additional shared characters are not shown in this message.", inline=False)
        embed.set_footer(text="Only Party Dashboard-shared details are shown.")
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    async def _send_character(interaction: discord.Interaction, campaign_id: str, name: str, *, ephemeral=False):
        try:
            rows = await _party_rows(campaign_id)
        except Exception as error:
            logging.exception("Character view failed")
            await interaction.followup.send(friendly_runtime_error(error, "load shared characters"), ephemeral=True)
            return
        needle = str(name or "").strip().casefold()
        candidates = []
        for row in rows:
            state = _party_state(row)
            display = str(state.get("name") or "Unnamed Character")
            if needle in display.casefold():
                candidates.append((row, state, display))
        if not candidates:
            await interaction.followup.send(f"No shared character matched **{name}**.", ephemeral=True)
            return
        candidates.sort(key=lambda item: (0 if item[2].casefold() == needle else 1, item[2].casefold()))
        _row, state, _display = candidates[0]
        char_name, summary = character_summary(state, include_details=True)
        embed = discord.Embed(title=_truncate(char_name, 256), description=_truncate(summary, 4000), color=0xC79A3B)
        sharing = state.get("sharing") if isinstance(state.get("sharing"), dict) else {}
        if sharing.get("inventory"):
            items = state.get("inventory") if isinstance(state.get("inventory"), list) else []
            if items:
                names = [str(item.get("name") or "Item") for item in items if isinstance(item, dict)]
                embed.add_field(name="Shared Inventory", value=_truncate(", ".join(names), 1000), inline=False)
        if sharing.get("notes"):
            notes = state.get("notes") if isinstance(state.get("notes"), list) else []
            if notes:
                names = [str(item.get("title") or "Untitled note") for item in notes if isinstance(item, dict)]
                embed.add_field(name="Shared Notes", value=_truncate(", ".join(names), 1000), inline=False)
        embed.set_footer(text="Only Party Dashboard-shared details are shown.")
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    async def _send_rolls(interaction: discord.Interaction, campaign_id: str, binding, *, ephemeral=False):
        try:
            active = await bot._fetch_session(campaign_id)
            if not active:
                await interaction.followup.send("There is no active session, so there are no current shared session rolls.", ephemeral=ephemeral)
                return
            rows = await bot._fetch_rolls(campaign_id, str(active.get("id") or ""), 10)
        except Exception as error:
            logging.exception("Recent rolls view failed")
            await interaction.followup.send(friendly_runtime_error(error, "load recent shared rolls"), ephemeral=True)
            return
        if not rows:
            await interaction.followup.send("No rolls have been shared during the active session yet.", ephemeral=ephemeral)
            return
        embed = discord.Embed(
            title=_truncate(f"{binding.get('campaign_name') or 'Campaign'} • Recent Rolls", 256),
            description=f"{_session_label(active)} • newest first",
            color=0xC79A3B,
        )
        for row in rows[:10]:
            event = row.get("event") if isinstance(row.get("event"), dict) else {}
            embed.add_field(name=_truncate(roll_title(event), 256), value=_truncate(roll_result(event), 1000), inline=False)
        embed.set_footer(text="Only rolls admitted to the Party Dashboard shared-roll feed are shown.")
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    async def _send_campaign(interaction: discord.Interaction, campaign_id: str, binding, *, ephemeral=False):
        try:
            rows = await asyncio.to_thread(query_visible_campaign_entries, bot.cloud, campaign_id, 15)
        except Exception as error:
            logging.exception("Campaign view failed")
            await interaction.followup.send(friendly_runtime_error(error, "load shared campaign information"), ephemeral=True)
            return
        if not rows:
            await interaction.followup.send("The DM has not revealed any campaign information yet.", ephemeral=ephemeral)
            return
        embed = discord.Embed(title=_truncate(f"{binding.get('campaign_name') or 'Campaign'} • Campaign Info", 256), color=0xC79A3B)
        for row in rows[:15]:
            kind = str(row.get("entry_type") or "Info").replace("_", " ").title()
            status = str(row.get("status") or "").strip()
            body = str(row.get("body") or "").strip() or "No details."
            body = f"*{kind} • {status}*\n{body}" if status else f"*{kind}*\n{body}"
            embed.add_field(name=_truncate(row.get("title") or "Untitled", 256), value=_truncate(body, 1000), inline=False)
        embed.set_footer(text="Only campaign entries explicitly revealed to players are queried.")
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    async def _send_npcs(interaction: discord.Interaction, campaign_id: str, binding, *, ephemeral=False):
        try:
            rows = await asyncio.to_thread(query_visible_campaign_npcs, bot.cloud, campaign_id, 20)
        except Exception as error:
            logging.exception("NPC view failed")
            await interaction.followup.send(friendly_runtime_error(error, "load revealed NPCs"), ephemeral=True)
            return
        if not rows:
            await interaction.followup.send("The DM has not revealed any NPCs yet.", ephemeral=ephemeral)
            return
        embed = discord.Embed(
            title=_truncate(f"{binding.get('campaign_name') or 'Campaign'} • NPCs", 256),
            description=f"{len(rows)} revealed NPC{'s' if len(rows) != 1 else ''}",
            color=0xC79A3B,
        )
        for row in rows[:20]:
            status = str(row.get("status") or "").strip()
            description = str(row.get("description") or "").strip() or "No description."
            value = f"*{status}*\n{description}" if status else description
            embed.add_field(name=_truncate(row.get("name") or "Unnamed NPC", 256), value=_truncate(value, 1000), inline=False)
        embed.set_footer(text="Only NPCs explicitly revealed to players are queried; DM notes are never selected.")
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    async def _send_session(interaction: discord.Interaction, campaign_id: str, binding, *, ephemeral=False):
        try:
            active = await bot._fetch_session(campaign_id)
        except Exception as error:
            logging.exception("Session status view failed")
            await interaction.followup.send(friendly_runtime_error(error, "load session status"), ephemeral=True)
            return
        if not active:
            await interaction.followup.send(f"**{binding.get('campaign_name') or 'Campaign'}:** no active session.", ephemeral=ephemeral)
            return
        await interaction.followup.send(
            f"**{binding.get('campaign_name') or 'Campaign'}:** {_session_label(active)} is live.",
            ephemeral=ephemeral,
        )

    async def _start_session_control(interaction: discord.Interaction, campaign_id: str, binding, *, use_here: bool):
        if not bot._is_dm(interaction, binding):
            await interaction.followup.send("This control is for the campaign DM.", ephemeral=True)
            return
        try:
            active = await bot._fetch_session(campaign_id)
            if active:
                await interaction.followup.send(
                    f"{_session_label(active)} is already live.",
                    ephemeral=True,
                )
                return
            # Clear any stale temporary destination before creating a new session.
            bot._clear_session_channel(campaign_id)
            started = await asyncio.to_thread(start_campaign_session, bot.cloud, campaign_id)
            session_id = str(started.get("id") or "")
            if use_here:
                bot._set_session_channel(campaign_id, interaction.channel_id, session_id)
            destination = " This channel is now the active session channel." if use_here else ""
            await interaction.followup.send(
                f"{_session_label(started)} started.{destination}",
                ephemeral=True,
            )
        except Exception as error:
            logging.exception("Discord session start failed")
            await interaction.followup.send(friendly_runtime_error(error, "start the session"), ephemeral=True)

    async def _end_session_control(interaction: discord.Interaction, campaign_id: str, binding):
        if not bot._is_dm(interaction, binding):
            await interaction.followup.send("This control is for the campaign DM.", ephemeral=True)
            return
        try:
            active = await bot._fetch_session(campaign_id)
            if not active:
                bot._clear_session_channel(campaign_id)
                await interaction.followup.send("There is no active session to end.", ephemeral=True)
                return
            ended = await asyncio.to_thread(end_campaign_session, bot.cloud, campaign_id)
            # Leave the temporary route in place for the polling loop's end
            # announcement, then it is cleared automatically on that transition.
            await interaction.followup.send(
                f"{_session_label(active or ended)} ended.",
                ephemeral=True,
            )
        except Exception as error:
            logging.exception("Discord session end failed")
            await interaction.followup.send(friendly_runtime_error(error, "end the session"), ephemeral=True)

    async def _use_this_channel_control(interaction: discord.Interaction, campaign_id: str, binding):
        if not bot._is_dm(interaction, binding):
            await interaction.followup.send("This control is for the campaign DM.", ephemeral=True)
            return
        try:
            active = await bot._fetch_session(campaign_id)
            if not active:
                await interaction.followup.send("Start a session before choosing an active session channel.", ephemeral=True)
                return
            bot._set_session_channel(campaign_id, interaction.channel_id, str(active.get("id") or ""))
            await interaction.followup.send("This channel is now the active session channel.", ephemeral=True)
        except Exception as error:
            logging.exception("Discord session channel change failed")
            await interaction.followup.send(friendly_runtime_error(error, "change the active session channel"), ephemeral=True)

    async def _use_selected_channel_control(interaction: discord.Interaction, campaign_id: str, binding, channel_id):
        if not bot._is_dm(interaction, binding):
            await interaction.followup.send("This control is for the campaign DM.", ephemeral=True)
            return
        try:
            active = await bot._fetch_session(campaign_id)
            if not active:
                await interaction.followup.send("Start a session before choosing an active session channel.", ephemeral=True)
                return
            raw_channel_id = str(channel_id or "").strip()
            if not raw_channel_id.isdigit():
                await interaction.followup.send("Choose a valid Discord channel.", ephemeral=True)
                return
            channel = bot.get_channel(int(raw_channel_id))
            if channel is None:
                channel = await bot.fetch_channel(int(raw_channel_id))
            channel_guild = getattr(getattr(channel, "guild", None), "id", None)
            if str(channel_guild or "") != str(interaction.guild_id or ""):
                await interaction.followup.send("The session channel must be in this Discord server.", ephemeral=True)
                return
            channel_type = getattr(channel, "type", None)
            if channel_type not in (discord.ChannelType.text, discord.ChannelType.voice):
                await interaction.followup.send("Choose a text channel or a voice channel with attached text chat.", ephemeral=True)
                return
            bot._set_session_channel(campaign_id, raw_channel_id, str(active.get("id") or ""))
            if channel_type == discord.ChannelType.voice:
                description = f"<#{raw_channel_id}> is now the active session channel. DID will use its voice-channel text chat only; the bot will not join audio."
            else:
                description = f"<#{raw_channel_id}> is now the active session channel."
            await interaction.followup.send(description, ephemeral=True)
        except Exception as error:
            logging.exception("Discord selected session channel change failed")
            await interaction.followup.send(friendly_runtime_error(error, "change the active session channel"), ephemeral=True)

    class SessionChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, campaign_id: str):
            self.campaign_id = str(campaign_id)
            super().__init__(
                placeholder="Choose text or voice session channel…",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text, discord.ChannelType.voice],
                row=2,
            )

        async def callback(self, interaction: discord.Interaction):
            resolved = await _resolved_for_expected_campaign(interaction, self.campaign_id)
            if not resolved:
                return
            campaign_id, binding = resolved
            if not bot._is_dm(interaction, binding):
                await interaction.response.send_message("This control is for the campaign DM.", ephemeral=True)
                return
            selected = self.values[0]
            await interaction.response.defer(ephemeral=True, thinking=True)
            await _use_selected_channel_control(interaction, campaign_id, binding, getattr(selected, "id", ""))


    class SessionControlView(discord.ui.View):
        def __init__(self, campaign_id: str):
            super().__init__(timeout=300)
            self.campaign_id = str(campaign_id)
            self.add_item(SessionChannelSelect(self.campaign_id))

        async def _prepare(self, interaction: discord.Interaction):
            resolved = await _resolved_for_expected_campaign(interaction, self.campaign_id)
            if not resolved:
                return None
            _campaign_id, binding = resolved
            if not bot._is_dm(interaction, binding):
                await interaction.response.send_message("These session controls are for the campaign DM.", ephemeral=True)
                return None
            await interaction.response.defer(ephemeral=True, thinking=True)
            return resolved

        @discord.ui.button(label="Start Session", style=discord.ButtonStyle.success, row=0)
        async def start_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _start_session_control(interaction, campaign_id, binding, use_here=False)

        @discord.ui.button(label="Start Session Here", style=discord.ButtonStyle.success, row=0)
        async def start_here_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _start_session_control(interaction, campaign_id, binding, use_here=True)

        @discord.ui.button(label="End Session", style=discord.ButtonStyle.danger, row=1)
        async def end_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _end_session_control(interaction, campaign_id, binding)

        @discord.ui.button(label="Use This Channel", style=discord.ButtonStyle.secondary, row=1)
        async def use_channel_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _use_this_channel_control(interaction, campaign_id, binding)

    class CharacterSelect(discord.ui.Select):
        def __init__(self, campaign_id: str, names):
            self.campaign_id = str(campaign_id)
            options = [discord.SelectOption(label=_truncate(name, 100), value=_truncate(name, 100)) for name in names[:25]]
            super().__init__(placeholder="Choose a shared character…", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            resolved = await _resolved_for_expected_campaign(interaction, self.campaign_id)
            if not resolved:
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            await _send_character(interaction, self.campaign_id, self.values[0], ephemeral=True)

    class CharacterSelectView(discord.ui.View):
        def __init__(self, campaign_id: str, names):
            super().__init__(timeout=180)
            self.add_item(CharacterSelect(campaign_id, names))

    class DIDMenuView(discord.ui.View):
        def __init__(self, campaign_id: str):
            super().__init__(timeout=300)
            self.campaign_id = str(campaign_id)

        async def _prepare(self, interaction: discord.Interaction):
            resolved = await _resolved_for_expected_campaign(interaction, self.campaign_id)
            if not resolved:
                return None
            await interaction.response.defer(ephemeral=True, thinking=True)
            return resolved

        @discord.ui.button(label="Party", style=discord.ButtonStyle.primary, row=0)
        async def party_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _send_party(interaction, campaign_id, binding, ephemeral=True)

        @discord.ui.button(label="Character", style=discord.ButtonStyle.secondary, row=0)
        async def character_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await _resolved_for_expected_campaign(interaction, self.campaign_id)
            if not resolved:
                return
            campaign_id, _binding = resolved
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                rows = await _party_rows(campaign_id)
            except Exception as error:
                logging.exception("Interactive character chooser failed")
                await interaction.followup.send(friendly_runtime_error(error, "load shared characters"), ephemeral=True)
                return
            names = sorted({_party_name(row) for row in rows}, key=str.casefold)
            if not names:
                await interaction.followup.send("No characters are currently sharing with the party.", ephemeral=True)
                return
            await interaction.followup.send(
                "Choose a character:",
                view=CharacterSelectView(campaign_id, names),
                ephemeral=True,
            )

        @discord.ui.button(label="Campaign", style=discord.ButtonStyle.secondary, row=0)
        async def campaign_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _send_campaign(interaction, campaign_id, binding, ephemeral=True)

        @discord.ui.button(label="Recent Rolls", style=discord.ButtonStyle.secondary, row=1)
        async def rolls_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _send_rolls(interaction, campaign_id, binding, ephemeral=True)

        @discord.ui.button(label="NPCs", style=discord.ButtonStyle.secondary, row=1)
        async def npcs_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _send_npcs(interaction, campaign_id, binding, ephemeral=True)

        @discord.ui.button(label="Session", style=discord.ButtonStyle.success, row=1)
        async def session_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            resolved = await self._prepare(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved
            await _send_session(interaction, campaign_id, binding, ephemeral=True)

    @bot.tree.command(name="did", description="Open the DID interactive menu for this campaign")
    async def did(interaction: discord.Interaction):
        # Acknowledge the interaction first.  Routing/session validation may
        # touch cloud state and must never consume Discord's response window.
        await interaction.response.defer(ephemeral=False, thinking=True)
        try:
            resolved = await _resolved_or_error(interaction)
            if not resolved:
                return
            campaign_id, binding = resolved

            session_lookup_failed = False
            try:
                active = await bot._fetch_session(campaign_id)
            except Exception:
                logging.exception("/did session lookup failed")
                active = None
                session_lookup_failed = True
            campaign_name = str(binding.get("campaign_name") or "Campaign")
            if session_lookup_failed:
                session_text = "Session status is temporarily unavailable."
            else:
                session_text = f"{_session_label(active)} is live." if active else "No active session."
            embed = discord.Embed(
                title=_truncate(f"{campaign_name} • DID", 256),
                description=f"{session_text}\n\nUse the buttons below, or the slash commands directly.",
                color=0xC79A3B,
            )
            embed.add_field(name="Party", value="Party Dashboard-shared character summaries", inline=True)
            embed.add_field(name="Character", value="Choose one shared character", inline=True)
            embed.add_field(name="Campaign", value="Information revealed by the DM", inline=True)
            embed.add_field(name="Recent Rolls", value="Shared rolls from the active session", inline=True)
            embed.add_field(name="NPCs", value="NPCs revealed by the DM", inline=True)
            embed.add_field(name="Session", value="Current live-session status", inline=True)
            if bot._is_dm(interaction, binding):
                embed.add_field(name="DM", value="Use `/dashboard` for the DM Dashboard.", inline=False)
            embed.set_footer(text="Discord only shows data already shared or revealed to players. Menu buttons expire after 5 minutes.")
            await interaction.followup.send(embed=embed, view=DIDMenuView(campaign_id))
        except Exception as error:
            logging.exception("/did failed")
            try:
                await interaction.followup.send(
                    friendly_runtime_error(error, "open the DID menu"),
                    ephemeral=True,
                )
            except Exception:
                logging.exception("Could not send /did failure response")

    @bot.tree.command(name="party", description="Show the campaign party using Party Dashboard sharing choices")
    async def party(interaction: discord.Interaction):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        campaign_id, binding = resolved
        await interaction.response.defer(ephemeral=False, thinking=True)
        await _send_party(interaction, campaign_id, binding)

    @bot.tree.command(name="character", description="Show one Party Dashboard-shared DID character")
    @app_commands.describe(name="Choose a shared character")
    async def character(interaction: discord.Interaction, name: str):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        campaign_id, _binding = resolved
        await interaction.response.defer(ephemeral=False, thinking=True)
        await _send_character(interaction, campaign_id, name)

    @character.autocomplete("name")
    async def character_name_autocomplete(interaction: discord.Interaction, current: str):
        resolved = await bot._validated_binding_for_interaction(interaction)
        if not resolved:
            return []
        campaign_id, _binding = resolved
        try:
            rows = await _party_rows(campaign_id)
        except Exception:
            logging.exception("/character autocomplete failed")
            return []
        needle = str(current or "").strip().casefold()
        names = sorted({_party_name(row) for row in rows}, key=str.casefold)
        if needle:
            names = [name for name in names if needle in name.casefold()]
        return [app_commands.Choice(name=_truncate(name, 100), value=_truncate(name, 100)) for name in names[:25]]

    @bot.tree.command(name="rolls", description="Show recent rolls shared during the active DID session")
    async def rolls(interaction: discord.Interaction):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        campaign_id, binding = resolved
        await interaction.response.defer(ephemeral=False, thinking=True)
        await _send_rolls(interaction, campaign_id, binding)

    @bot.tree.command(name="campaign", description="Show campaign information revealed to players")
    async def campaign(interaction: discord.Interaction):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        campaign_id, binding = resolved
        await interaction.response.defer(ephemeral=False, thinking=True)
        await _send_campaign(interaction, campaign_id, binding)

    @bot.tree.command(name="npcs", description="Show NPCs the DM has revealed to players")
    async def npcs(interaction: discord.Interaction):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        campaign_id, binding = resolved
        await interaction.response.defer(ephemeral=False, thinking=True)
        await _send_npcs(interaction, campaign_id, binding)

    @bot.tree.command(name="session", description="Show or manage the DID campaign live session")
    async def session(interaction: discord.Interaction):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        campaign_id, binding = resolved
        is_dm = bot._is_dm(interaction, binding)
        await interaction.response.defer(ephemeral=is_dm, thinking=True)
        if not is_dm:
            # Players get status only - no management controls.
            await _send_session(interaction, campaign_id, binding, ephemeral=False)
            return
        try:
            active = await bot._fetch_session(campaign_id)
        except Exception as error:
            logging.exception("DM /session status failed")
            await interaction.followup.send(friendly_runtime_error(error, "load session status"), ephemeral=True)
            return
        if active:
            status = f"{_session_label(active)} is live."
            current_binding = get_binding(normalize_config(load_config()), campaign_id)
            channel_id = str(current_binding.get("session_channel_id") or "").strip()
            session_route_id = str(current_binding.get("session_channel_session_id") or "").strip()
            if channel_id and (not session_route_id or session_route_id == str(active.get("id") or "")):
                status += f"\nActive session channel: <#{channel_id}>"
            else:
                status += "\nActive session channel: Home Channel"
        else:
            status = "No active session."
        embed = discord.Embed(
            title=_truncate(f"{binding.get('campaign_name') or 'Campaign'} • Session", 256),
            description=status,
            color=0xC79A3B,
        )
        embed.set_footer(text="Choose a text or voice channel for session text. DID never joins, listens to, records, or transcribes voice audio.")
        await interaction.followup.send(embed=embed, view=SessionControlView(campaign_id), ephemeral=True)

    @bot.tree.command(name="dashboard", description="Open or locate the DID DM dashboard")
    async def dashboard(interaction: discord.Interaction):
        resolved = await _resolved_or_error(interaction)
        if not resolved:
            return
        _campaign_id, binding = resolved
        if not bot._is_dm(interaction, binding):
            await interaction.response.send_message("This command is for the campaign DM.", ephemeral=True)
            return
        url = str(binding.get("dashboard_url") or "").strip()
        if url:
            await interaction.response.send_message(f"DM Dashboard: {url}", ephemeral=True)
        else:
            await interaction.response.send_message(
                "The DM Dashboard is currently local to the DM computer. Open DID Character Sheet → Campaign Manager → Open DM Dashboard.\n\n"
                "If you later host the dashboard remotely, add its URL in Campaigns → Discord Settings.",
                ephemeral=True,
            )


    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        # A final safety net so unexpected command failures are acknowledged
        # instead of surfacing Discord's "The application did not respond".
        original = getattr(error, "original", error)
        logging.exception("Unhandled Discord application command error", exc_info=original)
        await bot._send_ephemeral(
            interaction,
            friendly_runtime_error(original, "complete that Discord command"),
        )


async def run(app_dir: Path):
    config = normalize_config(load_config())
    token = str(config.get("bot_token") or "").strip()
    if not token:
        raise RuntimeError("Discord Bot Token is missing. Configure it from Campaigns → Discord Settings.")

    bot = DIDDiscordBot(app_dir)
    install_commands(bot)
    try:
        await bot.start(token, reconnect=True)
    finally:
        await bot.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()

    user_dir = default_user_data_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Starting DID Discord bot. Config: %s", config_path())
    asyncio.run(run(Path(args.app_dir)))


if __name__ == "__main__":
    main()
