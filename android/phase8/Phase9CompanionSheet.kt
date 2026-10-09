package com.did.charactersheet.sync

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.did.charactersheet.ui.DidPalette
import org.json.JSONObject

/** Polished Phase 9 phone layout derived from the finished Windows redesign. */
@Composable
fun Phase9CompanionSheet(
    snapshot: DidCharacterSnapshot,
    connected: Boolean,
    pending: Boolean,
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
    var page by remember { mutableStateOf(Phase9Page.Character) }
    var identityEdit by remember { mutableStateOf<IdentityEdit?>(null) }
    var inventoryEdit by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    var addingInventory by remember { mutableStateOf(false) }
    val canEdit = connected && !pending

    Column(modifier.fillMaxSize()) {
        when (page) {
            Phase9Page.Character -> Phase9CharacterPage(
                snapshot = snapshot,
                controlsEnabled = canEdit,
                onHpChange = onHpChange,
                onAtChange = onAtChange,
                onIpChange = onIpChange,
                onEditName = { identityEdit = IdentityEdit.Name },
                onEditBackstory = { identityEdit = IdentityEdit.Backstory },
                modifier = Modifier.weight(1f),
            )
            Phase9Page.Equipment -> Phase9EquipmentPage(
                snapshot = snapshot,
                controlsEnabled = canEdit,
                onAdd = { addingInventory = true },
                onEdit = { inventoryEdit = it },
                modifier = Modifier.weight(1f),
            )
            Phase9Page.Notes -> Phase9NotesPage(snapshot, Modifier.weight(1f))
        }
        Phase9BottomNavigation(page = page, onPage = { page = it })
    }

    when (identityEdit) {
        IdentityEdit.Name -> Phase9TextDialog(
            title = "Character name",
            initial = snapshot.name,
            multiline = false,
            onDismiss = { identityEdit = null },
            onSave = {
                onSetName(it)
                identityEdit = null
            },
        )
        IdentityEdit.Backstory -> Phase9TextDialog(
            title = "Backstory",
            initial = snapshot.backstory,
            multiline = true,
            onDismiss = { identityEdit = null },
            onSave = {
                onSetBackstory(it)
                identityEdit = null
            },
        )
        null -> Unit
    }

    if (addingInventory || inventoryEdit != null) {
        Phase9InventoryEditDialog(
            item = inventoryEdit,
            onDismiss = {
                addingInventory = false
                inventoryEdit = null
            },
            onSave = { name, description, quantity ->
                val item = inventoryEdit
                if (item?.id != null) {
                    onUpdateInventoryItem(item.id, name, description, quantity)
                } else {
                    onAddInventoryItem(name, description, quantity)
                }
                addingInventory = false
                inventoryEdit = null
            },
            onRemove = inventoryEdit?.id?.let { id ->
                {
                    onRemoveInventoryItem(id)
                    inventoryEdit = null
                }
            },
        )
    }
}

private enum class Phase9Page(val label: String, val symbol: String) {
    Character("Character", "◆"), Equipment("Equipment", "▣"), Notes("Notes", "✎")
}

private enum class IdentityEdit { Name, Backstory }

@Composable
private fun Phase9BottomNavigation(page: Phase9Page, onPage: (Phase9Page) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 8.dp,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        NavigationBar(containerColor = Color.Transparent, tonalElevation = 0.dp) {
            Phase9Page.entries.forEach { item ->
                NavigationBarItem(
                    selected = page == item,
                    onClick = { onPage(item) },
                    icon = { Text(item.symbol, fontWeight = FontWeight.Black) },
                    label = { Text(item.label) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                        selectedTextColor = MaterialTheme.colorScheme.onSurface,
                        indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                        unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                )
            }
        }
    }
}

@Composable
private fun Phase9CharacterPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    onEditName: () -> Unit,
    onEditBackstory: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }
    Column(modifier.fillMaxSize()) {
        Phase9CharacterHeader(snapshot, controlsEnabled, onEditName, onEditBackstory)
        Phase9ResourcePanel(snapshot, controlsEnabled, onHpChange, onAtChange, onIpChange)
        TabRow(
            selectedTabIndex = tab,
            containerColor = MaterialTheme.colorScheme.surface,
            contentColor = MaterialTheme.colorScheme.onSurface,
            divider = { HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant) },
        ) {
            listOf("Abilities", "Improvements").forEachIndexed { index, label ->
                Tab(
                    selected = tab == index,
                    onClick = { tab = index },
                    text = { Text(label, fontWeight = if (tab == index) FontWeight.Black else FontWeight.Bold) },
                )
            }
        }
        if (tab == 0) Phase9Abilities(snapshot, Modifier.fillMaxSize())
        else Phase9Improvements(snapshot, Modifier.fillMaxSize())
    }
}

