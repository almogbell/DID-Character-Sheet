package com.did.charactersheet.sync

import android.graphics.Typeface
import android.text.Html
import android.text.Spanned
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import org.json.JSONArray
import org.json.JSONObject

/** Typed, read-only view of the canonical character snapshot sent by Windows. */
data class DidCharacterSnapshot(
    val id: String?,
    val name: String,
    val speciesName: String,
    val backstory: String,
    val stats: List<StatSnapshot>,
    val hp: HpSnapshot,
    val adversity: AdversitySnapshot,
    val progression: ProgressionSnapshot,
    val bdv: Int,
    val dr: Int,
    val defenseStatName: String?,
    val combatModeEnabled: Boolean,
    val improvements: List<ImprovementSnapshot>,
    val inventory: List<InventoryItemSnapshot>,
    val notes: List<NoteSnapshot>,
    val portrait: PortraitSnapshot,
    /** Exact SVG artwork supplied by the connected Windows DID installation. */
    val uiIcons: Map<String, String>,
) {
    companion object {
        fun fromJson(json: JSONObject): DidCharacterSnapshot {
            val statsObject = json.optJSONObject("stats") ?: JSONObject()
            val stats = statsObject.keys().asSequence().map { statKey ->
                val stat = statsObject.optJSONObject(statKey) ?: JSONObject()
                StatSnapshot(
                    key = statKey,
                    name = statKey.displayStatName(),
                    dieSize = stat.optInt("die_size", 0),
                    bonus = stat.optInt("bonus", 0),
                )
            }.toList()

            val hpJson = json.optJSONObject("HP") ?: JSONObject()
            val atJson = json.optJSONObject("Adversity") ?: JSONObject()
            val progressionJson = json.optJSONObject("progression") ?: JSONObject()
            val improvementsJson = json.optJSONObject("improvements")
                ?.optJSONArray("list_of_taken_improvements") ?: JSONArray()
            val inventoryJson = json.optJSONObject("inventory")
                ?.optJSONArray("list_of_items") ?: JSONArray()
            val notesJson = json.optJSONObject("notes")
                ?.optJSONArray("list_of_notes") ?: JSONArray()
            val imageJson = json.optJSONObject("image") ?: JSONObject()
            val iconJson = json.optJSONObject("_mobile_ui")?.optJSONObject("icons")

            val defenseKey = json.optString("selected_defense_stat_name")
                .nonBlankOrNull()
                ?.takeIf { selected -> stats.any { it.key == selected } }
                ?: stats.maxWithOrNull(
                    compareBy<StatSnapshot> { it.dieSize }.thenBy { it.bonus }
                )?.key
            val defenseStat = stats.firstOrNull { it.key == defenseKey }
            val maxAt = atJson.optInt("max_AT", 0)

            return DidCharacterSnapshot(
                id = json.optString("id").nonBlankOrNull(),
                name = json.optString("name", "Unnamed character"),
                speciesName = json.optString("species_name", ""),
                backstory = json.optString("backstory", ""),
                stats = stats,
                hp = HpSnapshot(
                    current = hpJson.optInt("current_HP", 0),
                    max = hpJson.optInt("max_HP", hpJson.optInt("max_hearts", 0) * 4),
                    maxHearts = hpJson.optInt("max_hearts", 0),
                ),
                adversity = AdversitySnapshot(
                    current = atJson.optInt("current_AT", 0),
                    max = maxAt,
                ),
                progression = ProgressionSnapshot(
                    currentIp = progressionJson.optInt("current_IP", 0),
                    usedIp = progressionJson.optInt("used_IP", 0),
                    level = progressionJson.optInt("level", 1),
                ),
                bdv = maxAt / 2,
                dr = defenseStat?.let { (it.dieSize / 2) + it.bonus } ?: 0,
                defenseStatName = defenseStat?.name,
                combatModeEnabled = json.optBoolean("combat_mode_enabled", false),
                improvements = improvementsJson.mapObjects(::parseImprovement),
                inventory = inventoryJson.mapObjects { item ->
                    InventoryItemSnapshot(
                        id = item.optString("id").nonBlankOrNull(),
                        name = item.optString("name", ""),
                        description = item.optString("description", ""),
                        quantity = item.optInt("quantity", 1),
                        expanded = item.optBoolean("expanded", true),
                    )
                },
                notes = notesJson.mapObjects { note ->
                    val rawText = note.optString("text", "")
                    NoteSnapshot(
                        id = note.optString("id").nonBlankOrNull(),
                        title = note.optString("title", ""),
                        rawText = rawText,
                        text = parseNoteText(rawText),
                        color = note.optString("color").nonBlankOrNull(),
                        expanded = note.optBoolean("expanded", true),
                        pinned = note.optBoolean("pinned", false),
                        linkedImprovementId = note.optString("linked_improvement_id").nonBlankOrNull(),
                    )
                },
                portrait = PortraitSnapshot(
                    images = imageJson.optJSONArray("images").portraitImages(),
                    currentIndex = imageJson.optInt("current_index", 0),
                    offsetX = imageJson.optDouble("offset_x", 0.0),
                    offsetY = imageJson.optDouble("offset_y", 0.0),
                    scale = imageJson.optDouble("scale", 1.0),
                ),
                uiIcons = iconJson.stringMap(),
            )
        }

        private fun parseImprovement(json: JSONObject): ImprovementSnapshot {
            val empowerments = json.optJSONArray("empowerments")?.mapObjects { empowerment ->
                EmpowermentSnapshot(
                    id = empowerment.optString("id").nonBlankOrNull(),
                    groupId = empowerment.optString("group_id").nonBlankOrNull(),
                    catalogId = empowerment.optString("catalog_id").nonBlankOrNull(),
                    name = empowerment.optString("name", ""),
                    cost = empowerment.optInt("cost", 0),
                    description = empowerment.optString("description", ""),
                    source = empowerment.optString("source", ""),
                    choices = empowerment.optJSONObject("choices")?.copyJson(),
                )
            } ?: emptyList()

            return ImprovementSnapshot(
                id = json.optString("id").nonBlankOrNull(),
                catalogId = json.optString("catalog_id").nonBlankOrNull(),
                name = json.optString("name", ""),
                cost = json.optInt("cost", 0),
                description = json.optString("description", ""),
                source = json.optString("source", ""),
                choices = json.optJSONObject("choices")?.copyJson(),
                expanded = json.optBoolean("expanded", true),
                timesTaken = json.optInt("times_taken", 1),
                sortOrder = json.optInt("sort_order", 0),
                empowerments = empowerments,
            )
        }
    }
}

