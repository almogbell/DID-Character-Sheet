package com.did.charactersheet.update

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun UpdateNotice(
    state: AndroidUpdateController.State,
    onCheckAgain: () -> Unit,
    onInstall: (GitHubUpdateChecker.UpdateInfo) -> Unit,
    modifier: Modifier = Modifier,
) {
    when (state) {
        AndroidUpdateController.State.Idle -> Unit
        AndroidUpdateController.State.Checking -> Text("Checking for DID Android updates…", modifier)
        AndroidUpdateController.State.UpToDate -> Unit
        is AndroidUpdateController.State.Error -> Card(modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Could not check for updates", style = MaterialTheme.typography.titleSmall)
                Text(state.message, style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = onCheckAgain) { Text("Try again") }
            }
        }
        is AndroidUpdateController.State.Available -> Card(modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("DID Android ${state.info.version} is available", style = MaterialTheme.typography.titleMedium)
                state.info.releaseNotes?.takeIf { it.isNotBlank() }?.let { Text(it) }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { onInstall(state.info) }) { Text("Update") }
                    OutlinedButton(onClick = onCheckAgain) { Text("Check again") }
                }
            }
        }
    }
}
