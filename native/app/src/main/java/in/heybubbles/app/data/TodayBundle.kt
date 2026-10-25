package `in`.heybubbles.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull

/**
 * What Today needs from GET /today, in one pass. A part the server could not read is null there and simply absent here: a gap, never a guess.
 * No health logic lives in the app; the lede sentence is chosen by the server (today_brief.py).
 */
data class TodayBundle(
    val lede: String? = null,
    val ledeKind: String? = null,
    val gaps: List<String> = emptyList(),
    val safetyNote: String = "",
    val orbitQuestionWaiting: Boolean = false,
    val displayName: String? = null,
    /** One honest sentence about the newest guess Bubbles has scored against the person's own logs (a miss is said as plainly as a hit); null when none. */
    val checked: String? = null,
    /** The tracker entries the server already read for Today, by slug. A tracker it could not read is absent (never an empty list). */
    val trackers: Map<String, List<Entry>> = emptyMap(),
)

private fun JsonElement?.obj(): JsonObject? = this as? JsonObject
private fun JsonElement?.text(): String? = (this as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }

private fun JsonElement.readable(): String? = when (this) {
    is JsonPrimitive -> contentOrNull?.takeIf { it.isNotBlank() }
    is JsonObject -> listOf("title", "label", "text", "message", "summary", "reason", "name").firstNotNullOfOrNull { k -> this[k].text() }
    else -> null
}

fun parseToday(root: JsonObject): TodayBundle {
    val lede = root["lede"].obj()
    val brief = root["brief"].obj()
    val state = brief?.get("state").obj()
    val gaps = (state?.get("data_gaps").obj()?.get("gaps") as? JsonArray).orEmpty().mapNotNull { it.readable() }.distinct().take(4)
    val orbitQuestion = root["orbit"].obj()?.get("question").obj()
    val profile = root["profile"].obj()
    val name = (profile?.get("profile").obj() ?: profile)?.get("display_name").text()
    return TodayBundle(
        lede = lede?.get("text").text(),
        ledeKind = lede?.get("kind").text(),
        gaps = gaps,
        safetyNote = brief?.get("companion").obj()?.get("safety_note").text().orEmpty(),
        orbitQuestionWaiting = (orbitQuestion?.get("answered") as? JsonPrimitive)?.booleanOrNull == false,
        displayName = name,
        checked = root["learned"].obj()?.get("checked").text(),
        trackers = root["trackers"].obj()?.mapNotNull { (slug, v) -> v.obj()?.let { slug to parseEntries(it) } }?.toMap().orEmpty(),
    )
}

/** The entries of one tracker answer (`{"entries": [...]}`), newest first. Rows without an id are skipped. Shared by GET /health/<slug> and GET /today. */
fun parseEntries(root: JsonObject): List<Entry> {
    val rows = root["entries"] as? JsonArray ?: return emptyList()
    return rows.mapNotNull { el ->
        val o = el as? JsonObject ?: return@mapNotNull null
        val id = (o["id"] as? JsonPrimitive)?.contentOrNull ?: return@mapNotNull null
        Entry(id, (o["date"] as? JsonPrimitive)?.contentOrNull.orEmpty(), o)
    }.sortedByDescending { it.date }
}
