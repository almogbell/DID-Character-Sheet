package com.did.charactersheet.sync

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/** Connection/pairing surface for Phase 8. */
@Composable
fun CompanionConnectionScreen(
    state: DidCompanionViewModel.UiState,
    onPairingQrScanned: () -> Unit,
    onPairingCodeEntered: (String) -> Unit,
    onReconnect: () -> Unit,
    onForgetComputer: () -> Unit,
    onRefresh: () -> Unit,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    var manualCode by remember { mutableStateOf("") }

    Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Computer connection", style = MaterialTheme.typography.titleLarge)

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(connectionLabel(state.connection))
                if (state.connection is DidSyncClient.ConnectionState.Connected) {
                    state.connection.desktopVersion?.let { Text("Windows DID: $it") }
                }
                Text("Android DID: ${DidCompanionViewModel.ANDROID_VERSION}")
                Text("Sync protocol: ${DidSyncClient.PROTOCOL}")
                if (state.revision > 0) Text("Character revision: ${state.revision}")
                if (state.reconnectingAutomatically) {
                    Text("Trying to reconnect automatically…")
                }
                state.minimumVersionProblem?.let {
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
                state.lastError?.takeIf { it != state.minimumVersionProblem }?.let {
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onPairingQrScanned) { Text("Scan pairing QR") }
            OutlinedButton(onClick = onReconnect) { Text("Reconnect") }
            if (state.isConnected) {
                OutlinedButton(onClick = onRefresh) { Text("Refresh") }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Can't scan the QR?", style = MaterialTheme.typography.titleSmall)
                Text(
                    "On Windows choose Copy pairing code, paste it here, then tap Pair.",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = manualCode,
                    onValueChange = { manualCode = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Pairing code") },
                    minLines = 2,
                    maxLines = 5,
                )
                Button(
                    enabled = manualCode.isNotBlank(),
                    onClick = {
                        onPairingCodeEntered(manualCode.trim())
                        manualCode = ""
                    },
                ) {
                    Text("Pair")
                }
            }
        }

        if (state.character != null) {
            CharacterSyncSummary(
                character = state.character,
                enabled = state.isConnected && state.pendingRequestIds.isEmpty(),
                onHpChange = onHpChange,
                onAtChange = onAtChange,
                onIpChange = onIpChange,
            )
        } else {
            Text("No character received from the computer yet.")
        }

        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = onForgetComputer) {
            Text("Forget paired computer")
        }
    }
}

@Composable
private fun CharacterSyncSummary(
    character: JSONObject,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    val hp = character.optJSONObject("HP")
    val at = character.optJSONObject("Adversity")
    val ip = character.optJSONObject("progression")

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(character.optString("name", "Unnamed character"), style = MaterialTheme.typography.titleMedium)
            ResourceSyncRow(
                label = "HP",
                value = hp?.optInt("current_HP") ?: 0,
                enabled = enabled,
                onChange = onHpChange,
            )
            ResourceSyncRow(
                label = "AT",
                value = at?.optInt("current_AT") ?: 0,
                enabled = enabled,
                onChange = onAtChange,
            )
            ResourceSyncRow(
                label = "IP",
                value = ip?.optInt("current_IP") ?: 0,
                enabled = enabled,
                onChange = onIpChange,
            )
        }
    }
}

@Composable
private fun ResourceSyncRow(
    label: String,
    value: Int,
    enabled: Boolean,
    onChange: (Int) -> Unit,
) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text("$label: $value")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(enabled = enabled, onClick = { onChange(-1) }) { Text("−") }
            OutlinedButton(enabled = enabled, onClick = { onChange(1) }) { Text("+") }
        }
    }
}

private fun connectionLabel(state: DidSyncClient.ConnectionState): String = when (state) {
    DidSyncClient.ConnectionState.Disconnected -> "Disconnected"
    DidSyncClient.ConnectionState.Connecting -> "Connecting to computer…"
    DidSyncClient.ConnectionState.Pairing -> "Pairing with computer…"
    is DidSyncClient.ConnectionState.Connected -> "Connected${state.computerName?.let { " • $it" } ?: ""}"
    is DidSyncClient.ConnectionState.Error -> "Connection error"
}
