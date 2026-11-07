"""Apply tested conflict-free auto-merge changes to matching DID 1.0.13 source.
Run from the project containing mobile_sync_frontend_adapter.py and phase8/.
The script refuses mismatched anchors and backs up the exact originals.
"""
from pathlib import Path
from datetime import datetime
import shutil, sys
root=Path.cwd()
android_root = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)==2 else root
if len(sys.argv)>2:
    raise SystemExit("Usage: python patch_problem20_auto_merge.py [ANDROID_PROJECT_PATH]")
changes={}

def ch(path,old,new,occurrences=1):
    p = (android_root if path.startswith("phase8/") else root) / path
    text=changes.get(p,p.read_text(encoding='utf-8'))
    num=text.count(old)
    if num != occurrences:
        raise RuntimeError(f'{path}: expected {occurrences} occurrences of anchor, found {num}: {old[:70]!r}')
    changes[p]=text.replace(old,new)

try:
    # Give the phone the exact canonical baseline that was hashed, rather
    # than the display-enriched payload (the latter has extra fields).
    ch('mobile_sync_frontend_adapter.py', '''            canonical_hash = self._character_content_hash(state)
            assets = self._load_mobile_assets()
''','''            canonical_hash = self._character_content_hash(state)
            canonical_base = json.loads(json.dumps(state))
            assets = self._load_mobile_assets()
''')
    ch('mobile_sync_frontend_adapter.py', '''                "content_hash": canonical_hash,
                "conflict_policy": "explicit",
''','''                "content_hash": canonical_hash,
                "base_character": canonical_base,
                "conflict_policy": "merge_v2",
''')
    ch('mobile_sync_frontend_adapter.py', '''        data = self.storage_system.character_to_dict(character)
        self._enrich_improvements(data, character)
''','''        data = self.storage_system.character_to_dict(character)
        canonical_hash = self._character_content_hash(data)
        canonical_base = json.loads(json.dumps(data))
        self._enrich_improvements(data, character)
''')
    ch('mobile_sync_frontend_adapter.py', '''            "content_hash": self._character_content_hash(data),
            "conflict_policy": "explicit",
''','''            "content_hash": canonical_hash,
            "base_character": canonical_base,
            "conflict_policy": "merge_v2",
''')
    # Windows version: use real three-way merged snapshot, not whole-character winner.
    ch('mobile_sync_frontend_adapter.py', '''        try:
            character = converter(data)
            character.validate()
        except Exception as exc:
            raise MobileSyncValidationError(
                f"The phone-created character could not be validated: {exc}"
            ) from exc

        try:
            existing_path, existing_character = self._saved_character_by_id(character_id)
''','''        try:
            existing_path, existing_character = self._saved_character_by_id(character_id)
''')
    start='''        # A full phone snapshot is the only operation that can replace many
        # fields at once. Never silently overwrite a PC copy that changed while
        # the devices were apart. The phone must explicitly choose "Keep Phone"
        # before force=True is sent.
        if existing_character is not None:
            current_dict = self.storage_system.character_to_dict(existing_character)
            current_hash = self._character_content_hash(current_dict)
            phone_hash = self._character_content_hash(data)
            base_hash = str(payload.get("base_hash") or "").strip()
            force = bool(payload.get("force", False))
            if phone_hash != current_hash and not force:
                if not base_hash or base_hash != current_hash:
                    raise MobileSyncValidationError(
                        "SYNC_CONFLICT: This character changed on both the phone and the PC while they were apart. "
                        "Choose Keep Phone or Use PC on the phone before syncing continues."
                    )

        # Protect unsaved edits in the active desktop character, which may
        # be newer than the saved file used for base-hash comparison.
        if (
            self._character_id() == character_id
            and bool(getattr(self.window, "unsaved_changes", False))
            and not bool(payload.get("force", False))
        ):
            raise MobileSyncValidationError(
                "SYNC_CONFLICT: This character has unsaved changes on Windows. "
                "Save or resolve the PC changes before accepting the phone snapshot."
            )
'''
    end='''        # Compare with the current open PC sheet if it has unsaved edits.
        # An incoming phone snapshot must merge these edits, not overwrite them.
        if existing_character is not None:
            pc_character = existing_character
            if self._character_id() == character_id and bool(getattr(self.window, "unsaved_changes", False)):
                pc_character = self.window.character
            current_dict = self.storage_system.character_to_dict(pc_character)
            current_hash = self._character_content_hash(current_dict)
            phone_hash = self._character_content_hash(data)
            base_hash = str(payload.get("base_hash") or "").strip()
            if phone_hash != current_hash and base_hash != current_hash:
                base_character = payload.get("base_character")
                if not isinstance(base_character, dict):
                    raise MobileSyncValidationError(
                        "SYNC_MERGE_NEEDS_BASE: This phone has older unsynchronized edits "
                        "without a common snapshot. Both copies are preserved; update the apps and export a backup."
                    )
                if not base_hash or self._character_content_hash(base_character) != base_hash:
                    raise MobileSyncValidationError(
                        "SYNC_MERGE_NEEDS_BASE: The common snapshot does not match its hash. Both copies are preserved."
                    )
                try:
                    try:
                        from .mobile_sync_merge import merge_characters
                    except ImportError:
                        from mobile_sync_merge import merge_characters
                    outcome = merge_characters(
                        self._strip_mobile_transport_fields(base_character),
                        self._strip_mobile_transport_fields(current_dict),
                        data,
                        hp_at_choice=payload.get("hp_at_choice"),
                    )
                except ValueError as exc:
                    raise MobileSyncValidationError(f"SYNC_MERGE_NEEDS_BASE: {exc}") from exc
                if outcome.merged is None:
                    raise MobileSyncValidationError(
                        "HP_AT_CONFLICT:" + ",".join(outcome.conflicting_resources)
                    )
                data = outcome.merged

        try:
            character = converter(data)
            character.validate()
        except Exception as exc:
            raise MobileSyncValidationError(
                f"The merged phone character could not be validated: {exc}"
            ) from exc
'''
    ch('mobile_sync_frontend_adapter.py',start,end)
    ch('mobile_sync_frontend_adapter.py','''            "content_hash": self._character_content_hash(
                self.storage_system.character_to_dict(character)
            ),
        }
''','''            "content_hash": self._character_content_hash(
                self.storage_system.character_to_dict(character)
            ),
            "character": self.storage_system.character_to_dict(character),
        }
''')
    # Back up otherwise unrepresentable concurrent scalar changes outside of
    # the DID schema, rather than having the deserializer quietly drop them.
    ch('mobile_sync_frontend_adapter.py', '''        try:
            character = converter(data)
            character.validate()
''','''        alternatives = data.pop("sync_alternatives", [])
        try:
            character = converter(data)
            character.validate()
''')
    ch('mobile_sync_frontend_adapter.py', '''        # Clear a prior deletion record only after an explicit restore has
        # successfully saved the character (handled below).
        try:
            exporter(character, existing_path)
''','''        # Save both competing scalar values in a durable sidecar before
        # updating the character. A backup failure blocks the merge.
        if alternatives:
            sidecar_path = existing_path + ".sync-alternatives.json"
            try:
                old_values = []
                if os.path.isfile(sidecar_path):
                    with open(sidecar_path, encoding="utf-8") as fh:
                        old_values = json.load(fh)
                if not isinstance(old_values, list):
                    raise ValueError("Invalid existing recovery file")
                seen = {json.dumps(value, sort_keys=True) for value in old_values}
                for alternative in alternatives:
                    key = json.dumps(alternative, sort_keys=True)
                    if key not in seen:
                        old_values.append(alternative)
                        seen.add(key)
                temporary = sidecar_path + ".tmp"
                with open(temporary, "w", encoding="utf-8") as fh:
                    json.dump(old_values, fh, ensure_ascii=False, indent=2)
                os.replace(temporary, sidecar_path)
            except (OSError, ValueError, TypeError) as exc:
                raise MobileSyncValidationError(
                    f"Could not preserve conflicting field edits: {exc}"
                ) from exc

        # Clear a prior deletion record only after an explicit restore has
        # successfully saved the character (handled below).
        try:
            exporter(character, existing_path)
''')
    # Android store: retain canonical base character until the next confirmed sync.
    ch('phase8/DidOfflineStore.kt','''        val syncedHash: String? = null,
    )
''','''        val syncedHash: String? = null,
        val syncedCharacter: JSONObject? = null,
    )
''')
    ch('phase8/DidOfflineStore.kt','''        val record = JSONObject()
            .put("revision", revision)
            .put("synced_hash", effectiveSyncedHash ?: JSONObject.NULL)
            .put("character", copy)
''','''        val baseline = if (syncedHash != null) {
            character.optJSONObject("_mobile_sync")?.optJSONObject("base_character")
                ?.let { JSONObject(it.toString()) } ?: JSONObject(copy.toString())
        } else current?.syncedCharacter
        val record = JSONObject()
            .put("revision", revision)
            .put("synced_hash", effectiveSyncedHash ?: JSONObject.NULL)
            .put("character", copy)
            .put("synced_character", baseline?.let { JSONObject(it.toString()) } ?: JSONObject.NULL)
''')
    ch('phase8/DidOfflineStore.kt','''        return CachedCharacter(id, displayName(copy), revision, copy, effectiveSyncedHash)
''','''        return CachedCharacter(id, displayName(copy), revision, copy, effectiveSyncedHash, baseline)
''')
    ch('phase8/DidOfflineStore.kt','''                syncedHash = rootJson.optString("synced_hash").trim().takeIf { it.isNotBlank() },
''','''                syncedHash = rootJson.optString("synced_hash").trim().takeIf { it.isNotBlank() },
                syncedCharacter = rootJson.optJSONObject("synced_character"),
''',2)
    ch('phase8/DidOfflineStore.kt','''    fun updateSyncedHash(
        characterId: String,
        syncedHash: String,
    ) {
''','''    fun updateSyncedHash(
        characterId: String,
        syncedHash: String,
        canonical: JSONObject? = null,
    ) {
''')
    ch('phase8/DidOfflineStore.kt','''            .put("synced_hash", clean)
            .put(
                "character",
                JSONObject(current.character.toString()),
            )
''','''            .put("synced_hash", clean)
            .put("synced_character", JSONObject((canonical ?: current.character).toString()))
            .put(
                "character",
                JSONObject(current.character.toString()),
            )
''')
    ch('phase8/DidOfflineStore.kt','''        cached.syncedHash?.let { payload.put("base_hash", it) }
''','''        cached.syncedHash?.let { payload.put("base_hash", it) }
        cached.syncedCharacter?.let { payload.put("base_character", JSONObject(it.toString())) }
''')
    # Android queue sync: include last shared baseline. The server will merge.
    ch('phase8/DidCompanionViewModel.kt','''                            cached.syncedHash?.let { refreshed.put("base_hash", it) }
                            if (command.payload.optBoolean("force", false)) refreshed.put("force", true)
''','''                            cached.syncedHash?.let { refreshed.put("base_hash", it) }
                            cached.syncedCharacter?.let { refreshed.put("base_character", JSONObject(it.toString())) }
                            command.payload.optString("hp_at_choice").takeIf { it in setOf("pc", "phone") }
                                ?.let { refreshed.put("hp_at_choice", it) }
                            if (command.payload.optBoolean("force", false)) refreshed.put("force", true)
''')
    # Rework resource-only choices without wiping or force-replacing entire char.
    ch('phase8/DidCompanionViewModel.kt','''        conflictedCharacters.remove(conflict.characterId)
        offlineStore.removePendingForCharacter(conflict.characterId)

        if (conflict.remoteDeleted) {
''','''        conflictedCharacters.remove(conflict.characterId)
        if (conflict.message.startsWith("HP_AT_CONFLICT:")) {
            requeueResourceDecision(conflict.characterId, "pc")
            return
        }
        offlineStore.removePendingForCharacter(conflict.characterId)

        if (conflict.remoteDeleted) {
''')
    ch('phase8/DidCompanionViewModel.kt','''        conflictedCharacters.remove(conflict.characterId)

        val existingPending = offlineStore.listPending(conflict.characterId)
''','''        conflictedCharacters.remove(conflict.characterId)
        if (conflict.message.startsWith("HP_AT_CONFLICT:")) {
            requeueResourceDecision(conflict.characterId, "phone")
            return
        }

        val existingPending = offlineStore.listPending(conflict.characterId)
''')
    ch('phase8/DidCompanionViewModel.kt','''    private fun reloadCommandQueueForLiveCharacter() {
''','''    private fun requeueResourceDecision(characterId: String, choice: String) {
        val cached = offlineStore.load(characterId) ?: return
        offlineStore.removePendingForCharacter(characterId)
        val payload = JSONObject()
            .put("character", JSONObject(cached.character.toString()))
            .put("modified_at", cached.revision)
            .put("hp_at_choice", choice)
        cached.syncedHash?.let { payload.put("base_hash", it) }
        cached.syncedCharacter?.let { payload.put("base_character", JSONObject(it.toString())) }
        val pending = offlineStore.enqueuePending(characterId, "character.upsert_snapshot", payload)
        commandQueue.clear()
        commandQueue.addLast(QueuedCommand(pending.id, characterId, "character.upsert_snapshot", payload))
        waitingForResync = false
        _uiState.update { it.copy(syncConflict = null, lastError = null) }
        updatePendingCount()
        sendNextIfPossible()
    }

    private fun reloadCommandQueueForLiveCharacter() {
''')
    ch('phase8/DidCompanionViewModel.kt','''                        offlineStore.updateSyncedHash(id, hash)
''','''                        val canonical = result?.optJSONObject("character")
                        offlineStore.updateSyncedHash(id, hash, canonical)
                        val remaining = offlineStore.listPending(id)
                            .any { it.action == "character.upsert_snapshot" }
                        if (!remaining && canonical != null) {
                            val saved = offlineStore.saveLive(
                                JSONObject(canonical.toString()).put(
                                    "_mobile_sync", JSONObject().put("content_hash", hash)
                                ), select = _uiState.value.snapshot?.id == id
                            )
                            if (saved != null && _uiState.value.snapshot?.id == id) {
                                applyCachedCharacter(saved, offlineViewing = false)
                            }
                        }
''')
    ch('phase8/Phase9CompanionSheetV8.kt', '''            Text("Sync conflict", fontWeight = FontWeight.Black)
            Text(conflict.message, style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onUsePc) { Text("Use PC") }
                Button(onClick = onKeepPhone) { Text("Keep Phone") }
            }
''','''            val resourcesOnly = conflict.message.startsWith("HP_AT_CONFLICT:")
            Text(if (resourcesOnly) "Choose HP / AT values" else "Sync conflict", fontWeight = FontWeight.Black)
            Text(
                if (resourcesOnly) "Both devices changed ${conflict.message.removePrefix("HP_AT_CONFLICT:")}. Other edits will merge automatically."
                else conflict.message,
                style = MaterialTheme.typography.bodySmall,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onUsePc) { Text(if (resourcesOnly) "Windows HP/AT" else "Use PC") }
                Button(onClick = onKeepPhone) { Text(if (resourcesOnly) "Phone HP/AT" else "Keep Phone") }
            }
''')
    ch('phase8/DidCompanionViewModel.kt', '''        // A stale revision on a read-only fetch can safely retry after a fresh
''','''        // STALE_REVISION is not a content conflict. Keep the phone snapshot
        // queued and retry after refreshing Windows' revision. The desktop
        // three-way merger will handle concurrent edits on the retry.
        if (code == "STALE_REVISION" && rejectedAction == "character.upsert_snapshot") {
            _uiState.update { current ->
                current.copy(pendingRequestIds = requestId?.let { current.pendingRequestIds - it }
                    ?: current.pendingRequestIds)
            }
            waitingForResync = true
            syncClient.requestFreshState()
            return
        }

        // A stale revision on a read-only fetch can safely retry after a fresh
''')
    ch('phase8/DidCompanionViewModel.kt','''        val conflict = explicitConflict || staleMutation
''','''        val resourceConflict = message.startsWith("HP_AT_CONFLICT:")
        val conflict = explicitConflict || resourceConflict || staleMutation
''')
    ch('phase8/DidCompanionViewModel.kt','''                        message = if (staleMutation) {
''','''                        message = if (resourceConflict) {
                            message // HP/AT only; the rest will be merged.
                        } else if (staleMutation) {
''')
except Exception as exc:
    print('STOPPED: no project files changed.',exc)
    sys.exit(1)

suffix=datetime.now().strftime('%Y%m%d_%H%M%S')
for p,t in changes.items():
    b=p.with_name(p.name+'.before_merge_'+suffix)
    shutil.copy2(p,b)
    p.write_text(t,encoding='utf-8')
    print('Patched',p,'backup',b.name)
print('Done. Keep backups and test with two devices before publishing.')