data class StatSnapshot(val key: String, val name: String, val dieSize: Int, val bonus: Int)
data class HpSnapshot(val current: Int, val max: Int, val maxHearts: Int)
data class AdversitySnapshot(val current: Int, val max: Int)
data class ProgressionSnapshot(val currentIp: Int, val usedIp: Int, val level: Int)
data class ImprovementSnapshot(
    val id: String?,
    val catalogId: String?,
    val name: String,
    val cost: Int,
    val description: String,
    val source: String,
    val choices: JSONObject?,
    val expanded: Boolean,
    val timesTaken: Int,
    val sortOrder: Int,
    val empowerments: List<EmpowermentSnapshot>,
)
data class EmpowermentSnapshot(
    val id: String?,
    val groupId: String?,
    val catalogId: String?,
    val name: String,
    val cost: Int,
    val description: String,
    val source: String,
    val choices: JSONObject?,
)
data class InventoryItemSnapshot(
    val id: String?,
    val name: String,
    val description: String,
    val quantity: Int,
    val expanded: Boolean,
)
data class NoteSnapshot(
    val id: String?,
    val title: String,
    val rawText: String,
    val text: AnnotatedString,
    val color: String?,
    val expanded: Boolean,
    val pinned: Boolean,
    val linkedImprovementId: String?,
)
data class PortraitImageSnapshot(val id: String?, val data: String)
data class PortraitSnapshot(
    val images: List<PortraitImageSnapshot>,
    val currentIndex: Int,
    val offsetX: Double,
    val offsetY: Double,
    val scale: Double,
) {
    val currentImage: PortraitImageSnapshot?
        get() = images.getOrNull(currentIndex.coerceIn(0, (images.size - 1).coerceAtLeast(0)))
}

