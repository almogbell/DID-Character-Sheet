package com.did.charactersheet.sync

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.did.charactersheet.ui.DidPalette
import org.json.JSONObject
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * Phase 9 visual-parity pass based directly on the finished Windows sheet.
 * Windows remains authoritative for every mutation.
 */
@Composable
fun Phase9CompanionSheetV2(
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
    var page by remember { mutableStateOf(Phase9V2Page.Character) }
    var editName by remember { mutableStateOf(false) }
    var inventoryEdit by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    var addingInventory by remember { mutableStateOf(false) }
    val canEdit = connected && !pending

    Column(modifier.fillMaxSize()) {
        when (page) {
            Phase9V2Page.Character -> Phase9V2CharacterPage(
                snapshot = snapshot,
                controlsEnabled = canEdit,
                onHpChange = onHpChange,
                onAtChange = onAtChange,
                onIpChange = onIpChange,
                onEditName = { editName = true },
                modifier = Modifier.weight(1f),
            )
            Phase9V2Page.Equipment -> Phase9V2EquipmentPage(
                snapshot = snapshot,
                controlsEnabled = canEdit,
                onAdd = { addingInventory = true },
                onEdit = { inventoryEdit = it },
                modifier = Modifier.weight(1f),
            )
            Phase9V2Page.Notes -> Phase9V2NotesPage(snapshot, Modifier.weight(1f))
        }
        Phase9V2BottomNavigation(page = page, onPage = { page = it })
    }

    if (editName) {
        Phase9V2TextDialog(
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
        Phase9V2InventoryEditDialog(
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

    // Intentionally retained in the signature because the sync protocol already
    // supports it; Phase 9 no longer exposes a dedicated Backstory button.
    @Suppress("UNUSED_VARIABLE")
    val retainedBackstoryCommand = onSetBackstory
}

private enum class Phase9V2Page(val label: String, val symbol: String) {
    Character("Character", "◆"), Equipment("Equipment", "▣"), Notes("Notes", "✎")
}

@Composable
private fun Phase9V2BottomNavigation(page: Phase9V2Page, onPage: (Phase9V2Page) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 8.dp,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        NavigationBar(containerColor = Color.Transparent, tonalElevation = 0.dp) {
            Phase9V2Page.entries.forEach { item ->
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
private fun Phase9V2CharacterPage(
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
        Phase9V2CharacterHeader(snapshot, controlsEnabled, onEditName)
        Phase9V2ResourcePanel(snapshot, controlsEnabled, onHpChange, onAtChange, onIpChange)
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
        if (tab == 0) Phase9V2Abilities(snapshot, Modifier.fillMaxSize())
        else Phase9V2Improvements(snapshot, Modifier.fillMaxSize())
    }
}

@Composable
private fun Phase9V2CharacterHeader(
    snapshot: DidCharacterSnapshot,
    canEdit: Boolean,
    onEditName: () -> Unit,
) {
    Phase9V2SheetCard(
        Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 7.dp),
        strongBorder = true,
    ) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Phase9V2Portrait(snapshot, Modifier.width(112.dp).aspectRatio(0.78f))
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
private fun Phase9V2Portrait(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val raw = snapshot.portrait.currentImage?.data
    val bitmap = remember(raw) { raw?.phase9V2DecodeBitmap() }
    Box(
        modifier.clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.surface),
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(
                bitmap = bitmap.asImageBitmap(),
                contentDescription = "Character portrait",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize().padding(3.dp),
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

private fun String.phase9V2DecodeBitmap() = runCatching {
    val bytes = Base64.decode(substringAfter("base64,", this), Base64.DEFAULT)
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
}.getOrNull()

@Composable
private fun Phase9V2ResourcePanel(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
) {
    Phase9V2SheetCard(
        Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp),
        strongBorder = true,
    ) {
        Column(Modifier.fillMaxWidth().padding(10.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Hearts", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Black)
                    Phase9V2Hearts(snapshot.hp)
                }
                Phase9V2DefenseBadge("BDV", snapshot.bdv, DefenseBadgeKind.BDV)
                Spacer(Modifier.width(5.dp))
                Phase9V2DefenseBadge("DR", snapshot.dr, DefenseBadgeKind.DR)
            }

            HorizontalDivider(Modifier.padding(vertical = 7.dp), color = MaterialTheme.colorScheme.outlineVariant)

            Phase9V2ResourceRow(
                "HP", "${snapshot.hp.current} / ${snapshot.hp.max}", enabled,
                snapshot.hp.current > 0, snapshot.hp.current < snapshot.hp.max, onHpChange,
            )

            Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Adversity Tokens", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Black)
                    Phase9V2Adversity(snapshot.adversity)
                }
                Phase9V2DeltaButtons(
                    enabled,
                    snapshot.adversity.current > 0,
                    snapshot.adversity.current < snapshot.adversity.max,
                    onAtChange,
                )
            }

            Phase9V2ResourceRow(
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
private fun Phase9V2ResourceRow(
    title: String,
    value: String,
    enabled: Boolean,
    canDown: Boolean,
    canUp: Boolean,
    onChange: (Int) -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(top = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Black)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
        }
        Phase9V2DeltaButtons(enabled, canDown, canUp, onChange)
    }
}

@Composable
private fun Phase9V2DeltaButtons(enabled: Boolean, canDown: Boolean, canUp: Boolean, onChange: (Int) -> Unit) {
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
private fun Phase9V2Hearts(hp: HpSnapshot) {
    val hearts = hp.maxHearts.coerceAtLeast(((hp.max + 3) / 4).coerceAtLeast(1))
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        repeat(hearts) { heartIndex ->
            Phase9V2Heart((hp.current - heartIndex * 4).coerceIn(0, 4))
        }
    }
}

@Composable
private fun Phase9V2Heart(filledQuarters: Int) {
    val fill = if (isSystemInDarkTheme()) Color(0xFFB33A42) else Color.Red
    val empty = if (isSystemInDarkTheme()) Color(0xFF18232E) else Color.White
    Canvas(Modifier.size(35.dp, 32.dp)) {
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
            if (filledQuarters >= 1) drawRect(fill, topLeft = Offset(0f, 0f), size = androidx.compose.ui.geometry.Size(w / 2, h / 2))
            if (filledQuarters >= 2) drawRect(fill, topLeft = Offset(w / 2, 0f), size = androidx.compose.ui.geometry.Size(w / 2, h / 2))
            if (filledQuarters >= 3) drawRect(fill, topLeft = Offset(0f, h / 2), size = androidx.compose.ui.geometry.Size(w / 2, h / 2))
            if (filledQuarters >= 4) drawRect(fill, topLeft = Offset(w / 2, h / 2), size = androidx.compose.ui.geometry.Size(w / 2, h / 2))
        }
        drawPath(heart, fill, style = Stroke(width = 2.2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        drawLine(fill, Offset(w * 0.50f, h * 0.15f), Offset(w * 0.50f, h * 0.95f), 1.7f)
        drawLine(fill, Offset(w * 0.12f, h * 0.50f), Offset(w * 0.90f, h * 0.50f), 1.7f)
    }
}

private enum class DefenseBadgeKind { BDV, DR }

@Composable
private fun Phase9V2DefenseBadge(label: String, value: Int, kind: DefenseBadgeKind) {
    Column(Modifier.width(54.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Black)
        Box(Modifier.size(47.dp), contentAlignment = Alignment.Center) {
            Canvas(Modifier.fillMaxSize()) {
                if (kind == DefenseBadgeKind.BDV) {
                    val p = Path()
                    val cx = size.width / 2
                    val cy = size.height / 2
                    repeat(24) { n ->
                        val angle = -PI / 2 + n * PI / 12
                        val radius = if (n % 2 == 0) size.minDimension * 0.48 else size.minDimension * 0.34
                        val x = cx + (radius * cos(angle)).toFloat()
                        val y = cy + (radius * sin(angle)).toFloat()
                        if (n == 0) p.moveTo(x, y) else p.lineTo(x, y)
                    }
                    p.close()
                    drawPath(p, Color(0xFFC82541))
                } else {
                    val p = Path().apply {
                        moveTo(size.width * 0.18f, size.height * 0.12f)
                        lineTo(size.width * 0.82f, size.height * 0.12f)
                        lineTo(size.width * 0.78f, size.height * 0.58f)
                        cubicTo(size.width * 0.72f, size.height * 0.78f, size.width * 0.59f, size.height * 0.89f, size.width * 0.50f, size.height * 0.96f)
                        cubicTo(size.width * 0.41f, size.height * 0.89f, size.width * 0.28f, size.height * 0.78f, size.width * 0.22f, size.height * 0.58f)
                        close()
                    }
                    drawPath(p, Color(0xFF2F5F91))
                }
            }
            Text(value.toString(), color = Color(0xFFF5EEE3), fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun Phase9V2Adversity(at: AdversitySnapshot) {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(at.max.coerceAtLeast(0)) { index ->
            val filled = index < at.current
            Canvas(Modifier.size(21.dp)) {
                val p = Path().apply {
                    moveTo(size.width / 2, 1f)
                    lineTo(size.width - 1f, size.height / 2)
                    lineTo(size.width / 2, size.height - 1f)
                    lineTo(1f, size.height / 2)
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

private val phase9V2AbilityColors = mapOf(
    "agility" to Color(0xFF6F8F2C),
    "finesse" to Color(0xFF356FA8),
    "instinct" to Color(0xFF6B55A6),
    "knowledge" to Color(0xFFB17828),
    "presence" to Color(0xFF2F8792),
    "strength" to Color(0xFFA8453C),
)

@Composable
private fun Phase9V2Abilities(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val sorted = snapshot.stats.sortedWith(compareByDescending<StatSnapshot> { it.dieSize }.thenByDescending { it.bonus }.thenBy { it.key })
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item { Phase9V2Heading("Abilities", snapshot.defenseStatName?.let { "Defense: $it" }) }
        items(sorted, key = { it.key }) { stat ->
            val accent = phase9V2AbilityColors[stat.key] ?: Color(0xFF2F5F91)
            Phase9V2SheetCard(Modifier.fillMaxWidth(), false) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Phase9V2AbilityEmblem(stat.key, accent)
                    Text(
                        "d${stat.dieSize}",
                        modifier = Modifier.width(50.dp),
                        color = accent,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Black,
                    )
                    Column(Modifier.weight(1f)) {
                        Text(stat.name, color = accent, fontWeight = FontWeight.Black)
                        if (stat.name == snapshot.defenseStatName) {
                            Text("Defense ability", style = MaterialTheme.typography.labelSmall, color = accent.copy(alpha = 0.82f))
                        }
                    }
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
private fun Phase9V2AbilityEmblem(kind: String, accent: Color) {
    Canvas(Modifier.size(44.dp)) {
        val stroke = Stroke(width = 2.4f, cap = StrokeCap.Round, join = StrokeJoin.Round)
        drawCircle(Color(0xFFFFFDF7))
        drawCircle(accent, style = Stroke(width = 2f))
        val w = size.width
        val h = size.height
        when (kind) {
            "agility" -> {
                val wing = Path().apply {
                    moveTo(w * 0.25f, h * 0.67f)
                    cubicTo(w * 0.33f, h * 0.30f, w * 0.68f, h * 0.22f, w * 0.78f, h * 0.31f)
                    cubicTo(w * 0.62f, h * 0.42f, w * 0.56f, h * 0.62f, w * 0.25f, h * 0.67f)
                }
                drawPath(wing, accent, style = stroke)
                drawLine(accent, Offset(w * 0.30f, h * 0.59f), Offset(w * 0.63f, h * 0.38f), 2f)
                drawLine(accent, Offset(w * 0.36f, h * 0.64f), Offset(w * 0.68f, h * 0.48f), 2f)
            }
            "finesse" -> {
                drawLine(accent, Offset(w * 0.28f, h * 0.72f), Offset(w * 0.72f, h * 0.28f), 3f, StrokeCap.Round)
                drawLine(accent, Offset(w * 0.28f, h * 0.28f), Offset(w * 0.72f, h * 0.72f), 3f, StrokeCap.Round)
                drawLine(accent, Offset(w * 0.23f, h * 0.60f), Offset(w * 0.40f, h * 0.77f), 2f)
                drawLine(accent, Offset(w * 0.60f, h * 0.23f), Offset(w * 0.77f, h * 0.40f), 2f)
            }
            "instinct" -> {
                val eye = Path().apply {
                    moveTo(w * 0.18f, h * 0.50f)
                    cubicTo(w * 0.33f, h * 0.28f, w * 0.67f, h * 0.28f, w * 0.82f, h * 0.50f)
                    cubicTo(w * 0.67f, h * 0.72f, w * 0.33f, h * 0.72f, w * 0.18f, h * 0.50f)
                }
                drawPath(eye, accent, style = stroke)
                drawCircle(accent, radius = w * 0.09f, center = Offset(w * 0.50f, h * 0.50f))
            }
            "knowledge" -> {
                val left = Path().apply {
                    moveTo(w * 0.20f, h * 0.30f)
                    cubicTo(w * 0.34f, h * 0.26f, w * 0.42f, h * 0.30f, w * 0.50f, h * 0.38f)
                    lineTo(w * 0.50f, h * 0.72f)
                    cubicTo(w * 0.40f, h * 0.64f, w * 0.31f, h * 0.62f, w * 0.20f, h * 0.66f)
                    close()
                }
                val right = Path().apply {
                    moveTo(w * 0.80f, h * 0.30f)
                    cubicTo(w * 0.66f, h * 0.26f, w * 0.58f, h * 0.30f, w * 0.50f, h * 0.38f)
                    lineTo(w * 0.50f, h * 0.72f)
                    cubicTo(w * 0.60f, h * 0.64f, w * 0.69f, h * 0.62f, w * 0.80f, h * 0.66f)
                    close()
                }
                drawPath(left, accent, style = stroke)
                drawPath(right, accent, style = stroke)
            }
            "presence" -> {
                val mask = Path().apply {
                    moveTo(w * 0.27f, h * 0.27f)
                    cubicTo(w * 0.40f, h * 0.20f, w * 0.60f, h * 0.20f, w * 0.73f, h * 0.27f)
                    lineTo(w * 0.68f, h * 0.65f)
                    cubicTo(w * 0.60f, h * 0.76f, w * 0.40f, h * 0.76f, w * 0.32f, h * 0.65f)
                    close()
                }
                drawPath(mask, accent, style = stroke)
                drawLine(accent, Offset(w * 0.34f, h * 0.43f), Offset(w * 0.44f, h * 0.46f), 2f)
                drawLine(accent, Offset(w * 0.56f, h * 0.46f), Offset(w * 0.66f, h * 0.43f), 2f)
                drawLine(accent, Offset(w * 0.42f, h * 0.61f), Offset(w * 0.58f, h * 0.61f), 2f)
            }
            "strength" -> {
                val fist = Path().apply {
                    moveTo(w * 0.27f, h * 0.68f)
                    lineTo(w * 0.25f, h * 0.43f)
                    cubicTo(w * 0.25f, h * 0.35f, w * 0.32f, h * 0.31f, w * 0.38f, h * 0.35f)
                    cubicTo(w * 0.39f, h * 0.27f, w * 0.49f, h * 0.25f, w * 0.54f, h * 0.33f)
                    cubicTo(w * 0.59f, h * 0.26f, w * 0.69f, h * 0.29f, w * 0.70f, h * 0.38f)
                    lineTo(w * 0.73f, h * 0.56f)
                    cubicTo(w * 0.70f, h * 0.69f, w * 0.60f, h * 0.75f, w * 0.46f, h * 0.75f)
                    close()
                }
                drawPath(fist, accent, style = stroke)
                drawLine(accent, Offset(w * 0.38f, h * 0.36f), Offset(w * 0.39f, h * 0.50f), 1.8f)
                drawLine(accent, Offset(w * 0.53f, h * 0.34f), Offset(w * 0.54f, h * 0.50f), 1.8f)
                drawLine(accent, Offset(w * 0.67f, h * 0.39f), Offset(w * 0.66f, h * 0.52f), 1.8f)
            }
        }
    }
}

@Composable
private fun Phase9V2Improvements(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    var previewNote by remember { mutableStateOf<NoteSnapshot?>(null) }
    val improvements = snapshot.improvements.sortedWith(compareBy<ImprovementSnapshot> { it.sortOrder }.thenBy { it.name.lowercase() })

    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item { Phase9V2Heading("Improvements", trailing = "${snapshot.progression.currentIp} IP") }
        if (improvements.isEmpty()) item { Phase9V2Empty("No improvements yet.") }
        items(improvements, key = { it.id ?: "${it.name}:${it.sortOrder}" }) { improvement ->
            var expanded by remember(improvement.id, improvement.expanded) {
                mutableStateOf(improvement.expanded || improvement.description.isNotBlank())
            }
            val linkedNotes = phase9V2LinkedNotes(snapshot, improvement)
            Phase9V2SheetCard(Modifier.fillMaxWidth().clickable { expanded = !expanded }, false) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(if (expanded) "▾" else "▸", Modifier.width(20.dp), color = MaterialTheme.colorScheme.secondary)
                        Text(improvement.name, Modifier.weight(1f), fontWeight = FontWeight.Black)
                        linkedNotes.take(3).forEach { note ->
                            Phase9V2NoteIcon(note.color) { previewNote = note }
                            Spacer(Modifier.width(3.dp))
                        }
                        if (improvement.timesTaken > 1) Text("×${improvement.timesTaken}  ")
                        if (improvement.cost > 0) Text("${improvement.cost} IP", fontWeight = FontWeight.Bold)
                    }
                    if (expanded) {
                        if (improvement.description.isNotBlank()) {
                            Text(didRichText(improvement.description), style = MaterialTheme.typography.bodyMedium)
                        }
                        phase9V2Choices(improvement.choices)?.let {
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
                                        Text(didRichText(empowerment.description), style = MaterialTheme.typography.bodySmall)
                                    }
                                    phase9V2Choices(empowerment.choices)?.let {
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
        AlertDialog(
            onDismissRequest = { previewNote = null },
            title = { Text(note.title.ifBlank { "Note" }, fontWeight = FontWeight.Black) },
            text = { Text(note.text) },
            confirmButton = { TextButton(onClick = { previewNote = null }) { Text("Close") } },
        )
    }
}

private fun phase9V2LinkedNotes(snapshot: DidCharacterSnapshot, improvement: ImprovementSnapshot): List<NoteSnapshot> {
    val direct = snapshot.notes.filter { note ->
        improvement.id != null && note.linkedImprovementId == improvement.id
    }
    val builtinTitle = when (improvement.catalogId) {
        "spellcasting", "magic_novice" -> "spellcasting verbs"
        "sneak_attack" -> "sneak attack"
        "animal_buddy" -> "animal buddy"
        else -> null
    }
    val builtin = if (builtinTitle == null) emptyList() else snapshot.notes.filter { it.title.trim().lowercase() == builtinTitle }
    return (direct + builtin).distinctBy { it.id ?: "${it.title}:${it.text.text}" }
}

private fun phase9V2Choices(choices: JSONObject?): String? {
    if (choices == null || choices.length() == 0) return null
    val parts = choices.keys().asSequence().filterNot { it.startsWith("_") }.mapNotNull { key ->
        val value = choices.opt(key)?.toString()?.takeIf { it.isNotBlank() && it != "null" } ?: return@mapNotNull null
        "${key.replace('_', ' ').replaceFirstChar { it.titlecase() }}: $value"
    }.toList()
    return parts.takeIf { it.isNotEmpty() }?.joinToString(" • ")
}

@Composable
private fun Phase9V2NoteIcon(colorKey: String?, onClick: () -> Unit) {
    val (border, fill) = phase9V2NoteColors(colorKey)
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
private fun Phase9V2EquipmentPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onAdd: () -> Unit,
    onEdit: (InventoryItemSnapshot) -> Unit,
    modifier: Modifier,
) {
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Phase9V2Heading("Inventory", trailing = "${snapshot.inventory.size} items", modifier = Modifier.weight(1f))
                Spacer(Modifier.width(6.dp))
                Button(onClick = onAdd, enabled = controlsEnabled) { Text("+ Add") }
            }
        }
        if (snapshot.inventory.isEmpty()) item { Phase9V2Empty("No equipment.") }
        items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
            var expanded by remember(item.id, item.expanded) { mutableStateOf(item.expanded) }
            Phase9V2SheetCard(Modifier.fillMaxWidth(), false) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(if (expanded) "▾" else "▸", Modifier.width(22.dp).clickable { expanded = !expanded }, color = MaterialTheme.colorScheme.secondary)
                        Text(item.name.ifBlank { "Unnamed item" }, Modifier.weight(1f).clickable { expanded = !expanded }, fontWeight = FontWeight.Black)
                        Surface(
                            shape = RoundedCornerShape(7.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        ) { Text("×${item.quantity}", Modifier.padding(horizontal = 8.dp, vertical = 4.dp), fontWeight = FontWeight.Black) }
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
private fun Phase9V2NotesPage(snapshot: DidCharacterSnapshot, modifier: Modifier) {
    val notes = snapshot.notes.sortedWith(compareByDescending<NoteSnapshot> { it.pinned }.thenBy { it.title.lowercase() })
    LazyColumn(modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Phase9V2Heading("Notes", trailing = notes.size.toString()) }
        if (notes.isEmpty()) item { Phase9V2Empty("No notes.") }
        items(notes, key = { it.id ?: "${it.title}:${it.text.text.hashCode()}" }) { note ->
            var expanded by remember(note.id, note.expanded) { mutableStateOf(note.expanded) }
            val colors = phase9V2NoteColors(note.color)
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
private fun phase9V2NoteColors(value: String?): Pair<Color, Color> {
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
private fun Phase9V2Heading(
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
private fun Phase9V2Empty(text: String) {
    Phase9V2SheetCard(Modifier.fillMaxWidth(), false) {
        Text(text, Modifier.fillMaxWidth().padding(18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Phase9V2SheetCard(modifier: Modifier, strongBorder: Boolean, content: @Composable () -> Unit) {
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
private fun Phase9V2TextDialog(
    title: String,
    initial: String,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
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
private fun Phase9V2InventoryEditDialog(
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
