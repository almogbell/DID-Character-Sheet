package com.did.charactersheet.sync

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
    val improvements: List<ImprovementSnapshot>,
    val inventory: List<InventoryItemSnapshot>,
    val notes: List<NoteSnapshot>,
    val portrait: PortraitSnapshot,
) {
    companion object {
        fun fromJson(json: JSONObject): DidCharacterSnapshot {
            val statsObject = json.optJSONObject("stats") ?: JSONObject()
            val stats = statsObject.keys().asSequence().map { statName ->
                val stat = statsObject.optJSONObject(statName) ?: JSONObject()
                StatSnapshot(
                    name = statName,
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

            return DidCharacterSnapshot(
                id = json.optString("id").ifBlank { null },
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
                    max = atJson.optInt("max_AT", 0),
                ),
                progression = ProgressionSnapshot(
                    currentIp = progressionJson.optInt("current_IP", 0),
                    usedIp = progressionJson.optInt("used_IP", 0),
                    level = progressionJson.optInt("level", 1),
                ),
                improvements = improvementsJson.mapObjects(::parseImprovement),
                inventory = inventoryJson.mapObjects { item ->
                    InventoryItemSnapshot(
                        id = item.optString("id").ifBlank { null },
                        name = item.optString("name", ""),
                        description = item.optString("description", ""),
                        quantity = item.optInt("quantity", 1),
                        expanded = item.optBoolean("expanded", true),
                    )
                },
                notes = notesJson.mapObjects { note ->
                    NoteSnapshot(
                        id = note.optString("id").ifBlank { null },
                        title = note.optString("title", ""),
                        text = note.optString("text", ""),
                        color = note.optString("color").ifBlank { null },
                        expanded = note.optBoolean("expanded", true),
                        pinned = note.optBoolean("pinned", false),
                        linkedImprovementId = note.optString("linked_improvement_id").ifBlank { null },
                    )
                },
                portrait = PortraitSnapshot(
                    images = imageJson.optJSONArray("images").toStringList(),
                    offsetX = imageJson.optDouble("offset_x", 0.0),
                    offsetY = imageJson.optDouble("offset_y", 0.0),
                    scale = imageJson.optDouble("scale", 1.0),
                ),
            )
        }

        private fun parseImprovement(json: JSONObject): ImprovementSnapshot {
            val empowerments = json.optJSONArray("empowerments")?.mapObjects { empowerment ->
                EmpowermentSnapshot(
                    id = empowerment.optString("id").ifBlank { null },
                    groupId = empowerment.optString("group_id").ifBlank { null },
                    catalogId = empowerment.optString("catalog_id").ifBlank { null },
                    name = empowerment.optString("name", ""),
                    cost = empowerment.optInt("cost", 0),
                    description = empowerment.optString("description", ""),
                    source = empowerment.optString("source", ""),
                    choices = empowerment.optJSONObject("choices")?.copyJson(),
                )
            } ?: emptyList()

            return ImprovementSnapshot(
                id = json.optString("id").ifBlank { null },
                catalogId = json.optString("catalog_id").ifBlank { null },
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

data class StatSnapshot(val name: String, val dieSize: Int, val bonus: Int)
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
    val text: String,
    val color: String?,
    val expanded: Boolean,
    val pinned: Boolean,
    val linkedImprovementId: String?,
)
data class PortraitSnapshot(
    val images: List<String>,
    val offsetX: Double,
    val offsetY: Double,
    val scale: Double,
)

private inline fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> = buildList {
    for (i in 0 until length()) {
        optJSONObject(i)?.let { add(transform(it)) }
    }
}

private fun JSONArray?.toStringList(): List<String> {
    if (this == null) return emptyList()
    return buildList {
        for (i in 0 until length()) {
            when (val item = opt(i)) {
                is String -> add(item)
                is JSONObject -> item.optString("display").takeIf { it.isNotBlank() }?.let(::add)
            }
        }
    }
}

private fun JSONObject.copyJson(): JSONObject = JSONObject(toString())
