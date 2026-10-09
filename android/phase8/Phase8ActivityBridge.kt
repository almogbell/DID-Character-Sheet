package com.did.charactersheet.sync

import android.app.Activity
import com.did.charactersheet.update.AndroidUpdateController
import com.did.charactersheet.update.GitHubUpdateChecker

/**
 * Thin host-Activity bridge so the finished Android app only needs a small
 * amount of Phase 8 glue code.
 */
class Phase8ActivityBridge(
    private val activity: Activity,
    private val viewModel: DidCompanionViewModel,
) {
    private val pairingScanner = PairingScanner(activity)
    private val updateController = AndroidUpdateController(
        context = activity.applicationContext,
        currentVersion = DidCompanionViewModel.ANDROID_VERSION,
    )

    fun scanPairingQr(onMessage: (String?) -> Unit = {}) {
        pairingScanner.start(activity) { result ->
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

    fun checkForUpdates(onState: (AndroidUpdateController.State) -> Unit) {
        updateController.check(onState)
    }

    fun openUpdate(info: GitHubUpdateChecker.UpdateInfo): Result<Unit> =
        updateController.openUpdate(info)
}
