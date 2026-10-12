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
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.caverock.androidsvg.SVG
import com.did.charactersheet.ui.DidPalette
import org.json.JSONObject

/** Phase 9 V8: desktop-parity interaction and layout pass. */
@Composable
fun Phase9CompanionSheetV8(
    state: DidCompanionViewModel.UiState,
    onSetHp: (Int) -> Unit,
    onSetAt: (Int) -> Unit,
    onSetName: (String) -> Unit,
    onAddInventoryItem: (String, String, Int) -> Unit,
    onUpdateInventoryItem: (String, String, String, Int) -> Unit,
    onRemoveInventoryItem: (String) -> Unit,
    onAddNote: (String, String, String, Boolean) -> Unit,
    onUpdateNote: (String, String, String, String, Boolean) -> Unit,
    onRemoveNote: (String) -> Unit,
    onPickImages: () -> Unit,
    onRemoveImage: (String) -> Unit,
    onEditImprovement: (String, JSONObject, String?, String?) -> Unit,
    onAdjustResources: (Int, Int, Int) -> Unit,
    onRollAbility: (String) -> Unit,
    onRollOtherDice: (Map<Int, Int>) -> Unit,
    onClearDiceResult: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val snapshot = state.snapshot ?: return
    val canEdit = state.isConnected
    var page by remember { mutableStateOf(V8Page.Character) }
    var editName by remember { mutableStateOf(false) }
    var inventoryEdit by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    var addingInventory by remember { mutableStateOf(false) }
    var noteEdit by remember { mutableStateOf<NoteSnapshot?>(null) }
    var addingNote by remember { mutableStateOf(false) }
    var improvementEdit by remember { mutableStateOf<ImprovementSnapshot?>(null) }
    var linkedNoteView by remember { mutableStateOf<NoteSnapshot?>(null) }
    var abilityInfo by remember { mutableStateOf<StatSnapshot?>(null) }
    var abilityMenu by remember { mutableStateOf<StatSnapshot?>(null) }
    var toolsOpen by remember { mutableStateOf(false) }
    var adjustResources by remember { mutableStateOf(false) }
    var otherDice by remember { mutableStateOf(false) }
    var historyOpen by remember { mutableStateOf(false) }

    Column(modifier.fillMaxSize()) {
        when (page) {
            V8Page.Character -> V8CharacterPage(
                snapshot, canEdit, state.pendingRequestIds.isNotEmpty(), toolsOpen,
                { toolsOpen = true }, { toolsOpen = false },
                { toolsOpen = false; adjustResources = true },
                { toolsOpen = false; otherDice = true },
                { toolsOpen = false; historyOpen = true },
                onSetHp, onSetAt, { editName = true }, onRemoveImage, onPickImages,
                { improvementEdit = it }, { linkedNoteView = it },
                { abilityInfo = it }, { stat -> abilityMenu = stat }, onRollAbility,
                Modifier.weight(1f),
            )
            V8Page.Equipment -> V8EquipmentPage(
                snapshot, canEdit, toolsOpen, { toolsOpen = true }, { toolsOpen = false },
                { toolsOpen = false; adjustResources = true },
                { toolsOpen = false; otherDice = true },
                { toolsOpen = false; historyOpen = true },
                { addingInventory = true }, { inventoryEdit = it }, onUpdateInventoryItem,
                onRemoveInventoryItem, Modifier.weight(1f),
            )
            V8Page.Notes -> V8NotesPage(
                snapshot, canEdit, toolsOpen, { toolsOpen = true }, { toolsOpen = false },
                { toolsOpen = false; adjustResources = true },
                { toolsOpen = false; otherDice = true },
                { toolsOpen = false; historyOpen = true },
                { addingNote = true }, { noteEdit = it }, Modifier.weight(1f),
            )
        }
        V8BottomNavigation(page, snapshot) { page = it }
    }

    if (editName) V8TextDialog("Character name", snapshot.name, { editName = false }) {
        onSetName(it); editName = false
    }

    if (addingInventory || inventoryEdit != null) {
        V8InventoryDialog(
            inventoryEdit,
            { addingInventory = false; inventoryEdit = null },
            { name, description, quantity ->
                inventoryEdit?.id?.let { onUpdateInventoryItem(it, name, description, quantity) }
                    ?: onAddInventoryItem(name, description, quantity)
                addingInventory = false; inventoryEdit = null
            },
            inventoryEdit?.id?.let { id -> { onRemoveInventoryItem(id); inventoryEdit = null } },
        )
    }

    if (addingNote || noteEdit != null) {
        V8NoteDialog(
            noteEdit,
            { addingNote = false; noteEdit = null },
            { title, text, color, pinned ->
                val existing = noteEdit
                if (existing?.id != null) {
                    val storedText = if (text == existing.text.text) existing.rawText else text
                    onUpdateNote(existing.id, title, storedText, color, pinned)
                } else onAddNote(title, text, color, pinned)
                addingNote = false; noteEdit = null
            },
            noteEdit?.id?.let { id -> { onRemoveNote(id); noteEdit = null } },
        )
    }

    improvementEdit?.let { improvement ->
        V8ImprovementEditDialog(improvement, { improvementEdit = null }) { choices, name, description ->
            improvement.id?.let { onEditImprovement(it, choices, name, description) }
            improvementEdit = null
        }
    }

    linkedNoteView?.let { V8LinkedNoteDialog(it) { linkedNoteView = null } }
    abilityInfo?.let { V8AbilityInfoDialog(it, snapshot) { abilityInfo = null } }
    abilityMenu?.let { stat ->
        V8AbilityActionDialog(
            stat = stat,
            snapshot = snapshot,
            onDismiss = { abilityMenu = null },
            onInfo = { abilityMenu = null; abilityInfo = stat },
            onRoll = { abilityMenu = null; onRollAbility(stat.key) },
        )
    }

    if (adjustResources) V8AdjustResourcesDialog(snapshot, { adjustResources = false }) { hearts, ip, at ->
        onAdjustResources(hearts, ip, at); adjustResources = false
    }
    if (otherDice) V8OtherDiceDialog({ otherDice = false }) { counts ->
        onRollOtherDice(counts); otherDice = false
    }
    if (historyOpen) V8HistoryDialog(state.rollHistory) { historyOpen = false }
    state.lastDiceResult?.let { V8DiceResultDialog(it, onClearDiceResult) }
}

