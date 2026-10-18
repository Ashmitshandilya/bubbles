package `in`.heybubbles.app.data

import androidx.compose.ui.graphics.Color
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** One row from GET /health/<slug>: {id, date, ...fields} (see backend/health_logs.py). */
class Entry(val id: String, val date: String, val json: JsonObject) {
    fun text(key: String): String? = (json[key] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() && it != "null" }
    fun number(key: String): Double? = (json[key] as? JsonPrimitive)?.doubleOrNull

    /** The calendar day in the phone's own time zone, so "today" matches what the person sees. */
    val day: LocalDate? get() = runCatching { OffsetDateTime.parse(date).atZoneSameInstant(ZoneId.systemDefault()).toLocalDate() }
        .recoverCatching { LocalDate.parse(date.take(10)) }.getOrNull()
}

sealed interface Kind {
    data class Number(val min: Double, val max: Double, val unit: String = "", val whole: Boolean = false) : Kind
    data class Choice(val options: List<String>) : Kind
    data object Text : Kind
}

data class Field(val key: String, val label: String, val kind: Kind, val required: Boolean = false, val hint: String? = null)

/** Everything the app needs to show and fill one tracker. Field keys are the server's form keys, so nothing is translated. */
class TrackerSpec(
    val slug: String,
    val title: String,
    val ask: String,
    val tint: Color,
    val ink: Color,
    val fields: List<Field>,
    /** One short line for a history row, e.g. "7.5 h · quality 4/10". */
    val line: (Entry) -> String,
    /** The headline number for charts and cards, or null when an entry has none. */
    val value: ((Entry) -> Double?)? = null,
    val valueUnit: String = "",
    /** Turns what the person typed into the server's unit (the server keeps weight in pounds). */
    val toServer: (key: String, value: Double) -> Double = { _, v -> v },
)

private fun fmt(v: Double): String = if (v % 1.0 == 0.0) v.toLong().toString() else String.format(Locale.US, "%.1f", v)
private fun join(vararg parts: String?): String = parts.filterNotNull().joinToString(" · ")

object Trackers {
    const val LBS_PER_KG = 2.2046226218