@Composable
private fun Phase9CharacterHeader(
    snapshot: DidCharacterSnapshot,
    canEdit: Boolean,
    onEditName: () -> Unit,
    onEditBackstory: () -> Unit,
) {
    Phase9SheetCard(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 7.dp),
        strongBorder = true,
    ) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Phase9Portrait(snapshot, Modifier.width(104.dp).aspectRatio(0.78f))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        snapshot.name.ifBlank { "Unnamed Character" },
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.headlineSmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    TextButton(onClick = onEditName, enabled = canEdit) { Text("Edit") }
                }
                if (snapshot.speciesName.isNotBlank()) {
                    Text(
                        snapshot.speciesName,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
                if (snapshot.backstory.isNotBlank()) {
                    Text(
                        snapshot.backstory,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                TextButton(
                    onClick = onEditBackstory,
                    enabled = canEdit,
                    contentPadding = ButtonDefaults.TextButtonContentPadding,
                ) { Text(if (snapshot.backstory.isBlank()) "+ Backstory" else "Edit backstory") }
                if (snapshot.combatModeEnabled) {
                    Text(
                        "COMBAT MODE",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.error,
                        fontWeight = FontWeight.Black,
                    )
                }
            }
        }
    }
}

@Composable
private fun Phase9Portrait(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val raw = snapshot.portrait.currentImage?.data
    val bitmap = remember(raw) { raw?.phase9DecodeBitmap() }
    Box(
        modifier.clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.secondaryContainer),
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(
                bitmap.asImageBitmap(),
                contentDescription = "Character portrait",
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Text(
                snapshot.name.trim().take(1).uppercase().ifBlank { "D" },
                style = MaterialTheme.typography.displaySmall,
                color = MaterialTheme.colorScheme.secondary,
                fontWeight = FontWeight.Black,
            )
        }
    }
}

private fun String.phase9DecodeBitmap() = runCatching {
    val bytes = Base64.decode(substringAfter("base64,", this), Base64.DEFAULT)
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
}.getOrNull()

@Composable
private fun Phase9ResourcePanel(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    Phase9SheetCard(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp),
        strongBorder = true,
    ) {
        Column(Modifier.fillMaxWidth().padding(10.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Hearts", style = MaterialTheme.typography.labelLarge)
                    Phase9Hearts(snapshot.hp)
                }
                Phase9DefenseBox("BDV", snapshot.bdv)
                Spacer(Modifier.width(5.dp))
                Phase9DefenseBox("DR", snapshot.dr)
            }
            HorizontalDivider(Modifier.padding(vertical = 7.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Phase9ResourceRow(
                "HP", "${snapshot.hp.current} / ${snapshot.hp.max}", enabled,
                snapshot.hp.current > 0, snapshot.hp.current < snapshot.hp.max, onHpChange,
            )
            Row(Modifier.fillMaxWidth().padding(top = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Adversity", style = MaterialTheme.typography.labelLarge)
                    Phase9Adversity(snapshot.adversity)
                }
                Phase9DeltaButtons(
                    enabled,
                    snapshot.adversity.current > 0,
                    snapshot.adversity.current < snapshot.adversity.max,
                    onAtChange,
                )
            }
            Phase9ResourceRow(
                "Improvement Points",
                "${snapshot.progression.currentIp} IP  •  Level ${snapshot.progression.level}",
                enabled,
                snapshot.progression.currentIp > 0,
                true,
                onIpChange,
            )
        }
    }
}

@Composable
private fun Phase9ResourceRow(
    title: String,
    value: String,
    enabled: Boolean,
    canDown: Boolean,
    canUp: Boolean,
    onChange: (Int) -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().padding(top = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.labelLarge)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
        }
        Phase9DeltaButtons(enabled, canDown, canUp, onChange)
    }
}

