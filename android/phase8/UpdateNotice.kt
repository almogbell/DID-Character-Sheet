package com.did.charactersheet.update

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
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
        AndroidUpdateController.State.Checking -> Text(
            "Checking for DID Android updates…",
            modifier.padding(vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        AndroidUpdateController.State.UpToDate -> Unit
        is AndroidUpdateController.State.Error -> NoticeSurface(modifier) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Could not check for updates", style = MaterialTheme.typography.titleSmall)
                Text(state.message, style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = onCheckAgain) { Text("Try again") }
            }
        }
        is AndroidUpdateController.State.Available -> NoticeSurface(modifier) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "DID Android ${state.info.version} is available",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Black,
                )
                state.info.releaseNotes?.takeIf { it.isNotBlank() }?.let { Text(it) }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { onInstall(state.info) }) { Text("Update") }
                    OutlinedButton(onClick = onCheckAgain) { Text("Check again") }
                }
            }
        }
    }
}

@Composable
private fun NoticeSurface(modifier: Modifier, content: @Composable () -> Unit) {
    Surface(
        modifier = modifier.fillMaxWidth().padding(vertical = 4.dp),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        content = content,
    )
}