    val all: List<TrackerSpec> = listOf(
        TrackerSpec(
            "sleep", "Sleep", "How did you sleep?", Bubbles.TintGrape, Bubbles.GrapeDeep,
            listOf(
                Field("duration", "Hours slept", Kind.Number(0.0, 24.0, "h"), required = true),
                Field("quality", "How rested (1–10)", Kind.Number(1.0, 10.0, whole = true)),
                Field("notes", "Notes", Kind.Text),
            ),
            line = { e -> join(e.number("duration")?.let { "${fmt(it)} h" }, e.number("quality")?.let { "rested ${fmt(it)}/10" }, e.text("notes")) },
            value = { it.number("duration") }, valueUnit = "h",
        ),
        TrackerSpec(
            "mood", "Mood", "How are you feeling?", Bubbles.TintPink, Bubbles.PinkDeep,
            listOf(
                Field("mood", "Mood (1–10)", Kind.Number(1.0, 10.0, whole = true), required = true),
                Field("stress", "Stress (0–10)", Kind.Number(0.0, 10.0, whole = true)),
                Field("anxiety", "Anxiety (0–10)", Kind.Number(0.0, 10.0, whole = true)),
                Field("notes", "Notes", Kind.Text),
            ),
            line = { e -> join(e.number("mood")?.let { "mood ${fmt(it)}/10" }, e.text("notes")) },
            value = { it.number("mood") }, valueUnit = "/10",
        ),
        TrackerSpec(
            "hydration", "Water", "What did you drink?", Bubbles.TintSky, Bubbles.SkyDeep,
            listOf(
                Field("volume", "Amount", Kind.Number(1.0, 10000.0, "ml", whole = true), required = true),
                Field("type", "Drink", Kind.Choice(listOf("water", "tea", "coffee", "juice", "other"))),
            ),
            line = { e -> join(e.number("volume")?.let { "${fmt(it)} ml" }, e.text("type")) },
            value = { it.number("volume") }, valueUnit = "ml",
        ),
        TrackerSpec(
            "nutrition", "Food", "What did you eat?", Bubbles.TintPeach, Bubbles.PeachDeep,
            listOf(
                Field("description", "What you ate", Kind.Text, required = true, hint = "2 rotis, dal and curd"),
                Field("meal_type", "Meal", Kind.Choice(listOf("breakfast", "lunch", "dinner", "snack"))),
                Field("calories", "Calories (if you know)", Kind.Number(0.0, 10000.0, "kcal", whole = true)),
            ),
            line = { e -> join(e.text("description") ?: e.text("name"), e.number("calories")?.let { "${fmt(it)} kcal" }) },
            value = { it.number("calories") }, valueUnit = "kcal",
        ),
        TrackerSpec(
            "activity", "Activity", "How did you move?", Bubbles.TintSun, Bubbles.SunDeep,
            listOf(
                Field("type", "What you did", Kind.Text, required = true, hint = "Walk, yoga, run"),
                Field("duration", "Minutes", Kind.Number(1.0, 1440.0, "min", whole = true), required = true),
                Field("intensity", "Effort", Kind.Choice(listOf("light", "moderate", "vigorous"))),
            ),
            line = { e -> join(e.text("type"), e.number("duration")?.let { "${fmt(it)} min" }, e.text("intensity")) },
            value = { it.number("duration") }, valueUnit = "min",
        ),
        TrackerSpec(
            "weight", "Weight", "What does the scale say?", Bubbles.TintMint, Bubbles.MintDeep,
            listOf(Field("weight", "Weight", Kind.Number(22.7, 317.0, "kg"), required = true), Field("notes", "Notes", Kind.Text)),
            line = { e -> join(e.number("weight")?.let { "${fmt((it / LBS_PER_KG * 10).toLong() / 10.0)} kg" }, e.text("notes")) },
            // The server stores pounds; the app shows and asks in kilograms.
            value = { e -> e.number("weight")?.let { (it / LBS_PER_KG * 10).toLong() / 10.0 } }, valueUnit = "kg",
            toServer = { k, v -> if (k == "weight") v * LBS_PER_KG else v },
        ),
        TrackerSpec(
            "symptoms", "Symptoms", "Anything bothering you?", Bubbles.TintUrgent, Bubbles.Urgent,
            listOf(
                Field("symptom", "What's going on", Kind.Text, required = true, hint = "Headache, cramps, nausea"),
                Field("severity", "How bad (1–10)", Kind.Number(1.0, 10.0, whole = true)),
                Field("notes", "Notes", Kind.Text),
            ),
            line = { e -> join(e.text("symptom"), e.number("severity")?.let { "${fmt(it)}/10" }, e.text("notes")) },
            value = { it.number("severity") }, valueUnit = "/10",
        ),
        TrackerSpec(
            "vitals", "Vitals", "Any readings?", Bubbles.TintSky, Bubbles.SkyDeep,
            listOf(
                Field("heart_rate", "Heart rate", Kind.Number(20.0, 300.0, "bpm", whole = true)),
                Field("blood_pressure", "Blood pressure", Kind.Text, hint = "120/80"),
                Field("notes", "Notes", Kind.Text),
            ),
            line = { e -> join(e.number("heart_rate")?.let { "${fmt(it)} bpm" }, e.text("blood_pressure")?.let { "BP $it" }, e.text("notes")) },
            value = { it.number("heart_rate") }, valueUnit = "bpm",
        ),
    )

    fun bySlug(slug: String) = all.first { it.slug == slug }
}

private val dayFmt = DateTimeFormatter.ofPattern("EEE d MMM", Locale.ENGLISH)

/** "Today", "Yesterday" or "Fri 17 Oct". */
fun Entry.dayLabel(today: LocalDate = LocalDate.now()): String {
    val d = day ?: return ""
    return when (d) { today -> "Today"; today.minusDays(1) -> "Yesterday"; else -> d.format(dayFmt) }
}
