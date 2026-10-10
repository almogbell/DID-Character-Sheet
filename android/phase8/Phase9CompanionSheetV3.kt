package com.did.charactersheet.sync

import android.graphics.BitmapFactory
import android.graphics.drawable.PictureDrawable
import android.util.Base64
import android.view.View
import android.widget.ImageView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
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
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.caverock.androidsvg.SVG
import org.json.JSONObject

/**
 * Phase 9 V3 phone UI. This pass uses the real SVG artwork supplied by the
 * connected Windows installation and mirrors desktop click semantics for HP/AT.
 */
@Composable
fun Phase9CompanionSheetV3(
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
    var page by remember { mutableStateOf(V3Page.Character) }
    var editName by remember { mutableStateOf(false) }
    var inventoryEdit by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    var addingInventory by remember { mutableStateOf(false) }
    val canEdit = connected && !pending

    Column(modifier.fillMaxSize()) {
        when (page) {
            V3Page.Character -> V3CharacterPage(
                snapshot = snapshot,
                controlsEnabled = canEdit,
                onHpChange = onHpChange,
                onAtChange = onAtChange,
                onIpChange = onIpChange,
                onEditName = { editName = true },
                modifier = Modifier.weight(1f),
            )
            V3Page.Equipment -> V3EquipmentPage(
                snapshot = snapshot,
                controlsEnabled = canEdit,
                onAdd = { addingInventory = true },
                onEdit = { inventoryEdit = it },
                onRemove = onRemoveInventoryItem,
                modifier = Modifier.weight(1f),
            )
            V3Page.Notes -> V3NotesPage(snapshot, Modifier.weight(1f))
        }
        V3BottomNavigation(page, onPage = { page = it })
    }

    if (editName) {
        V3TextDialog(
            title = "Character name",
            initial = snapshot.name,
            onDismiss = { editName = false },
            onSave = {
                onSetName(it)
                editName = false
            },
        )
    }

    if (addingInventory || inventoryEdit != null) {
        V3InventoryEditDialog(
            item = inventoryEdit,
            onDismiss = {
                addingInventory = false
                inventoryEdit = null
            },
            onSave = { name, description, quantity ->
                val item = inventoryEdit
                if (item?.id != null) onUpdateInventoryItem(item.id, name, description, quantity)
                else onAddInventoryItem(name, description, quantity)
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

    @Suppress("UNUSED_VARIABLE")
    val retainedBackstoryCommand = onSetBackstory
}

private enum class V3Page(val label: String, val symbol: String) {
    Character("Character", "◆"), Equipment("Equipment", "▣"), Notes("Notes", "✎")
}

@Composable
private fun V3BottomNavigation(page: V3Page, onPage: (V3Page) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 8.dp,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        NavigationBar(containerColor = Color.Transparent, tonalElevation = 0.dp) {
            V3Page.entries.forEach { item ->
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
private fun V3CharacterPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    onEditName: () -> Unit,
    modifier: Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }
    Column(modifier.fillMaxSize()) {
        V3CharacterHeader(snapshot, controlsEnabled, onEditName)
        V3ResourcePanel(snapshot, controlsEnabled, onHpChange, onAtChange, onIpChange)
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
        if (tab == 0) V3Abilities(snapshot, Modifier.fillMaxSize())
        else V3Improvements(snapshot, Modifier.fillMaxSize())
    }
}

@Composable
private fun V3CharacterHeader(snapshot: DidCharacterSnapshot, canEdit: Boolean, onEditName: () -> Unit) {
    V3SheetCard(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 7.dp), strongBorder = true) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            V3Portrait(snapshot, Modifier.width(118.dp).aspectRatio(0.82f))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        snapshot.name.ifBlank { "Unnamed Character" },
                        Modifier.weight(1f),
                        style = MaterialTheme.typography.headlineSmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    TextButton(onClick = onEditName, enabled = canEdit) { Text("Edit") }
                }
                if (snapshot.speciesName.isNotBlank()) {
                    Text(snapshot.speciesName, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.secondary)
                }
                if (snapshot.backstory.isNotBlank()) {
                    Text(
                        snapshot.backstory,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 4,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (snapshot.combatModeEnabled) {
                    Text("COMBAT MODE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.Black)
                }
            }
        }
    }
}

@Composable
private fun V3Portrait(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val raw = snapshot.portrait.currentImage?.data
    val bitmap = remember(raw) { raw?.v3DecodeBitmap() }
    Box(
        modifier.clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.surface),
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(
                bitmap = bitmap.asImageBitmap(),
                contentDescription = "Character portrait",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize().padding(2.dp),
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

private fun String.v3DecodeBitmap() = runCatching {
    val bytes = Base64.decode(substringAfter("base64,", this), Base64.DEFAULT)
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
}.getOrNull()

@Composable
private fun V3ResourcePanel(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    V3SheetCard(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp), strongBorder = true) {
        Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "HP  ${snapshot.hp.current} / ${snapshot.hp.max}",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Black,
                    )
                    Spacer(Modifier.height(3.dp))
                    V3Hearts(snapshot.hp, enabled, onHpChange)
                }
                V3DefenseBadge("BDV", snapshot.bdv, snapshot.uiIcons["bdv"])
                Spacer(Modifier.width(4.dp))
                V3DefenseBadge("DR", snapshot.dr, snapshot.uiIcons["dr"])
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)

            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Adversity Tokens", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Black)
                    Spacer(Modifier.height(2.dp))
                    V3Adversity(snapshot.adversity, enabled, onAtChange)
                }
            }

            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Improvement Points", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Black)
                    Text(
                        "${snapshot.progression.currentIp} IP  •  Level ${snapshot.progression.level}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Black,
                    )
                }
                V3DeltaButtons(
                    enabled = enabled,
                    canDown = snapshot.progression.currentIp > 0,
                    canUp = true,
                    onChange = onIpChange,
                )
            }
        }
    }
}

