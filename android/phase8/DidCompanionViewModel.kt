package com.did.charactersheet.sync

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.util.ArrayDeque

/** UI-facing state holder for the Windows-authoritative DID companion. */
class DidCompanionViewModel(application: Application) : AndroidViewModel(application), DidSyncClient.Listener {

    data class DiceResult(val title: String, val total: Int, val detail: String)

    data class UiState(
        val connection: DidSyncClient.ConnectionState = DidSyncClient.ConnectionState.Disconnected,
        val revision: Int = 0,
        val character: JSONObject? = null,
        val snapshot: DidCharacterSnapshot? = null,
        val lastError: String? = null,
        val pendingRequestIds: Set<String> = emptySet(),
        val protocolMismatchDesktopVersion: String? = null,
        val minimumVersionProblem: String? = null,
        val snapshotProblem: String? = null,
        val reconnectingAutomatically: Boolean = false,
        val lastDiceResult: DiceResult? = null,
        val rollHistory: List<String> = emptyList(),
    ) {
        val isConnected: Boolean
            get() = connection is DidSyncClient.ConnectionState.Connected &&
                minimumVersionProblem == null && snapshotProblem == null
        val isReadOnly: Boolean get() = !isConnected
        val characterName: String
            get() = snapshot?.name ?: character?.optString("name")?.takeIf { it.isNotBlank() } ?: "No character"
    }

    private data class QueuedCommand(val action: String, val payload: JSONObject)

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val syncClient = DidSyncClient(application, ANDROID_VERSION, this)
    private val commandQueue = ArrayDeque<QueuedCommand>()
    private var inFlightRequestId: String? = null
    private var waitingForResync = false

    private var retryJob: Job? = null
    private var retryAttempt = 0
    private var allowAutoReconnect = true

    init { syncClient.connectSaved() }

    fun pairFromQrJson(qrJson: String): Result<Unit> = runCatching {
        val payload = DidSyncClient.PairingPayload.fromQrJson(qrJson)
        allowAutoReconnect = true
        cancelRetry()
        _uiState.update { it.copy(lastError = null, protocolMismatchDesktopVersion = null, minimumVersionProblem = null, snapshotProblem = null) }
        syncClient.pair(payload)
    }

    fun reconnect() {
        allowAutoReconnect = true
        retryAttempt = 0
        cancelRetry()
        _uiState.update { it.copy(lastError = null, protocolMismatchDesktopVersion = null, minimumVersionProblem = null, snapshotProblem = null) }
        if (!syncClient.connectSaved()) {
            _uiState.update { it.copy(lastError = "No paired computer is saved. Pair this phone from the Windows DID app first.") }
        }
    }

    fun forgetComputer() {
        allowAutoReconnect = false
        cancelRetry()
        commandQueue.clear()
        inFlightRequestId = null
        waitingForResync = false
        syncClient.forgetComputer()
        _uiState.value = UiState()
    }

    fun refresh() {
        if (_uiState.value.connection is DidSyncClient.ConnectionState.Connected) syncClient.requestFreshState()
    }

    // Absolute setters prevent rapid taps from being interpreted against an old
    // desktop value. The UI may remain optimistic while the serialized command
    // queue waits for Windows to accept each target value.
    fun setHp(value: Int) = submitCommand("resource.set", JSONObject().put("resource", "HP").put("value", value))
    fun setAdversity(value: Int) = submitCommand("resource.set", JSONObject().put("resource", "Adversity").put("value", value))
    fun setImprovementPoints(value: Int) = submitCommand("resource.set", JSONObject().put("resource", "IP").put("value", value))

    // Retained for older screens/tests while V7 uses the absolute setters above.
    fun changeHp(delta: Int) { _uiState.value.snapshot?.let { setHp((it.hp.current + delta).coerceIn(0, it.hp.max)) } }
    fun changeAdversity(delta: Int) { _uiState.value.snapshot?.let { setAdversity((it.adversity.current + delta).coerceIn(0, it.adversity.max)) } }
    fun changeImprovementPoints(delta: Int) { _uiState.value.snapshot?.let { setImprovementPoints((it.progression.currentIp + delta).coerceAtLeast(it.progression.usedIp)) } }

    fun adjustResources(maxHearts: Int, totalIp: Int, maxAt: Int) = submitCommand(
        "resource.adjust",
        JSONObject().put("max_hearts", maxHearts).put("total_ip", totalIp).put("max_at", maxAt),
    )

