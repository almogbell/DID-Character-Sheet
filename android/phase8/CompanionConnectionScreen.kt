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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/**
 * Minimal Phase 8 connection/status surface.
 *
 * This is intentionally small so it can be embedded into the existing DID
 * phone UI without replacing the sheet redesign. QR scanning itself is wired
 * by the host Activity and passes the scanned JSON into onPairingQrScanned.
 */
@Composable
fun CompanionConnectionScreen(
    state: DidCompanionViewModel.UiState,
    onPairingQrScanned: () -> Unit,
    onReconnect: () -> Unit,
    onForgetComputer: () -> Unit,
    onRefresh: () -> Unit,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Computer connection", style = MaterialTheme.typography.titleLarge)

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(connectionLabel(state.connection))
                Text("Sync protocol: 1")
                if (state.revision > 0) Text("Character revision: ${state.revision}")
                state.lastError?.let {
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onPairingQrScanned) { Text("Connect phone") }
            OutlinedButton(onClick = onReconnect) { Text("Reconnect") }
            if (state.isConnected) {
                OutlinedButton(onClick = onRefresh) { Text("Refresh") }
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
