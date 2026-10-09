package com.did.charactersheet.sync

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/** Connection/pairing surface styled as part of the DID character sheet. */
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

    Column(
        modifier
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("DID Mobile Companion", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Connect this phone to the running Windows character sheet. Windows remains the authoritative copy of the character.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        ConnectionPanel(state)

        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Button(
                onClick = onPairingQrScanned,
                modifier = Modifier.weight(1f),
            ) { Text("Scan QR") }
            OutlinedButton(
                onClick = onReconnect,
                modifier = Modifier.weight(1f),
            ) { Text("Reconnect") }
        }

        if (state.isConnected) {
            OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) {
                Text("Refresh character from Windows")
            }
        }

        SheetPanel {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Manual pairing", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
                Text(
                    "If QR scanning is unavailable, use Copy pairing code on Windows and paste the full code here.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
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
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Pair with Windows")
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
        }

        Spacer(Modifier.height(3.dp))
        OutlinedButton(onClick = onForgetComputer, modifier = Modifier.fillMaxWidth()) {
            Text("Forget paired computer")
        }
    }
}

@Composable
private fun ConnectionPanel(state: DidCompanionViewModel.UiState) {
    SheetPanel {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(connectionLabel(state.connection), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
            val connected = state.connection as? DidSyncClient.ConnectionState.Connected
            connected?.desktopVersion?.let { Text("Windows DID $it") }
            Text("Android DID ${DidCompanionViewModel.ANDROID_VERSION}")
            Text("Sync protocol ${DidSyncClient.PROTOCOL}")
            if (state.revision > 0) Text("Character revision ${state.revision}")
            if (state.reconnectingAutomatically) {
                Text("Trying to reconnect automatically…", color = MaterialTheme.colorScheme.secondary)
            }
            state.minimumVersionProblem?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            state.lastError?.takeIf { it != state.minimumVersionProblem }?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }
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

    SheetPanel {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                character.optString("name", "Unnamed character"),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Black,
            )
            Text(
                "A character was received but could not yet be rendered as the full typed sheet.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            ResourceSyncRow("HP", hp?.optInt("current_HP") ?: 0, enabled, onHpChange)
            ResourceSyncRow("AT", at?.optInt("current_AT") ?: 0, enabled, onAtChange)
            ResourceSyncRow("IP", ip?.optInt("current_IP") ?: 0, enabled, onIpChange)
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
        Text("$label  $value", fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            OutlinedButton(enabled = enabled, onClick = { onChange(-1) }) { Text("−") }
            OutlinedButton(enabled = enabled, onClick = { onChange(1) }) { Text("+") }
        }
    }
}

@Composable
private fun SheetPanel(content: @Composable () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(2.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        content()
    }
}

private fun connectionLabel(state: DidSyncClient.ConnectionState): String = when (state) {
    DidSyncClient.ConnectionState.Disconnected -> "Not connected"
    DidSyncClient.ConnectionState.Connecting -> "Connecting to Windows…"
    DidSyncClient.ConnectionState.Pairing -> "Pairing with Windows…"
    is DidSyncClient.ConnectionState.Connected -> "Connected${state.computerName?.let { " • $it" } ?: ""}"
    is DidSyncClient.ConnectionState.Error -> "Connection error"
}
