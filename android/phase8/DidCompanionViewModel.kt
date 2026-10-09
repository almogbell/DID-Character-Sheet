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

/**
 * UI-facing state holder for the Phase 8 companion connection.
 *
 * The Windows app remains authoritative. Android only displays the latest
 * canonical state received from Windows and sends commands back to it.
 */
class DidCompanionViewModel(application: Application) : AndroidViewModel(application), DidSyncClient.Listener {

    data class UiState(
        val connection: DidSyncClient.ConnectionState = DidSyncClient.ConnectionState.Disconnected,
        val revision: Int = 0,
        val character: JSONObject? = null,
        val snapshot: DidCharacterSnapshot? = null,
        val lastError: String? = null,
        val pendingRequestIds: Set<String> = emptySet(),
        val protocolMismatchDesktopVersion: String? = null,
        val minimumVersionProblem: String? = null,
        val reconnectingAutomatically: Boolean = false,
    ) {
        val isConnected: Boolean
            get() = connection is DidSyncClient.ConnectionState.Connected && minimumVersionProblem == null

        val isReadOnly: Boolean
            get() = !isConnected

        val characterName: String
            get() = snapshot?.name ?: character?.optString("name")?.takeIf { it.isNotBlank() } ?: "No character"
    }

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val syncClient = DidSyncClient(
        context = application,
        androidVersion = ANDROID_VERSION,
        listener = this,
    )

    private var retryJob: Job? = null
    private var retryAttempt = 0
    private var allowAutoReconnect = true

    init {
        syncClient.connectSaved()
    }

    fun pairFromQrJson(qrJson: String): Result<Unit> = runCatching {
        val payload = DidSyncClient.PairingPayload.fromQrJson(qrJson)
        allowAutoReconnect = true
        cancelRetry()
        _uiState.update {
            it.copy(
                lastError = null,
                protocolMismatchDesktopVersion = null,
                minimumVersionProblem = null,
            )
        }
        syncClient.pair(payload)
    }

    fun reconnect() {
        allowAutoReconnect = true
        retryAttempt = 0
        cancelRetry()
        _uiState.update {
            it.copy(
                lastError = null,
                protocolMismatchDesktopVersion = null,
                minimumVersionProblem = null,
            )
        }
        if (!syncClient.connectSaved()) {
            _uiState.update {
                it.copy(lastError = "No paired computer is saved. Pair this phone from the Windows DID app first.")
            }
        }
    }

    fun forgetComputer() {
        allowAutoReconnect = false
        cancelRetry()
        syncClient.forgetComputer()
        _uiState.value = UiState()
    }

    fun refresh() {
        if (_uiState.value.isConnected) syncClient.requestFreshState()
    }

    fun changeHp(delta: Int) = submitResourceChange("HP", delta)
    fun changeAdversity(delta: Int) = submitResourceChange("Adversity", delta)
    fun changeImprovementPoints(delta: Int) = submitResourceChange("IP", delta)

    private fun submitResourceChange(resource: String, delta: Int) {
        if (!_uiState.value.isConnected) {
            _uiState.update {
                it.copy(lastError = it.minimumVersionProblem ?: "The computer is not connected. Reconnect before changing the character.")
            }
            return
        }
        val requestId = syncClient.changeResource(resource, delta)
        _uiState.update { it.copy(pendingRequestIds = it.pendingRequestIds + requestId, lastError = null) }
    }

    override fun onConnectionState(state: DidSyncClient.ConnectionState) {
        if (state is DidSyncClient.ConnectionState.Connected) {
            val desktopVersion = state.desktopVersion
            if (desktopVersion != null && compareVersions(desktopVersion, MINIMUM_DESKTOP_VERSION) < 0) {
                allowAutoReconnect = false
                cancelRetry()
                val message = "Windows DID $MINIMUM_DESKTOP_VERSION or newer is required. The connected computer is running $desktopVersion."
                _uiState.update {
                    it.copy(
                        connection = state,
                        minimumVersionProblem = message,
                        lastError = message,
                        reconnectingAutomatically = false,
                    )
                }
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
                syncClient.requestFreshState()
            }
            is DidSyncClient.ConnectionState.Error,
            DidSyncClient.ConnectionState.Disconnected -> scheduleReconnect()
            DidSyncClient.ConnectionState.Connecting,
            DidSyncClient.ConnectionState.Pairing -> Unit
        }
    }

    override fun onCharacterState(revision: Int, character: JSONObject?) {
        val typedSnapshot = character?.let { runCatching { DidCharacterSnapshot.fromJson(it) }.getOrNull() }
        _uiState.update {
            it.copy(
                revision = revision,
                character = character,
                snapshot = typedSnapshot,
                lastError = if (it.minimumVersionProblem == null) null else it.lastError,
                reconnectingAutomatically = false,
                pendingRequestIds = emptySet(),
            )
        }
    }

    override fun onCommandAccepted(requestId: String, revision: Int) {
        _uiState.update {
            it.copy(
                revision = maxOf(it.revision, revision),
                pendingRequestIds = it.pendingRequestIds - requestId,
            )
        }
    }

    override fun onCommandRejected(requestId: String?, code: String, message: String) {
        _uiState.update {
            it.copy(
                pendingRequestIds = requestId?.let { id -> it.pendingRequestIds - id } ?: it.pendingRequestIds,
                lastError = message,
            )
        }
        syncClient.requestFreshState()
    }

    override fun onProtocolMismatch(desktopVersion: String?) {
        allowAutoReconnect = false
        cancelRetry()
        _uiState.update {
            it.copy(
                protocolMismatchDesktopVersion = desktopVersion,
                reconnectingAutomatically = false,
                lastError = "This phone and the Windows DID app use incompatible sync versions. Update the older app.",
            )
        }
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
            val hasSavedComputer = syncClient.connectSaved()
            if (!hasSavedComputer) allowAutoReconnect = false
        }
    }

    private fun cancelRetry() {
        retryJob?.cancel()
        retryJob = null
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
