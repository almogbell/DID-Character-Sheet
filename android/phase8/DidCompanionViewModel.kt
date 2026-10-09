package com.did.charactersheet.sync

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
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
        val lastError: String? = null,
        val pendingRequestIds: Set<String> = emptySet(),
        val protocolMismatchDesktopVersion: String? = null,
    ) {
        val isConnected: Boolean
            get() = connection is DidSyncClient.ConnectionState.Connected

        val characterName: String
            get() = character?.optString("name")?.takeIf { it.isNotBlank() } ?: "No character"
    }

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val syncClient = DidSyncClient(
        context = application,
        androidVersion = ANDROID_VERSION,
        listener = this,
    )

    init {
        // Normal startup path: reconnect to the previously paired desktop.
        syncClient.connectSaved()
    }

    fun pairFromQrJson(qrJson: String): Result<Unit> = runCatching {
        val payload = DidSyncClient.PairingPayload.fromQrJson(qrJson)
        _uiState.update { it.copy(lastError = null) }
        syncClient.pair(payload)
    }

    fun reconnect() {
        _uiState.update { it.copy(lastError = null) }
        if (!syncClient.connectSaved()) {
            _uiState.update {
                it.copy(lastError = "No paired computer is saved. Pair this phone from the Windows DID app first.")
            }
        }
    }

    fun forgetComputer() {
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
            _uiState.update { it.copy(lastError = "The computer is not connected. Reconnect before changing the character.") }
            return
        }
        val requestId = syncClient.changeResource(resource, delta)
        _uiState.update { it.copy(pendingRequestIds = it.pendingRequestIds + requestId, lastError = null) }
    }

    override fun onConnectionState(state: DidSyncClient.ConnectionState) {
        _uiState.update { current ->
            current.copy(
                connection = state,
                lastError = if (state is DidSyncClient.ConnectionState.Error) state.message else current.lastError,
            )
        }
        if (state is DidSyncClient.ConnectionState.Connected) {
            syncClient.requestFreshState()
        }
    }

    override fun onCharacterState(revision: Int, character: JSONObject?) {
        _uiState.update {
            it.copy(
                revision = revision,
                character = character,
                lastError = null,
                // A canonical state supersedes all optimistic/pending assumptions.
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
        // Always re-fetch canonical state after a rejection.
        syncClient.requestFreshState()
    }

    override fun onProtocolMismatch(desktopVersion: String?) {
        _uiState.update {
            it.copy(
                protocolMismatchDesktopVersion = desktopVersion,
                lastError = "This phone and the Windows DID app use incompatible sync versions. Update the older app.",
            )
        }
    }

    override fun onCleared() {
        syncClient.disconnect()
        super.onCleared()
    }

    companion object {
        // Keep this independent from the Windows application version.
        const val ANDROID_VERSION = "0.8.0"
    }
}
