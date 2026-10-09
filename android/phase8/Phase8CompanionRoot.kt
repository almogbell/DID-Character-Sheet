package com.did.charactersheet.sync

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.did.charactersheet.ui.DidPalette

/** Companion entry surface. Windows remains the authoritative character. */
@Composable
fun Phase8CompanionRoot(
    state: DidCompanionViewModel.UiState,
    onScanPairingQr: () -> Unit,
    onManualPairingCode: (String) -> Unit,
    onReconnect: () -> Unit,
    onForgetComputer: () -> Unit,
    onRefresh: () -> Unit,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    onSetName: (String) -> Unit,
    onSetBackstory: (String) -> Unit,
    onAddInventoryItem: (String, String, Int) -> Unit,
    onUpdateInventoryItem: (String, String, String, Int) -> Unit,
    onRemoveInventoryItem: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val snapshot = state.snapshot

    if (snapshot == null) {
        CompanionConnectionScreen(
            state = state,
            onPairingQrScanned = onScanPairingQr,
            onPairingCodeEntered = onManualPairingCode,
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

        Phase9CompanionSheet(
            snapshot = snapshot,
            connected = state.isConnected,
            pending = state.pendingRequestIds.isNotEmpty(),
            onHpChange = onHpChange,
            onAtChange = onAtChange,
            onIpChange = onIpChange,
            onSetName = onSetName,
            onSetBackstory = onSetBackstory,
            onAddInventoryItem = onAddInventoryItem,
            onUpdateInventoryItem = onUpdateInventoryItem,
            onRemoveInventoryItem = onRemoveInventoryItem,
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
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 5.dp),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Box(
                Modifier
                    .padding(end = 9.dp)
                    .size(10.dp)
                    .background(
                        if (state.isConnected) DidPalette.Positive else DidPalette.Negative,
                        CircleShape,
                    )
            )
            Column(Modifier.weight(1f)) {
                Text(
                    if (state.isConnected) "Windows companion connected" else "Computer unavailable — read only",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Black,
                )
                val connected = state.connection as? DidSyncClient.ConnectionState.Connected
                connected?.desktopVersion?.let {
                    Text(
                        "Windows DID $it  •  Sync ${DidSyncClient.PROTOCOL}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (state.reconnectingAutomatically) {
                    Text(
                        "Reconnecting automatically…",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                    )
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
