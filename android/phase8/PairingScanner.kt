package com.did.charactersheet.sync

import android.app.Activity
import android.content.Context
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning

/**
 * QR pairing helper for Phase 8.
 *
 * Uses Google Code Scanner so the app doesn't need to own a camera preview or
 * request CAMERA permission. A pasted-code fallback remains available in the
 * connection UI for devices without compatible Google Play services.
 */
class PairingScanner(context: Context) {
    sealed class Result {
        data class Success(
            val rawJson: String,
            val payload: DidSyncClient.PairingPayload,
        ) : Result()
        data class Error(val message: String) : Result()
        data object Cancelled : Result()
    }

    private val options = GmsBarcodeScannerOptions.Builder()
        .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
        .enableAutoZoom()
        .build()

    private val scanner: GmsBarcodeScanner = GmsBarcodeScanning.getClient(context, options)

    fun start(activity: Activity, callback: (Result) -> Unit) {
        scanner.startScan()
            .addOnSuccessListener(activity) { barcode ->
                val raw = barcode.rawValue
                if (raw.isNullOrBlank()) {
                    callback(Result.Error("The QR code did not contain a DID pairing code."))
                    return@addOnSuccessListener
                }
                try {
                    val payload = DidSyncClient.PairingPayload.fromQrJson(raw)
                    callback(Result.Success(raw, payload))
                } catch (e: Exception) {
                    callback(Result.Error(e.message ?: "This is not a valid DID pairing code."))
                }
            }
            .addOnCanceledListener(activity) {
                callback(Result.Cancelled)
            }
            .addOnFailureListener(activity) { error ->
                callback(Result.Error(error.message ?: "Could not scan the pairing code."))
            }
    }

    companion object {
        const val GRADLE_DEPENDENCY =
            "com.google.android.gms:play-services-code-scanner:16.1.0"
    }
}