    fun setCharacterName(name: String) = submitCommand("identity.set", JSONObject().put("field", "name").put("value", name))
    fun setBackstory(backstory: String) = submitCommand("identity.set", JSONObject().put("field", "backstory").put("value", backstory))

    fun addInventoryItem(name: String, description: String, quantity: Int) = submitCommand(
        "inventory.add", JSONObject().put("name", name).put("description", description).put("quantity", quantity)
    )
    fun updateInventoryItem(id: String, name: String, description: String, quantity: Int) = submitCommand(
        "inventory.update", JSONObject().put("id", id).put("name", name).put("description", description).put("quantity", quantity)
    )
    fun removeInventoryItem(id: String) = submitCommand("inventory.remove", JSONObject().put("id", id))

    fun addNote(title: String, text: String, color: String, pinned: Boolean) = submitCommand(
        "note.add", JSONObject().put("title", title).put("text", text).put("color", color).put("pinned", pinned)
    )
    fun updateNote(id: String, title: String, text: String, color: String, pinned: Boolean) = submitCommand(
        "note.update", JSONObject().put("id", id).put("title", title).put("text", text).put("color", color).put("pinned", pinned)
    )
    fun removeNote(id: String) = submitCommand("note.remove", JSONObject().put("id", id))

    fun addCharacterImages(images: List<String>) {
        images.forEach { submitCommand("image.add", JSONObject().put("data", it)) }
    }
    fun removeCharacterImage(id: String) = submitCommand("image.remove", JSONObject().put("id", id))

    fun editImprovement(id: String, choices: JSONObject, customName: String?, customDescription: String?) {
        val payload = JSONObject().put("id", id).put("choices", JSONObject(choices.toString()))
        if (customName != null) payload.put("name", customName)
        if (customDescription != null) payload.put("description", customDescription)
        submitCommand("improvement.edit", payload)
    }

    fun rollAbility(statKey: String) = submitCommand(
        "dice.roll", JSONObject().put("mode", "ability").put("stat", statKey)
    )

    fun rollOtherDice(counts: Map<Int, Int>) {
        val dice = JSONObject()
        counts.filterValues { it > 0 }.forEach { (sides, count) -> dice.put(sides.toString(), count) }
        submitCommand("dice.roll", JSONObject().put("mode", "other").put("dice", dice))
    }

    fun clearDiceResult() { _uiState.update { it.copy(lastDiceResult = null) } }

    private fun submitCommand(action: String, payload: JSONObject) {
        if (!_uiState.value.isConnected) {
            _uiState.update { it.copy(lastError = it.snapshotProblem ?: it.minimumVersionProblem ?: "The computer is not connected. Reconnect before changing the character.") }
            return
        }
        commandQueue.addLast(QueuedCommand(action, JSONObject(payload.toString())))
        sendNextIfPossible()
    }

    private fun sendNextIfPossible() {
        if (inFlightRequestId != null || waitingForResync || commandQueue.isEmpty() || !_uiState.value.isConnected) return
        val command = commandQueue.removeFirst()
        val requestId = syncClient.sendCommand(command.action, command.payload)
        inFlightRequestId = requestId
        _uiState.update { it.copy(pendingRequestIds = it.pendingRequestIds + requestId, lastError = null) }
    }

    override fun onConnectionState(state: DidSyncClient.ConnectionState) {
        if (state is DidSyncClient.ConnectionState.Connected) {
            val desktopVersion = state.desktopVersion
            if (desktopVersion != null && compareVersions(desktopVersion, MINIMUM_DESKTOP_VERSION) < 0) {
                allowAutoReconnect = false
                cancelRetry()
                val message = "Windows DID $MINIMUM_DESKTOP_VERSION or newer is required. The connected computer is running $desktopVersion."
                _uiState.update { it.copy(connection = state, minimumVersionProblem = message, lastError = message, reconnectingAutomatically = false) }
                return
            }
        }
        _uiState.update { current ->
            current.copy(
                connection = state,
                minimumVersionProblem = null,
                lastError = if (state is DidSyncClient.ConnectionState.Error) state.message else current.lastError,
                reconnectingAutomatically = false,
            )
        }
        when (state) {
            is DidSyncClient.ConnectionState.Connected -> {
                retryAttempt = 0
                cancelRetry()
                waitingForResync = false
                syncClient.requestFreshState()
            }
            is DidSyncClient.ConnectionState.Error, DidSyncClient.ConnectionState.Disconnected -> scheduleReconnect()
            DidSyncClient.ConnectionState.Connecting, DidSyncClient.ConnectionState.Pairing -> Unit
        }
    }

