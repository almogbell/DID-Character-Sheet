from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "android" / "phase8" / "Phase9CompanionSheetV4.kt"
BUILD = ROOT / "android" / "app" / "build.gradle.kts"
MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
DEBUG_MANIFEST = ROOT / "android" / "app" / "src" / "debug" / "AndroidManifest.xml"
VALIDATOR = ROOT / "sync" / "validate_phase9_mobile.py"
ICON = ROOT / "android" / "app" / "src" / "main" / "res" / "drawable" / "did_app_icon.xml"


def sub_once(text: str, pattern: str, replacement: str, *, flags: int = 0, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Could not patch {label}: matches={count}")
    return out


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Could not patch {label}: matches={count}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")

    if "import androidx.compose.runtime.LaunchedEffect" not in text:
        text = replace_once(
            text,
            "import androidx.compose.runtime.Composable\n",
            "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.LaunchedEffect\n",
            label="LaunchedEffect import",
        )

    old_remove = '''            onRemove = inventoryEdit?.id?.let { id ->
                {
                    onRemoveInventoryItem(id)
                    inventoryEdit = null
                }
            },'''
    if old_remove in text:
        text = text.replace(old_remove, "            onRemove = null,", 1)

    nav = r'''private enum class V4Page\(val label: String, val symbol: String\) \{.*?\n\}\n\n@Composable\nprivate fun V4BottomNavigation\(page: V4Page, onPage: \(V4Page\) -> Unit\) \{.*?\n\}\n\n@Composable\nprivate fun V4CharacterPage'''
    nav_replacement = '''private enum class V4Page(val label: String) {
    Character("Character"), Equipment("Equipment"), Notes("Notes")
}

@Composable
private fun V4BottomNavigation(page: V4Page, onPage: (V4Page) -> Unit) {
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
                    icon = { V4AppNavigationIcon(item, selected = page == item) },
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
private fun V4AppNavigationIcon(page: V4Page, selected: Boolean) {
    val color = if (selected) MaterialTheme.colorScheme.onPrimaryContainer
    else MaterialTheme.colorScheme.onSurfaceVariant
    Canvas(Modifier.size(28.dp)) {
        val stroke = Stroke(width = 2.0f, cap = StrokeCap.Round, join = StrokeJoin.Round)
        val w = size.width
        val h = size.height
        when (page) {
            V4Page.Character -> {
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
            V4Page.Equipment -> {
                val bag = Path().apply {
                    moveTo(w * .24f, h * .40f)
                    quadraticBezierTo(w * .24f, h * .34f, w * .32f, h * .34f)
                    lineTo(w * .68f, h * .34f)
                    quadraticBezierTo(w * .76f, h * .34f, w * .76f, h * .40f)
                    lineTo(w * .76f, h * .78f)
                    quadraticBezierTo(w * .76f, h * .82f, w * .70f, h * .82f)
                    lineTo(w * .30f, h * .82f)
                    quadraticBezierTo(w * .24f, h * .82f, w * .24f, h * .78f)
                    close()
                }
                drawPath(bag, color, style = stroke)
                val handle = Path().apply {
                    moveTo(w * .34f, h * .38f)
                    cubicTo(w * .36f, h * .12f, w * .64f, h * .12f, w * .66f, h * .38f)
                }
                drawPath(handle, color, style = stroke)
                drawLine(color, Offset(w * .39f, h * .29f), Offset(w * .61f, h * .29f), strokeWidth = 2f)
            }
            V4Page.Notes -> {
                val left = Path().apply {
                    moveTo(w * .12f, h * .25f)
                    quadraticBezierTo(w * .30f, h * .17f, w * .48f, h * .29f)
                    lineTo(w * .48f, h * .78f)
                    quadraticBezierTo(w * .30f, h * .67f, w * .12f, h * .74f)
                    close()
                }
                val right = Path().apply {
                    moveTo(w * .52f, h * .29f)
                    quadraticBezierTo(w * .70f, h * .17f, w * .88f, h * .25f)
                    lineTo(w * .88f, h * .74f)
                    quadraticBezierTo(w * .70f, h * .67f, w * .52f, h * .78f)
                    close()
                }
                drawPath(left, color, style = stroke)
                drawPath(right, color, style = stroke)
                drawLine(color, Offset(w * .50f, h * .29f), Offset(w * .50f, h * .79f), strokeWidth = 2f)
                drawLine(color, Offset(w * .20f, h * .39f), Offset(w * .40f, h * .42f), strokeWidth = 1.6f)
                drawLine(color, Offset(w * .60f, h * .42f), Offset(w * .80f, h * .39f), strokeWidth = 1.6f)
            }
        }
    }
}

@Composable
private fun V4CharacterPage'''
    text = sub_once(text, nav, nav_replacement, flags=re.S, label="bottom navigation icons")

    name_pattern = r'''@Composable\nprivate fun V4NameHeader\(snapshot: DidCharacterSnapshot, canEdit: Boolean, onEditName: \(\) -> Unit\) \{.*?\n\}\n\n@Composable\nprivate fun V4PortraitGallery'''
    name_replacement = '''@Composable
private fun V4NameHeader(snapshot: DidCharacterSnapshot, canEdit: Boolean, onEditName: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 9.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        Text(
            snapshot.name.ifBlank { "Unnamed Character" },
            modifier = Modifier.pointerInput(canEdit) {
                detectTapGestures(onDoubleTap = { if (canEdit) onEditName() })
            },
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Black,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        if (snapshot.speciesName.isNotBlank()) {
            Text(
                snapshot.speciesName,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
                textAlign = TextAlign.Center,
            )
        }
        if (snapshot.backstory.isNotBlank()) {
            Text(
                snapshot.backstory,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun V4PortraitGallery'''
    text = sub_once(text, name_pattern, name_replacement, flags=re.S, label="name header")

    gallery_pattern = r'''@Composable\nprivate fun V4PortraitGallery\(snapshot: DidCharacterSnapshot\) \{.*?\n\}\n\nprivate fun String\.v4DecodeBitmap'''
    gallery_replacement = '''@Composable
private fun V4PortraitGallery(snapshot: DidCharacterSnapshot) {
    V4SheetCard(
        Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 3.dp),
        strongBorder = true,
    ) {
        if (snapshot.portrait.images.isEmpty()) {
            Text(
                "No character images",
                Modifier.fillMaxWidth().padding(18.dp),
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@V4SheetCard
        }
        LazyRow(
            modifier = Modifier.fillMaxWidth().height(184.dp),
            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items(snapshot.portrait.images.indices.toList()) { index ->
                val image = snapshot.portrait.images[index]
                val bitmap = remember(image.data) { image.data.v4DecodeBitmap() }
                Surface(
                    modifier = Modifier.size(132.dp, 164.dp),
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(1.2.dp, MaterialTheme.colorScheme.outlineVariant),
                ) {
                    Box(Modifier.fillMaxSize().padding(4.dp), contentAlignment = Alignment.Center) {
                        if (bitmap != null) {
                            Image(
                                bitmap = bitmap.asImageBitmap(),
                                contentDescription = "Character image ${index + 1}",
                                contentScale = ContentScale.Fit,
                                modifier = Modifier.fillMaxSize(),
                            )
                        } else {
                            Text("Image ${index + 1}", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
    }
}

private fun String.v4DecodeBitmap'''
    text = sub_once(text, gallery_pattern, gallery_replacement, flags=re.S, label="portrait gallery")

    resource_pattern = r'''@Composable\nprivate fun V4ResourcePanel\(\n    snapshot: DidCharacterSnapshot,\n    enabled: Boolean,\n    onHpChange: \(Int\) -> Unit,\n    onAtChange: \(Int\) -> Unit,\n\) \{.*?\n\}\n\n@Composable\nprivate fun V4Hearts'''
    resource_replacement = '''@Composable
private fun V4ResourcePanel(
    snapshot: DidCharacterSnapshot,
    enabled: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
) {
    var shownHp by remember(snapshot.id) { mutableIntStateOf(snapshot.hp.current) }
    var shownAt by remember(snapshot.id) { mutableIntStateOf(snapshot.adversity.current) }
    LaunchedEffect(snapshot.hp.current) { shownHp = snapshot.hp.current }
    LaunchedEffect(snapshot.adversity.current) { shownAt = snapshot.adversity.current }

    V4SheetCard(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp), strongBorder = true) {
        Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
                    V4Hearts(
                        snapshot.hp.copy(current = shownHp),
                        enabled,
                    ) { delta ->
                        val next = (shownHp + delta).coerceIn(0, snapshot.hp.max)
                        val actual = next - shownHp
                        if (actual != 0) {
                            shownHp = next
                            onHpChange(actual)
                        }
                    }
                }
                V4DefenseBadge("BDV", snapshot.bdv, snapshot.uiIcons["bdv"])
                Spacer(Modifier.width(4.dp))
                V4DefenseBadge("DR", snapshot.dr, snapshot.uiIcons["dr"])
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            V4Adversity(
                snapshot.adversity.copy(current = shownAt),
                enabled,
            ) { delta ->
                val next = (shownAt + delta).coerceIn(0, snapshot.adversity.max)
                val actual = next - shownAt
                if (actual != 0) {
                    shownAt = next
                    onAtChange(actual)
                }
            }
        }
    }
}

@Composable
private fun V4Hearts'''
    text = sub_once(text, resource_pattern, resource_replacement, flags=re.S, label="optimistic resources")

    text = replace_once(
        text,
        "val modifier = Modifier.size(36.dp, 33.dp).then(",
        "val modifier = Modifier.size(46.dp, 42.dp).then(",
        label="larger hearts",
    )
    text = replace_once(
        text,
        "Modifier.size(23.dp).then(",
        "Modifier.size(31.dp).then(",
        label="larger adversity",
    )

    UI.write_text(text, encoding="utf-8")


def patch_manifest() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    if 'android:icon="@drawable/did_app_icon"' not in text:
        text = text.replace(
            '        android:allowBackup="true"\n',
            '        android:allowBackup="true"\n'
            '        android:icon="@drawable/did_app_icon"\n'
            '        android:roundIcon="@drawable/did_app_icon"\n',
            1,
        )
    MANIFEST.write_text(text, encoding="utf-8")

    debug = DEBUG_MANIFEST.read_text(encoding="utf-8")
    debug = debug.replace('android:label="DID Phase 9 Test"', 'android:label="DID Phase 9 Test 2"')
    DEBUG_MANIFEST.write_text(debug, encoding="utf-8")

    ICON.parent.mkdir(parents=True, exist_ok=True)
    ICON.write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:fillColor="#FFFDF7" android:pathData="M0,0h108v108h-108z" />
    <path
        android:fillColor="#A87824"
        android:pathData="M54,16 L59,42 L79,29 L66,49 L92,54 L66,59 L79,79 L59,66 L54,92 L49,66 L29,79 L42,59 L16,54 L42,49 L29,29 L49,42 Z" />
    <path android:fillColor="#FFFDF7" android:pathData="M50,50h8v8h-8z" />
    <path android:fillColor="#2F5F91" android:pathData="M52,52h4v4h-4z" />
</vector>
''', encoding="utf-8")


def patch_build() -> None:
    text = BUILD.read_text(encoding="utf-8")
    text = text.replace("versionCode = 11", "versionCode = 12", 1)
    text = text.replace('versionNameSuffix = "-phase9-test2-v4"', 'versionNameSuffix = "-phase9-test2-v5"', 1)
    BUILD.write_text(text, encoding="utf-8")


def patch_validator() -> None:
    text = VALIDATOR.read_text(encoding="utf-8")
    text = text.replace('"versionCode = 11",', '"versionCode = 12",', 1)
    marker = '        "onRemoveInventoryItem",\n'
    if '"V4AppNavigationIcon"' not in text:
        text = text.replace(
            marker,
            marker
            + '        "V4AppNavigationIcon",\n'
            + '        "onDoubleTap",\n'
            + '        "LaunchedEffect(snapshot.hp.current)",\n'
            + '        "Modifier.size(46.dp, 42.dp)",\n'
            + '        "Modifier.size(31.dp)",\n',
            1,
        )
    if 'android:icon="@drawable/did_app_icon"' not in text:
        insertion = '''    require(
        "android/app/src/main/AndroidManifest.xml",
        'android:icon="@drawable/did_app_icon"',
        'android:roundIcon="@drawable/did_app_icon"',
    )
    require(
        "android/app/src/main/res/drawable/did_app_icon.xml",
        "#A87824",
        "#2F5F91",
    )
'''
        text = text.replace('    require(\n        "android/app/build.gradle.kts",', insertion + '    require(\n        "android/app/build.gradle.kts",', 1)
    for forbidden in (
        'Text("HP  ${snapshot.hp.current} / ${snapshot.hp.max}"',
        'Text("Adversity Tokens"',
        'Text("Edit") },\n    }\n}\n\n@Composable\nprivate fun V4PortraitGallery',
    ):
        if forbidden not in text:
            pass
    VALIDATOR.write_text(text, encoding="utf-8")


def main() -> None:
    patch_ui()
    patch_manifest()
    patch_build()
    patch_validator()
    print("Applied Phase 9 V5 feedback patch")


if __name__ == "__main__":
    main()