private enum class V8Page(val label: String) { Character("Character"), Equipment("Equipment"), Notes("Notes") }

@Composable
private fun V8ToolsButton(
    open: Boolean,
    onOpen: () -> Unit,
    onDismiss: () -> Unit,
    onAdjustResources: () -> Unit,
    onOtherDice: () -> Unit,
    onHistory: () -> Unit,
) {
    Box {
        TextButton(onClick = onOpen, contentPadding = PaddingValues(horizontal = 7.dp, vertical = 3.dp)) {
            Text("⚙", color = DidPalette.GoldDeep, style = MaterialTheme.typography.titleLarge)
        }
        DropdownMenu(expanded = open, onDismissRequest = onDismiss) {
            DropdownMenuItem(text = { Text("Adjust Resources") }, onClick = onAdjustResources)
            HorizontalDivider()
            DropdownMenuItem(text = { Text("Roll Other Dice…") }, onClick = onOtherDice)
            DropdownMenuItem(text = { Text("Previous Rolls (This Session)") }, onClick = onHistory)
        }
    }
}

@Composable
private fun V8Header(
    title: String,
    toolsOpen: Boolean,
    onToolsOpen: () -> Unit,
    onToolsDismiss: () -> Unit,
    onAdjustResources: () -> Unit,
    onOtherDice: () -> Unit,
    onHistory: () -> Unit,
    trailing: (@Composable () -> Unit)? = null,
) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        V8ToolsButton(toolsOpen, onToolsOpen, onToolsDismiss, onAdjustResources, onOtherDice, onHistory)
        Text(title, Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Black)
        trailing?.invoke()
    }
}

@Composable
private fun V8CharacterPage(
    snapshot: DidCharacterSnapshot,
    connected: Boolean,
    pending: Boolean,
    toolsOpen: Boolean,
    onToolsOpen: () -> Unit,
    onToolsDismiss: () -> Unit,
    onAdjustResources: () -> Unit,
    onOtherDice: () -> Unit,
    onHistory: () -> Unit,
    onSetHp: (Int) -> Unit,
    onSetAt: (Int) -> Unit,
    onEditName: () -> Unit,
    onRemoveImage: (String) -> Unit,
    onPickImages: () -> Unit,
    onEditImprovement: (ImprovementSnapshot) -> Unit,
    onOpenLinkedNote: (NoteSnapshot) -> Unit,
    onAbilityInfo: (StatSnapshot) -> Unit,
    onAbilityLongPress: (StatSnapshot) -> Unit,
    onRollAbility: (String) -> Unit,
    modifier: Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }
    Column(modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
            V8ToolsButton(toolsOpen, onToolsOpen, onToolsDismiss, onAdjustResources, onOtherDice, onHistory)
            Text(
                snapshot.name.ifBlank { "Unnamed Character" },
                Modifier.weight(1f).pointerInput(connected) { detectTapGestures(onDoubleTap = { if (connected) onEditName() }) },
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.width(48.dp))
        }
        V8PortraitGallery(snapshot, connected, onPickImages, onRemoveImage)
        V8ResourcePanel(snapshot, connected, pending, onSetHp, onSetAt)
        TabRow(selectedTabIndex = tab, containerColor = MaterialTheme.colorScheme.surface, contentColor = MaterialTheme.colorScheme.onSurface) {
            listOf("Abilities", "Improvements").forEachIndexed { index, label ->
                Tab(selected = tab == index, onClick = { tab = index }, text = {
                    Text(label, fontWeight = if (tab == index) FontWeight.Black else FontWeight.Bold)
                })
            }
        }
        if (tab == 0) V8Abilities(snapshot, connected, onAbilityInfo, onAbilityLongPress, onRollAbility, Modifier.fillMaxSize())
        else V8Improvements(snapshot, connected, onEditImprovement, onOpenLinkedNote, Modifier.fillMaxSize())
    }
}