    override fun onCharacterState(revision: Int, character: JSONObject?) {
        if (character == null) {
            _uiState.update { it.copy(revision = revision, character = null, snapshot = null, snapshotProblem = null, reconnectingAutomatically = false) }
            if (waitingForResync) { waitingForResync = false; sendNextIfPossible() }
            return
        }
        val parsed = runCatching { DidCharacterSnapshot.fromJson(character) }
        val parsedSnapshot = parsed.getOrNull()
        val parseProblem = parsed.exceptionOrNull()?.let { "The computer sent character data this Android version cannot read. Update both DID apps and refresh." }
        _uiState.update { current ->
            current.copy(
                revision = revision,
                character = character,
                snapshot = parsedSnapshot ?: current.snapshot,
                snapshotProblem = parseProblem,
                lastError = when {
                    parseProblem != null -> parseProblem
                    current.minimumVersionProblem != null -> current.lastError
                    else -> current.lastError
                },
                reconnectingAutomatically = false,
            )
        }
        if (waitingForResync) { waitingForResync = false; sendNextIfPossible() }
    }

    override fun onCommandAccepted(requestId: String, revision: Int, result: JSONObject?) {
        if (inFlightRequestId == requestId) inFlightRequestId = null
        val dice = result?.let(::parseDiceResult)
        _uiState.update { current ->
            val entry = dice?.let { "${it.title}: ${it.total} — ${it.detail}" }
            current.copy(
                revision = maxOf(current.revision, revision),
                pendingRequestIds = current.pendingRequestIds - requestId,
                lastDiceResult = dice ?: current.lastDiceResult,
                rollHistory = entry?.let { listOf(it) + current.rollHistory.take(99) } ?: current.rollHistory,
            )
        }
        sendNextIfPossible()
    }

    override fun onCommandRejected(requestId: String?, code: String, message: String) {
        if (requestId != null && inFlightRequestId == requestId) inFlightRequestId = null
        _uiState.update { it.copy(pendingRequestIds = requestId?.let { id -> it.pendingRequestIds - id } ?: it.pendingRequestIds, lastError = message) }
        waitingForResync = true
        syncClient.requestFreshState()
    }

    private fun parseDiceResult(result: JSONObject): DiceResult? {
        if (!result.has("total")) return null
        return DiceResult(
            title = result.optString("title", "Roll"),
            total = result.optInt("total", 0),
            detail = result.optString("detail", ""),
        )
    }

    override fun onProtocolMismatch(desktopVersion: String?) {
        allowAutoReconnect = false
        cancelRetry()
        _uiState.update { it.copy(protocolMismatchDesktopVersion = desktopVersion, reconnectingAutomatically = false, lastError = "This phone and the Windows DID app use incompatible sync versions. Update the older app.") }
    }

    private fun scheduleReconnect() {
        if (!allowAutoReconnect || retryJob?.isActive == true) return
        val seconds = RETRY_SECONDS[minOf(retryAttempt, RETRY_SECONDS.lastIndex)]
        retryAttempt += 1
        _uiState.update { it.copy(reconnectingAutomatically = true) }
        retryJob = viewModelScope.launch {
            delay(seconds * 1000L)
            _uiState.update { it.copy(reconnectingAutomatically = false) }
            if (!allowAutoReconnect) return@launch
            if (!syncClient.connectSaved()) allowAutoReconnect = false
        }
    }

    private fun cancelRetry() {
        retryJob?.cancel(); retryJob = null
        _uiState.update { it.copy(reconnectingAutomatically = false) }
    }

    override fun onCleared() {
        allowAutoReconnect = false
        cancelRetry()
        syncClient.disconnect()
        super.onCleared()
    }

    companion object {
        const val ANDROID_VERSION = "0.8.0"
        const val MINIMUM_DESKTOP_VERSION = "1.0.11"
        private val RETRY_SECONDS = intArrayOf(2, 4, 8, 16, 30)

        internal fun compareVersions(a: String, b: String): Int {
            val left = a.trim().removePrefix("v").split('.')
            val right = b.trim().removePrefix("v").split('.')
            val max = maxOf(left.size, right.size)
            for (i in 0 until max) {
                val x = left.getOrNull(i)?.takeWhile { it.isDigit() }?.toIntOrNull() ?: 0
                val y = right.getOrNull(i)?.takeWhile { it.isDigit() }?.toIntOrNull() ?: 0
                if (x != y) return x.compareTo(y)
            }
            return 0
        }
    }
}
