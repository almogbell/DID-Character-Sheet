package com.did.charactersheet.sync

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.rememberScrollState
import androidx.compose.foundation.layout.verticalScroll
import androidx.compose.foundation.layout.weight
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val DidPage = Color(0xFFF0FFFF)
private val DidSurface = Color(0xFFFFFDF7)
private val DidBlue = Color(0xFFD8EDF7)
private val DidGold = Color(0xFFC79A3B)
private val DidText = Color(0xFF25190F)
private val DidMuted = Color(0xFF6C6258)

/**
 * Phone layout backed only by the canonical Windows snapshot.
 *
 * HP/AT/IP are the first Phase 8 writable controls. All other sections are
 * intentionally read-only until their desktop command contracts are added.
 */
@Composable
fun CompanionSheetScreen(
    state: DidCompanionViewModel.UiState,
    onOpenConnection: () -> Unit,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val character = state.snapshot
    if (character == null) {
        Column(
            modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("No character is connected to this phone yet.", color = DidText)
            Spacer(Modifier.height(12.dp))
            Button(onClick = onOpenConnection) { Text("Connect to computer") }
        }
        return
    }

    var tab by remember { mutableIntStateOf(0) }

    Scaffold(
        modifier = modifier,
        containerColor = DidPage,
        topBar = {
            ConnectionStrip(
                state = state,
                onOpenConnection = onOpenConnection,
            )
        },
        bottomBar = {
            NavigationBar(containerColor = DidSurface) {
                listOf("Character", "Equipment", "Notes").forEachIndexed { index, label ->
                    NavigationBarItem(
                        selected = tab == index,
                        onClick = { tab = index },
                        icon = { Text(listOf("✦", "▣", "✎")[index], fontSize = 20.sp) },
                        label = { Text(label) },
                    )
                }
            }
        },
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            IdentityHeader(character)

            when (tab) {
                0 -> CharacterPage(
                    character = character,
                    editable = !state.isReadOnly,
                    pending = state.pendingRequestIds.isNotEmpty(),
                    onHpChange = onHpChange,
                    onAtChange = onAtChange,
                    onIpChange = onIpChange,
                )
                1 -> EquipmentPage(character)
                else -> NotesPage(character)
            }

            Spacer(Modifier.height(18.dp))
        }
    }
}

@Composable
private fun ConnectionStrip(
    state: DidCompanionViewModel.UiState,
    onOpenConnection: () -> Unit,
) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = DidSurface),
        border = BorderStroke(1.dp, DidGold),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    if (state.isConnected) "Connected to Windows" else "Computer unavailable",
                    color = DidText,
                    fontWeight = FontWeight.Bold,
                )
                if (state.reconnectingAutomatically) {
                    Text("Reconnecting automatically…", color = DidMuted, fontSize = 12.sp)
                } else if (!state.lastError.isNullOrBlank()) {
                    Text(state.lastError, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
            }
            OutlinedButton(onClick = onOpenConnection) {
                Text("Connection")
            }
        }
    }
}

@Composable
private fun IdentityHeader(character: DidCharacterSnapshot) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = DidSurface),
        border = BorderStroke(1.dp, DidGold),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(14.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                character.name.ifBlank { "Unnamed Character" },
                style = MaterialTheme.typography.headlineSmall,
                color = DidText,
                fontWeight = FontWeight.Bold,
            )
            if (character.speciesName.isNotBlank()) {
                Text(character.speciesName, color = DidMuted)
            }
            Text("Level ${character.progression.level}", color = DidMuted, fontSize = 12.sp)
        }
    }
}

@Composable
private fun CharacterPage(
    character: DidCharacterSnapshot,
    editable: Boolean,
    pending: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    val enabled = editable && !pending

    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ResourceCard(
            label = "HP",
            value = character.hp.current,
            maximum = character.hp.max.takeIf { it > 0 },
            enabled = enabled,
            onMinus = { onHpChange(-1) },
            onPlus = { onHpChange(1) },
            modifier = Modifier.weight(1f),
        )
        ResourceCard(
            label = "AT",
            value = character.adversity.current,
            maximum = character.adversity.max.takeIf { it > 0 },
            enabled = enabled,
            onMinus = { onAtChange(-1) },
            onPlus = { onAtChange(1) },
            modifier = Modifier.weight(1f),
        )
        ResourceCard(
            label = "IP",
            value = character.progression.currentIp,
            maximum = null,
            enabled = enabled,
            onMinus = { onIpChange(-1) },
            onPlus = { onIpChange(1) },
            modifier = Modifier.weight(1f),
        )
    }

    var subsection by remember { mutableIntStateOf(0) }
    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
        listOf("Abilities", "Improvements").forEachIndexed { index, title ->
            SegmentedButton(
                selected = subsection == index,
                onClick = { subsection = index },
                shape = SegmentedButtonDefaults.itemShape(index, 2),
            ) { Text(title) }
        }
    }

    if (subsection == 0) {
        AbilitiesSection(character.stats)
    } else {
        ImprovementsSection(character.improvements)
    }
}

