package com.did.charactersheet.sync

import androidx.activity.ComponentActivity
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

/** Reliable in-app QR pairing scanner which doesn't depend on Google Code Scanner. */
class PairingScanner(activity: ComponentActivity) {
    sealed class Result {
        data class Success(
            val rawJson: String,
            val payload: DidSyncClient.PairingPayload,
        ) : Result()
        data class Error(val message: String) : Result()
        data object Cancelled : Result()
    }

    private var pendingCallback: ((Result) -> Unit)? = null

    private val launcher = activity.registerForActivityResult(ScanContract()) { scan ->
        val callback = pendingCallback ?: return@registerForActivityResult
        pendingCallback = null
        val raw = scan.contents
        if (raw.isNullOrBlank()) {
            callback(Result.Cancelled)
            return@registerForActivityResult
        }
        try {
            val payload = DidSyncClient.PairingPayload.fromQrJson(raw)
            callback(Result.Success(raw, payload))
        } catch (e: Exception) {
            callback(Result.Error(e.message ?: "This is not a valid DID pairing code."))
        }
    }

    fun start(callback: (Result) -> Unit) {
        if (pendingCallback != null) return
        pendingCallback = callback
        val options = ScanOptions()
            .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
            .setPrompt("Scan the pairing QR shown by Windows DID")
            .setBeepEnabled(false)
            .setOrientationLocked(false)
        launcher.launch(options)
    }

    companion object {
        const val GRADLE_DEPENDENCY = "com.journeyapps:zxing-android-embedded:4.3.0"
    }
}
