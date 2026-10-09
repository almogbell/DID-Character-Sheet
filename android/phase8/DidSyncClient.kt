package com.did.charactersheet.sync

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * Phase 8 DID Android companion connection.
 *
 * Windows is authoritative. This client never saves a DID character file and
 * never assumes a mutation succeeded until a canonical `state` message arrives.
 */
class DidSyncClient(
    context: Context,
    private val androidVersion: String,
    private val listener: Listener,
) {
    interface Listener {
        fun onConnectionState(state: ConnectionState)
        fun onCharacterState(revision: Int, character: JSONObject?)
        fun onCommandAccepted(requestId: String, revision: Int) {}
        fun onCommandRejected(requestId: String?, code: String, message: String) {}
        fun onProtocolMismatch(desktopVersion: String?) {}
    }

    sealed class ConnectionState {
        data object Disconnected : ConnectionState()
        data object Connecting : ConnectionState()
        data object Pairing : ConnectionState()
        data class Connected(val computerName: String?) : ConnectionState()
        data class Error(val message: String) : ConnectionState()
    }

    data class PairingPayload(
        val host: String,
        val port: Int,
        val pairingToken: String,
        val serverId: String?,
    ) {
        companion object {
            fun fromQrJson(text: String): PairingPayload {
                val json = JSONObject(text)
                require(json.optString("type") == "did_pairing") { "Not a DID pairing code" }
                require(json.optInt("protocol", -1) == PROTOCOL) { "Unsupported DID sync protocol" }
                return PairingPayload(
                    host = json.getString("host"),
                    port = json.getInt("port"),
                    pairingToken = json.getString("pairing_token"),
                    serverId = json.optString("server_id").ifBlank { null },
                )
            }
        }
    }

    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences("did_companion_sync", Context.MODE_PRIVATE)
    private val main = Handler(Looper.getMainLooper())
    private val http = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .connectTimeout(8, TimeUnit.SECONDS)
        .build()

    private var socket: WebSocket? = null
    private var pendingPairing: PairingPayload? = null
    @Volatile private var revision: Int = 0

    private val deviceId: String by lazy {
        prefs.getString(KEY_DEVICE_ID, null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString(KEY_DEVICE_ID, it).apply()
        }
    }

    fun connectSaved(): Boolean {
        val host = prefs.getString(KEY_HOST, null) ?: return false
        val port = prefs.getInt(KEY_PORT, -1)
        val token = prefs.getString(KEY_DEVICE_TOKEN, null) ?: return false
        if (port <= 0 || token.isBlank()) return false
        pendingPairing = null
        connectSocket(host, port)
        return true
    }

    fun pair(payload: PairingPayload) {
        pendingPairing = payload
        emit(ConnectionState.Pairing)
        connectSocket(payload.host, payload.port)
    }

    fun disconnect() {
        socket?.close(1000, "User disconnected")
        socket = null
        emit(ConnectionState.Disconnected)
    }

    fun forgetComputer() {
        disconnect()
        prefs.edit()
            .remove(KEY_HOST)
            .remove(KEY_PORT)
            .remove(KEY_SERVER_ID)
            .remove(KEY_DEVICE_TOKEN)
            .apply()
    }

    fun requestFreshState() {
        send(JSONObject().put("type", "get_state"))
    }

    /** Generic command. Use specific helpers in UI code where possible. */
    fun sendCommand(action: String, payload: JSONObject): String {
        val requestId = UUID.randomUUID().toString()
        send(
            JSONObject()
                .put("type", "command")
                .put("request_id", requestId)
                .put("base_revision", revision)
                .put("action", action)
                .put("payload", payload)
        )
        return requestId
    }

    fun changeResource(resource: String, delta: Int): String = sendCommand(
        action = "resource.change",
        payload = JSONObject().put("resource", resource).put("delta", delta),
    )

    private fun connectSocket(host: String, port: Int) {
        socket?.cancel()
        emit(ConnectionState.Connecting)
        val request = Request.Builder().url("ws://$host:$port").build()
        socket = http.newWebSocket(request, SocketListener())
    }

    private inner class SocketListener : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            val pairing = pendingPairing
            if (pairing != null) {
                val message = JSONObject()
                    .put("type", "pair")
                    .put("protocol", PROTOCOL)
                    .put("pairing_token", pairing.pairingToken)
                    .put("device_id", deviceId)
                    .put("device_name", android.os.Build.MODEL ?: "Android phone")
                    .put("android_version", androidVersion)
                webSocket.send(message.toString())
                return
            }

            val token = prefs.getString(KEY_DEVICE_TOKEN, null)
            if (token.isNullOrBlank()) {
                webSocket.close(1008, "Not paired")
                emit(ConnectionState.Error("This phone is not paired with the computer."))
                return
            }
            webSocket.send(
                JSONObject()
                    .put("type", "hello")
                    .put("protocol", PROTOCOL)
                    .put("android_version", androidVersion)
                    .put("device_id", deviceId)
                    .put("device_name", android.os.Build.MODEL ?: "Android phone")
                    .put("device_token", token)
                    .toString()
            )
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                handleMessage(JSONObject(text))
            } catch (e: Exception) {
                emit(ConnectionState.Error("Invalid response from computer: ${e.message}"))
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            socket = null
            emit(ConnectionState.Error(t.message ?: "Could not connect to the computer."))
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            socket = null
            emit(ConnectionState.Disconnected)
        }
    }

    private fun handleMessage(message: JSONObject) {
        when (message.optString("type")) {
            "pair_ok" -> {
                val pairing = pendingPairing ?: return
                val token = message.getString("device_token")
                val serverId = message.optString("server_id").ifBlank { pairing.serverId }
                prefs.edit()
                    .putString(KEY_HOST, pairing.host)
                    .putInt(KEY_PORT, pairing.port)
                    .putString(KEY_DEVICE_TOKEN, token)
                    .putString(KEY_SERVER_ID, serverId)
                    .apply()
                pendingPairing = null
                emit(ConnectionState.Connected(serverId))
            }
            "hello_ok" -> {
                revision = message.optInt("revision", revision)
                emit(ConnectionState.Connected(message.optString("server_id").ifBlank { null }))
            }
            "state" -> {
                revision = message.getInt("revision")
                val character = if (message.isNull("character")) null else message.optJSONObject("character")
                main.post { listener.onCharacterState(revision, character) }
            }
            "command_ok" -> {
                val requestId = message.optString("request_id")
                val rev = message.optInt("revision", revision)
                main.post { listener.onCommandAccepted(requestId, rev) }
            }
            "command_error" -> {
                val requestId = message.optString("request_id").ifBlank { null }
                val code = message.optString("code", "COMMAND_ERROR")
                val detail = message.optString("message", "The computer rejected the change.")
                main.post { listener.onCommandRejected(requestId, code, detail) }
            }
            "error" -> {
                val code = message.optString("code", "ERROR")
                if (code == "PROTOCOL_MISMATCH") {
                    main.post { listener.onProtocolMismatch(message.optString("desktop_version").ifBlank { null }) }
                }
                emit(ConnectionState.Error(code))
            }
            "pair_error", "hello_error" -> emit(
                ConnectionState.Error(message.optString("code", "Connection rejected"))
            )
        }
    }

    private fun send(json: JSONObject) {
        val ok = socket?.send(json.toString()) ?: false
        if (!ok) emit(ConnectionState.Error("Not connected to the computer."))
    }

    private fun emit(state: ConnectionState) {
        main.post { listener.onConnectionState(state) }
    }

    companion object {
        const val PROTOCOL = 1
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_HOST = "host"
        private const val KEY_PORT = "port"
        private const val KEY_SERVER_ID = "server_id"
        private const val KEY_DEVICE_TOKEN = "device_token"
    }
}