@Composable
private fun V3DeltaButtons(enabled: Boolean, canDown: Boolean, canUp: Boolean, onChange: (Int) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        TextButton(
            onClick = { onChange(-1) },
            enabled = enabled && canDown,
            modifier = Modifier.size(46.dp),
        ) { Text("−", fontWeight = FontWeight.Black) }
        Button(
            onClick = { onChange(1) },
            enabled = enabled && canUp,
            modifier = Modifier.size(46.dp),
            contentPadding = ButtonDefaults.TextButtonContentPadding,
        ) { Text("+", fontWeight = FontWeight.Black) }
    }
}

@Composable
private fun V3Hearts(hp: HpSnapshot, enabled: Boolean, onHpChange: (Int) -> Unit) {
    val hearts = hp.maxHearts.coerceAtLeast(((hp.max + 3) / 4).coerceAtLeast(1))
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        repeat(hearts) { heartIndex ->
            val available = (hp.max - heartIndex * 4).coerceIn(0, 4)
            val filled = (hp.current - heartIndex * 4).coerceIn(0, 4)
            V3Heart(
                filledQuarters = filled,
                availableQuarters = available,
                enabled = enabled,
                onQuarterTap = { quarter ->
                    val target = (heartIndex * 4 + quarter + 1).coerceAtMost(hp.max)
                    val delta = target - hp.current
                    if (delta != 0) onHpChange(delta)
                },
            )
        }
    }
}

