from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one match for replacement, found {text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    kt = "android/phase8/Phase9CompanionSheetV4.kt"

    replace_once(
        kt,
        "import androidx.compose.ui.draw.clip\n",
        "import androidx.compose.ui.draw.clip\nimport androidx.compose.ui.draw.scale\n",
    )

    replace_once(
        kt,
        "        V4BottomNavigation(page, onPage = { page = it })",
        "        V4BottomNavigation(page, snapshot, onPage = { page = it })",
    )

    start = "@Composable\nprivate fun V4BottomNavigation(page: V4Page, onPage: (V4Page) -> Unit) {"
    end = "\n\n@Composable\nprivate fun V4CharacterPage("
    p = ROOT / kt
    text = p.read_text(encoding="utf-8")
    i = text.find(start)
    j = text.find(end, i)
    if i < 0 or j < 0:
        raise SystemExit("Could not locate bottom navigation block")
    nav = '''@Composable
private fun V4BottomNavigation(page: V4Page, snapshot: DidCharacterSnapshot, onPage: (V4Page) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 8.dp,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        NavigationBar(containerColor = Color.Transparent, tonalElevation = 0.dp) {
            V4Page.entries.forEach { item ->
                NavigationBarItem(
                    selected = page == item,
                    onClick = { onPage(item) },
                    icon = { V4AppNavigationIcon(item, selected = page == item, snapshot = snapshot) },
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
private fun V4AppNavigationIcon(page: V4Page, selected: Boolean, snapshot: DidCharacterSnapshot) {
    when (page) {
        V4Page.Equipment -> V4DesktopSvg(snapshot.uiIcons["inventory"], Modifier.size(30.dp))
        V4Page.Notes -> V4DesktopSvg(snapshot.uiIcons["notes"], Modifier.size(30.dp))
        V4Page.Character -> {
            val color = if (selected) MaterialTheme.colorScheme.onPrimaryContainer
            else MaterialTheme.colorScheme.onSurfaceVariant
            Canvas(Modifier.size(28.dp)) {
                val stroke = Stroke(width = 2.0f, cap = StrokeCap.Round, join = StrokeJoin.Round)
                val w = size.width
                val h = size.height
                val points = listOf(
                    Offset(w * .50f, h * .14f), Offset(w * .548f, h * .384f),
                    Offset(w * .755f, h * .245f), Offset(w * .616f, h * .452f),
                    Offset(w * .86f, h * .50f), Offset(w * .616f, h * .548f),
                    Offset(w * .755f, h * .755f), Offset(w * .548f, h * .616f),
                    Offset(w * .50f, h * .86f), Offset(w * .452f, h * .616f),
                    Offset(w * .245f, h * .755f), Offset(w * .384f, h * .548f),
                    Offset(w * .14f, h * .50f), Offset(w * .384f, h * .452f),
                    Offset(w * .245f, h * .245f), Offset(w * .452f, h * .384f),
                )
                val path = Path().apply {
                    moveTo(points.first().x, points.first().y)
                    points.drop(1).forEach { lineTo(it.x, it.y) }
                    close()
                }
                drawPath(path, color, style = stroke)
                drawCircle(color, radius = w * .045f, center = Offset(w / 2f, h / 2f), style = stroke)
            }
        }
    }
}'''
    p.write_text(text[:i] + nav + text[j:], encoding="utf-8")

    replace_once(
        kt,
        "                                modifier = Modifier.fillMaxSize(),",
        "                                modifier = Modifier.fillMaxSize().scale(1.48f),",
    )

    replace_once(
        kt,
        "        Text(\"${at.current}/${at.max}\", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)\n",
        "",
    )

    replace_once(
        kt,
        "                onEdit = { inventoryEdit = it },\n                onRemove = onRemoveInventoryItem,",
        "                onEdit = { inventoryEdit = it },\n                onUpdate = onUpdateInventoryItem,\n                onRemove = onRemoveInventoryItem,",
    )

    text = p.read_text(encoding="utf-8")
    start = "@Composable\nprivate fun V4EquipmentPage("
    end = "\n\n@Composable\nprivate fun V4NotesPage("
    i = text.find(start)
    j = text.find(end, i)
    if i < 0 or j < 0:
        raise SystemExit("Could not locate equipment block")
    equipment = '''@Composable
private fun V4EquipmentPage(
    snapshot: DidCharacterSnapshot,
    controlsEnabled: Boolean,
    onAdd: () -> Unit,
    onEdit: (InventoryItemSnapshot) -> Unit,
    onUpdate: (String, String, String, Int) -> Unit,
    onRemove: (String) -> Unit,
    modifier: Modifier,
) {
    var deleteCandidate by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    Box(modifier) {
        LazyColumn(Modifier.fillMaxSize().padding(10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    V4Heading("Inventory", modifier = Modifier.weight(1f))
                    Spacer(Modifier.width(6.dp))
                    Button(onClick = onAdd, enabled = controlsEnabled) { Text("+ Add") }
                }
            }
            if (snapshot.inventory.isEmpty()) item { V4Empty("No equipment.") }
            items(snapshot.inventory, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
                var expanded by remember(item.id, item.expanded) { mutableStateOf(item.expanded) }
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(7.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    V4SheetCard(Modifier.weight(1f), strongBorder = false) {
                        Column(
                            Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                            verticalArrangement = Arrangement.spacedBy(5.dp),
                        ) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    if (expanded) "▾" else "▸",
                                    Modifier.width(22.dp).clickable { expanded = !expanded },
                                    color = MaterialTheme.colorScheme.secondary,
                                )
                                Text(
                                    item.name.ifBlank { "Unnamed item" },
                                    Modifier.weight(1f).pointerInput(item.id, controlsEnabled) {
                                        detectTapGestures(
                                            onTap = { expanded = !expanded },
                                            onDoubleTap = { if (controlsEnabled) onEdit(item) },
                                        )
                                    },
                                    fontWeight = FontWeight.Black,
                                )
                                if (item.id != null) {
                                    Text(
                                        "×",
                                        modifier = Modifier
                                            .padding(start = 8.dp)
                                            .clickable(enabled = controlsEnabled) { deleteCandidate = item },
                                        color = MaterialTheme.colorScheme.secondary,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Black,
                                    )
                                }
                            }
                            if (expanded && item.description.isNotBlank()) Text(item.description)
                        }
                    }
                    V4InventoryQuantityBox(
                        quantity = item.quantity,
                        enabled = controlsEnabled && item.id != null,
                        onIncrease = {
                            item.id?.let { id ->
                                onUpdate(id, item.name, item.description, item.quantity + 1)
                            }
                        },
                    )
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
private fun V4InventoryQuantityBox(quantity: Int, enabled: Boolean, onIncrease: () -> Unit) {
    Surface(
        modifier = Modifier.width(48.dp).height(58.dp),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.5.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                "+",
                modifier = Modifier.clickable(enabled = enabled, onClick = onIncrease),
                color = MaterialTheme.colorScheme.secondary,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Black,
            )
            Text(quantity.toString(), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Black)
        }
    }
}'''
    p.write_text(text[:i] + equipment + text[j:], encoding="utf-8")

    adapter = "windows/mobile_sync_frontend_adapter.py"
    replace_once(
        adapter,
        '            "dr": os.path.join(app_dir, "icons", "defenses", "dr.svg"),\n        }\n        result: dict[str, str] = {}',
        '            "dr": os.path.join(app_dir, "icons", "defenses", "dr.svg"),\n            "inventory": os.path.join(app_dir, "icons", "headers", "inventory.svg"),\n        }\n        for candidate in (\n            os.path.join(app_dir, "icons", "notes", "custom.svg"),\n            os.path.join(app_dir, "icons", "headers", "notes.svg"),\n            os.path.join(app_dir, "icons", "notes.svg"),\n        ):\n            if os.path.isfile(candidate):\n                paths["notes"] = candidate\n                break\n        result: dict[str, str] = {}',
    )

    replace_once(
        "android/app/build.gradle.kts",
        '        versionCode = 12\n        versionName = "0.8.0"',
        '        versionCode = 13\n        versionName = "0.8.0"',
    )
    replace_once(
        "android/app/build.gradle.kts",
        '            versionNameSuffix = "-phase9-test2-v5"',
        '            versionNameSuffix = "-phase9-test2-v6"',
    )

    validator = "sync/validate_phase9_mobile.py"
    replace_once(
        validator,
        '        "V4QuantityCircle",\n        \'Text("⋮"\',',
        '        "V4InventoryQuantityBox",\n        \'Text("×"\',',
    )
    replace_once(
        validator,
        '        "V4AppNavigationIcon",\n        "onDoubleTap",',
        '        "V4AppNavigationIcon",\n        \'snapshot.uiIcons["inventory"]\',\n        \'snapshot.uiIcons["notes"]\',\n        ".scale(1.48f)",\n        "onDoubleTap",',
    )
    replace_once(
        validator,
        '        \'"dr": os.path.join(app_dir, "icons", "defenses", "dr.svg")\',\n        \'action == "identity.set"\',',
        '        \'"dr": os.path.join(app_dir, "icons", "defenses", "dr.svg")\',\n        \'"inventory": os.path.join(app_dir, "icons", "headers", "inventory.svg")\',\n        \'os.path.join(app_dir, "icons", "notes", "custom.svg")\',\n        \'action == "identity.set"\',',
    )
    replace_once(
        validator,
        '        "versionCode = 12",',
        '        "versionCode = 13",',
    )
    replace_once(
        validator,
        '        \'"${snapshot.progression.currentIp} IP  •  Level ${snapshot.progression.level}"\',\n    )',
        '        \'"${snapshot.progression.currentIp} IP  •  Level ${snapshot.progression.level}"\',\n        \'Text("${at.current}/${at.max}"\',\n        \'Text("⋮"\',\n        "V4QuantityCircle",\n    )',
    )

    print("Applied Phase 9 V6 real-device feedback patch")


if __name__ == "__main__":
    main()