@Composable
private fun V8PortraitGallery(snapshot: DidCharacterSnapshot, enabled: Boolean, onAdd: () -> Unit, onRemove: (String) -> Unit) {
    V8SheetCard(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp), true) {
        LazyRow(
            Modifier.fillMaxWidth().height(184.dp),
            contentPadding = PaddingValues(8.dp),
            horizontalArrangement = Arrangement.spacedBy(7.dp, Alignment.CenterHorizontally),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items(snapshot.portrait.images, key = { it.id ?: it.data.hashCode() }) { image ->
                val bitmap = remember(image.data) { image.data.v8DecodeBitmap() }
                Surface(Modifier.size(132.dp, 164.dp), RoundedCornerShape(10.dp), MaterialTheme.colorScheme.surface, border = BorderStroke(1.2.dp, MaterialTheme.colorScheme.outlineVariant)) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        if (bitmap != null) {
                            Image(bitmap.asImageBitmap(), "Character picture", Modifier.fillMaxSize().padding(3.dp), contentScale = ContentScale.Fit)
                        } else {
                            Text("Image could not be displayed", style = MaterialTheme.typography.labelSmall, textAlign = TextAlign.Center)
                        }
                        image.id?.let { id ->
                            Text("×", Modifier.align(Alignment.TopEnd).padding(5.dp).clickable(enabled = enabled) { onRemove(id) }, color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.Black)
                        }
                    }
                }
            }
            item {
                Surface(Modifier.size(70.dp, 164.dp).clickable(enabled = enabled, onClick = onAdd), RoundedCornerShape(10.dp), MaterialTheme.colorScheme.surfaceVariant, border = BorderStroke(1.2.dp, MaterialTheme.colorScheme.outlineVariant)) {
                    Box(contentAlignment = Alignment.Center) { Text("+", style = MaterialTheme.typography.headlineLarge, color = DidPalette.GoldDeep) }
                }
            }
        }
    }
}

private fun String.v8DecodeBitmap() = runCatching {
    val source = substringAfter("base64,", this).trim()
    val bytes = Base64.decode(source, Base64.DEFAULT)
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
}.getOrNull()

@Composable
private fun V8ResourcePanel(snapshot: DidCharacterSnapshot, enabled: Boolean, pending: Boolean, onSetHp: (Int) -> Unit, onSetAt: (Int) -> Unit) {
    var shownHp by remember(snapshot.id) { mutableIntStateOf(snapshot.hp.current) }
    var shownAt by remember(snapshot.id) { mutableIntStateOf(snapshot.adversity.current) }
    LaunchedEffect(snapshot.hp.current, pending) { if (!pending) shownHp = snapshot.hp.current }
    LaunchedEffect(snapshot.adversity.current, pending) { if (!pending) shownAt = snapshot.adversity.current }

    V8SheetCard(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp), true) {
        Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    val hearts = snapshot.hp.maxHearts.coerceAtLeast(((snapshot.hp.max + 3) / 4).coerceAtLeast(1))
                    repeat(hearts) { heartIndex ->
                        val available = (snapshot.hp.max - heartIndex * 4).coerceIn(0, 4)
                        val filled = (shownHp - heartIndex * 4).coerceIn(0, 4)
                        V8Heart(filled, available, enabled) { quarter ->
                            val target = (heartIndex * 4 + quarter + 1).coerceAtMost(snapshot.hp.max)
                            if (target != shownHp) { shownHp = target; onSetHp(target) }
                        }
                    }
                }
                V8DefenseBadge("BDV", snapshot.bdv, snapshot.uiIcons["bdv"])
                Spacer(Modifier.width(4.dp))
                V8DefenseBadge("DR", snapshot.dr, snapshot.uiIcons["dr"])
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                repeat(snapshot.adversity.max.coerceAtLeast(0)) { index ->
                    val filled = index < shownAt
                    Canvas(Modifier.size(33.dp).clickable(enabled = enabled) {
                        val target = if (index < shownAt) index else index + 1
                        if (target != shownAt) { shownAt = target; onSetAt(target) }
                    }) {
                        val p = Path().apply {
                            moveTo(size.width / 2f, 1f); lineTo(size.width - 1f, size.height / 2f)
                            lineTo(size.width / 2f, size.height - 1f); lineTo(1f, size.height / 2f); close()
                        }
                        val fill = if (filled) Color(0xFFD4AF37) else Color(0xFFF7EFD0)
                        drawPath(p, fill); drawPath(p, Color(0xFFD4AF37), style = Stroke(width = 2f, join = StrokeJoin.Round))
                    }
                }
            }
        }
    }
}