@Composable
private fun V3Heart(
    filledQuarters: Int,
    availableQuarters: Int,
    enabled: Boolean,
    onQuarterTap: (Int) -> Unit,
) {
    val fill = if (isSystemInDarkTheme()) Color(0xFFB33A42) else Color(0xFFFF0000)
    val empty = if (isSystemInDarkTheme()) Color(0xFF18232E) else Color.White
    val locked = if (isSystemInDarkTheme()) Color(0xFF33414C) else Color(0xFFDDDDDD)
    val modifier = Modifier
        .size(36.dp, 33.dp)
        .then(
            if (enabled) Modifier.pointerInput(availableQuarters) {
                detectTapGestures { pos ->
                    val quarter = if (pos.y < size.height * 0.42f) {
                        if (pos.x < size.width / 2f) 0 else 1
                    } else {
                        if (pos.x < size.width / 2f) 2 else 3
                    }
                    if (quarter < availableQuarters) onQuarterTap(quarter)
                }
            } else Modifier
        )

    Canvas(modifier) {
        val w = size.width
        val h = size.height
        val heart = Path().apply {
            moveTo(w * 0.50f, h * 0.20f)
            cubicTo(w * 0.50f, h * 0.04f, w * 0.78f, h * 0.02f, w * 0.88f, h * 0.22f)
            cubicTo(w * 0.98f, h * 0.42f, w * 0.88f, h * 0.70f, w * 0.50f, h * 0.95f)
            cubicTo(w * 0.12f, h * 0.70f, w * 0.02f, h * 0.42f, w * 0.12f, h * 0.22f)
            cubicTo(w * 0.22f, h * 0.02f, w * 0.50f, h * 0.04f, w * 0.50f, h * 0.20f)
            close()
        }
        drawPath(heart, empty)
        clipPath(heart) {
            val quarterRects = listOf(
                Offset(0f, 0f), Offset(w / 2f, 0f), Offset(0f, h / 2f), Offset(w / 2f, h / 2f)
            )
            repeat(4) { index ->
                val color = when {
                    index >= availableQuarters -> locked
                    index < filledQuarters -> fill
                    else -> empty
                }
                drawRect(
                    color,
                    topLeft = quarterRects[index],
                    size = androidx.compose.ui.geometry.Size(w / 2f, h / 2f),
                )
            }
        }
        drawPath(heart, fill, style = Stroke(width = 2.2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        drawLine(fill, Offset(w * 0.50f, h * 0.15f), Offset(w * 0.50f, h * 0.95f), 1.6f)
        drawLine(fill, Offset(w * 0.12f, h * 0.50f), Offset(w * 0.90f, h * 0.50f), 1.6f)
    }
}

@Composable
private fun V3Adversity(at: AdversitySnapshot, enabled: Boolean, onAtChange: (Int) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(at.max.coerceAtLeast(0)) { index ->
            val filled = index < at.current
            Canvas(
                Modifier.size(23.dp).then(
                    if (enabled) Modifier.clickable {
                        val target = if (index < at.current) index else index + 1
                        val delta = target - at.current
                        if (delta != 0) onAtChange(delta)
                    } else Modifier
                )
            ) {
                val p = Path().apply {
                    moveTo(size.width / 2f, 1f)
                    lineTo(size.width - 1f, size.height / 2f)
                    lineTo(size.width / 2f, size.height - 1f)
                    lineTo(1f, size.height / 2f)
                    close()
                }
                val fill = if (filled) Color(0xFFD4AF37) else Color(0xFFF7EFD0)
                val border = if (filled) Color(0xFFB8962E) else Color(0xFFD4AF37)
                drawPath(p, fill)
                drawPath(p, border, style = Stroke(width = 2f, join = StrokeJoin.Round))
            }
        }
        Text("${at.current}/${at.max}", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun V3DefenseBadge(label: String, value: Int, encodedSvg: String?) {
    Column(Modifier.width(55.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Black)
        Box(Modifier.size(48.dp), contentAlignment = Alignment.Center) {
            V3DesktopSvg(encodedSvg, Modifier.fillMaxSize())
            Text(value.toString(), color = Color(0xFFF7F0E7), fontWeight = FontWeight.Black)
        }
    }
}

private val v3AbilityColors = mapOf(
    "agility" to Color(0xFF6F8F2C),
    "finesse" to Color(0xFF356FA8),
    "instinct" to Color(0xFF6B55A6),
    "knowledge" to Color(0xFFB17828),
    "presence" to Color(0xFF2F8792),
    "strength" to Color(0xFFA8453C),
)

@Composable
private fun V3Abilities(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val sorted = snapshot.stats.sortedWith(
        compareByDescending<StatSnapshot> { it.dieSize }
            .thenByDescending { it.bonus }
            .thenBy { it.key }
    )
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item { V3Heading("Abilities") }
        items(sorted, key = { it.key }) { stat ->
            val accent = v3AbilityColors[stat.key] ?: Color(0xFF2F5F91)
            V3SheetCard(Modifier.fillMaxWidth(), strongBorder = false) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Surface(
                        modifier = Modifier.size(46.dp),
                        shape = CircleShape,
                        color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.5.dp, accent),
                    ) {
                        Box(Modifier.padding(5.dp), contentAlignment = Alignment.Center) {
                            V3DesktopSvg(snapshot.uiIcons[stat.key], Modifier.fillMaxSize())
                        }
                    }
                    Text(
                        "d${stat.dieSize}",
                        color = accent,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        stat.name,
                        Modifier.weight(1f),
                        color = accent,
                        fontWeight = FontWeight.Black,
                    )
                    Surface(
                        modifier = Modifier.size(48.dp, 32.dp),
                        shape = RoundedCornerShape(7.dp),
                        color = Color(0xFFF4FBFF),
                        border = BorderStroke(1.dp, Color(0xFFD9BD82)),
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                if (stat.bonus >= 0) "+${stat.bonus}" else stat.bonus.toString(),
                                color = Color.Black,
                                fontWeight = FontWeight.Black,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun V3DesktopSvg(encoded: String?, modifier: Modifier) {
    val drawable = remember(encoded) {
        encoded?.let { data ->
            runCatching {
                val bytes = Base64.decode(data, Base64.DEFAULT)
                val svg = SVG.getFromString(String(bytes, Charsets.UTF_8))
                PictureDrawable(svg.renderToPicture())
            }.getOrNull()
        }
    }
    if (drawable == null) {
        Box(modifier, contentAlignment = Alignment.Center) {
            Text("◇", color = MaterialTheme.colorScheme.secondary)
        }
        return
    }
    AndroidView(
        modifier = modifier,
        factory = { context ->
            ImageView(context).apply {
                setLayerType(View.LAYER_TYPE_SOFTWARE, null)
                scaleType = ImageView.ScaleType.FIT_CENTER
            }
        },
        update = { image -> image.setImageDrawable(drawable) },
    )
}

@Composable
private fun V3Improvements(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    var previewNote by remember { mutableStateOf<NoteSnapshot?>(null) }
    val improvements = snapshot.improvements.sortedWith(
        compareBy<ImprovementSnapshot> { it.sortOrder }.thenBy { it.name.lowercase() }
    )

    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item { V3Heading("Improvements", trailing = "${snapshot.progression.currentIp} IP") }
        if (improvements.isEmpty()) item { V3Empty("No improvements yet.") }
        items(improvements, key = { it.id ?: "${it.name}:${it.sortOrder}" }) { improvement ->
            var expanded by remember(improvement.id, improvement.expanded) {
                mutableStateOf(improvement.expanded || improvement.description.isNotBlank())
            }
            val linkedNotes = v3LinkedNotes(snapshot, improvement)
            V3SheetCard(Modifier.fillMaxWidth().clickable { expanded = !expanded }, strongBorder = false) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(if (expanded) "▾" else "▸", Modifier.width(20.dp), color = MaterialTheme.colorScheme.secondary)
                        Text(improvement.name, Modifier.weight(1f), fontWeight = FontWeight.Black)
                        linkedNotes.take(3).forEach { note ->
                            V3NoteIcon(note.color) { previewNote = note }
                            Spacer(Modifier.width(3.dp))
                        }
                        if (improvement.timesTaken > 1) Text("×${improvement.timesTaken}  ")
                        if (improvement.cost > 0) Text("${improvement.cost} IP", fontWeight = FontWeight.Bold)
                    }
                    if (expanded) {
                        if (improvement.description.isNotBlank()) {
                            Text(didHtmlToAnnotatedString(improvement.description), style = MaterialTheme.typography.bodyMedium)
                        }
                        v3Choices(improvement.choices)?.let {
                            Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        improvement.empowerments.forEach { empowerment ->
                            Surface(
                                Modifier.fillMaxWidth().padding(top = 2.dp),
                                shape = RoundedCornerShape(8.dp),
                                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                            ) {
                                Column(Modifier.padding(9.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                    Row(Modifier.fillMaxWidth()) {
                                        Text(empowerment.name, Modifier.weight(1f), fontWeight = FontWeight.Bold)
                                        if (empowerment.cost > 0) Text("${empowerment.cost} IP", style = MaterialTheme.typography.labelMedium)
                                    }
                                    if (empowerment.description.isNotBlank()) {
                                        Text(didHtmlToAnnotatedString(empowerment.description), style = MaterialTheme.typography.bodySmall)
                                    }
                                    v3Choices(empowerment.choices)?.let {
                                        Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    previewNote?.let { note ->
        val rendered: AnnotatedString = if (note.text.text.contains('<') && note.text.text.contains('>')) {
            didHtmlToAnnotatedString(note.text.text)
        } else note.text
        AlertDialog(
            onDismissRequest = { previewNote = null },
            title = { Text(note.title.ifBlank { "Note" }, fontWeight = FontWeight.Black) },
            text = { Text(rendered) },
            confirmButton = { TextButton(onClick = { previewNote = null }) { Text("Close") } },
        )
    }
}

private fun v3LinkedNotes(snapshot: DidCharacterSnapshot, improvement: ImprovementSnapshot): List<NoteSnapshot> {
    val direct = snapshot.notes.filter { note ->
        improvement.id != null && note.linkedImprovementId == improvement.id
    }
    val builtinTitle = when (improvement.catalogId) {
        "spellcasting", "magic_novice" -> "spellcasting verbs"
        "sneak_attack" -> "sneak attack"
        "animal_buddy" -> "animal buddy"
        else -> null
    }
    val builtin = if (builtinTitle == null) emptyList() else snapshot.notes.filter {
        it.title.trim().lowercase() == builtinTitle
    }
    return (direct + builtin).distinctBy { it.id ?: "${it.title}:${it.text.text}" }
}

private fun v3Choices(choices: JSONObject?): String? {
    if (choices == null || choices.length() == 0) return null
    val parts = choices.keys().asSequence().filterNot { it.startsWith("_") }.mapNotNull { key ->
        val value = choices.opt(key)?.toString()?.takeIf { it.isNotBlank() && it != "null" } ?: return@mapNotNull null
        "${key.replace('_', ' ').replaceFirstChar { it.titlecase() }}: $value"
    }.toList()
    return parts.takeIf { it.isNotEmpty() }?.joinToString(" • ")
}

@Composable
private fun V3NoteIcon(colorKey: String?, onClick: () -> Unit) {
    val (border, fill) = v3NoteColors(colorKey)
    Canvas(Modifier.size(27.dp).clickable(onClick = onClick)) {
        val page = Path().apply {
            moveTo(size.width * 0.23f, size.height * 0.12f)
            lineTo(size.width * 0.68f, size.height * 0.12f)
            lineTo(size.width * 0.80f, size.height * 0.25f)
            lineTo(size.width * 0.80f, size.height * 0.88f)
            lineTo(size.width * 0.23f, size.height * 0.88f)
            close()
        }
        drawPath(page, fill)
        drawPath(page, border, style = Stroke(width = 2f, join = StrokeJoin.Round))
        drawLine(border, Offset(size.width * 0.35f, size.height * 0.45f), Offset(size.width * 0.68f, size.height * 0.45f), 1.6f)
        drawLine(border, Offset(size.width * 0.35f, size.height * 0.60f), Offset(size.width * 0.68f, size.height * 0.60f), 1.6f)
    }
}

@Composable
private fun V3EquipmentPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onAdd: () -> Unit,
    onEdit: (InventoryItemSnapshot) -> Unit,
    onRemove: (String) -> Unit,
    modifier: Modifier,
) {
    var deleteCandidate by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    Box(modifier) {
        LazyColumn(Modifier.fillMaxSize().padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    V3Heading("Inventory", modifier = Modifier.weight(1f))
                    Spacer(Modifier.width(6.dp))
                    Button(onClick = onAdd, enabled = controlsEnabled) { Text("+ Add") }
                }
            }
            if (snapshot.inventory.isEmpty()) item { V3Empty("No equipment.") }
            items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
                var expanded by remember(item.id, item.expanded) { mutableStateOf(item.expanded) }
                var menuOpen by remember(item.id) { mutableStateOf(false) }
                V3SheetCard(Modifier.fillMaxWidth(), strongBorder = false) {
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
                            V3QuantityCircle(item.quantity)
                            Box {
                                TextButton(
                                    onClick = { menuOpen = true },
                                    enabled = controlsEnabled,
                                    modifier = Modifier.width(42.dp),
                                    contentPadding = ButtonDefaults.TextButtonContentPadding,
                                ) { Text("⋮", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Black) }
                                DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                                    DropdownMenuItem(
                                        text = { Text("Edit") },
                                        onClick = {
                                            menuOpen = false
                                            onEdit(item)
                                        },
                                    )
                                    if (item.id != null) {
                                        DropdownMenuItem(
                                            text = { Text("Delete", color = MaterialTheme.colorScheme.error) },
                                            onClick = {
                                                menuOpen = false
                                                deleteCandidate = item
                                            },
                                        )
                                    }
                                }
                            }
                        }
                        if (expanded && item.description.isNotBlank()) Text(item.description)
                    }
                }
            }
        }

        deleteCandidate?.let { item ->
            AlertDialog(
                onDismissRequest = { deleteCandidate = null },
                title = { Text("Delete ${item.name.ifBlank { "item" }}?") },
                text = { Text("This removes the item from the Windows character too.") },
                confirmButton = {
                    Button(
                        onClick = {
                            item.id?.let(onRemove)
                            deleteCandidate = null
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                    ) { Text("Delete") }
                },
                dismissButton = { TextButton(onClick = { deleteCandidate = null }) { Text("Cancel") } },
            )
        }
    }
}

@Composable
private fun V3QuantityCircle(quantity: Int) {
    Surface(
        modifier = Modifier.size(34.dp),
        shape = CircleShape,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.2.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(quantity.toString(), fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun V3NotesPage(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val notes = snapshot.notes.sortedWith(compareByDescending<NoteSnapshot> { it.pinned }.thenBy { it.title.lowercase() })
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { V3Heading("Notes") }
        if (notes.isEmpty()) item { V3Empty("No notes.") }
        items(notes, key = { it.id ?: "${it.title}:${it.text.text.hashCode()}" }) { note ->
            var expanded by remember(note.id, note.expanded) { mutableStateOf(note.expanded) }
            val colors = v3NoteColors(note.color)
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
                }
            }
        }
    }
}

@Composable
private fun v3NoteColors(value: String?): Pair<Color, Color> {
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
private fun V3Heading(
    title: String,
    trailing: String? = null,
    modifier: Modifier = Modifier,
) {
    Row(modifier.fillMaxWidth().padding(horizontal = 3.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
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
private fun V3Empty(text: String) {
    V3SheetCard(Modifier.fillMaxWidth(), strongBorder = false) {
        Text(text, Modifier.fillMaxWidth().padding(18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun V3SheetCard(modifier: Modifier, strongBorder: Boolean, content: @Composable () -> Unit) {
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
private fun V3TextDialog(title: String, initial: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var value by remember(initial) { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title, fontWeight = FontWeight.Black) },
        text = { OutlinedTextField(value, { value = it }, Modifier.fillMaxWidth(), singleLine = true) },
        confirmButton = { Button(onClick = { onSave(value) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun V3InventoryEditDialog(
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
                OutlinedTextField(description, { description = it }, Modifier.fillMaxWidth(), label = { Text("Description") }, minLines = 3, maxLines = 8)
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
            Button(enabled = quantity.toIntOrNull() != null, onClick = { onSave(name, description, quantity.toIntOrNull() ?: 0) }) { Text("Save") }
        },
        dismissButton = {
            Row {
                if (onRemove != null) TextButton(onClick = { confirmDelete = true }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
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
                Button(onClick = onRemove, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}
