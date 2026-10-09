package com.did.charactersheet.sync

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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

/**
 * Single Phase 8 entry surface for the existing Android Activity.
 *
 * The host Activity owns QR scanning and Android update launching.  This root
 * decides whether to show connection setup or the synchronized character sheet.
 */
@Composable
fun Phase8CompanionRoot(
    state: DidCompanionViewModel.UiState,
    onScanPairingQr: () -> Unit,
    onReconnect: () -> Unit,
    onForgetComputer: () -> Unit,
    onRefresh: () -> Unit,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val snapshot = state.snapshot

    if (snapshot == null) {
        CompanionConnectionScreen(
            state = state,
            onPairingQrScanned = onScanPairingQr,
            onReconnect = onReconnect,
            onForgetComputer = onForgetComputer,
            onRefresh = onRefresh,
            onHpChange = onHpChange,
            onAtChange = onAtChange,
            onIpChange = onIpChange,
            modifier = modifier.fillMaxSize(),
        )
        return
    }

    Column(modifier.fillMaxSize()) {
        ConnectionBanner(
            state = state,
            onReconnect = onReconnect,
            onRefresh = onRefresh,
        )

        DidCompanionSheet(
            snapshot = snapshot,
            connected = state.isConnected,
            pending = state.pendingRequestIds.isNotEmpty(),
            onHpChange = onHpChange,
            onAtChange = onAtChange,
            onIpChange = onIpChange,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun ConnectionBanner(
    state: DidCompanionViewModel.UiState,
    onReconnect: () -> Unit,
    onRefresh: () -> Unit,
) {
    Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp)) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    if (state.isConnected) "Connected to Windows" else "Computer unavailable — read only",
                    style = MaterialTheme.typography.labelLarge,
                )
                if (state.reconnectingAutomatically) {
                    Text("Reconnecting automatically…", style = MaterialTheme.typography.labelSmall)
                }
                state.lastError?.takeIf { !state.isConnected }?.let {
                    Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
                }
            }

            if (state.isConnected) {
                OutlinedButton(onClick = onRefresh) { Text("Refresh") }
            } else {
                Button(onClick = onReconnect) { Text("Reconnect") }
            }
        }
    }
}
