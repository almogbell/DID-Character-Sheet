(() => {
  "use strict";

  const config = window.DID_PARTY_DASHBOARD_CONFIG || {};
  const supabaseFactory = window.supabase;
  const els = {
    connection: document.getElementById("connectionBadge"),
    claimPanel: document.getElementById("claimPanel"),
    claimCode: document.getElementById("claimCode"),
    claimBtn: document.getElementById("claimBtn"),
    claimError: document.getElementById("claimError"),
    content: document.getElementById("dashboardContent"),
    campaignSelect: document.getElementById("campaignSelect"),
    refresh: document.getElementById("refreshBtn"),
    campaignTitle: document.getElementById("campaignTitle"),
    partySummary: document.getElementById("partySummary"),
    partyGrid: document.getElementById("partyGrid"),
    dialog: document.getElementById("characterDialog"),
    dialogClose: document.getElementById("dialogClose"),
    dialogBody: document.getElementById("characterDialogBody"),
  };

  let client = null;
  let authSession = null;
  let campaigns = [];
  let currentCampaignId = "";
  let stateRows = [];
  let realtimeChannel = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
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
    return String(new URLSearchParams(raw).get("code") || "").trim();
  }

  function clearAccessCode() {
    history.replaceState(null, "", location.pathname + location.search);
  }

  async function ensureAnonymousSession() {
    const existing = await client.auth.getSession();
    if (existing.error) throw existing.error;
    if (existing.data && existing.data.session) {
      authSession = existing.data.session;
      return authSession;
    }
    const created = await client.auth.signInAnonymously({
      options: { data: { application: "did_party_dashboard" } },
    });
    if (created.error) throw created.error;
    authSession = created.data.session;
    return authSession;
  }

  async function claimPartyDashboard(code) {
    const normalized = String(code || "").trim().toUpperCase().replaceAll(" ", "");
    if (!normalized) return null;
    els.claimError.textContent = "Connecting…";
    const response = await client.rpc("did_claim_party_dashboard", {
      p_dashboard_code: normalized,
    });
    if (response.error) throw response.error;
    const rows = Array.isArray(response.data) ? response.data : [];
    if (!rows.length) throw new Error("That Party Dashboard code is invalid or has expired.");
    clearAccessCode();
    return rows[0];
  }

  async function loadCampaigns(preferredId = "") {
    const userId = authSession && authSession.user ? authSession.user.id : "";
    if (!userId) return;
    const memberships = await client
      .from("campaign_members")
      .select("campaign_id")
      .eq("user_id", userId);
    if (memberships.error) throw memberships.error;
    const ids = [...new Set((memberships.data || []).map(row => row.campaign_id).filter(Boolean))];
    if (!ids.length) {
      campaigns = [];
      showClaim();
      return;
    }
    const response = await client
      .from("campaigns")
      .select("id,name,created_at,active")
      .in("id", ids)
      .eq("active", true)
      .order("created_at", { ascending: false });
    if (response.error) throw response.error;
    campaigns = response.data || [];
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
    for (const campaign of campaigns) {
      const option = document.createElement("option");
      option.value = String(campaign.id);
      option.textContent = campaign.name || "Unnamed Campaign";
      option.selected = option.value === currentCampaignId;
      els.campaignSelect.appendChild(option);
    }
  }

  function initials(name) {
    const words = String(name || "?").trim().split(/\s+/).filter(Boolean);
    if (!words.length) return "?";
    return words.slice(0, 2).map(word => word[0].toUpperCase()).join("");
  }

  function portraitSource(state) {
    const portrait = state && typeof state.portrait === "object" ? state.portrait : {};
    if (!portrait.shared || !portrait.data) return "";
    const raw = String(portrait.data || "").trim();
    if (!raw) return "";
    if (raw.startsWith("data:image/")) return raw;
    if (/^[A-Za-z0-9+/=\s]+$/.test(raw)) return `data:image/png;base64,${raw.replace(/\s+/g, "")}`;
    return "";
  }

  function avatarHtml(state, name) {
    const source = portraitSource(state);
    return source
      ? `<div class="avatar"><img src="${escapeHtml(source)}" alt=""></div>`
      : `<div class="avatar">${escapeHtml(initials(name))}</div>`;
  }

  function formatDie(value) {
    value = value || {};
    const die = Math.max(0, Number(value.die_size) || 0);
    const bonus = Number(value.bonus) || 0;
    return `${die ? `d${die}` : "—"}${bonus > 0 ? ` +${bonus}` : bonus < 0 ? ` ${bonus}` : ""}`;
  }

  function abilitiesHtml(state) {
    const sharing = state.sharing || {};
    if (!sharing.abilities) return "";
    const abilities = state.abilities && typeof state.abilities === "object" ? state.abilities : {};
    const order = ["agility", "strength", "finesse", "instinct", "presence", "knowledge"];
    return `<div class="abilities">${order.map(name => `
      <div class="ability ${name}">
        <div class="ability-name">${escapeHtml(name)}</div>
        <div class="ability-die">${escapeHtml(formatDie(abilities[name]))}</div>
      </div>`).join("")}</div>`;
  }

  function resourcesHtml(state) {
    const sharing = state.sharing || {};
    const parts = [];
    if (sharing.hp && state.hp) {
      parts.push(`<div class="resource-box hp"><div class="resource-label">HP</div><div class="resource-value">${Number(state.hp.current) || 0} / ${Number(state.hp.max) || 0}</div></div>`);
    }
    if (sharing.at && state.at) {
      parts.push(`<div class="resource-box at"><div class="resource-label">AT</div><div class="resource-value">${Number(state.at.current) || 0} / ${Number(state.at.max) || 0}</div></div>`);
    }
    return parts.length ? `<div class="resources">${parts.join("")}</div>` : "";
  }

  function sharingLabel(state) {
    const sharing = state.sharing || {};
    const labels = [];
    for (const [key, label] of Object.entries({ hp:"HP", at:"AT", abilities:"Abilities", improvements:"Improvements", portrait:"Portrait", inventory:"Inventory", notes:"Notes" })) {
      if (sharing[key]) labels.push(label);
    }
    return labels.length ? labels.join(" • ") : "Name only";
  }

  function detailSections(state) {
    const sharing = state.sharing || {};
    const sections = [];
    if (sharing.improvements) {
      const items = Array.isArray(state.improvements) ? state.improvements : [];
      const body = items.length
        ? `<ul class="improvement-list">${items.map(item => `<li>${escapeHtml(item.name || item.catalog_id || "Improvement")}${Number(item.times_taken) > 1 ? ` ×${Number(item.times_taken)}` : ""}</li>`).join("")}</ul>`
        : '<div class="summary-text">No shared Improvements.</div>';
      sections.push(`<section class="detail-section"><h3>Improvements</h3>${body}</section>`);
    }
    if (sharing.inventory) {
      const items = Array.isArray(state.inventory) ? state.inventory : [];
      const body = items.length
        ? `<ul class="shared-list">${items.map(item => `<li><b>${escapeHtml(item.name || "Item")}${Number(item.quantity) !== 1 ? ` ×${Number(item.quantity) || 0}` : ""}</b>${item.description ? `<div>${escapeHtml(item.description)}</div>` : ""}</li>`).join("")}</ul>`
        : '<div class="summary-text">No inventory items shared.</div>';
      sections.push(`<section class="detail-section"><h3>Shared Inventory</h3>${body}</section>`);
    }
    if (sharing.notes) {
      const notes = Array.isArray(state.notes) ? state.notes : [];
      const body = notes.length
        ? notes.map(note => `<article class="shared-note"><h4>${escapeHtml(note.title || "Untitled note")}</h4><div class="note-rich-text">${sanitizeRichNoteHtml(note.text || "")}</div></article>`).join("")
        : '<div class="summary-text">No notes shared.</div>';
      sections.push(`<section class="detail-section"><h3>Shared Notes</h3>${body}</section>`);
    }
    return sections.join("");
  }

  function renderParty() {
    els.partySummary.textContent = `${stateRows.length} shared character${stateRows.length === 1 ? "" : "s"}`;
    if (!stateRows.length) {
      els.partyGrid.innerHTML = '<div class="empty-state">No characters are sharing anything with the party yet.</div>';
      return;
    }
    els.partyGrid.innerHTML = stateRows.map(row => {
      const state = row.state || {};
      const name = String(state.name || "Unnamed Character");
      const subtitle = [state.species || "", state.level ? `Level ${state.level}` : ""].filter(Boolean).join(" • ");
      return `<article class="character-card" data-char-id="${escapeHtml(row.campaign_character_id)}" tabindex="0">
        <div class="card-head">${avatarHtml(state, name)}<div class="card-title"><h3>${escapeHtml(name)}</h3><div class="card-subtitle">${escapeHtml(subtitle || "Character")}</div></div></div>
        ${resourcesHtml(state)}
        ${abilitiesHtml(state)}
        <div class="card-foot"><span>${escapeHtml(sharingLabel(state))}</span></div>
      </article>`;
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

  function openCharacter(characterId) {
    const row = stateRows.find(item => String(item.campaign_character_id) === String(characterId));
    if (!row) return;
    const state = row.state || {};
    const name = state.name || "Unnamed Character";
    els.dialogBody.innerHTML = `
      <div class="eyebrow">PARTY CHARACTER</div>
      <h2>${escapeHtml(name)}</h2>
      <div class="summary-text">${escapeHtml([state.species || "", state.level ? `Level ${state.level}` : ""].filter(Boolean).join(" • "))}</div>
      ${resourcesHtml(state)}
      ${abilitiesHtml(state)}
      ${detailSections(state)}
      <div class="sharing-footnote">Shared with party: ${escapeHtml(sharingLabel(state))}</div>`;
    els.dialog.showModal();
  }

  async function loadCurrentCampaign() {
    const campaign = campaigns.find(c => String(c.id) === currentCampaignId);
    if (!campaign) return;
    setConnection("Refreshing…", "neutral");
    els.campaignTitle.textContent = campaign.name || "Campaign";
    const response = await client
      .from("party_character_state")
      .select("campaign_character_id,campaign_id,state,updated_at")
      .eq("campaign_id", currentCampaignId)
      .order("updated_at", { ascending: false });
    if (response.error) throw response.error;
    stateRows = response.data || [];
    renderParty();
    subscribeRealtime();
    setConnection("Live", "live");
  }

  function subscribeRealtime() {
    if (realtimeChannel) {
      client.removeChannel(realtimeChannel);
      realtimeChannel = null;
    }
    if (!currentCampaignId) return;
    realtimeChannel = client
      .channel(`did-party-dashboard-${currentCampaignId}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "party_character_state", filter: `campaign_id=eq.${currentCampaignId}` }, async () => {
        try { await loadCurrentCampaign(); } catch (error) { console.error(error); }
      })
      .subscribe(status => {
        if (status === "SUBSCRIBED") setConnection("Live", "live");
        else if (["CHANNEL_ERROR", "TIMED_OUT", "CLOSED"].includes(status)) setConnection("Reconnecting…", "offline");
      });
  }

  async function boot() {
    if (!supabaseFactory || !config.supabaseUrl || !config.supabaseKey) {
      showClaim("Dashboard configuration is missing.");
      setConnection("Not configured", "offline");
      return;
    }
    client = supabaseFactory.createClient(config.supabaseUrl, config.supabaseKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    });
    try {
      await ensureAnonymousSession();
      const code = codeFromHash();
      let preferredId = "";
      if (code) {
        const claimed = await claimPartyDashboard(code);
        preferredId = String((claimed && claimed.id) || "");
      }
      await loadCampaigns(preferredId);
      if (!campaigns.length) showClaim();
    } catch (error) {
      console.error(error);
      showClaim(error.message || String(error));
      setConnection("Connection problem", "offline");
    }
  }

  els.claimBtn.addEventListener("click", async () => {
    try {
      const claimed = await claimPartyDashboard(els.claimCode.value);
      await loadCampaigns(String((claimed && claimed.id) || ""));
    } catch (error) {
      els.claimError.textContent = error.message || String(error);
    }
  });
  els.claimCode.addEventListener("keydown", event => { if (event.key === "Enter") els.claimBtn.click(); });
  els.campaignSelect.addEventListener("change", async () => {
    currentCampaignId = String(els.campaignSelect.value || "");
    try { await loadCurrentCampaign(); } catch (error) { console.error(error); setConnection("Connection problem", "offline"); }
  });
  els.refresh.addEventListener("click", async () => { try { await loadCurrentCampaign(); } catch (error) { console.error(error); } });
  els.dialogClose.addEventListener("click", () => els.dialog.close());
  els.dialog.addEventListener("click", event => { if (event.target === els.dialog) els.dialog.close(); });

  boot();
})();