@Composable
private fun V8Heart(filled: Int, available: Int, enabled: Boolean, onQuarter: (Int) -> Unit) {
    val red = if (isSystemInDarkTheme()) Color(0xFFB33A42) else Color.Red
    val empty = if (isSystemInDarkTheme()) Color(0xFF18232E) else Color.White
    Canvas(Modifier.size(48.dp, 44.dp).then(if (enabled) Modifier.pointerInput(available) {
        detectTapGestures { pos ->
            val q = if (pos.y < size.height / 2f) { if (pos.x < size.width / 2f) 0 else 1 } else { if (pos.x < size.width / 2f) 2 else 3 }
            if (q < available) onQuarter(q)
        }
    } else Modifier)) {
        val w = size.width; val h = size.height
        val heart = Path().apply {
            moveTo(w * .50f, h * .20f)
            cubicTo(w * .50f, h * .04f, w * .78f, h * .02f, w * .88f, h * .22f)
            cubicTo(w * .98f, h * .42f, w * .88f, h * .70f, w * .50f, h * .95f)
            cubicTo(w * .12f, h * .70f, w * .02f, h * .42f, w * .12f, h * .22f)
            cubicTo(w * .22f, h * .02f, w * .50f, h * .04f, w * .50f, h * .20f); close()
        }
        drawPath(heart, empty)
        clipPath(heart) {
            repeat(4) { q ->
                val left = if (q % 2 == 0) 0f else w / 2f
                val top = if (q < 2) 0f else h / 2f
                val color = when { q >= available -> Color(0xFFDDDDDD); q < filled -> red; else -> empty }
                drawRect(color, Offset(left, top), androidx.compose.ui.geometry.Size(w / 2f, h / 2f))
            }
        }
        drawPath(heart, red, style = Stroke(2.2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        drawLine(red, Offset(w / 2f, h * .15f), Offset(w / 2f, h * .95f), 1.5f)
        drawLine(red, Offset(w * .12f, h / 2f), Offset(w * .90f, h / 2f), 1.5f)
    }
}

@Composable
private fun V8DefenseBadge(label: String, value: Int, svg: String?) {
    Column(Modifier.width(55.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Black)
        Box(Modifier.size(48.dp), contentAlignment = Alignment.Center) {
            V8DesktopSvg(svg, Modifier.fillMaxSize())
            Text(value.toString(), color = Color(0xFFF7F0E7), fontWeight = FontWeight.Black)
        }
    }
}

private val v8AbilityColors = mapOf(
    "agility" to Color(0xFF6F8F2C), "finesse" to Color(0xFF356FA8), "instinct" to Color(0xFF6B55A6),
    "knowledge" to Color(0xFFB17828), "presence" to Color(0xFF2F8792), "strength" to Color(0xFFA8453C),
)

@Composable
private fun V8Abilities(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onInfo: (StatSnapshot) -> Unit,
    onLongPress: (StatSnapshot) -> Unit,
    onRoll: (String) -> Unit,
    modifier: Modifier,
) {
    val sorted = snapshot.stats.sortedWith(compareByDescending<StatSnapshot> { it.dieSize }.thenByDescending { it.bonus }.thenBy { it.key })
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item { Text("Abilities", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Black) }
        items(sorted, key = { it.key }) { stat ->
            val accent = v8AbilityColors[stat.key] ?: DidPalette.BlueStrong
            V8SheetCard(
                Modifier.fillMaxWidth().pointerInput(stat.key, enabled) {
                    detectTapGestures(
                        onTap = { onInfo(stat) },
                        onDoubleTap = { if (enabled) onRoll(stat.key) },
                        onLongPress = { onLongPress(stat) },
                    )
                }, false
            ) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Surface(Modifier.size(46.dp), CircleShape, MaterialTheme.colorScheme.surface, border = BorderStroke(1.5.dp, accent)) {
                        Box(Modifier.padding(5.dp)) { V8DesktopSvg(snapshot.uiIcons[stat.key], Modifier.fillMaxSize()) }
                    }
                    Text("d${stat.dieSize}", color = accent, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Black)
                    Text(stat.name, Modifier.weight(1f), color = accent, fontWeight = FontWeight.Black)
                    Surface(Modifier.size(48.dp, 32.dp), RoundedCornerShape(7.dp), Color(0xFFF4FBFF), border = BorderStroke(1.dp, Color(0xFFD9BD82))) {
                        Box(contentAlignment = Alignment.Center) { Text(if (stat.bonus >= 0) "+${stat.bonus}" else stat.bonus.toString(), color = Color.Black, fontWeight = FontWeight.Black) }
                    }
                }
            }
        }
    }
}

