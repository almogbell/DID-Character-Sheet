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
    rollEyebrow: document.getElementById("rollEyebrow"),
    rollTitle: document.getElementById("rollTitle"),
    sessionTitle: document.getElementById("sessionTitle"),
    sessionStatus: document.getElementById("sessionStatus"),
    startSessionBtn: document.getElementById("startSessionBtn"),
    endSessionBtn: document.getElementById("endSessionBtn"),
    renameSessionBtn: document.getElementById("renameSessionBtn"),
    sessionRenameRow: document.getElementById("sessionRenameRow"),
    sessionNameInput: document.getElementById("sessionNameInput"),
    cancelSessionNameBtn: document.getElementById("cancelSessionNameBtn"),
    saveSessionNameBtn: document.getElementById("saveSessionNameBtn"),
    dialog: document.getElementById("characterDialog"),
    dialogClose: document.getElementById("dialogClose"),
    dialogBody: document.getElementById("characterDialogBody"),
  };

  let client = null;
  let currentAuthSession = null;
  let campaigns = [];
  let currentCampaignId = "";
  let campaignLoadSerial = 0;
  let displayedCampaignId = "";
  let characters = [];
  let statesByCharacter = new Map();
  let rolls = [];
  let activeSession = null;
  let effectsByCharacter = new Map();
  let realtimeChannel = null;
  let subscribedCampaignId = "";
  let realtimeLive = false;
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


  function sessionLabel(session) {
    if (!session) return "Session";
    const custom = String(session.session_name || "").trim();
    if (custom) return custom;
    const started = session.started_at ? new Date(session.started_at) : null;
    if (started && !Number.isNaN(started.getTime())) {
      return started.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    }
    return "Session";
  }

  function sanitizeRichNoteHtml(value) {
    const raw = String(value || "");
    if (!raw) return "";
    const doc = new DOMParser().parseFromString(`<div>${raw}</div>`, "text/html");
    const root = doc.body.firstElementChild;
    if (!root) return escapeHtml(raw);
    const allowed = new Set(["B", "STRONG", "I", "EM", "U", "BR", "P", "DIV", "UL", "OL", "LI", "SPAN"]);
    const walk = node => {
      for (const child of [...node.children]) {
        if (!allowed.has(child.tagName)) {
          child.replaceWith(...child.childNodes);
          continue;
        }
        [...child.attributes].forEach(attr => child.removeAttribute(attr.name));
        walk(child);
      }
    };
    walk(root);
    return root.innerHTML;
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
      currentAuthSession = existing.data.session;
      return currentAuthSession;
    }

    const created = await client.auth.signInAnonymously({
      options: { data: { application: "did_dm_dashboard" } },
    });
    if (created.error) throw created.error;
    currentAuthSession = created.data.session;
    return currentAuthSession;
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
    const userId = currentAuthSession && currentAuthSession.user
      ? currentAuthSession.user.id
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

  async function loadSessionState(campaignId) {
    const response = await client
      .from("campaign_sessions")
      .select("*")
      .eq("campaign_id", campaignId)
      .is("ended_at", null)
      .order("started_at", { ascending: false })
      .limit(1);
    if (response.error) throw response.error;
    const rows = response.data || [];
    return rows.length ? rows[0] : null;
  }

  function setLiveBoardVisible(visible) {
    for (const id of ["liveRollsSection"]) {
      const element = document.getElementById(id);
      if (element) element.classList.toggle("hidden", !visible);
    }
  }

  function renderSessionControls() {
    const live = Boolean(activeSession);
    setLiveBoardVisible(live);

    if (live) {
      const label = sessionLabel(activeSession);
      els.sessionTitle.innerHTML = `<span class="session-live-dot"></span>${escapeHtml(label)} is live`;
      els.sessionStatus.textContent = `Started ${formatDateTime(activeSession.started_at)} • only this session's shared rolls are shown.`;
      els.startSessionBtn.classList.add("hidden");
      els.endSessionBtn.classList.remove("hidden");
      els.renameSessionBtn.classList.remove("hidden");
      els.rollEyebrow.textContent = "LIVE SESSION";
      els.rollTitle.textContent = `${label} Rolls`;
    } else {
      els.sessionTitle.textContent = "No active session";
      els.sessionStatus.textContent = "Start a session when the party is ready. The party remains visible; session rolls appear while a session is running.";
      els.startSessionBtn.classList.remove("hidden");
      els.endSessionBtn.classList.add("hidden");
      els.renameSessionBtn.classList.add("hidden");
      els.sessionRenameRow.classList.add("hidden");
      els.rollCount.textContent = "";
      els.rollList.innerHTML = "";
    }
  }

  async function loadCurrentCampaign(quiet = false) {
    const campaignId = currentCampaignId;
    const serial = ++campaignLoadSerial;
    const campaign = campaigns.find(c => String(c.id) === campaignId);
    if (!campaign) return;

    if (!quiet) setConnection("Refreshing…", "neutral");
    // Clear the previous campaign immediately rather than showing its private
    // character data beneath the next campaign name during network loading.
    if (displayedCampaignId !== campaignId) {
      displayedCampaignId = campaignId;
      els.partyGrid.replaceChildren();
      els.rollList.replaceChildren();
      if (els.dialog.open) els.dialog.close();
    }
    els.campaignTitle.textContent = campaign.name || "Campaign";

    const characterResponse = await client
      .from("campaign_characters")
      .select("id,campaign_id,character_id,display_name,active,created_at,updated_at,last_seen_at,share_session_rolls")
      .eq("campaign_id", campaignId)
      .eq("active", true)
      .order("created_at", { ascending: true });
    if (characterResponse.error) throw characterResponse.error;

    const nextCharacters = characterResponse.data || [];
    const characterIds = nextCharacters.map(c => c.id).filter(Boolean);

    const effectResponse = await client
      .from("campaign_character_effects")
      .select("id,campaign_character_id,name,description,status,visible_to_player,updated_at")
      .eq("campaign_id", campaignId)
      .eq("status", "active")
      .order("updated_at", { ascending: false });
    if (effectResponse.error) throw effectResponse.error;
    const effectRows = effectResponse.data || [];


    const nextSession = await loadSessionState(campaignId);

    let stateRows = [];
    let rollRows = [];
    if (characterIds.length) {
      const stateResponse = await client
        .from("character_state")
        .select("campaign_character_id,state,updated_at")
        .in("campaign_character_id", characterIds);
      if (stateResponse.error) throw stateResponse.error;
      stateRows = stateResponse.data || [];

      if (nextSession) {
        const rollResponse = await client
          .from("campaign_rolls")
          .select("event_id,campaign_character_id,rolled_at,event,session_id")
          .in("campaign_character_id", characterIds)
          .eq("session_id", nextSession.id)
          .order("rolled_at", { ascending: false })
          .limit(150);
        if (rollResponse.error) throw rollResponse.error;
        rollRows = rollResponse.data || [];
      }
    }

    // Switching campaigns (or overlapping refreshes) invalidates this result.
    // Never commit a stale response after the selection has changed.
    if (serial !== campaignLoadSerial || campaignId !== currentCampaignId) return;
    characters = nextCharacters;
    activeSession = nextSession;
    renderSessionControls();
    statesByCharacter = new Map(
      stateRows.map(row => [String(row.campaign_character_id), row])
    );
    effectsByCharacter = new Map();
    for (const effect of effectRows) {
      const key = String(effect.campaign_character_id || "");
      if (!effectsByCharacter.has(key)) effectsByCharacter.set(key, []);
      effectsByCharacter.get(key).push(effect);
    }
    rolls = activeSession ? rollRows : [];

    renderParty();
    renderRolls();
    subscribeRealtime();
    setConnection(realtimeLive ? "Live" : "Updated — awaiting live connection", realtimeLive ? "live" : "neutral");
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
    // A state update refreshes the display; it must NOT recreate the subscription.
    // Only switching campaigns warrants unsubscribing and subscribing again.
    if (realtimeChannel && subscribedCampaignId === currentCampaignId) return;
    if (realtimeChannel) {
      client.removeChannel(realtimeChannel);
      realtimeChannel = null;
    }
    subscribedCampaignId = "";
    realtimeLive = false;
    if (!currentCampaignId) return;
    subscribedCampaignId = currentCampaignId;
    const subscriptionCampaignId = currentCampaignId;

    realtimeChannel = client
      .channel(`did-dm-dashboard-${currentCampaignId}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_characters" }, scheduleRefresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "character_state" }, scheduleRefresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_rolls" }, scheduleRefresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_sessions" }, scheduleRefresh)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_character_effects" }, scheduleRefresh)
      .subscribe(status => {
        if (subscriptionCampaignId !== currentCampaignId ||
            subscriptionCampaignId !== subscribedCampaignId) return;
        if (status === "SUBSCRIBED") { realtimeLive = true; setConnection("Live", "live"); }
        else if (["CHANNEL_ERROR", "TIMED_OUT", "CLOSED"].includes(status)) {
          realtimeLive = false;
          setConnection("Reconnecting…", "offline");
        }
      });
  }

  function abilityEntries(state) {
    const raw = state && typeof state.abilities === "object" ? state.abilities : {};
    const order = ["agility", "strength", "finesse", "instinct", "presence", "knowledge"];
    return order.map(name => {
      const value = raw[name] || {};
      return { name, die: Math.max(0, Number(value.die_size) || 0), bonus: Number(value.bonus) || 0 };
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
    const maxHp = maxHearts * 4;
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
      maxHp,
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

  function portraitSource(state) {
    const portrait = state && state.portrait && typeof state.portrait === "object"
      ? state.portrait
      : {};
    if (!portrait.shared || !portrait.data) return "";
    const raw = String(portrait.data || "").trim();
    if (!raw) return "";
    if (raw.startsWith("data:image/")) return raw;
    if (/^[A-Za-z0-9+/=\s]+$/.test(raw)) {
      return `data:image/png;base64,${raw.replace(/\s+/g, "")}`;
    }
    return "";
  }

  function renderAvatar(state, name) {
    const source = portraitSource(state);
    if (!source) {
      return `<div class="avatar">${escapeHtml(initials(name))}</div>`;
    }
    return `<div class="avatar portrait-avatar"><img src="${escapeHtml(source)}" alt=""></div>`;
  }

  function sharedExtrasHtml(state) {
    state = state || {};
    const sharing = state.sharing && typeof state.sharing === "object" ? state.sharing : {};
    const sections = [];

    if (sharing.inventory === true) {
      const items = Array.isArray(state.inventory) ? state.inventory : [];
      const body = items.length
        ? `<ul class="shared-list">${items.map(item => {
            const quantity = Number(item.quantity) || 0;
            const qty = quantity !== 1 ? ` ×${quantity}` : "";
            const description = String(item.description || "").trim();
            return `<li><b>${escapeHtml(item.name || "Item")}${escapeHtml(qty)}</b>${description ? `<div>${escapeHtml(description)}</div>` : ""}</li>`;
          }).join("")}</ul>`
        : '<div class="shared-empty">No inventory items selected for sharing.</div>';
      sections.push(`<section class="shared-section"><h3>Shared Inventory</h3>${body}</section>`);
    }

    if (sharing.notes === true) {
      const notes = Array.isArray(state.notes) ? state.notes : [];
      const body = notes.length
        ? `<div class="shared-notes">${notes.map(note => `
            <article class="shared-note">
              <h4>${escapeHtml(note.title || "Untitled note")}</h4>
              <div class="note-rich-text">${sanitizeRichNoteHtml(note.text || "")}</div>
            </article>`).join("")}</div>`
        : '<div class="shared-empty">No notes selected for sharing.</div>';
      sections.push(`<section class="shared-section"><h3>Shared Notes</h3>${body}</section>`);
    }

    if (!state.sharing) return sections.join("");
    const labels = ["Core"];
    if (sharing.improvements) labels.push("Improvements");
    if (sharing.portrait) labels.push("Portrait");
    if (sharing.inventory) labels.push("Inventory");
    if (sharing.notes) labels.push("Notes");
    sections.push(`<div class="sharing-footnote">Player sharing: ${escapeHtml(labels.join(" • "))}</div>`);
    return sections.join("");
  }

  function percent(value, max) {
    if (!max) return 0;
    return Math.max(0, Math.min(100, (Number(value) / Number(max)) * 100));
  }

  function renderParty() {
    const onlineCount = characters.filter(c => presenceInfo(c).online).length;
    const privateRollCount = activeSession
      ? characters.filter(c => c.share_session_rolls === false).length
      : 0;
    const privacyText = activeSession && privateRollCount
      ? ` • ${privateRollCount} roll-private`
      : "";
    els.partySummary.textContent = `${characters.length} character${characters.length === 1 ? "" : "s"} • ${onlineCount} online${privacyText}`;

    if (!characters.length) {
      els.partyGrid.innerHTML = '<div class="empty-state">No shared characters yet. When a player shares a character, it will appear here.</div>';
      return;
    }

    els.partyGrid.innerHTML = characters.map(character => {
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
        <div class="ability ${escapeHtml(ability.name)}">
          <div class="ability-name">${escapeHtml(ability.name)}</div>
          <div class="ability-die">${escapeHtml(formatDie(ability))}</div>
        </div>
      `).join("");

      const heartMaxHp = metrics.maxHearts * 4;
      const subtitle = [species, `Level ${level}`].filter(Boolean).join(" • ");
      const portraitNote = state.portrait && state.portrait.shared && state.portrait.available ? " • portrait shared" : "";
      const privacy = activeSession
        ? character.share_session_rolls === false
          ? '<span class="roll-privacy private">rolls private</span>'
          : '<span class="roll-privacy">rolls shared</span>'
        : "";
      const activeEffects = effectsByCharacter.get(String(character.id)) || [];
      const effectsHtml = activeEffects.length
        ? `<div class="active-effects">${activeEffects.map(effect =>
            `<span class="effect-chip ${effect.visible_to_player ? "player-visible" : ""}" title="${escapeHtml(effect.description || "")}">${escapeHtml(effect.name || "Effect")}</span>`
          ).join("")}</div>`
        : "";

      return `
        <article class="character-card ${changed ? "changed" : ""}" data-char-id="${escapeHtml(character.id)}" tabindex="0">
          <div class="card-head">
            ${renderAvatar(state, name)}
            <div class="card-title">
              <h3>${escapeHtml(name)}</h3>
              <div class="card-subtitle">${escapeHtml(subtitle || "Character")}${escapeHtml(portraitNote)} ${privacy}</div>
            </div>
            <span class="presence ${presence.online ? "online" : "offline"}">${escapeHtml(presence.text)}</span>
          </div>

          <div class="resources">
            <div class="resource-box">
              <div class="resource-label">HP</div>
              <div class="resource-value">${metrics.currentHp} / ${metrics.maxHp}</div>
              <div class="bar"><span style="width:${percent(metrics.currentHp, metrics.maxHp)}%"></span></div>
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
          ${effectsHtml}
          <div class="card-foot">
            <span>IP ${metrics.ipRemaining} remaining</span>
            <span class="click-hint">Open details</span>
          </div>
        </article>
      `;
    }).join("");

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

  function formatDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  }

  function renderRolls() {
    if (!activeSession) {
      els.rollCount.textContent = "";
      els.rollList.innerHTML = "";
      return;
    }
    els.rollCount.textContent = `${rolls.length} shown`;
    if (!rolls.length) {
      els.rollList.innerHTML = '<div class="empty-state">No shared rolls in this session yet.</div>';
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
    const sharing = state.sharing && typeof state.sharing === "object" ? state.sharing : null;
    const improvementsShared = sharing ? sharing.improvements === true : true;

    const improvementsHtml = !improvementsShared
      ? '<p class="shared-empty">Not shared by this player.</p>'
      : improvements.length
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
        <div class="detail-block"><div class="resource-label">HP</div><div class="resource-value">${metrics.currentHp} / ${metrics.maxHp}</div></div>
        <div class="detail-block"><div class="resource-label">AT</div><div class="resource-value">${metrics.currentAT} / ${metrics.maxAT}</div></div>
        <div class="detail-block"><div class="resource-label">BDV</div><div class="resource-value">${metrics.bdv}</div></div>
        <div class="detail-block"><div class="resource-label">DR</div><div class="resource-value">${metrics.dr}</div><div class="card-subtitle">${escapeHtml(metrics.defenseKey)}</div></div>
        <div class="detail-block"><div class="resource-label">IP Remaining</div><div class="resource-value">${metrics.ipRemaining} / ${metrics.ipTotal}</div></div>
      </div>
      <h3>Abilities</h3>
      <div class="abilities">${metrics.abilities.map(a => `<div class="ability ${escapeHtml(a.name)}"><div class="ability-name">${escapeHtml(a.name)}</div><div class="ability-die">${escapeHtml(formatDie(a))}</div></div>`).join("")}</div>
      <h3 style="margin-top:18px">Improvements</h3>
      ${improvementsHtml}
      ${sharedExtrasHtml(state)}
    `;

    els.dialog.showModal();
  }

  async function startSession() {
    if (!currentCampaignId || activeSession) return;
    els.startSessionBtn.disabled = true;
    try {
      const response = await client.rpc("did_start_session", { p_campaign_id: currentCampaignId });
      if (response.error) throw response.error;
      const rows = Array.isArray(response.data) ? response.data : [];
      if (!rows.length) throw new Error("The session could not be started.");
      await loadCurrentCampaign();
    } catch (error) {
      console.error(error);
      alert(error.message || String(error));
    } finally {
      els.startSessionBtn.disabled = false;
    }
  }

  async function endSession() {
    if (!currentCampaignId || !activeSession) return;
    const label = sessionLabel(activeSession);
    if (!confirm(`End "${label}"?\n\nThis ends the live dashboard for this session. The next session will start with an empty roll feed.`)) {
      return;
    }

    els.endSessionBtn.disabled = true;
    try {
      const response = await client.rpc("did_end_session", { p_campaign_id: currentCampaignId });
      if (response.error) throw response.error;
      const rows = Array.isArray(response.data) ? response.data : [];
      if (!rows.length) throw new Error("The session could not be ended.");
      rolls = [];
      await loadCurrentCampaign();
    } catch (error) {
      console.error(error);
      alert(error.message || String(error));
    } finally {
      els.endSessionBtn.disabled = false;
    }
  }


  function openSessionRename() {
    if (!activeSession) return;
    els.sessionNameInput.value = String(activeSession.session_name || sessionLabel(activeSession));
    els.sessionRenameRow.classList.remove("hidden");
    els.sessionNameInput.focus();
    els.sessionNameInput.select();
  }

  function cancelSessionRename() {
    els.sessionRenameRow.classList.add("hidden");
  }

  async function saveSessionRename() {
    if (!activeSession) return;
    const value = String(els.sessionNameInput.value || "").trim();
    els.saveSessionNameBtn.disabled = true;
    try {
      const response = await client.rpc("did_rename_session", {
        p_session_id: activeSession.id,
        p_session_name: value || null,
      });
      if (response.error) throw response.error;
      els.sessionRenameRow.classList.add("hidden");
      await loadCurrentCampaign();
    } catch (error) {
      console.error(error);
      alert(error.message || String(error));
    } finally {
      els.saveSessionNameBtn.disabled = false;
    }
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
    try { await loadDMCampaigns(currentCampaignId); }
    catch (error) { console.error(error); setConnection("Connection problem", "offline"); }
  });

  els.campaignSelect.addEventListener("change", async () => {
    currentCampaignId = String(els.campaignSelect.value || "");
    if (!currentCampaignId) return;
    try { await loadCurrentCampaign(); }
    catch (error) { console.error(error); setConnection("Connection problem", "offline"); }
  });

  els.startSessionBtn.addEventListener("click", startSession);
  els.endSessionBtn.addEventListener("click", endSession);
  els.renameSessionBtn.addEventListener("click", openSessionRename);
  els.cancelSessionNameBtn.addEventListener("click", cancelSessionRename);
  els.saveSessionNameBtn.addEventListener("click", saveSessionRename);
  els.sessionNameInput.addEventListener("keydown", event => {
    if (event.key === "Enter") saveSessionRename();
    if (event.key === "Escape") cancelSessionRename();
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
    if (!els.content.classList.contains("hidden") && activeSession) renderParty();
  }, 10000);

  // DID114_SHARING_AUTO_REFRESH_V1: quiet 20-second fallback to live changes.
  let did114RefreshBusy = false;
  setInterval(async () => {
    if (did114RefreshBusy || document.hidden || !client || !currentCampaignId
        || els.content.classList.contains("hidden")
        || (els.dialog && els.dialog.open)
        || (els.sessionRenameRow && !els.sessionRenameRow.classList.contains("hidden"))) return;
    did114RefreshBusy = true;
    try { await loadCurrentCampaign(true); }
    catch (error) { console.error("Automatic refresh:", error); }
    finally { did114RefreshBusy = false; }
  }, 20000);

  boot();
})();
