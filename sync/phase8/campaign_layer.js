(() => {
  "use strict";

  const config = window.DID_DASHBOARD_CONFIG || {};
  const supabaseFactory = window.supabase;
  if (!supabaseFactory || !config.supabaseUrl || !config.supabaseKey) return;

  const state = {
    client: null,
    campaignId: "",
    notes: [],
    npcs: [],
    relationships: [],
    entries: [],
    effects: [],
    characters: [],
    tab: "notes",
    channel: null,
    refreshTimer: null,
  };

  const escapeHtml = value => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function host() {
    return document.getElementById("campaignLayerSection");
  }

  function setStatus(text, error = false) {
    const el = document.getElementById("campaignLayerStatus");
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("error-text", !!error);
  }

  function ensureUi() {
    if (host()) return;
    const dashboard = document.getElementById("dashboardContent");
    if (!dashboard) return;

    const section = document.createElement("section");
    section.id = "campaignLayerSection";
    section.className = "p8-layer";
    section.innerHTML = `
      <div class="p8-heading">
        <div>
          <div class="eyebrow">CAMPAIGN LAYER</div>
          <h2>DM Workspace</h2>
          <div class="summary-text">Campaign-only information. Nothing here is written into a player's .didchar file.</div>
        </div>
        <div id="campaignLayerStatus" class="summary-text"></div>
      </div>
      <div class="p8-tabs" role="tablist">
        <button data-p8-tab="notes" class="active">DM Notes</button>
        <button data-p8-tab="npcs">NPCs</button>
        <button data-p8-tab="entries">Hooks & Clues</button>
        <button data-p8-tab="effects">Character Effects</button>
      </div>
      <div id="campaignLayerBody" class="p8-body"></div>`;

    const rolls = dashboard.querySelector(".rolls-section");
    if (rolls) dashboard.insertBefore(section, rolls);
    else dashboard.appendChild(section);

    const dialog = document.createElement("dialog");
    dialog.id = "p8EditorDialog";
    dialog.className = "p8-dialog";
    dialog.innerHTML = `<button class="dialog-close" data-p8-close aria-label="Close">×</button><div id="p8EditorBody"></div>`;
    document.body.appendChild(dialog);

    section.addEventListener("click", onSectionClick);
    dialog.addEventListener("click", event => {
      if (event.target === dialog || event.target.closest("[data-p8-close]")) dialog.close();
    });
  }

  async function ensureAuth() {
    const current = await state.client.auth.getSession();
    if (current.error) throw current.error;
    if (current.data && current.data.session) return current.data.session;
    const created = await state.client.auth.signInAnonymously({ options: { data: { application: "did_dm_dashboard_phase8" } } });
    if (created.error) throw created.error;
    return created.data.session;
  }

  function currentCampaignId() {
    const select = document.getElementById("campaignSelect");
    return String(select && select.value || "").trim();
  }

  function scheduleLoad() {
    if (state.refreshTimer) clearTimeout(state.refreshTimer);
    state.refreshTimer = setTimeout(() => {
      state.refreshTimer = null;
      load().catch(error => {
        console.error(error);
        setStatus(error.message || String(error), true);
      });
    }, 120);
  }

  async function load() {
    ensureUi();
    const campaignId = currentCampaignId();
    if (!campaignId) {
      state.campaignId = "";
      render();
      return;
    }
    await ensureAuth();
    state.campaignId = campaignId;
    setStatus("Refreshing…");

    const [notes, npcs, relationships, entries, effects, characters] = await Promise.all([
      state.client.from("campaign_dm_notes").select("*").eq("campaign_id", campaignId).order("updated_at", { ascending: false }),
      state.client.from("campaign_npcs").select("*").eq("campaign_id", campaignId).order("name", { ascending: true }),
      state.client.from("campaign_npc_relationships").select("*").eq("campaign_id", campaignId).order("updated_at", { ascending: false }),
      state.client.from("campaign_entries").select("*").eq("campaign_id", campaignId).order("updated_at", { ascending: false }),
      state.client.from("campaign_character_effects").select("*").eq("campaign_id", campaignId).order("updated_at", { ascending: false }),
      state.client.from("campaign_characters").select("id,display_name,character_id,active").eq("campaign_id", campaignId).eq("active", true).order("display_name", { ascending: true }),
    ]);

    for (const response of [notes, npcs, relationships, entries, effects, characters]) {
      if (response.error) throw response.error;
    }
    state.notes = notes.data || [];
    state.npcs = npcs.data || [];
    state.relationships = relationships.data || [];
    state.entries = entries.data || [];
    state.effects = effects.data || [];
    state.characters = characters.data || [];
    render();
    subscribe();
    setStatus("Live");
  }

  function subscribe() {
    if (state.channel) {
      state.client.removeChannel(state.channel);
      state.channel = null;
    }
    if (!state.campaignId) return;
    const filter = `campaign_id=eq.${state.campaignId}`;
    state.channel = state.client.channel(`did-phase8-${state.campaignId}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_dm_notes", filter }, scheduleLoad)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_npcs", filter }, scheduleLoad)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_npc_relationships", filter }, scheduleLoad)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_entries", filter }, scheduleLoad)
      .on("postgres_changes", { event: "*", schema: "public", table: "campaign_character_effects", filter }, scheduleLoad)
      .subscribe();
  }

  function empty(text) {
    return `<div class="p8-empty">${escapeHtml(text)}</div>`;
  }

  function visibilityBadge(visible, playerWord = "Players") {
    return visible
      ? `<span class="p8-badge public">Visible to ${escapeHtml(playerWord)}</span>`
      : `<span class="p8-badge private">DM only</span>`;
  }

  function actionButtons(kind, id, extra = "") {
    return `<div class="p8-actions">${extra}<button data-p8-edit="${kind}" data-id="${escapeHtml(id)}">Edit</button><button data-p8-delete="${kind}" data-id="${escapeHtml(id)}" class="danger-action">Delete</button></div>`;
  }

  function renderNotes() {
    const cards = state.notes.map(note => `
      <article class="p8-card">
        <div class="p8-card-head"><h3>${escapeHtml(note.title)}</h3>${visibilityBadge(false)}</div>
        <div class="p8-text">${escapeHtml(note.body).replaceAll("\n", "<br>")}</div>
        ${actionButtons("note", note.id)}
      </article>`).join("");
    return `<div class="p8-toolbar"><button data-p8-add="note" class="primary-action">New DM Note</button></div>${cards || empty("No DM notes yet.")}`;
  }

  function relationTarget(row) {
    if (row.target_kind === "npc") {
      const npc = state.npcs.find(item => String(item.id) === String(row.target_npc_id));
      return npc ? npc.name : "NPC";
    }
    const character = state.characters.find(item => String(item.id) === String(row.target_campaign_character_id));
    return character ? character.display_name : "Character";
  }

  function renderNpcRelationships(npcId) {
    const rows = state.relationships.filter(row => String(row.npc_id) === String(npcId));
    if (!rows.length) return `<div class="p8-subtle">No relationships recorded.</div>`;
    return `<div class="p8-relations">${rows.map(row => `
      <div class="p8-relation">
        <div><b>${escapeHtml(row.relationship)}</b> → ${escapeHtml(relationTarget(row))}${row.notes ? `<div class="p8-subtle">${escapeHtml(row.notes)}</div>` : ""}</div>
        <div class="p8-mini-actions"><button data-p8-edit="relationship" data-id="${escapeHtml(row.id)}">Edit</button><button data-p8-delete="relationship" data-id="${escapeHtml(row.id)}">×</button></div>
      </div>`).join("")}</div>`;
  }

  function renderNpcs() {
    const cards = state.npcs.map(npc => `
      <article class="p8-card">
        <div class="p8-card-head"><div><h3>${escapeHtml(npc.name)}</h3>${npc.status ? `<div class="p8-subtle">${escapeHtml(npc.status)}</div>` : ""}</div>${visibilityBadge(npc.visible_to_players)}</div>
        ${npc.description ? `<div class="p8-text">${escapeHtml(npc.description).replaceAll("\n", "<br>")}</div>` : ""}
        ${npc.gm_notes ? `<div class="p8-gm-note"><b>DM:</b> ${escapeHtml(npc.gm_notes).replaceAll("\n", "<br>")}</div>` : ""}
        <h4>Relationships</h4>
        ${renderNpcRelationships(npc.id)}
        ${actionButtons("npc", npc.id, `<button data-p8-add="relationship" data-npc-id="${escapeHtml(npc.id)}">Add Relationship</button>`)}
      </article>`).join("");
    return `<div class="p8-toolbar"><button data-p8-add="npc" class="primary-action">New NPC</button></div>${cards || empty("No NPCs yet.")}`;
  }

  function renderEntries() {
    const cards = state.entries.map(entry => `
      <article class="p8-card">
        <div class="p8-card-head"><div><span class="p8-type">${escapeHtml(entry.entry_type)}</span><h3>${escapeHtml(entry.title)}</h3></div>${visibilityBadge(entry.visible_to_players)}</div>
        ${entry.status ? `<div class="p8-subtle">Status: ${escapeHtml(entry.status)}</div>` : ""}
        <div class="p8-text">${escapeHtml(entry.body).replaceAll("\n", "<br>")}</div>
        ${actionButtons("entry", entry.id)}
      </article>`).join("");
    return `<div class="p8-toolbar"><button data-p8-add="entry" class="primary-action">New Hook / Clue</button></div>${cards || empty("No hooks, secrets, clues, quests, objectives, or messages yet.")}`;
  }

  function effectTarget(row) {
    const character = state.characters.find(item => String(item.id) === String(row.campaign_character_id));
    return character ? character.display_name : "Removed character";
  }

  function renderEffects() {
    const cards = state.effects.map(effect => `
      <article class="p8-card">
        <div class="p8-card-head"><div><h3>${escapeHtml(effect.name)}</h3><div class="p8-subtle">${escapeHtml(effectTarget(effect))} • ${escapeHtml(effect.status || "active")}</div></div>${visibilityBadge(effect.visible_to_player, "player")}</div>
        <div class="p8-text">${escapeHtml(effect.description).replaceAll("\n", "<br>")}</div>
        ${actionButtons("effect", effect.id)}
      </article>`).join("");
    return `<div class="p8-toolbar"><button data-p8-add="effect" class="primary-action">New Character Effect</button></div>${cards || empty("No campaign-layer character effects yet.")}`;
  }

  function render() {
    ensureUi();
    const body = document.getElementById("campaignLayerBody");
    if (!body) return;
    document.querySelectorAll("[data-p8-tab]").forEach(button => button.classList.toggle("active", button.dataset.p8Tab === state.tab));
    if (!state.campaignId) {
      body.innerHTML = empty("Select a DM campaign to use the campaign layer.");
      return;
    }
    body.innerHTML = state.tab === "npcs" ? renderNpcs()
      : state.tab === "entries" ? renderEntries()
      : state.tab === "effects" ? renderEffects()
      : renderNotes();
  }

  function rowFor(kind, id) {
    const map = { note: state.notes, npc: state.npcs, relationship: state.relationships, entry: state.entries, effect: state.effects };
    return (map[kind] || []).find(row => String(row.id) === String(id)) || null;
  }

  function field(name, label, value = "", type = "text") {
    return `<label class="p8-field"><span>${escapeHtml(label)}</span><input name="${escapeHtml(name)}" type="${escapeHtml(type)}" value="${escapeHtml(value)}"></label>`;
  }

  function textarea(name, label, value = "") {
    return `<label class="p8-field"><span>${escapeHtml(label)}</span><textarea name="${escapeHtml(name)}" rows="5">${escapeHtml(value)}</textarea></label>`;
  }

  function checkbox(name, label, checked) {
    return `<label class="p8-check"><input name="${escapeHtml(name)}" type="checkbox" ${checked ? "checked" : ""}><span>${escapeHtml(label)}</span></label>`;
  }

  function selectField(name, label, options, selected = "") {
    return `<label class="p8-field"><span>${escapeHtml(label)}</span><select name="${escapeHtml(name)}">${options.map(([value, text]) => `<option value="${escapeHtml(value)}" ${String(value) === String(selected) ? "selected" : ""}>${escapeHtml(text)}</option>`).join("")}</select></label>`;
  }

  function openEditor(kind, row = null, context = {}) {
    const dialog = document.getElementById("p8EditorDialog");
    const body = document.getElementById("p8EditorBody");
    if (!dialog || !body) return;
    const editing = !!row;
    let title = "";
    let fields = "";

    if (kind === "note") {
      title = editing ? "Edit DM Note" : "New DM Note";
      fields = field("title", "Title", row?.title) + textarea("body", "Private DM note", row?.body);
    } else if (kind === "npc") {
      title = editing ? "Edit NPC" : "New NPC";
      fields = field("name", "Name", row?.name)
        + field("status", "Status", row?.status)
        + textarea("description", "Description", row?.description)
        + textarea("gm_notes", "DM-only notes", row?.gm_notes)
        + field("portrait_url", "Portrait URL (optional)", row?.portrait_url, "url")
        + checkbox("visible_to_players", "Reveal this NPC to players", !!row?.visible_to_players);
    } else if (kind === "entry") {
      title = editing ? "Edit Campaign Entry" : "New Hook / Clue";
      fields = selectField("entry_type", "Type", [["hook","Hook"],["secret","Secret"],["clue","Clue"],["quest","Quest"],["objective","Objective"],["message","Message"]], row?.entry_type || "hook")
        + field("title", "Title", row?.title)
        + textarea("body", "Details", row?.body)
        + field("status", "Status", row?.status || "active")
        + checkbox("visible_to_players", "Reveal to campaign players", !!row?.visible_to_players);
    } else if (kind === "effect") {
      title = editing ? "Edit Character Effect" : "New Character Effect";
      const options = state.characters.map(item => [item.id, item.display_name || "Character"]);
      fields = selectField("campaign_character_id", "Character", options, row?.campaign_character_id || options[0]?.[0] || "")
        + field("name", "Effect / status", row?.name)
        + textarea("description", "Description", row?.description)
        + field("status", "Status", row?.status || "active")
        + checkbox("visible_to_player", "Show this effect to the affected player", !!row?.visible_to_player);
    } else if (kind === "relationship") {
      title = editing ? "Edit Relationship" : "New Relationship";
      const npcId = row?.npc_id || context.npcId;
      const targetValue = row
        ? (row.target_kind === "npc" ? `npc:${row.target_npc_id}` : `character:${row.target_campaign_character_id}`)
        : "";
      const targets = [
        ...state.npcs.filter(item => String(item.id) !== String(npcId)).map(item => [`npc:${item.id}`, `NPC: ${item.name}`]),
        ...state.characters.map(item => [`character:${item.id}`, `Character: ${item.display_name}`]),
      ];
      fields = `<input type="hidden" name="npc_id" value="${escapeHtml(npcId)}">`
        + selectField("target", "Related to", targets, targetValue || targets[0]?.[0] || "")
        + field("relationship", "Relationship", row?.relationship)
        + textarea("notes", "DM notes", row?.notes)
        + checkbox("visible_to_players", "Mark relationship as player-visible for future player UI", !!row?.visible_to_players);
    }

    body.innerHTML = `<div class="eyebrow">PHASE 8</div><h2>${escapeHtml(title)}</h2><form id="p8EditorForm" data-kind="${escapeHtml(kind)}" data-id="${escapeHtml(row?.id || "")}">${fields}<div class="p8-dialog-actions"><button type="button" data-p8-close>Cancel</button><button type="submit" class="primary-action">Save</button></div></form>`;
    body.querySelector("form").addEventListener("submit", saveEditor);
    dialog.showModal();
  }

  async function saveEditor(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const kind = form.dataset.kind;
    const id = form.dataset.id;
    const data = new FormData(form);
    let table;
    let payload;

    if (kind === "note") {
      table = "campaign_dm_notes";
      payload = { title: String(data.get("title") || "").trim(), body: String(data.get("body") || "") };
    } else if (kind === "npc") {
      table = "campaign_npcs";
      payload = { name: String(data.get("name") || "").trim(), status: String(data.get("status") || "").trim(), description: String(data.get("description") || ""), gm_notes: String(data.get("gm_notes") || ""), portrait_url: String(data.get("portrait_url") || "").trim(), visible_to_players: data.get("visible_to_players") === "on" };
    } else if (kind === "entry") {
      table = "campaign_entries";
      payload = { entry_type: String(data.get("entry_type") || "hook"), title: String(data.get("title") || "").trim(), body: String(data.get("body") || ""), status: String(data.get("status") || "active").trim() || "active", visible_to_players: data.get("visible_to_players") === "on" };
    } else if (kind === "effect") {
      table = "campaign_character_effects";
      payload = { campaign_character_id: String(data.get("campaign_character_id") || ""), name: String(data.get("name") || "").trim(), description: String(data.get("description") || ""), status: String(data.get("status") || "active").trim() || "active", visible_to_player: data.get("visible_to_player") === "on" };
    } else if (kind === "relationship") {
      table = "campaign_npc_relationships";
      const [targetKind, targetId] = String(data.get("target") || "").split(":", 2);
      payload = { npc_id: String(data.get("npc_id") || ""), target_kind: targetKind, target_npc_id: targetKind === "npc" ? targetId : null, target_campaign_character_id: targetKind === "character" ? targetId : null, relationship: String(data.get("relationship") || "").trim(), notes: String(data.get("notes") || ""), visible_to_players: data.get("visible_to_players") === "on" };
    }

    if (!payload || !table) return;
    if (id) {
      const response = await state.client.from(table).update(payload).eq("id", id).eq("campaign_id", state.campaignId);
      if (response.error) return setStatus(response.error.message, true);
    } else {
      payload.campaign_id = state.campaignId;
      const response = await state.client.from(table).insert(payload);
      if (response.error) return setStatus(response.error.message, true);
    }
    document.getElementById("p8EditorDialog").close();
    await load();
  }

  async function remove(kind, id) {
    const table = { note: "campaign_dm_notes", npc: "campaign_npcs", relationship: "campaign_npc_relationships", entry: "campaign_entries", effect: "campaign_character_effects" }[kind];
    if (!table || !confirm("Delete this campaign-layer item?")) return;
    const response = await state.client.from(table).delete().eq("id", id).eq("campaign_id", state.campaignId);
    if (response.error) return setStatus(response.error.message, true);
    await load();
  }

  function onSectionClick(event) {
    const tab = event.target.closest("[data-p8-tab]");
    if (tab) {
      state.tab = tab.dataset.p8Tab;
      render();
      return;
    }
    const add = event.target.closest("[data-p8-add]");
    if (add) {
      openEditor(add.dataset.p8Add, null, { npcId: add.dataset.npcId || "" });
      return;
    }
    const edit = event.target.closest("[data-p8-edit]");
    if (edit) {
      openEditor(edit.dataset.p8Edit, rowFor(edit.dataset.p8Edit, edit.dataset.id));
      return;
    }
    const del = event.target.closest("[data-p8-delete]");
    if (del) remove(del.dataset.p8Delete, del.dataset.id);
  }

  function attachToDashboard() {
    ensureUi();
    const campaignSelect = document.getElementById("campaignSelect");
    if (campaignSelect && !campaignSelect.dataset.p8Bound) {
      campaignSelect.dataset.p8Bound = "1";
      campaignSelect.addEventListener("change", () => setTimeout(scheduleLoad, 50));
    }
    const refresh = document.getElementById("refreshBtn");
    if (refresh && !refresh.dataset.p8Bound) {
      refresh.dataset.p8Bound = "1";
      refresh.addEventListener("click", () => setTimeout(scheduleLoad, 150));
    }
    scheduleLoad();
  }

  state.client = supabaseFactory.createClient(config.supabaseUrl, config.supabaseKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", attachToDashboard);
  else attachToDashboard();

  const observer = new MutationObserver(() => {
    const dashboard = document.getElementById("dashboardContent");
    if (dashboard && !dashboard.classList.contains("hidden")) attachToDashboard();
  });
  observer.observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ["class"] });
})();
