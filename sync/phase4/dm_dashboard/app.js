(() => {
  "use strict";

  const config = window.DID_DASHBOARD_CONFIG || {};
  const supabaseFactory = window.supabase;

  const els = {
    connection: document.getElementById("connectionBadge"),
    campaignSelect: document.getElementById("campaignSelect"),
    refresh: document.getElementById("refreshBtn"),
    claimPanel: document.getElementById("claimPanel"),
    claimCode: document.getElementById("claimCode"),
    claimBtn: document.getElementById("claimBtn"),
    claimError: document.getElementById("claimError"),
    content: document.getElementById("dashboardContent"),
    campaignTitle: document.getElementById("campaignTitle"),
    partySummary: document.getElementById("partySummary"),
    partyGrid: document.getElementById("partyGrid"),
    rollList: document.getElementById("rollList"),
    rollCount: document.getElementById("rollCount"),
    dialog: document.getElementById("characterDialog"),
    dialogClose: document.getElementById("dialogClose"),
    dialogBody: document.getElementById("characterDialogBody"),
  };

  let client = null;
  let currentSession = null;
  let campaigns = [];
  let currentCampaignId = "";
  let characters = [];
  let statesByCharacter = new Map();
  let rolls = [];
  let realtimeChannel = null;
  let refreshTimer = null;
  const previousStateTimes = new Map();

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setConnection(text, mode = "neutral") {
    els.connection.textContent = text;
    els.connection.className = `status-badge ${mode}`;
  }

  function showClaim(message = "") {
    els.claimPanel.classList.remove("hidden");
    els.content.classList.add("hidden");
    els.claimError.textContent = message;
  }

  function showDashboard() {
    els.claimPanel.classList.add("hidden");
    els.content.classList.remove("hidden");
    els.claimError.textContent = "";
  }

  function codeFromHash() {
    const raw = String(location.hash || "").replace(/^#/, "");
    const params = new URLSearchParams(raw);
    return String(params.get("code") || "").trim();
  }

  function clearAccessCodeFromAddressBar() {
    history.replaceState(null, "", location.pathname + location.search);
  }

  async function ensureAnonymousSession() {
    const existing = await client.auth.getSession();
    if (existing.error) throw existing.error;
    if (existing.data && existing.data.session) {
      currentSession = existing.data.session;
      return currentSession;
    }

    const created = await client.auth.signInAnonymously({
      options: { data: { application: "did_dm_dashboard" } },
    });
    if (created.error) throw created.error;
    currentSession = created.data.session;
    return currentSession;
  }

  async function claimDashboard(code) {
    code = String(code || "").trim().toUpperCase().replaceAll(" ", "");
    if (!code) return null;

    els.claimError.textContent = "Connecting…";
    const response = await client.rpc("did_claim_dashboard", {
      p_dashboard_code: code,
    });
    if (response.error) throw response.error;

    const rows = Array.isArray(response.data) ? response.data : [];
    if (!rows.length) {
      throw new Error("That dashboard code is invalid or has expired.");
    }

    clearAccessCodeFromAddressBar();
    return rows[0];
  }

  async function loadDMCampaigns(preferredId = "") {
    const userId = currentSession && currentSession.user
      ? currentSession.user.id
      : "";
    if (!userId) {
      campaigns = [];
      return;
    }

    const memberships = await client
      .from("campaign_members")
      .select("campaign_id,role")
      .eq("user_id", userId)
      .eq("role", "dm");
    if (memberships.error) throw memberships.error;

    const ids = [...new Set((memberships.data || []).map(row => row.campaign_id).filter(Boolean))];
    if (!ids.length) {
      campaigns = [];
      currentCampaignId = "";
      renderCampaignSelector();
      showClaim();
      return;
    }

    const campaignResponse = await client
      .from("campaigns")
      .select("id,name,created_at,active")
      .in("id", ids)
      .eq("active", true)
      .order("created_at", { ascending: false });
    if (campaignResponse.error) throw campaignResponse.error;

    campaigns = campaignResponse.data || [];
    const requested = String(preferredId || currentCampaignId || "");
    currentCampaignId = campaigns.some(c => String(c.id) === requested)
      ? requested
      : String(campaigns[0].id);

    renderCampaignSelector();
    showDashboard();
    await loadCurrentCampaign();
  }

  function renderCampaignSelector() {
    els.campaignSelect.innerHTML = "";
    if (!campaigns.length) {
      const option = document.createElement("option");
      option.textContent = "No DM campaigns";
      option.value = "";
      els.campaignSelect.appendChild(option);
      els.campaignSelect.disabled = true;
      return;
    }

    els.campaignSelect.disabled = false;
    for (const campaign of campaigns) {
      const option = document.createElement("option");
      option.value = String(campaign.id);
      option.textContent = campaign.name || "Unnamed Campaign";
      option.selected = option.value === currentCampaignId;
      els.campaignSelect.appendChild(option);
    }
  }

  async function loadCurrentCampaign() {
    const campaign = campaigns.find(c => String(c.id) === currentCampaignId);
    if (!campaign) return;

    setConnection("Refreshing…", "neutral");
    els.campaignTitle.textContent = campaign.name || "Campaign";

    const characterResponse = await client
      .from("campaign_characters")
      .select("id,campaign_id,character_id,display_name,active,created_at,updated_at,last_seen_at")
      .eq("campaign_id", currentCampaignId)
      .eq("active", true)
      .order("created_at", { ascending: true });
    if (characterResponse.error) throw characterResponse.error;

    characters = characterResponse.data || [];
    const characterIds = characters.map(c => c.id).filter(Boolean);

    let stateRows = [];
    let rollRows = [];
    if (characterIds.length) {
      const [stateResponse, rollResponse] = await Promise.all([
        client
          .from("character_state")
          .select("campaign_character_id,state,updated_at")
          .in("campaign_character_id", characterIds),
        client
          .from("campaign_rolls")
          .select("event_id,campaign_character_id,rolled_at,event")
          .in("campaign_character_id", characterIds)
          .order("rolled_at", { ascending: false })
          .limit(100),
      ]);
      if (stateResponse.error) throw stateResponse.error;
      if (rollResponse.error) throw rollResponse.error;
      stateRows = stateResponse.data || [];
      rollRows = rollResponse.data || [];
    }

    statesByCharacter = new Map(
      stateRows.map(row => [String(row.campaign_character_id), row])
    );
    rolls = rollRows;

    renderParty();
    renderRolls();
    subscribeRealtime();
    setConnection("Live", "live");
  }

  function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      refreshTimer = null;
      try {
        await loadCurrentCampaign();
      } catch (error) {
        console.error(error);
        setConnection("Connection problem", "offline");
      }
    }, 180);
  }

  function subscribeRealtime() {
    if (realtimeChannel) {
      client.removeChannel(realtimeChannel);
      realtimeChannel = null;
    }
    if (!currentCampaignId) return;

    realtimeChannel = client
      .channel(`did-dm-dashboard-${currentCampaignId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "campaign_characters" },
        scheduleRefresh,
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "character_state" },
        scheduleRefresh,
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "campaign_rolls" },
        scheduleRefresh,
      )
      .subscribe(status => {
        if (status === "SUBSCRIBED") setConnection("Live", "live");
        else if (["CHANNEL_ERROR", "TIMED_OUT", "CLOSED"].includes(status)) {
          setConnection("Reconnecting…", "offline");
        }
      });
  }

  function abilityEntries(state) {
    const raw = state && typeof state.abilities === "object" ? state.abilities : {};
    const order = ["agility", "strength", "finesse", "instinct", "presence", "knowledge"];
    return order.map(name => {
      const value = raw[name] || {};
      return {
        name,
        die: Math.max(0, Number(value.die_size) || 0),
        bonus: Number(value.bonus) || 0,
      };
    });
  }

  function formatDie(ability) {
    const bonus = ability.bonus > 0 ? ` +${ability.bonus}` : ability.bonus < 0 ? ` ${ability.bonus}` : "";
    return `${ability.die ? `d${ability.die}` : "—"}${bonus}`;
  }

  function formatQuarterHearts(currentHp) {
    const hp = Math.max(0, Number(currentHp) || 0);
    const whole = Math.floor(hp / 4);
    const rem = hp % 4;
    const fraction = ["", "¼", "½", "¾"][rem];
    return `${whole}${fraction}`;
  }

  function stateMetrics(state) {
    state = state || {};
    const resources = state.resources || {};
    const hearts = resources.hearts || {};
    const at = resources.adversity_tokens || {};
    const ip = resources.improvement_points || {};

    const currentHp = Math.max(0, Number(hearts.current) || 0);
    const maxHearts = Math.max(0, Number(hearts.max) || 0);
    const currentAT = Math.max(0, Number(at.current) || 0);
    const maxAT = Math.max(0, Number(at.max) || 0);
    const abilities = abilityEntries(state);

    let defenseKey = String(state.defense_ability || "").toLowerCase();
    let defense = abilities.find(a => a.name === defenseKey);
    if (!defense) {
      defense = [...abilities].sort((a, b) => (b.die - a.die) || (b.bonus - a.bonus))[0];
      defenseKey = defense ? defense.name : "";
    }

    return {
      currentHp,
      maxHearts,
      currentAT,
      maxAT,
      bdv: Math.floor(maxAT / 2),
      dr: defense ? Math.floor(defense.die / 2) + defense.bonus : 0,
      defenseKey,
      ipRemaining: Math.max(0, Number(ip.remaining) || 0),
      ipTotal: Math.max(0, Number(ip.total) || 0),
      abilities,
    };
  }

  function presenceInfo(character) {
    const timestamp = character.last_seen_at ? Date.parse(character.last_seen_at) : NaN;
    if (!Number.isFinite(timestamp)) return { online: false, text: "Offline" };
    const seconds = Math.max(0, (Date.now() - timestamp) / 1000);
    if (seconds <= 40) return { online: true, text: "Online" };
    if (seconds < 120) return { online: false, text: "Just seen" };
    if (seconds < 3600) return { online: false, text: `${Math.floor(seconds / 60)}m ago` };
    return { online: false, text: "Offline" };
  }

  function initials(name) {
    const words = String(name || "?").trim().split(/\s+/).filter(Boolean);
    if (!words.length) return "?";
    return words.slice(0, 2).map(word => word[0].toUpperCase()).join("");
  }

  function percent(value, max) {
    if (!max) return 0;
    return Math.max(0, Math.min(100, (Number(value) / Number(max)) * 100));
  }

  function renderParty() {
    const onlineCount = characters.filter(c => presenceInfo(c).online).length;
    els.partySummary.textContent = `${characters.length} character${characters.length === 1 ? "" : "s"} • ${onlineCount} online`;

    if (!characters.length) {
      els.partyGrid.innerHTML = '<div class="empty-state">No shared characters yet. When a player shares a character, it will appear here.</div>';
      return;
    }

    const html = characters.map(character => {
      const stateRow = statesByCharacter.get(String(character.id));
      const state = stateRow && stateRow.state ? stateRow.state : {};
      const metrics = stateMetrics(state);
      const name = String(state.name || character.display_name || "Unnamed Character");
      const species = String(state.species || "");
      const level = Math.max(1, Number(state.level) || 1);
      const presence = presenceInfo(character);
      const stateTime = String((stateRow && stateRow.updated_at) || "");
      const previous = previousStateTimes.get(String(character.id));
      const changed = Boolean(previous && stateTime && previous !== stateTime);
      previousStateTimes.set(String(character.id), stateTime);

      const abilityHtml = metrics.abilities.map(ability => `
        <div class="ability">
          <div class="ability-name">${escapeHtml(ability.name)}</div>
          <div class="ability-die">${escapeHtml(formatDie(ability))}</div>
        </div>
      `).join("");

      const heartMaxHp = metrics.maxHearts * 4;
      const subtitle = [species, `Level ${level}`].filter(Boolean).join(" • ");
      const portraitNote = state.portrait && state.portrait.available ? " • portrait on sheet" : "";

      return `
        <article class="character-card ${changed ? "changed" : ""}" data-char-id="${escapeHtml(character.id)}" tabindex="0">
          <div class="card-head">
            <div class="avatar">${escapeHtml(initials(name))}</div>
            <div class="card-title">
              <h3>${escapeHtml(name)}</h3>
              <div class="card-subtitle">${escapeHtml(subtitle || "Character")}${escapeHtml(portraitNote)}</div>
            </div>
            <span class="presence ${presence.online ? "online" : "offline"}">${escapeHtml(presence.text)}</span>
          </div>

          <div class="resources">
            <div class="resource-box">
              <div class="resource-label">Hearts</div>
              <div class="resource-value">♥ ${escapeHtml(formatQuarterHearts(metrics.currentHp))} / ${metrics.maxHearts}</div>
              <div class="bar"><span style="width:${percent(metrics.currentHp, heartMaxHp)}%"></span></div>
            </div>
            <div class="resource-box">
              <div class="resource-label">AT</div>
              <div class="resource-value">${metrics.currentAT} / ${metrics.maxAT}</div>
              <div class="bar"><span style="width:${percent(metrics.currentAT, metrics.maxAT)}%"></span></div>
            </div>
            <div class="resource-box">
              <div class="resource-label">BDV / DR</div>
              <div class="resource-value">${metrics.bdv} / ${metrics.dr}</div>
              <div class="card-subtitle">${escapeHtml(metrics.defenseKey || "auto defense")}</div>
            </div>
          </div>

          <div class="abilities">${abilityHtml}</div>
          <div class="card-foot">
            <span>IP ${metrics.ipRemaining} remaining</span>
            <span class="click-hint">Open details</span>
          </div>
        </article>
      `;
    }).join("");

    els.partyGrid.innerHTML = html;
    els.partyGrid.querySelectorAll(".character-card").forEach(card => {
      const open = () => openCharacter(card.dataset.charId);
      card.addEventListener("click", open);
      card.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    });
  }

  function formatRollDice(event) {
    if (event && event.roll_type === "other_dice" && Array.isArray(event.groups)) {
      return event.groups
        .map(group => `d${Number(group.sides) || "?"}: ${(group.values || []).join(", ")}`)
        .join("  •  ");
    }

    const terms = Array.isArray(event && event.dice) ? event.dice : [];
    const text = terms.map(term => {
      const sign = Number(term.sign) < 0 ? "−" : "+";
      const values = Array.isArray(term.values) ? term.values : [];
      const chain = values.join("→");
      return `${sign} d${term.sides} [${chain}]`;
    }).join(" ").replace(/^\+\s*/, "");

    const flat = Number(event && event.flat_bonus) || 0;
    if (!flat) return text || "Roll";
    return `${text} ${flat > 0 ? "+" : "−"} ${Math.abs(flat)}`;
  }

  function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function renderRolls() {
    els.rollCount.textContent = `${rolls.length} shown`;
    if (!rolls.length) {
      els.rollList.innerHTML = '<div class="empty-state">No campaign rolls yet.</div>';
      return;
    }

    const charMap = new Map(characters.map(c => [String(c.id), c]));
    els.rollList.innerHTML = rolls.map(row => {
      const event = row.event || {};
      const character = charMap.get(String(row.campaign_character_id)) || {};
      const name = event.character_name || character.display_name || "Character";
      const ability = event.ability_name || (event.roll_type === "other_dice" ? "Other Dice" : "Roll");
      const deed = event.deed_success === true ? " • Deed ✓" : event.deed_success === false ? " • Deed ✕" : "";
      const hasTotal = event.total !== null && event.total !== undefined && event.roll_type !== "other_dice";

      return `
        <div class="roll-item">
          <div>
            <div class="roll-name">${escapeHtml(name)}</div>
            <div class="roll-meta">${escapeHtml(ability)} • ${escapeHtml(formatTime(row.rolled_at))}${escapeHtml(deed)}</div>
          </div>
          <div class="roll-detail">${escapeHtml(formatRollDice(event))}</div>
          <div class="roll-total ${hasTotal ? "" : "no-total"}">${hasTotal ? escapeHtml(event.total) : "individual"}</div>
        </div>
      `;
    }).join("");
  }

  function openCharacter(characterId) {
    const character = characters.find(c => String(c.id) === String(characterId));
    if (!character) return;
    const row = statesByCharacter.get(String(character.id));
    const state = row && row.state ? row.state : {};
    const metrics = stateMetrics(state);
    const name = state.name || character.display_name || "Unnamed Character";
    const improvements = Array.isArray(state.improvements) ? state.improvements : [];

    const improvementsHtml = improvements.length
      ? `<ul class="improvement-list">${improvements.map(item => {
          const times = Number(item.times_taken) > 1 ? ` ×${Number(item.times_taken)}` : "";
          return `<li>${escapeHtml(item.name || item.catalog_id || "Improvement")}${escapeHtml(times)}</li>`;
        }).join("")}</ul>`
      : "<p>No shared Improvements.</p>";

    els.dialogBody.innerHTML = `
      <div class="eyebrow">CHARACTER DETAILS</div>
      <h2>${escapeHtml(name)}</h2>
      <div class="summary-text">${escapeHtml(state.species || "")} ${state.level ? `• Level ${escapeHtml(state.level)}` : ""}</div>
      <div class="detail-grid">
        <div class="detail-block"><div class="resource-label">Hearts</div><div class="resource-value">${escapeHtml(formatQuarterHearts(metrics.currentHp))} / ${metrics.maxHearts}</div></div>
        <div class="detail-block"><div class="resource-label">AT</div><div class="resource-value">${metrics.currentAT} / ${metrics.maxAT}</div></div>
        <div class="detail-block"><div class="resource-label">BDV</div><div class="resource-value">${metrics.bdv}</div></div>
        <div class="detail-block"><div class="resource-label">DR</div><div class="resource-value">${metrics.dr}</div><div class="card-subtitle">${escapeHtml(metrics.defenseKey)}</div></div>
        <div class="detail-block"><div class="resource-label">IP Remaining</div><div class="resource-value">${metrics.ipRemaining} / ${metrics.ipTotal}</div></div>
      </div>
      <h3>Abilities</h3>
      <div class="abilities">${metrics.abilities.map(a => `<div class="ability"><div class="ability-name">${escapeHtml(a.name)}</div><div class="ability-die">${escapeHtml(formatDie(a))}</div></div>`).join("")}</div>
      <h3 style="margin-top:18px">Improvements</h3>
      ${improvementsHtml}
    `;

    els.dialog.showModal();
  }

  async function manualClaim() {
    try {
      const result = await claimDashboard(els.claimCode.value);
      if (result) {
        els.claimCode.value = "";
        await loadDMCampaigns(result.id);
      }
    } catch (error) {
      console.error(error);
      els.claimError.textContent = error.message || String(error);
    }
  }

  async function boot() {
    if (!config.supabaseUrl || !config.supabaseKey || !supabaseFactory) {
      showClaim("Dashboard configuration is missing. Open the dashboard from the DID desktop app again.");
      setConnection("Not configured", "offline");
      return;
    }

    client = supabaseFactory.createClient(config.supabaseUrl, config.supabaseKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: false,
        storageKey: "did-dm-dashboard-auth",
      },
    });

    try {
      setConnection("Signing in…", "neutral");
      await ensureAnonymousSession();

      const code = codeFromHash();
      let claimed = null;
      if (code) claimed = await claimDashboard(code);

      await loadDMCampaigns(claimed && claimed.id ? claimed.id : "");
      if (!campaigns.length) setConnection("Waiting for DM access", "neutral");
    } catch (error) {
      console.error(error);
      showClaim(error.message || String(error));
      setConnection("Connection problem", "offline");
    }
  }

  els.refresh.addEventListener("click", async () => {
    try {
      await loadDMCampaigns(currentCampaignId);
    } catch (error) {
      console.error(error);
      setConnection("Connection problem", "offline");
    }
  });

  els.campaignSelect.addEventListener("change", async () => {
    currentCampaignId = String(els.campaignSelect.value || "");
    if (!currentCampaignId) return;
    try {
      await loadCurrentCampaign();
    } catch (error) {
      console.error(error);
      setConnection("Connection problem", "offline");
    }
  });

  els.claimBtn.addEventListener("click", manualClaim);
  els.claimCode.addEventListener("keydown", event => {
    if (event.key === "Enter") manualClaim();
  });
  els.dialogClose.addEventListener("click", () => els.dialog.close());
  els.dialog.addEventListener("click", event => {
    if (event.target === els.dialog) els.dialog.close();
  });

  setInterval(() => {
    if (!els.content.classList.contains("hidden")) renderParty();
  }, 10000);

  boot();
})();
