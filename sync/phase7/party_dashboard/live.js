(() => {
  "use strict";

  const config = window.DID_PARTY_DASHBOARD_CONFIG || {};
  const supabaseFactory = window.supabase;
  const els = {
    campaignSelect: document.getElementById("campaignSelect"),
    refresh: document.getElementById("refreshBtn"),
    sessionBadge: document.getElementById("sessionBadge"),
    sessionText: document.getElementById("sessionText"),
    rollList: document.getElementById("recentRolls"),
    rollEmpty: document.getElementById("rollEmpty"),
  };

  if (!supabaseFactory || !config.supabaseUrl || !config.supabaseKey || !els.campaignSelect) {
    return;
  }

  const client = supabaseFactory.createClient(config.supabaseUrl, config.supabaseKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });

  let sessionChannel = null;
  let rollChannel = null;
  let subscribedCampaignId = "";
  let refreshSerial = 0;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function campaignId() {
    return String(els.campaignSelect.value || "").trim();
  }

  function setSession(active) {
    if (!els.sessionBadge || !els.sessionText) return;
    if (active) {
      els.sessionBadge.textContent = `Session ${Number(active.session_number) || ""} live`.trim();
      els.sessionBadge.className = "session-badge live";
      const started = active.started_at ? new Date(active.started_at) : null;
      els.sessionText.textContent = started && !Number.isNaN(started.getTime())
        ? `Live session started ${started.toLocaleString()}`
        : "Live session in progress";
    } else {
      els.sessionBadge.textContent = "No active session";
      els.sessionBadge.className = "session-badge idle";
      els.sessionText.textContent = "Recent rolls appear here only while a campaign session is active.";
    }
  }

  function dieGroups(event) {
    const groups = Array.isArray(event.groups) ? event.groups : [];
    if (groups.length) {
      return groups.map(group => {
        const sides = Number(group.sides) || 0;
        const values = Array.isArray(group.values) ? group.values.map(Number).filter(Number.isFinite) : [];
        return `${values.length || 1}d${sides}: ${values.join(", ") || "—"}`;
      }).join(" · ");
    }
    const dice = Array.isArray(event.dice) ? event.dice : [];
    return dice.map(term => {
      const sides = Number(term.sides) || 0;
      const values = Array.isArray(term.values) ? term.values.map(Number).filter(Number.isFinite) : [];
      return `d${sides}: ${values.join("+") || "—"}`;
    }).join(" · ");
  }

  function rollTitle(event) {
    const name = String(event.character_name || "Character");
    const ability = String(event.ability_name || "").trim();
    const type = String(event.roll_type || "ability");
    if (type === "other_dice") return `${name} · Other Dice`;
    return ability ? `${name} · ${ability}` : `${name} · Roll`;
  }

  function rollResult(event) {
    if (event.individual_only || event.total === null || event.total === undefined) {
      return dieGroups(event) || "Individual dice";
    }
    const total = Number(event.total);
    const detail = dieGroups(event);
    const deed = event.deed_success === true ? " · Deed success" : event.deed_success === false ? " · Deed failed" : "";
    return `${Number.isFinite(total) ? total : "—"}${detail ? `  (${detail})` : ""}${deed}`;
  }

  function renderRolls(rows) {
    if (!els.rollList || !els.rollEmpty) return;
    const clean = Array.isArray(rows) ? rows : [];
    els.rollEmpty.classList.toggle("hidden", clean.length > 0);
    els.rollList.innerHTML = clean.map(row => {
      const event = row && typeof row.event === "object" ? row.event : {};
      const when = row.rolled_at ? new Date(row.rolled_at) : null;
      const time = when && !Number.isNaN(when.getTime()) ? when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
      return `<article class="roll-item">
        <div class="roll-main">
          <div class="roll-title">${escapeHtml(rollTitle(event))}</div>
          <div class="roll-result">${escapeHtml(rollResult(event))}</div>
        </div>
        <time class="roll-time">${escapeHtml(time)}</time>
      </article>`;
    }).join("");
  }

  async function hasSession() {
    const result = await client.auth.getSession();
    return !result.error && !!(result.data && result.data.session);
  }

  async function fetchActiveSession(id) {
    const response = await client
      .from("campaign_sessions")
      .select("id,campaign_id,session_number,started_at,ended_at")
      .eq("campaign_id", id)
      .is("ended_at", null)
      .order("started_at", { ascending: false })
      .limit(1);
    if (response.error) throw response.error;
    return Array.isArray(response.data) && response.data.length ? response.data[0] : null;
  }

  async function fetchRolls(id, activeSession) {
    if (!activeSession) return [];
    const response = await client
      .from("party_session_rolls")
      .select("event_id,campaign_id,session_id,campaign_character_id,rolled_at,event")
      .eq("campaign_id", id)
      .eq("session_id", activeSession.id)
      .order("rolled_at", { ascending: false })
      .limit(24);
    if (response.error) throw response.error;
    return response.data || [];
  }

  async function refreshLive() {
    const serial = ++refreshSerial;
    const id = campaignId();
    if (!id || !(await hasSession())) {
      setSession(null);
      renderRolls([]);
      return;
    }
    try {
      const active = await fetchActiveSession(id);
      const rows = await fetchRolls(id, active);
      if (serial !== refreshSerial || id !== campaignId()) return;
      setSession(active);
      renderRolls(rows);
      subscribe(id);
    } catch (error) {
      console.error("Party live panel:", error);
      if (els.sessionText) els.sessionText.textContent = "Live session information could not be loaded.";
    }
  }

  function removeChannels() {
    if (sessionChannel) client.removeChannel(sessionChannel);
    if (rollChannel) client.removeChannel(rollChannel);
    sessionChannel = null;
    rollChannel = null;
    subscribedCampaignId = "";
  }

  function subscribe(id) {
    if (!id || subscribedCampaignId === id) return;
    removeChannels();
    subscribedCampaignId = id;
    sessionChannel = client
      .channel(`did-party-session-${id}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_sessions", filter: `campaign_id=eq.${id}` }, refreshLive)
      .subscribe();
    rollChannel = client
      .channel(`did-party-rolls-${id}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "party_session_rolls", filter: `campaign_id=eq.${id}` }, refreshLive)
      .subscribe();
  }

  els.campaignSelect.addEventListener("change", () => {
    removeChannels();
    setTimeout(refreshLive, 0);
  });
  if (els.refresh) els.refresh.addEventListener("click", () => setTimeout(refreshLive, 0));

  const observer = new MutationObserver(() => {
    if (campaignId()) refreshLive();
  });
  observer.observe(els.campaignSelect, { childList: true, subtree: true });

  window.addEventListener("beforeunload", removeChannels);
  setTimeout(refreshLive, 300);
})();
