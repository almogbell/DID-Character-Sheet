package com.did.charactersheet

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.did.charactersheet.sync.DidCompanionViewModel
import com.did.charactersheet.sync.Phase8ActivityBridge
import com.did.charactersheet.sync.Phase8CompanionRoot
import com.did.charactersheet.ui.DidTheme
import com.did.charactersheet.update.AndroidUpdateController
import com.did.charactersheet.update.UpdateNotice

/** Portrait-first DID companion host. Windows owns the canonical character. */
class MainActivity : ComponentActivity() {
    private val companionViewModel: DidCompanionViewModel by viewModels()
    private lateinit var phase8Bridge: Phase8ActivityBridge

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        phase8Bridge = Phase8ActivityBridge(this, companionViewModel)

        setContent {
            val state by companionViewModel.uiState.collectAsState()
            var updateState by remember {
                mutableStateOf<AndroidUpdateController.State>(AndroidUpdateController.State.Idle)
            }
            var activityMessage by remember { mutableStateOf<String?>(null) }

            LaunchedEffect(Unit) {
                phase8Bridge.checkForUpdates { updateState = it }
            }

            DidTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    Column(Modifier.fillMaxSize()) {
                        activityMessage?.let { message ->
                            Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp)) {
                                Text(
                                    text = message,
                                    modifier = Modifier.padding(12.dp),
                                    color = MaterialTheme.colorScheme.error,
                                )
                            }
                        }

                        UpdateNotice(
                            state = updateState,
                            onCheckAgain = {
                                phase8Bridge.checkForUpdates { updateState = it }
                            },
                            onInstall = { info ->
                                phase8Bridge.openUpdate(info)
                                    .onFailure { activityMessage = it.message ?: "Could not open the update." }
                            },
                            modifier = Modifier.padding(horizontal = 12.dp),
                        )

                        Phase8CompanionRoot(
                            state = state,
                            onScanPairingQr = {
                                activityMessage = null
                                phase8Bridge.scanPairingQr { activityMessage = it }
                            },
                            onManualPairingCode = { code ->
                                activityMessage = phase8Bridge
                                    .pairFromPastedCode(code)
                                    .exceptionOrNull()
                                    ?.message
                            },
                            onReconnect = companionViewModel::reconnect,
                            onForgetComputer = companionViewModel::forgetComputer,
                            onRefresh = companionViewModel::refresh,
                            onHpChange = companionViewModel::changeHp,
                            onAtChange = companionViewModel::changeAdversity,
                            onIpChange = companionViewModel::changeImprovementPoints,
                            onSetName = companionViewModel::setCharacterName,
                            onSetBackstory = companionViewModel::setBackstory,
                            onAddInventoryItem = companionViewModel::addInventoryItem,
                            onUpdateInventoryItem = companionViewModel::updateInventoryItem,
                            onRemoveInventoryItem = companionViewModel::removeInventoryItem,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }
        }
    }
}
