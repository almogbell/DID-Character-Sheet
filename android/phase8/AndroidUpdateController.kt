package com.did.charactersheet.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper

/**
 * Phase 8 Android update flow.
 *
 * The checker reads updates/android.json from GitHub. For the first release,
 * installation remains under Android's normal security model: the app opens
 * the published APK/release URL and Android handles download/install consent.
 * No silent installation is attempted.
 */
class AndroidUpdateController(
    private val context: Context,
    private val currentVersion: String,
) {
    sealed class State {
        data object Idle : State()
        data object Checking : State()
        data object UpToDate : State()
        data class Available(val info: GitHubUpdateChecker.UpdateInfo) : State()
        data class Error(val message: String) : State()
    }

    private val main = Handler(Looper.getMainLooper())
    private val checker = GitHubUpdateChecker(currentVersion)

    fun check(onState: (State) -> Unit) {
        onState(State.Checking)
        checker.check { result ->
            val state = result.fold(
                onSuccess = { info -> if (info == null) State.UpToDate else State.Available(info) },
                onFailure = { State.Error(it.message ?: "Could not check for updates") },
            )
            main.post { onState(state) }
        }
    }

    fun openUpdate(info: GitHubUpdateChecker.UpdateInfo): Result<Unit> = runCatching {
        val target = info.downloadUrl ?: info.releaseUrl
            ?: error("This update has not been published for download yet.")
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