@Composable
private fun ResourceCard(
    label: String,
    value: Int,
    maximum: Int?,
    enabled: Boolean,
    onMinus: () -> Unit,
    onPlus: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier,
        colors = CardDefaults.cardColors(containerColor = DidBlue),
        border = BorderStroke(1.dp, DidGold),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Text(label, color = DidText, fontWeight = FontWeight.Bold)
            Text(
                if (maximum == null) "$value" else "$value / $maximum",
                color = DidText,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                OutlinedButton(enabled = enabled, onClick = onMinus) { Text("−") }
                OutlinedButton(enabled = enabled, onClick = onPlus) { Text("+") }
            }
        }
    }
}

@Composable
private fun AbilitiesSection(stats: List<StatSnapshot>) {
    val order = listOf("Agility", "Strength", "Finesse", "Instinct", "Presence", "Knowledge")
    val sorted = stats.sortedWith(compareBy { stat ->
        order.indexOfFirst { it.equals(stat.name, ignoreCase = true) }.let { if (it < 0) Int.MAX_VALUE else it }
    })
    sorted.forEach { stat ->
        SheetCard(
            title = stat.name.replaceFirstChar { it.uppercase() },
            detail = "d${stat.dieSize}" + if (stat.bonus != 0) "  •  ${if (stat.bonus > 0) "+" else ""}${stat.bonus}" else "",
        )
    }
}

@Composable
private fun ImprovementsSection(improvements: List<ImprovementSnapshot>) {
    if (improvements.isEmpty()) {
        Text("No improvements on this character.", color = DidMuted)
        return
    }
    improvements.sortedBy { it.sortOrder }.forEach { improvement ->
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = DidSurface),
            border = BorderStroke(1.dp, DidGold),
        ) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(improvement.name, color = DidText, fontWeight = FontWeight.Bold)
                    Text("${improvement.cost} IP", color = DidMuted, fontSize = 12.sp)
                }
                if (improvement.description.isNotBlank()) {
                    Text(improvement.description, color = DidText, fontSize = 13.sp)
                }
                improvement.empowerments.forEach { empowerment ->
                    Text(
                        "• ${empowerment.name}" + if (empowerment.cost > 0) " (${empowerment.cost} IP)" else "",
                        color = DidText,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 13.sp,
                    )
                    if (empowerment.description.isNotBlank()) {
                        Text(empowerment.description, color = DidMuted, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun EquipmentPage(character: DidCharacterSnapshot) {
    Text("Equipment", style = MaterialTheme.typography.titleLarge, color = DidText)
    if (character.inventory.isEmpty()) {
        Text("Inventory is empty.", color = DidMuted)
        return
    }
    character.inventory.forEach { item ->
        val title = if (item.quantity > 1) "${item.name} ×${item.quantity}" else item.name
        SheetCard(title = title, detail = item.description)
    }
}

@Composable
private fun NotesPage(character: DidCharacterSnapshot) {
    Text("Notes", style = MaterialTheme.typography.titleLarge, color = DidText)
    if (character.notes.isEmpty()) {
        Text("No notes.", color = DidMuted)
        return
    }
    character.notes.sortedByDescending { it.pinned }.forEach { note ->
        val background = note.color.toComposeColor() ?: DidSurface
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = background),
            border = BorderStroke(1.dp, DidGold),
        ) {
            Column(Modifier.padding(12.dp)) {
                Text(
                    (if (note.pinned) "★ " else "") + note.title,
                    color = DidText,
                    fontWeight = FontWeight.Bold,
                )
                if (note.text.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(note.text, color = DidText, fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
private fun SheetCard(title: String, detail: String) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = DidSurface),
        border = BorderStroke(1.dp, DidGold),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(title, color = DidText, fontWeight = FontWeight.Bold)
            if (detail.isNotBlank()) {
                Spacer(Modifier.height(3.dp))
                Text(detail, color = DidText, fontSize = 13.sp)
            }
        }
    }
}

private fun String?.toComposeColor(): Color? {
    val raw = this?.trim()?.removePrefix("#") ?: return null
    val value = raw.toLongOrNull(16) ?: return null
    return when (raw.length) {
        6 -> Color(0xFF000000L or value)
        8 -> Color(value)
        else -> null
    }
}