@Composable
private fun V8Improvements(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onEdit: (ImprovementSnapshot) -> Unit,
    onLinkedNote: (NoteSnapshot) -> Unit,
    modifier: Modifier,
) {
    val improvements = snapshot.improvements.sortedWith(compareBy<ImprovementSnapshot> { it.sortOrder }.thenBy { it.name.lowercase() })
    LazyColumn(modifier.padding(horizontal = 10.dp, vertical = 7.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        item { Text("Improvements", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Black) }
        if (improvements.isEmpty()) item { Text("No improvements yet.") }
        items(improvements, key = { it.id ?: "${it.name}:${it.sortOrder}" }) { improvement ->
            var expanded by remember(improvement.id, improvement.expanded) { mutableStateOf(improvement.expanded) }
            val editable = improvement.id != null && (
                improvement.catalogId == "custom" || improvement.source == "custom" ||
                    improvement.choices?.keys()?.asSequence()?.any { !it.startsWith("_") } == true
                )
            val linkedNote = improvement.id?.let { id -> snapshot.notes.firstOrNull { it.linkedImprovementId == id } }
            val icon = improvement.catalogId?.let { id -> snapshot.uiIcons["improvement:$id"] }
                ?: snapshot.uiIcons["improvement-name:${improvement.name.lowercase().replace(' ', '_')}"]

            V8SheetCard(Modifier.fillMaxWidth(), false) {
                Column(Modifier.padding(horizontal = 7.dp, vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier.size(38.dp).clickable { expanded = !expanded },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(if (expanded) "▾" else "▸", color = DidPalette.GoldDeep, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Black)
                        }
                        if (icon != null) {
                            V8DesktopSvg(icon, Modifier.size(30.dp).padding(end = 5.dp))
                        }
                        Text(
                            improvement.name,
                            Modifier.weight(1f).pointerInput(improvement.id, editable, expanded) {
                                detectTapGestures(
                                    onTap = { expanded = !expanded },
                                    onDoubleTap = { if (editable && enabled) onEdit(improvement) },
                                )
                            },
                            fontWeight = FontWeight.Black,
                        )
                        linkedNote?.let { note ->
                            Box(Modifier.size(38.dp).clickable { onLinkedNote(note) }, contentAlignment = Alignment.Center) {
                                V8DesktopSvg(snapshot.uiIcons["notes"], Modifier.size(25.dp))
                            }
                        }
                    }
                    if (expanded) {
                        if (improvement.description.isNotBlank()) {
                            Text(didHtmlToAnnotatedString(improvement.description), style = MaterialTheme.typography.bodyMedium)
                        }
                        improvement.empowerments.forEach { empowerment ->
                            Surface(Modifier.fillMaxWidth(), RoundedCornerShape(8.dp), MaterialTheme.colorScheme.primaryContainer.copy(alpha = .35f), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                                Column(Modifier.padding(7.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(empowerment.name, fontWeight = FontWeight.Bold)
                                    if (empowerment.description.isNotBlank()) Text(didHtmlToAnnotatedString(empowerment.description), style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun V8EquipmentPage(
    snapshot: DidCharacterSnapshot,
    connected: Boolean,
    toolsOpen: Boolean,
    onToolsOpen: () -> Unit,
    onToolsDismiss: () -> Unit,
    onAdjustResources: () -> Unit,
    onOtherDice: () -> Unit,
    onHistory: () -> Unit,
    onAdd: () -> Unit,
    onEdit: (InventoryItemSnapshot) -> Unit,
    onUpdate: (String, String, String, Int) -> Unit,
    onRemove: (String) -> Unit,
    modifier: Modifier,
) {
    var deleteCandidate by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    Column(modifier.fillMaxSize()) {
        V8Header("Inventory", toolsOpen, onToolsOpen, onToolsDismiss, onAdjustResources, onOtherDice, onHistory,
            trailing = { Button(onClick = onAdd, enabled = connected) { Text("+ Add") } })
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
                var expanded by remember(item.id, item.expanded) { mutableStateOf(item.expanded) }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.Top) {
                    Surface(Modifier.weight(1f).height(56.dp), RoundedCornerShape(11.dp), MaterialTheme.colorScheme.surface, border = BorderStroke(1.4.dp, MaterialTheme.colorScheme.outlineVariant)) {
                        Row(Modifier.fillMaxSize().padding(end = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(42.dp).clickable { expanded = !expanded }, contentAlignment = Alignment.Center) {
                                Text(if (expanded) "▾" else "▸", color = DidPalette.GoldDeep, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Black)
                            }
                            Text(item.name.ifBlank { "Unnamed item" }, Modifier.weight(1f).pointerInput(item.id, connected) {
                                detectTapGestures(onDoubleTap = { if (connected) onEdit(item) })
                            }, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            item.id?.let { Text("×", Modifier.padding(start = 7.dp).clickable(enabled = connected) { deleteCandidate = item }, color = DidPalette.GoldDeep, fontWeight = FontWeight.Black) }
                        }
                    }
                    V8QuantityBox(item.quantity, connected && item.id != null,
                        { item.id?.let { onUpdate(it, item.name, item.description, item.quantity + 1) } },
                        { item.id?.let { onUpdate(it, item.name, item.description, (item.quantity - 1).coerceAtLeast(0)) } })
                }
                if (expanded && item.description.isNotBlank()) Text(item.description, Modifier.padding(start = 42.dp, end = 58.dp, bottom = 4.dp), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
    deleteCandidate?.let { item ->
        AlertDialog(
            onDismissRequest = { deleteCandidate = null },
            title = { Text("Delete ${item.name.ifBlank { "item" }}?") },
            confirmButton = { Button(onClick = { item.id?.let(onRemove); deleteCandidate = null }, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { deleteCandidate = null }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun V8QuantityBox(quantity: Int, enabled: Boolean, onPlus: () -> Unit, onMinus: () -> Unit) {
    Surface(Modifier.width(45.dp).height(56.dp), RoundedCornerShape(10.dp), MaterialTheme.colorScheme.surface, border = BorderStroke(1.4.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.SpaceEvenly) {
            Text("+", Modifier.clickable(enabled = enabled, onClick = onPlus).padding(horizontal = 12.dp), color = DidPalette.GoldDeep, fontWeight = FontWeight.Black)
            Text(quantity.toString(), fontWeight = FontWeight.Black)
            Text("-", Modifier.clickable(enabled = enabled && quantity > 0, onClick = onMinus).padding(horizontal = 12.dp), color = DidPalette.GoldDeep, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun V8NotesPage(
    snapshot: DidCharacterSnapshot,
    connected: Boolean,
    toolsOpen: Boolean,
    onToolsOpen: () -> Unit,
    onToolsDismiss: () -> Unit,
    onAdjustResources: () -> Unit,
    onOtherDice: () -> Unit,
    onHistory: () -> Unit,
    onAdd: () -> Unit,
    onEdit: (NoteSnapshot) -> Unit,
    modifier: Modifier,
) {
    val notes = snapshot.notes.sortedWith(compareByDescending<NoteSnapshot> { it.pinned }.thenBy { it.title.lowercase() })
    Column(modifier.fillMaxSize()) {
        V8Header("Notes", toolsOpen, onToolsOpen, onToolsDismiss, onAdjustResources, onOtherDice, onHistory,
            trailing = { Button(onClick = onAdd, enabled = connected) { Text("+ Add") } })
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(notes, key = { it.id ?: "${it.title}:${it.rawText.hashCode()}" }) { note ->
                var expanded by remember(note.id, note.expanded) { mutableStateOf(note.expanded) }
                val colors = v8NoteColors(note.color)
                Card(Modifier.fillMaxWidth(), RoundedCornerShape(11.dp), CardDefaults.cardColors(containerColor = colors.second), border = BorderStroke(1.5.dp, colors.first)) {
                    Column(Modifier.padding(horizontal = 8.dp, vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(38.dp).clickable { expanded = !expanded }, contentAlignment = Alignment.Center) {
                                Text(if (expanded) "▾" else "▸", fontWeight = FontWeight.Black)
                            }
                            Text(note.title.ifBlank { "Note" }, Modifier.weight(1f).clickable { expanded = !expanded }, fontWeight = FontWeight.Black)
                            if (note.pinned) Text("★", color = colors.first)
                            if (note.linkedImprovementId == null) TextButton(onClick = { onEdit(note) }, enabled = connected, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp)) { Text("Edit") }
                        }
                        if (expanded && note.text.isNotBlank()) Text(note.text, Modifier.padding(start = 38.dp, end = 4.dp, bottom = 2.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun V8BottomNavigation(page: V8Page, snapshot: DidCharacterSnapshot, onPage: (V8Page) -> Unit) {
    Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 8.dp, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        NavigationBar(containerColor = Color.Transparent, tonalElevation = 0.dp) {
            V8Page.entries.forEach { item ->
                NavigationBarItem(
                    selected = page == item,
                    onClick = { onPage(item) },
                    icon = {
                        when (item) {
                            V8Page.Character -> V8CharacterIcon()
                            V8Page.Equipment -> V8DesktopSvg(snapshot.uiIcons["inventory"], Modifier.size(30.dp))
                            V8Page.Notes -> V8DesktopSvg(snapshot.uiIcons["notes"], Modifier.size(30.dp))
                        }
                    },
                    label = { Text(item.label) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = DidPalette.GoldDeep,
                        selectedTextColor = MaterialTheme.colorScheme.onSurface,
                        indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                        unselectedIconColor = DidPalette.GoldDeep,
                        unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                )
            }
        }
    }
}

@Composable
private fun V8CharacterIcon() {
    Canvas(Modifier.size(28.dp)) {
        val c = Color(0xFFA87824); val w = size.width; val h = size.height
        val points = listOf(
            Offset(w*.50f,h*.14f), Offset(w*.548f,h*.384f), Offset(w*.755f,h*.245f), Offset(w*.616f,h*.452f),
            Offset(w*.86f,h*.50f), Offset(w*.616f,h*.548f), Offset(w*.755f,h*.755f), Offset(w*.548f,h*.616f),
            Offset(w*.50f,h*.86f), Offset(w*.452f,h*.616f), Offset(w*.245f,h*.755f), Offset(w*.384f,h*.548f),
            Offset(w*.14f,h*.50f), Offset(w*.384f,h*.452f), Offset(w*.245f,h*.245f), Offset(w*.452f,h*.384f),
        )
        val p = Path().apply { moveTo(points[0].x,points[0].y); points.drop(1).forEach { lineTo(it.x,it.y) }; close() }
        val s = Stroke(2f, cap = StrokeCap.Round, join = StrokeJoin.Round)
        drawPath(p,c,style=s); drawCircle(c,w*.045f,Offset(w/2f,h/2f),style=s)
    }
}

@Composable
private fun V8DesktopSvg(encoded: String?, modifier: Modifier) {
    val drawable = remember(encoded) {
        encoded?.let { data -> runCatching {
            val bytes = Base64.decode(data, Base64.DEFAULT)
            PictureDrawable(SVG.getFromString(String(bytes, Charsets.UTF_8)).renderToPicture())
        }.getOrNull() }
    }
    if (drawable == null) { Box(modifier, contentAlignment = Alignment.Center) { Text("◇", color = DidPalette.GoldDeep) }; return }
    AndroidView(modifier = modifier, factory = { context -> ImageView(context).apply { setLayerType(View.LAYER_TYPE_SOFTWARE, null); scaleType = ImageView.ScaleType.FIT_CENTER } }, update = { it.setImageDrawable(drawable) })
}

@Composable
private fun V8SheetCard(modifier: Modifier, strong: Boolean, content: @Composable () -> Unit) {
    Card(modifier, RoundedCornerShape(14.dp), CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), border = BorderStroke(if (strong) 2.dp else 1.5.dp, if (strong) MaterialTheme.colorScheme.outlineVariant else MaterialTheme.colorScheme.outline), content = { content() })
}

@Composable
private fun V8TextDialog(title: String, initial: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var value by remember(initial) { mutableStateOf(initial) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title, fontWeight = FontWeight.Black) }, text = { OutlinedTextField(value, { value = it }, Modifier.fillMaxWidth(), singleLine = true) }, confirmButton = { Button(onClick = { onSave(value) }) { Text("Save") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun V8InventoryDialog(item: InventoryItemSnapshot?, onDismiss: () -> Unit, onSave: (String,String,Int) -> Unit, onDelete: (() -> Unit)?) {
    var name by remember(item?.id) { mutableStateOf(item?.name.orEmpty()) }
    var description by remember(item?.id) { mutableStateOf(item?.description.orEmpty()) }
    var quantity by remember(item?.id) { mutableStateOf((item?.quantity ?: 1).toString()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (item == null) "Add inventory item" else "Edit inventory item", fontWeight = FontWeight.Black) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), label = { Text("Name") }, singleLine = true)
            OutlinedTextField(description, { description = it }, Modifier.fillMaxWidth(), label = { Text("Description") }, minLines = 3, maxLines = 7)
            OutlinedTextField(quantity, { if (it.all(Char::isDigit)) quantity = it }, Modifier.fillMaxWidth(), label = { Text("Quantity") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
        } },
        confirmButton = { Button(enabled = quantity.toIntOrNull() != null, onClick = { onSave(name, description, quantity.toIntOrNull() ?: 0) }) { Text("Save") } },
        dismissButton = { Row { onDelete?.let { TextButton(onClick = it) { Text("Delete", color = MaterialTheme.colorScheme.error) } }; TextButton(onClick = onDismiss) { Text("Cancel") } } },
    )
}

@Composable
private fun V8NoteDialog(note: NoteSnapshot?, onDismiss: () -> Unit, onSave: (String,String,String,Boolean) -> Unit, onDelete: (() -> Unit)?) {
    var title by remember(note?.id) { mutableStateOf(note?.title.orEmpty()) }
    var body by remember(note?.id) { mutableStateOf(note?.text?.text.orEmpty()) }
    var color by remember(note?.id) { mutableStateOf(note?.color ?: "#FFE98A") }
    var pinned by remember(note?.id) { mutableStateOf(note?.pinned ?: false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (note == null) "Add Note" else "Edit Note", fontWeight = FontWeight.Black) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), label = { Text("Title") }, singleLine = true)
            OutlinedTextField(body, { body = it }, Modifier.fillMaxWidth(), label = { Text("Text") }, minLines = 5, maxLines = 10)
            OutlinedTextField(color, { color = it }, Modifier.fillMaxWidth(), label = { Text("Color (name or #RRGGBB)") }, singleLine = true)
            Row(verticalAlignment = Alignment.CenterVertically) { Spacer(Modifier.weight(1f)); Text("Pinned"); Checkbox(pinned, { pinned = it }) }
        } },
        confirmButton = { Button(onClick = { onSave(title, body, color, pinned) }) { Text("Save") } },
        dismissButton = { Row { onDelete?.let { TextButton(onClick = it) { Text("Delete", color = MaterialTheme.colorScheme.error) } }; TextButton(onClick = onDismiss) { Text("Cancel") } } },
    )
}

@Composable
private fun V8ImprovementEditDialog(improvement: ImprovementSnapshot, onDismiss: () -> Unit, onSave: (JSONObject,String?,String?) -> Unit) {
    val initial = remember(improvement.id) { improvement.choices?.keys()?.asSequence()?.filterNot { it.startsWith("_") }?.associateWith { improvement.choices.opt(it)?.toString().orEmpty() } ?: emptyMap() }
    val values = remember(improvement.id) { mutableStateMapOf<String,String>().apply { putAll(initial) } }
    var customName by remember(improvement.id) { mutableStateOf(improvement.name) }
    var customDescription by remember(improvement.id) { mutableStateOf(improvement.description) }
    val custom = improvement.catalogId == "custom" || improvement.source == "custom"
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Edit ${improvement.name}", fontWeight = FontWeight.Black) },
        text = { LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (custom) {
                item { OutlinedTextField(customName, { customName = it }, Modifier.fillMaxWidth(), label = { Text("Name") }) }
                item { OutlinedTextField(customDescription, { customDescription = it }, Modifier.fillMaxWidth(), label = { Text("Description") }, minLines = 3) }
            }
            values.keys.sorted().forEach { key -> item(key) { OutlinedTextField(values[key].orEmpty(), { values[key] = it }, Modifier.fillMaxWidth(), label = { Text(key.replace('_',' ').replaceFirstChar { it.titlecase() }) }) } }
        } },
        confirmButton = { Button(onClick = { val json = JSONObject(); values.forEach { (k,v) -> json.put(k,v) }; onSave(json, customName.takeIf { custom }, customDescription.takeIf { custom }) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun V8LinkedNoteDialog(note: NoteSnapshot, onDismiss: () -> Unit) {
    val colors = v8NoteColors(note.color)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(note.title.ifBlank { "Note" }, fontWeight = FontWeight.Black) },
        text = { Surface(Modifier.fillMaxWidth(), RoundedCornerShape(10.dp), colors.second, border = BorderStroke(1.5.dp, colors.first)) { Text(note.text, Modifier.padding(10.dp)) } },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun V8AbilityInfoDialog(stat: StatSnapshot, snapshot: DidCharacterSnapshot, onDismiss: () -> Unit) {
    val help = snapshot.uiIcons["ability-help:${stat.key}"]?.takeIf { it.isNotBlank() }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stat.name, fontWeight = FontWeight.Black) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            help?.let { Text(it) }
            Text("Die: d${stat.dieSize}")
            Text("Bonus: ${if (stat.bonus >= 0) "+${stat.bonus}" else stat.bonus}")
        } },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun V8AbilityActionDialog(stat: StatSnapshot, snapshot: DidCharacterSnapshot, onDismiss: () -> Unit, onInfo: () -> Unit, onRoll: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stat.name, fontWeight = FontWeight.Black) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            snapshot.uiIcons["ability-help:${stat.key}"]?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            Text("Long-press options", fontWeight = FontWeight.Bold)
        } },
        confirmButton = { Button(onClick = onRoll) { Text("Roll") } },
        dismissButton = { Row { TextButton(onClick = onInfo) { Text("Info") }; TextButton(onClick = onDismiss) { Text("Cancel") } } },
    )
}

@Composable
private fun V8AdjustResourcesDialog(snapshot: DidCharacterSnapshot, onDismiss: () -> Unit, onSave: (Int,Int,Int) -> Unit) {
    var hearts by remember { mutableStateOf(snapshot.hp.maxHearts.toString()) }
    var ip by remember { mutableStateOf(snapshot.progression.currentIp.toString()) }
    var at by remember { mutableStateOf(snapshot.adversity.max.toString()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Adjust Resources", fontWeight = FontWeight.Black) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(hearts, { if (it.all(Char::isDigit)) hearts = it }, label = { Text("Maximum Hearts") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            OutlinedTextField(ip, { if (it.all(Char::isDigit)) ip = it }, label = { Text("Total IP") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            OutlinedTextField(at, { if (it.all(Char::isDigit)) at = it }, label = { Text("Maximum AT") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
        } },
        confirmButton = { Button(enabled = hearts.toIntOrNull()!=null && ip.toIntOrNull()!=null && at.toIntOrNull()!=null, onClick = { onSave(hearts.toIntOrNull()?:0, ip.toIntOrNull()?:0, at.toIntOrNull()?:0) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun V8OtherDiceDialog(onDismiss: () -> Unit, onRoll: (Map<Int,Int>) -> Unit) {
    val sides = listOf(4,6,8,10,12,20,100)
    val counts = remember { mutableStateMapOf<Int,Int>().apply { sides.forEach { put(it,0) } } }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Roll Other Dice", fontWeight = FontWeight.Black) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(4.dp)) { sides.forEach { die -> Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("d$die", Modifier.weight(1f), fontWeight = FontWeight.Bold)
            TextButton(onClick = { counts[die] = (counts[die] ?: 0).minus(1).coerceAtLeast(0) }) { Text("−") }
            Text((counts[die] ?: 0).toString(), Modifier.width(28.dp), textAlign = TextAlign.Center)
            TextButton(onClick = { counts[die] = ((counts[die] ?: 0) + 1).coerceAtMost(20) }) { Text("+") }
        } } } },
        confirmButton = { Button(enabled = counts.values.sum() > 0, onClick = { onRoll(counts.toMap()) }) { Text("Roll") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun V8HistoryDialog(history: List<String>, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Previous Rolls", fontWeight = FontWeight.Black) }, text = { LazyColumn(verticalArrangement = Arrangement.spacedBy(7.dp)) { if (history.isEmpty()) item { Text("No rolls this session.") } else items(history) { Text(it) } } }, confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } })
}

@Composable
private fun V8DiceResultDialog(result: DidCompanionViewModel.DiceResult, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text(result.title, fontWeight = FontWeight.Black) }, text = { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text(result.total.toString(), style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Black); Text(result.detail, textAlign = TextAlign.Center) } }, confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } })
}

@Composable
private fun v8NoteColors(value: String?): Pair<Color,Color> {
    val raw = value?.trim().orEmpty()
    val named = mapOf(
        "red" to Color(0xFFF3A6A6), "orange" to Color(0xFFFFC078), "yellow" to Color(0xFFFFE98A),
        "green" to Color(0xFFA8E6B0), "blue" to Color(0xFF9FCFE3), "purple" to Color(0xFFC8B6FF), "pink" to Color(0xFFF4B6CF),
    )
    val base = when {
        raw.matches(Regex("#[0-9A-Fa-f]{6}")) -> runCatching { Color(android.graphics.Color.parseColor(raw)) }.getOrNull()
        else -> named[raw.lowercase()]
    } ?: named.getValue("yellow")
    if (isSystemInDarkTheme()) {
        val body = Color(base.red * .34f, base.green * .34f, base.blue * .34f, 1f)
        val border = Color((base.red * .55f).coerceAtMost(1f), (base.green * .55f).coerceAtMost(1f), (base.blue * .55f).coerceAtMost(1f), 1f)
        return border to body
    }
    val body = Color(
        (base.red + (1f-base.red)*.42f).coerceAtMost(1f),
        (base.green + (1f-base.green)*.42f).coerceAtMost(1f),
        (base.blue + (1f-base.blue)*.42f).coerceAtMost(1f), 1f
    )
    return base to body
}
