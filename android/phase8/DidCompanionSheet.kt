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
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.did.charactersheet.ui.DidPalette
import org.json.JSONObject

/**
 * Phone reinterpretation of the finished Windows DID sheet.
 *
 * Windows remains authoritative. Local expansion/navigation state is UI-only;
 * every game-state mutation still goes through the companion protocol.
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

        BottomSheetNavigation(page = page, onPage = { page = it })
    }
}

private enum class CompanionPage(val label: String, val symbol: String) {
    Character("Character", "◆"),
    Equipment("Equipment", "▣"),
    Notes("Notes", "✎"),
}

@Composable
private fun BottomSheetNavigation(page: CompanionPage, onPage: (CompanionPage) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 8.dp,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        NavigationBar(
            containerColor = Color.Transparent,
            tonalElevation = 0.dp,
        ) {
            CompanionPage.entries.forEach { item ->
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
private fun CharacterPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }

    Column(modifier.fillMaxSize()) {
        CharacterHeader(snapshot)
        ResourcePanel(snapshot, controlsEnabled, onHpChange, onAtChange, onIpChange)

        TabRow(
            selectedTabIndex = tab,
            containerColor = MaterialTheme.colorScheme.surface,
            contentColor = MaterialTheme.colorScheme.onSurface,
            divider = {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            },
        ) {
            listOf("Abilities", "Improvements").forEachIndexed { index, label ->
                Tab(
                    selected = tab == index,
                    onClick = { tab = index },
                    text = {
                        Text(
                            label,
                            fontWeight = if (tab == index) FontWeight.Black else FontWeight.Bold,
                        )
                    },
                )
            }
        }

        if (tab == 0) AbilitiesList(snapshot, Modifier.fillMaxSize())
        else ImprovementsList(snapshot, Modifier.fillMaxSize())
    }
}

@Composable
private fun CharacterHeader(snapshot: DidCharacterSnapshot) {
    SheetCard(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 10.dp, vertical = 7.dp),
        surface = true,
    ) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Portrait(snapshot, Modifier.width(104.dp).aspectRatio(0.78f))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    snapshot.name.ifBlank { "Unnamed Character" },
                    style = MaterialTheme.typography.headlineSmall,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
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
                if (snapshot.combatModeEnabled) {
                    Text(
                        "COMBAT MODE",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Black,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}

@Composable
private fun Portrait(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    val raw = snapshot.portrait.currentImage?.data
    val bitmap = remember(raw) { raw?.decodeDataUriBitmap() }
    val shape = RoundedCornerShape(10.dp)

    Box(
        modifier = modifier
            .clip(shape)
            .background(MaterialTheme.colorScheme.secondaryContainer),
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(
                bitmap = bitmap.asImageBitmap(),
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

private fun String.decodeDataUriBitmap() = runCatching {
    val payload = substringAfter("base64,", this)
    val bytes = Base64.decode(payload, Base64.DEFAULT)
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
}.getOrNull()

@Composable
private fun ResourcePanel(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    SheetCard(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp),
        surface = true,
    ) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Hearts", style = MaterialTheme.typography.labelLarge)
                    HeartMeter(snapshot.hp)
                }
                Spacer(Modifier.width(8.dp))
                DefenseBox("BDV", snapshot.bdv.toString())
                Spacer(Modifier.width(5.dp))
                DefenseBox("DR", snapshot.dr.toString())
            }

            HorizontalDivider(
                Modifier.padding(vertical = 7.dp),
                color = MaterialTheme.colorScheme.outlineVariant,
            )

            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ResourceIdentity(
                    title = "HP",
                    value = "${snapshot.hp.current} / ${snapshot.hp.max}",
                    modifier = Modifier.weight(1f),
                )
                DeltaButtons(enabled, snapshot.hp.current > 0, snapshot.hp.current < snapshot.hp.max, onHpChange)
            }

            Row(
                Modifier.fillMaxWidth().padding(top = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Adversity", style = MaterialTheme.typography.labelLarge)
                    AdversityMeter(snapshot.adversity)
                }
                DeltaButtons(
                    enabled,
                    snapshot.adversity.current > 0,
                    snapshot.adversity.current < snapshot.adversity.max,
                    onAtChange,
                )
            }

            Row(
                Modifier.fillMaxWidth().padding(top = 5.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ResourceIdentity(
                    title = "Improvement Points",
                    value = "${snapshot.progression.currentIp} IP   •   Level ${snapshot.progression.level}",
                    modifier = Modifier.weight(1f),
                )
                DeltaButtons(enabled, snapshot.progression.currentIp > 0, true, onIpChange)
            }
        }
    }
}

@Composable
private fun HeartMeter(hp: HpSnapshot) {
    val hearts = hp.maxHearts.coerceAtLeast(((hp.max + 3) / 4).coerceAtLeast(1))
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        repeat(hearts) { heartIndex ->
            val filled = (hp.current - heartIndex * 4).coerceIn(0, 4)
            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(5.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(horizontal = 3.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                repeat(4) { segment ->
                    Box(
                        Modifier
                            .width(5.dp)
                            .height(16.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(
                                if (segment < filled) DidPalette.Heart else DidPalette.HeartEmpty
                            )
                    )
                }
            }
        }
    }
}

@Composable
private fun AdversityMeter(at: AdversitySnapshot) {
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        repeat(at.max.coerceAtLeast(0)) { index ->
            Box(
                Modifier
                    .size(15.dp)
                    .clip(CircleShape)
                    .background(
                        if (index < at.current) DidPalette.Adversity
                        else MaterialTheme.colorScheme.surfaceVariant
                    )
            )
        }
        Text(
            "  ${at.current} / ${at.max}",
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

@Composable
private fun DefenseBox(label: String, value: String) {
    Surface(
        shape = RoundedCornerShape(7.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            Modifier.width(46.dp).padding(vertical = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(label, style = MaterialTheme.typography.labelSmall)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun ResourceIdentity(title: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(title, style = MaterialTheme.typography.labelLarge)
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
    }
}

@Composable
private fun DeltaButtons(
    enabled: Boolean,
    canDecrease: Boolean,
    canIncrease: Boolean,
    onChange: (Int) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        OutlinedButton(
            onClick = { onChange(-1) },
            enabled = enabled && canDecrease,
            contentPadding = ButtonDefaults.TextButtonContentPadding,
            modifier = Modifier.width(48.dp),
        ) { Text("−", fontWeight = FontWeight.Black) }
        Button(
            onClick = { onChange(1) },
            enabled = enabled && canIncrease,
            contentPadding = ButtonDefaults.TextButtonContentPadding,
            modifier = Modifier.width(48.dp),
        ) { Text("+", fontWeight = FontWeight.Black) }
    }
}

@Composable
private fun AbilitiesList(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    val sorted = snapshot.stats.sortedWith(
        compareByDescending<StatSnapshot> { it.dieSize }
            .thenByDescending { it.bonus }
            .thenBy { it.key }
    )

    LazyColumn(
        modifier.padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        item {
            SectionHeading(
                title = "Abilities",
                subtitle = snapshot.defenseStatName?.let { "Defense: $it" },
            )
        }
        items(sorted, key = { it.key }) { stat ->
            val isDefense = stat.name == snapshot.defenseStatName
            SheetCard(modifier = Modifier.fillMaxWidth(), surface = false) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text(stat.name, fontWeight = FontWeight.Black)
                        if (isDefense) {
                            Text(
                                "Defense ability",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.secondary,
                            )
                        }
                    }
                    Surface(
                        shape = RoundedCornerShape(9.dp),
                        color = MaterialTheme.colorScheme.primaryContainer,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    ) {
                        Text(
                            buildString {
                                append("d")
                                append(stat.dieSize)
                                if (stat.bonus > 0) append(" +${stat.bonus}")
                                else if (stat.bonus < 0) append(" ${stat.bonus}")
                            },
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
private fun ImprovementsList(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    val improvements = snapshot.improvements.sortedWith(
        compareBy<ImprovementSnapshot> { it.sortOrder }.thenBy { it.name.lowercase() }
    )
    LazyColumn(
        modifier.padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        item {
            SectionHeading(
                title = "Improvements",
                trailing = "${snapshot.progression.currentIp} IP",
            )
        }
        if (improvements.isEmpty()) item { EmptySection("No improvements yet.") }
        items(improvements, key = { it.id ?: "${it.name}:${it.sortOrder}" }) { improvement ->
            ImprovementCard(improvement)
        }
        item { Spacer(Modifier.height(4.dp)) }
    }
}

@Composable
private fun ImprovementCard(improvement: ImprovementSnapshot) {
    var expanded by remember(improvement.id, improvement.expanded) {
        mutableStateOf(improvement.expanded || improvement.description.isNotBlank())
    }
    SheetCard(
        modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded },
        surface = false,
    ) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (expanded) "▾" else "▸",
                    modifier = Modifier.width(20.dp),
                    color = MaterialTheme.colorScheme.secondary,
                    fontWeight = FontWeight.Black,
                )
                Text(improvement.name, Modifier.weight(1f), fontWeight = FontWeight.Black)
                if (improvement.timesTaken > 1) {
                    Text("×${improvement.timesTaken}  ", style = MaterialTheme.typography.labelMedium)
                }
                if (improvement.cost > 0) {
                    Text("${improvement.cost} IP", fontWeight = FontWeight.Bold)
                }
            }

            if (expanded) {
                if (improvement.description.isNotBlank()) {
                    Text(improvement.description, style = MaterialTheme.typography.bodyMedium)
                }
                choicesSummary(improvement.choices)?.let {
                    Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                improvement.empowerments.forEach { empowerment ->
                    Surface(
                        modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    ) {
                        Column(Modifier.padding(9.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Row(Modifier.fillMaxWidth()) {
                                Text(empowerment.name, Modifier.weight(1f), fontWeight = FontWeight.Bold)
                                if (empowerment.cost > 0) Text("${empowerment.cost} IP", style = MaterialTheme.typography.labelMedium)
                            }
                            if (empowerment.description.isNotBlank()) {
                                Text(empowerment.description, style = MaterialTheme.typography.bodySmall)
                            }
                            choicesSummary(empowerment.choices)?.let {
                                Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun choicesSummary(choices: JSONObject?): String? {
    if (choices == null || choices.length() == 0) return null
    val entries = choices.keys().asSequence()
        .filterNot { it.startsWith("_") }
        .mapNotNull { key ->
            val value = choices.opt(key)?.toString()?.takeIf { it.isNotBlank() && it != "null" } ?: return@mapNotNull null
            "${key.replace('_', ' ').replaceFirstChar { it.titlecase() }}: $value"
        }
        .toList()
    return entries.takeIf { it.isNotEmpty() }?.joinToString(" • ")
}

@Composable
private fun EquipmentPage(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    LazyColumn(
        modifier.padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        item { SectionHeading("Inventory", trailing = "${snapshot.inventory.size} items") }
        if (snapshot.inventory.isEmpty()) item { EmptySection("No equipment.") }
        items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
            var expanded by remember(item.id, item.expanded) { mutableStateOf(item.expanded) }
            SheetCard(
                modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded },
                surface = false,
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(if (expanded) "▾" else "▸", Modifier.width(20.dp), color = MaterialTheme.colorScheme.secondary)
                        Text(item.name.ifBlank { "Unnamed item" }, Modifier.weight(1f), fontWeight = FontWeight.Black)
                        Surface(
                            shape = RoundedCornerShape(7.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        ) {
                            Text(
                                "×${item.quantity}",
                                Modifier.padding(horizontal = 9.dp, vertical = 4.dp),
                                fontWeight = FontWeight.Black,
                            )
                        }
                    }
                    if (expanded && item.description.isNotBlank()) {
                        Text(item.description, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
        item { Spacer(Modifier.height(4.dp)) }
    }
}

@Composable
private fun NotesPage(snapshot: DidCharacterSnapshot, modifier: Modifier = Modifier) {
    val notes = snapshot.notes.sortedWith(
        compareByDescending<NoteSnapshot> { it.pinned }.thenBy { it.title.lowercase() }
    )
    LazyColumn(
        modifier.padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item { SectionHeading("Notes", trailing = notes.size.toString()) }
        if (notes.isEmpty()) item { EmptySection("No notes.") }
        items(notes, key = { it.id ?: "${it.title}:${it.text.hashCode()}" }) { note ->
            NoteCard(note)
        }
        item { Spacer(Modifier.height(4.dp)) }
    }
}

@Composable
private fun NoteCard(note: NoteSnapshot) {
    var expanded by remember(note.id, note.expanded) { mutableStateOf(note.expanded) }
    val colors = noteColors(note.color)
    Card(
        modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded },
        shape = RoundedCornerShape(11.dp),
        colors = CardDefaults.cardColors(containerColor = colors.second),
        border = BorderStroke(1.5.dp, colors.first),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(if (expanded) "▾" else "▸", Modifier.width(20.dp), color = MaterialTheme.colorScheme.onSurface)
                Text(note.title.ifBlank { "Note" }, Modifier.weight(1f), fontWeight = FontWeight.Black)
                if (note.pinned) {
                    Text("★", color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Black)
                }
            }
            if (expanded && note.text.isNotBlank()) {
                Text(note.text, style = MaterialTheme.typography.bodyMedium)
            }
            if (expanded && note.linkedImprovementId != null) {
                Text(
                    "Linked to improvement",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun noteColors(value: String?): Pair<Color, Color> {
    val dark = isSystemInDarkTheme()
    val lightOuter = mapOf(
        "red" to 0xFFF3A6A6,
        "orange" to 0xFFFFC078,
        "yellow" to 0xFFFFE98A,
        "green" to 0xFFA8E6B0,
        "blue" to 0xFF9FCFE3,
        "purple" to 0xFFC8B6FF,
        "pink" to 0xFFF4B6CF,
    )
    val lightBody = mapOf(
        "red" to 0xFFF8CACA,
        "orange" to 0xFFFFD7AA,
        "yellow" to 0xFFFFF2B8,
        "green" to 0xFFC9EFCE,
        "blue" to 0xFFC7E5F1,
        "purple" to 0xFFDED5FF,
        "pink" to 0xFFF8D2E2,
    )
    val darkOuter = mapOf(
        "red" to 0xFF5A3333,
        "orange" to 0xFF60452F,
        "yellow" to 0xFF5E5530,
        "green" to 0xFF31563A,
        "blue" to 0xFF2F4E5B,
        "purple" to 0xFF463E60,
        "pink" to 0xFF5A3A49,
    )
    val darkBody = mapOf(
        "red" to 0xFF382526,
        "orange" to 0xFF3C3025,
        "yellow" to 0xFF3A3725,
        "green" to 0xFF243629,
        "blue" to 0xFF24343B,
        "purple" to 0xFF302B3D,
        "pink" to 0xFF392A31,
    )
    val key = value?.lowercase() ?: "yellow"
    val custom = value?.takeIf { it.matches(Regex("#[0-9a-fA-F]{6}")) }?.let { hex ->
        runCatching { Color(android.graphics.Color.parseColor(hex)) }.getOrNull()
    }
    if (custom != null) return custom to custom.copy(alpha = if (dark) 0.45f else 0.55f)
    val outer = if (dark) darkOuter[key] else lightOuter[key]
    val body = if (dark) darkBody[key] else lightBody[key]
    return Color(outer ?: if (dark) 0xFF5E5530 else 0xFFFFE98A) to
        Color(body ?: if (dark) 0xFF3A3725 else 0xFFFFF2B8)
}

@Composable
private fun SectionHeading(title: String, subtitle: String? = null, trailing: String? = null) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 3.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onBackground)
            subtitle?.let {
                Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        trailing?.let {
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(7.dp),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            ) {
                Text(it, Modifier.padding(horizontal = 10.dp, vertical = 5.dp), fontWeight = FontWeight.Black)
            }
        }
    }
}

@Composable
private fun EmptySection(text: String) {
    SheetCard(Modifier.fillMaxWidth(), surface = false) {
        Text(
            text,
            Modifier.fillMaxWidth().padding(18.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SheetCard(
    modifier: Modifier = Modifier,
    surface: Boolean,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (surface) MaterialTheme.colorScheme.surface
            else MaterialTheme.colorScheme.secondaryContainer,
        ),
        border = BorderStroke(
            if (surface) 2.dp else 1.5.dp,
            if (surface) MaterialTheme.colorScheme.outlineVariant
            else MaterialTheme.colorScheme.outline,
        ),
    ) {
        content()
    }
}
