package com.did.charactersheet.sync

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Phase 8 phone sheet backed exclusively by the canonical Windows snapshot.
 *
 * It intentionally does not own/save a .didchar file. Resource controls only
 * emit commands to Windows. Everything else is read-only until its matching
 * desktop command is added to Sync Protocol v1.
 */
@Composable
fun DidCompanionSheet(
    snapshot: DidCharacterSnapshot,
    connected: Boolean,
    pending: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    var page by remember { mutableStateOf(CompanionPage.Character) }

    Column(modifier.fillMaxSize()) {
        CharacterHeader(snapshot)

        when (page) {
            CompanionPage.Character -> CharacterPage(
                snapshot = snapshot,
                controlsEnabled = connected && !pending,
                onHpChange = onHpChange,
                onAtChange = onAtChange,
                onIpChange = onIpChange,
                modifier = Modifier.weight(1f),
            )
            CompanionPage.Equipment -> EquipmentPage(snapshot, Modifier.weight(1f))
            CompanionPage.Notes -> NotesPage(snapshot, Modifier.weight(1f))
        }

        NavigationBar {
            CompanionPage.entries.forEach { item ->
                NavigationBarItem(
                    selected = page == item,
                    onClick = { page = item },
                    icon = { Text(item.shortLabel) },
                    label = { Text(item.label) },
                )
            }
        }
    }
}

private enum class CompanionPage(val label: String, val shortLabel: String) {
    Character("Character", "C"),
    Equipment("Equipment", "E"),
    Notes("Notes", "N"),
}

@Composable
private fun CharacterHeader(snapshot: DidCharacterSnapshot) {
    Card(Modifier.fillMaxWidth().padding(12.dp)) {
        Column(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(snapshot.name.ifBlank { "Unnamed character" }, style = MaterialTheme.typography.headlineSmall)
            if (snapshot.speciesName.isNotBlank()) {
                Text(snapshot.speciesName, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun CharacterPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }

    Column(modifier) {
        ResourceStrip(snapshot, controlsEnabled, onHpChange, onAtChange, onIpChange)

        ScrollableTabRow(selectedTabIndex = tab) {
            listOf("Abilities", "Improvements").forEachIndexed { index, label ->
                Tab(
                    selected = tab == index,
                    onClick = { tab = index },
                    text = { Text(label) },
                )
            }
        }

        if (tab == 0) AbilitiesList(snapshot, Modifier.fillMaxSize())
        else ImprovementsList(snapshot, Modifier.fillMaxSize())
    }
}

@Composable
private fun ResourceStrip(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
        ResourceRow("HP", "${snapshot.hp.current} / ${snapshot.hp.max}", enabled, onHpChange)
        ResourceRow("AT", "${snapshot.adversity.current} / ${snapshot.adversity.max}", enabled, onAtChange)
        ResourceRow("IP", snapshot.progression.currentIp.toString(), enabled, onIpChange)
    }
}

@Composable
private fun ResourceRow(label: String, value: String, enabled: Boolean, onChange: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text("$label  $value", fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { onChange(-1) }, enabled = enabled) { Text("−") }
            Button(onClick = { onChange(1) }, enabled = enabled) { Text("+") }
        }
    }
}

@Composable
private fun AbilitiesList(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    val order = listOf("Agility", "Strength", "Finesse", "Instinct", "Presence", "Knowledge")
    val sorted = snapshot.stats.sortedWith(compareBy { order.indexOf(it.name).let { index -> if (index < 0) 999 else index } })

    LazyColumn(modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(sorted, key = { it.name }) { stat ->
            Card(Modifier.fillMaxWidth()) {
                Row(
                    Modifier.fillMaxWidth().padding(14.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(stat.name, fontWeight = FontWeight.Bold)
                    Text(buildString {
                        append("d")
                        append(stat.dieSize)
                        if (stat.bonus > 0) append(" +${stat.bonus}")
                        else if (stat.bonus < 0) append(" ${stat.bonus}")
                    })
                }
            }
        }
    }
}

@Composable
private fun ImprovementsList(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    LazyColumn(modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(snapshot.improvements, key = { it.id ?: "${it.name}:${it.sortOrder}" }) { improvement ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(improvement.name, fontWeight = FontWeight.Bold)
                        if (improvement.cost > 0) Text("${improvement.cost} IP")
                    }
                    if (improvement.description.isNotBlank()) Text(improvement.description)
                    improvement.empowerments.forEach { empowerment ->
                        HorizontalDivider()
                        Text(empowerment.name, fontWeight = FontWeight.SemiBold)
                        if (empowerment.description.isNotBlank()) Text(empowerment.description)
                    }
                }
            }
        }
    }
}

@Composable
private fun EquipmentPage(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    LazyColumn(modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (snapshot.inventory.isEmpty()) {
            item { Text("No equipment.") }
        }
        items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(item.name.ifBlank { "Unnamed item" }, fontWeight = FontWeight.Bold)
                        if (item.quantity != 1) Text("×${item.quantity}")
                    }
                    if (item.description.isNotBlank()) Text(item.description)
                }
            }
        }
    }
}

@Composable
private fun NotesPage(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    val notes = snapshot.notes.sortedWith(compareByDescending<NoteSnapshot> { it.pinned }.thenBy { it.title.lowercase() })
    LazyColumn(modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (notes.isEmpty()) item { Text("No notes.") }
        items(notes, key = { it.id ?: "${it.title}:${it.text.hashCode()}" }) { note ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(note.title.ifBlank { "Note" }, fontWeight = FontWeight.Bold)
                        if (note.pinned) Text("Pinned")
                    }
                    if (note.text.isNotBlank()) Text(note.text)
                    note.linkedImprovementId?.let { Text("Linked improvement", style = MaterialTheme.typography.labelSmall) }
                }
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}