@Composable
private fun Phase9DeltaButtons(enabled: Boolean, canDown: Boolean, canUp: Boolean, onChange: (Int) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        OutlinedButton(
            onClick = { onChange(-1) },
            enabled = enabled && canDown,
            modifier = Modifier.width(48.dp),
            contentPadding = ButtonDefaults.TextButtonContentPadding,
        ) { Text("−", fontWeight = FontWeight.Black) }
        Button(
            onClick = { onChange(1) },
            enabled = enabled && canUp,
            modifier = Modifier.width(48.dp),
            contentPadding = ButtonDefaults.TextButtonContentPadding,
        ) { Text("+", fontWeight = FontWeight.Black) }
    }
}

@Composable
private fun Phase9Hearts(hp: HpSnapshot) {
    val hearts = hp.maxHearts.coerceAtLeast(((hp.max + 3) / 4).coerceAtLeast(1))
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        repeat(hearts) { heart ->
            val filled = (hp.current - heart * 4).coerceIn(0, 4)
            Row(
                Modifier.clip(RoundedCornerShape(5.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(horizontal = 3.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                repeat(4) { segment ->
                    Box(
                        Modifier.width(5.dp).height(16.dp).clip(RoundedCornerShape(2.dp))
                            .background(if (segment < filled) DidPalette.Heart else DidPalette.HeartEmpty)
                    )
                }
            }
        }
    }
}

@Composable
private fun Phase9Adversity(at: AdversitySnapshot) {
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(at.max.coerceAtLeast(0)) { index ->
            Box(
                Modifier.size(15.dp).clip(CircleShape)
                    .background(if (index < at.current) DidPalette.Adversity else MaterialTheme.colorScheme.surfaceVariant)
            )
        }
        Text("${at.current}/${at.max}", style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun Phase9DefenseBox(label: String, value: Int) {
    Surface(
        shape = RoundedCornerShape(7.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.width(46.dp).padding(vertical = 4.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, style = MaterialTheme.typography.labelSmall)
            Text(value.toString(), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun Phase9Abilities(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val sorted = snapshot.stats.sortedWith(
        compareByDescending<StatSnapshot> { it.dieSize }.thenByDescending { it.bonus }.thenBy { it.key }
    )
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        item { Phase9Heading("Abilities", snapshot.defenseStatName?.let { "Defense: $it" }) }
        items(sorted, key = { it.key }) { stat ->
            Phase9SheetCard(Modifier.fillMaxWidth(), strongBorder = false) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(stat.name, fontWeight = FontWeight.Black)
                        if (stat.name == snapshot.defenseStatName) {
                            Text("Defense ability", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                        }
                    }
                    Surface(
                        shape = RoundedCornerShape(9.dp),
                        color = MaterialTheme.colorScheme.primaryContainer,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    ) {
                        Text(
                            "d${stat.dieSize}${if (stat.bonus > 0) " +${stat.bonus}" else if (stat.bonus < 0) " ${stat.bonus}" else ""}",
                            Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                            fontWeight = FontWeight.Black,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun Phase9Improvements(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val improvements = snapshot.improvements.sortedWith(compareBy<ImprovementSnapshot> { it.sortOrder }.thenBy { it.name.lowercase() })
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item { Phase9Heading("Improvements", trailing = "${snapshot.progression.currentIp} IP") }
        if (improvements.isEmpty()) item { Phase9Empty("No improvements yet.") }
        items(improvements, key = { it.id ?: "${it.name}:${it.sortOrder}" }) { improvement ->
            var expanded by remember(improvement.id, improvement.expanded) { mutableStateOf(improvement.expanded || improvement.description.isNotBlank()) }
            Phase9SheetCard(Modifier.fillMaxWidth().clickable { expanded = !expanded }, false) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth()) {
                        Text(if (expanded) "▾" else "▸", Modifier.width(20.dp), color = MaterialTheme.colorScheme.secondary)
                        Text(improvement.name, Modifier.weight(1f), fontWeight = FontWeight.Black)
                        if (improvement.timesTaken > 1) Text("×${improvement.timesTaken}  ")
                        if (improvement.cost > 0) Text("${improvement.cost} IP", fontWeight = FontWeight.Bold)
                    }
                    if (expanded) {
                        if (improvement.description.isNotBlank()) Text(improvement.description)
                        phase9Choices(improvement.choices)?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        improvement.empowerments.forEach { empowerment ->
                            Surface(
                                Modifier.fillMaxWidth().padding(top = 2.dp),
                                shape = RoundedCornerShape(8.dp),
                                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                            ) {
                                Column(Modifier.padding(9.dp)) {
                                    Row(Modifier.fillMaxWidth()) {
                                        Text(empowerment.name, Modifier.weight(1f), fontWeight = FontWeight.Bold)
                                        if (empowerment.cost > 0) Text("${empowerment.cost} IP", style = MaterialTheme.typography.labelMedium)
                                    }
                                    if (empowerment.description.isNotBlank()) Text(empowerment.description, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun phase9Choices(choices: JSONObject?): String? {
    if (choices == null || choices.length() == 0) return null
    val parts = choices.keys().asSequence().filterNot { it.startsWith("_") }.mapNotNull { key ->
        val value = choices.opt(key)?.toString()?.takeIf { it.isNotBlank() && it != "null" } ?: return@mapNotNull null
        "${key.replace('_', ' ').replaceFirstChar { it.titlecase() }}: $value"
    }.toList()
    return parts.takeIf { it.isNotEmpty() }?.joinToString(" • ")
}

@Composable
private fun Phase9EquipmentPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onAdd: () -> Unit,
    onEdit: (InventoryItemSnapshot) -> Unit,
    modifier: Modifier,
) {
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Phase9Heading("Inventory", trailing = "${snapshot.inventory.size} items", modifier = Modifier.weight(1f))
                Spacer(Modifier.width(6.dp))
                Button(onClick = onAdd, enabled = controlsEnabled) { Text("+ Add") }
            }
        }
        if (snapshot.inventory.isEmpty()) item { Phase9Empty("No equipment.") }
        items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
            var expanded by remember(item.id, item.expanded) { mutableStateOf(item.expanded) }
            Phase9SheetCard(Modifier.fillMaxWidth(), false) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (expanded) "▾" else "▸",
                            Modifier.width(22.dp).clickable { expanded = !expanded },
                            color = MaterialTheme.colorScheme.secondary,
                        )
                        Text(
                            item.name.ifBlank { "Unnamed item" },
                            Modifier.weight(1f).clickable { expanded = !expanded },
                            fontWeight = FontWeight.Black,
                        )
                        Surface(
                            shape = RoundedCornerShape(7.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        ) {
                            Text("×${item.quantity}", Modifier.padding(horizontal = 8.dp, vertical = 4.dp), fontWeight = FontWeight.Black)
                        }
                        Spacer(Modifier.width(5.dp))
                        OutlinedButton(onClick = { onEdit(item) }, enabled = controlsEnabled) { Text("Edit") }
                    }
                    if (expanded && item.description.isNotBlank()) Text(item.description)
                }
            }
        }
    }
}

@Composable
private fun Phase9NotesPage(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val notes = snapshot.notes.sortedWith(compareByDescending<NoteSnapshot> { it.pinned }.thenBy { it.title.lowercase() })
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Phase9Heading("Notes", trailing = notes.size.toString()) }
        if (notes.isEmpty()) item { Phase9Empty("No notes.") }
        items(notes, key = { it.id ?: "${it.title}:${it.text.hashCode()}" }) { note ->
            var expanded by remember(note.id, note.expanded) { mutableStateOf(note.expanded) }
            val colors = phase9NoteColors(note.color)
            Card(
                modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded },
                shape = RoundedCornerShape(11.dp),
                colors = CardDefaults.cardColors(containerColor = colors.second),
                border = BorderStroke(1.5.dp, colors.first),
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth()) {
                        Text(if (expanded) "▾" else "▸", Modifier.width(20.dp))
                        Text(note.title.ifBlank { "Note" }, Modifier.weight(1f), fontWeight = FontWeight.Black)
                        if (note.pinned) Text("★", color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Black)
                    }
                    if (expanded && note.text.isNotBlank()) Text(note.text)
                    if (expanded && note.linkedImprovementId != null) {
                        Text("Linked to improvement", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun phase9NoteColors(value: String?): Pair<Color, Color> {
    val dark = isSystemInDarkTheme()
    val outer = if (dark) mapOf(
        "red" to 0xFF5A3333, "orange" to 0xFF60452F, "yellow" to 0xFF5E5530,
        "green" to 0xFF31563A, "blue" to 0xFF2F4E5B, "purple" to 0xFF463E60, "pink" to 0xFF5A3A49,
    ) else mapOf(
        "red" to 0xFFF3A6A6, "orange" to 0xFFFFC078, "yellow" to 0xFFFFE98A,
        "green" to 0xFFA8E6B0, "blue" to 0xFF9FCFE3, "purple" to 0xFFC8B6FF, "pink" to 0xFFF4B6CF,
    )
    val body = if (dark) mapOf(
        "red" to 0xFF382526, "orange" to 0xFF3C3025, "yellow" to 0xFF3A3725,
        "green" to 0xFF243629, "blue" to 0xFF24343B, "purple" to 0xFF302B3D, "pink" to 0xFF392A31,
    ) else mapOf(
        "red" to 0xFFF8CACA, "orange" to 0xFFFFD7AA, "yellow" to 0xFFFFF2B8,
        "green" to 0xFFC9EFCE, "blue" to 0xFFC7E5F1, "purple" to 0xFFDED5FF, "pink" to 0xFFF8D2E2,
    )
    val key = value?.lowercase() ?: "yellow"
    val custom = value?.takeIf { it.matches(Regex("#[0-9a-fA-F]{6}")) }?.let {
        runCatching { Color(android.graphics.Color.parseColor(it)) }.getOrNull()
    }
    if (custom != null) return custom to custom.copy(alpha = if (dark) 0.45f else 0.55f)
    return Color(outer[key] ?: outer.getValue("yellow")) to Color(body[key] ?: body.getValue("yellow"))
}

@Composable
private fun Phase9Heading(
    title: String,
    subtitle: String? = null,
    trailing: String? = null,
    modifier: Modifier = Modifier,
) {
    Row(modifier.fillMaxWidth().padding(horizontal = 3.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            subtitle?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        trailing?.let {
            Surface(
                shape = RoundedCornerShape(7.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            ) { Text(it, Modifier.padding(horizontal = 10.dp, vertical = 5.dp), fontWeight = FontWeight.Black) }
        }
    }
}

@Composable
private fun Phase9Empty(text: String) {
    Phase9SheetCard(Modifier.fillMaxWidth(), false) {
        Text(text, Modifier.fillMaxWidth().padding(18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Phase9SheetCard(modifier: Modifier, strongBorder: Boolean, content: @Composable () -> Unit) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(
            if (strongBorder) 2.dp else 1.5.dp,
            if (strongBorder) MaterialTheme.colorScheme.outlineVariant else MaterialTheme.colorScheme.outline,
        ),
        content = { content() },
    )
}

@Composable
private fun Phase9TextDialog(
    title: String,
    initial: String,
    multiline: Boolean,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
    var value by remember(initial) { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title, fontWeight = FontWeight.Black) },
        text = {
            OutlinedTextField(
                value = value,
                onValueChange = { value = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = !multiline,
                minLines = if (multiline) 5 else 1,
                maxLines = if (multiline) 12 else 1,
            )
        },
        confirmButton = { Button(onClick = { onSave(value) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun Phase9InventoryEditDialog(
    item: InventoryItemSnapshot?,
    onDismiss: () -> Unit,
    onSave: (String, String, Int) -> Unit,
    onRemove: (() -> Unit)?,
) {
    var name by remember(item?.id) { mutableStateOf(item?.name.orEmpty()) }
    var description by remember(item?.id) { mutableStateOf(item?.description.orEmpty()) }
    var quantity by remember(item?.id) { mutableStateOf((item?.quantity ?: 1).toString()) }
    var confirmDelete by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (item == null) "Add inventory item" else "Edit inventory item", fontWeight = FontWeight.Black) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), label = { Text("Name") }, singleLine = true)
                OutlinedTextField(
                    description,
                    { description = it },
                    Modifier.fillMaxWidth(),
                    label = { Text("Description") },
                    minLines = 3,
                    maxLines = 8,
                )
                OutlinedTextField(
                    quantity,
                    { next -> if (next.all { it.isDigit() }) quantity = next },
                    Modifier.fillMaxWidth(),
                    label = { Text("Quantity") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            Button(
                enabled = quantity.toIntOrNull() != null,
                onClick = { onSave(name, description, quantity.toIntOrNull() ?: 0) },
            ) { Text("Save") }
        },
        dismissButton = {
            Row {
                if (onRemove != null) {
                    TextButton(onClick = { confirmDelete = true }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
                }
                TextButton(onClick = onDismiss) { Text("Cancel") }
            }
        },
    )

    if (confirmDelete && onRemove != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete item?") },
            text = { Text("This removes the item from the Windows character too.") },
            confirmButton = {
                Button(
                    onClick = onRemove,
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                ) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}
