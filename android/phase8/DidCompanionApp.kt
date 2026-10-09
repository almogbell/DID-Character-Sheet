package com.did.charactersheet.sync

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.did.charactersheet.update.AndroidUpdateController
import com.did.charactersheet.update.UpdateNotice

/**
 * Phase 8 application root.
 *
 * The host Activity owns the QR scanner because Google Code Scanner requires an
 * Activity. Everything after a QR string is returned is handled here.
 */
@Composable
fun DidCompanionApp(
    viewModel: DidCompanionViewModel,
    requestQrScan: (onScanned: (String) -> Unit, onError: (String) -> Unit) -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var showConnection by remember { mutableStateOf(state.snapshot == null) }
    var transientError by remember { mutableStateOf<String?>(null) }

    val updateController = remember {
        AndroidUpdateController(
            context = context.applicationContext,
            currentVersion = DidCompanionViewModel.ANDROID_VERSION,
        )
    }
    var updateState by remember {
        mutableStateOf<AndroidUpdateController.State>(AndroidUpdateController.State.Idle)
    }

    fun checkUpdates() {
        updateController.check { updateState = it }
    }

    LaunchedEffect(Unit) {
        checkUpdates()
    }

    MaterialTheme {
        Surface(modifier.fillMaxSize()) {
            Column(
                Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                UpdateNotice(
                    state = updateState,
                    onCheckAgain = ::checkUpdates,
                    onInstall = { info ->
                        updateController.openUpdate(info).onFailure { error ->
                            updateState = AndroidUpdateController.State.Error(
                                error.message ?: "Could not open the Android update"
                            )
                        }
                    },
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                )

                CompanionSheetScreen(
                    state = state,
                    onOpenConnection = { showConnection = true },
                    onHpChange = viewModel::changeHp,
                    onAtChange = viewModel::changeAdversity,
                    onIpChange = viewModel::changeImprovementPoints,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }

    if (showConnection) {
        Dialog(onDismissRequest = { if (state.snapshot != null) showConnection = false }) {
            Surface(shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(4.dp)) {
                    CompanionConnectionScreen(
                        state = state,
                        onPairingQrScanned = {
                            requestQrScan(
                                { raw ->
                                    viewModel.pairFromQrJson(raw).onFailure { error ->
                                        transientError = error.message ?: "Invalid pairing code"
                                    }
                                },
                                { error -> transientError = error },
                            )
                        },
                        onPairingCodeEntered = { raw ->
                            viewModel.pairFromQrJson(raw).onFailure { error ->
                                transientError = error.message ?: "Invalid pairing code"
                            }
                        },
                        onReconnect = viewModel::reconnect,
                        onForgetComputer = viewModel::forgetComputer,
                        onRefresh = viewModel::refresh,
                        onHpChange = viewModel::changeHp,
                        onAtChange = viewModel::changeAdversity,
                        onIpChange = viewModel::changeImprovementPoints,
                    )
                    if (state.snapshot != null) {
                        OutlinedButton(
                            onClick = { showConnection = false },
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        ) { Text("Back to character") }
                    }
                }
            }
        }
    }

    transientError?.let { message ->
        AlertDialog(
            onDismissRequest = { transientError = null },
            title = { Text("Could not connect") },
            text = { Text(message) },
            confirmButton = {
                Button(onClick = { transientError = null }) { Text("OK") }
            },
        )
    }
}
