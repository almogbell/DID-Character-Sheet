package com.did.charactersheet.sync

import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.did.charactersheet.update.AndroidUpdateController
import com.did.charactersheet.update.GitHubUpdateChecker

/** Activity-result glue for pairing, picture import and GitHub updating. */
class Phase8ActivityBridge(
    private val activity: ComponentActivity,
    private val viewModel: DidCompanionViewModel,
) {
    private val pairingScanner = PairingScanner(activity)
    private val updateController = AndroidUpdateController(
        context = activity.applicationContext,
        currentVersion = DidCompanionViewModel.ANDROID_VERSION,
    )

    private var imageCallback: ((Result<List<String>>) -> Unit)? = null
    private val imagePicker = activity.registerForActivityResult(
        ActivityResultContracts.GetMultipleContents()
    ) { uris ->
        val callback = imageCallback ?: return@registerForActivityResult
        imageCallback = null
        if (uris.isEmpty()) {
            callback(Result.success(emptyList()))
            return@registerForActivityResult
        }
        callback(runCatching {
            uris.map { uri ->
                val mime = activity.contentResolver.getType(uri)
                    ?.takeIf { it.startsWith("image/") }
                    ?: "image/png"
                val bytes = activity.contentResolver.openInputStream(uri)?.use { input ->
                    input.readBytes(MAX_IMAGE_BYTES + 1)
                } ?: error("Could not read the selected image.")
                require(bytes.isNotEmpty()) { "The selected image is empty." }
                require(bytes.size <= MAX_IMAGE_BYTES) {
                    "Each character picture must be 8 MB or smaller."
                }
                "data:$mime;base64," + Base64.encodeToString(bytes, Base64.NO_WRAP)
            }
        })
    }

    fun scanPairingQr(onMessage: (String?) -> Unit = {}) {
        pairingScanner.start { result ->
            when (result) {
                is PairingScanner.Result.Success -> {
                    val paired = viewModel.pairFromQrJson(result.rawJson)
                    onMessage(paired.exceptionOrNull()?.message)
                }
                is PairingScanner.Result.Error -> onMessage(result.message)
                PairingScanner.Result.Cancelled -> onMessage(null)
            }
        }
    }

    fun pairFromPastedCode(code: String): Result<Unit> = viewModel.pairFromQrJson(code)

    fun pickCharacterImages(onResult: (Result<List<String>>) -> Unit) {
        if (imageCallback != null) return
        imageCallback = onResult
        imagePicker.launch("image/*")
    }

    fun checkForUpdates(onState: (AndroidUpdateController.State) -> Unit) {
        updateController.check(onState)
    }

    fun openUpdate(info: GitHubUpdateChecker.UpdateInfo): Result<Unit> =
        updateController.openUpdate(info)

    companion object {
        private const val MAX_IMAGE_BYTES = 8 * 1024 * 1024
    }
}