private const val RICH_NOTE_MARKER = "<!--DID_RICH_NOTE-->"

/**
 * The desktop note editor stores formatted player notes as a tiny, controlled
 * HTML subset prefixed by RICH_NOTE_MARKER. Android must render that format,
 * not show the storage markup as literal text.
 */
private fun parseNoteText(raw: String): AnnotatedString {
    val plainNormalized = raw
        .replace('\u2028', '\n')
        .replace('\u2029', '\n')
        .replace("\uFFFC", "")

    if (!raw.startsWith(RICH_NOTE_MARKER)) {
        return AnnotatedString(plainNormalized)
    }

    val htmlSource = raw
        .removePrefix(RICH_NOTE_MARKER)
        .replace("\u2028", "<br>")
        .replace("\u2029", "<br>")
        .replace("\uFFFC", "")

    return htmlToAnnotatedString(htmlSource)
}

/** Render the small HTML subset also used by built-in/system notes and improvements. */
fun didHtmlToAnnotatedString(raw: String): AnnotatedString {
    val normalized = raw
        .removePrefix(RICH_NOTE_MARKER)
        .replace('\u2028', '\n')
        .replace('\u2029', '\n')
        .replace("\uFFFC", "")
        .replace("\n", "<br>")
    return htmlToAnnotatedString(normalized)
}

private fun htmlToAnnotatedString(htmlSource: String): AnnotatedString {
    val spanned: Spanned = Html.fromHtml(htmlSource, Html.FROM_HTML_MODE_LEGACY)
    return buildAnnotatedString {
        append(spanned.toString())

        spanned.getSpans(0, spanned.length, StyleSpan::class.java).forEach { span ->
            val start = spanned.getSpanStart(span).coerceAtLeast(0)
            val end = spanned.getSpanEnd(span).coerceAtMost(length)
            if (start >= end) return@forEach
            when (span.style) {
                Typeface.BOLD -> addStyle(SpanStyle(fontWeight = FontWeight.Bold), start, end)
                Typeface.ITALIC -> addStyle(SpanStyle(fontStyle = FontStyle.Italic), start, end)
                Typeface.BOLD_ITALIC -> addStyle(
                    SpanStyle(fontWeight = FontWeight.Bold, fontStyle = FontStyle.Italic),
                    start,
                    end,
                )
            }
        }
        spanned.getSpans(0, spanned.length, UnderlineSpan::class.java).forEach { span ->
            val start = spanned.getSpanStart(span).coerceAtLeast(0)
            val end = spanned.getSpanEnd(span).coerceAtMost(length)
            if (start < end) addStyle(SpanStyle(textDecoration = TextDecoration.Underline), start, end)
        }
    }
}

private fun JSONArray?.portraitImages(): List<PortraitImageSnapshot> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index ->
        val item = optJSONObject(index) ?: return@mapNotNull null
        val data = item.optString("image_data").nonBlankOrNull() ?: return@mapNotNull null
        PortraitImageSnapshot(
            id = item.optString("id").nonBlankOrNull(),
            data = data,
        )
    }
}

private fun JSONObject?.stringMap(): Map<String, String> {
    if (this == null) return emptyMap()
    return keys().asSequence().mapNotNull { key ->
        optString(key).nonBlankOrNull()?.let { key to it }
    }.toMap()
}

private fun JSONArray.mapObjects(transform: (JSONObject) -> ImprovementSnapshot): List<ImprovementSnapshot> =
    (0 until length()).mapNotNull { index -> optJSONObject(index)?.let(transform) }

private fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> =
    (0 until length()).mapNotNull { index -> optJSONObject(index)?.let(transform) }

private fun JSONObject.copyJson(): JSONObject = JSONObject(toString())
private fun String.nonBlankOrNull(): String? = takeIf { it.isNotBlank() }
private fun String.displayStatName(): String = replace('_', ' ').replaceFirstChar { it.titlecase() }
