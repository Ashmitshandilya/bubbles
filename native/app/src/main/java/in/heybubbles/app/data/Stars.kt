package `in`.heybubbles.app.data

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.LocalDate
import java.time.format.DateTimeParseException

/** Pure pieces of the Stars lens screen. The server works out the chart; the app only checks the form and puts words on the answer. */
object StarsLogic {
    data class Problems(val date: String? = null, val time: String? = null, val place: String? = null) {
        val any get() = date != null || time != null || place != null
    }

    private val TIME = Regex("^([01]\\d|2[0-3]):[0-5]\\d$")

    fun problems(date: String, time: String, timeUnknown: Boolean, placeId: String?, today: LocalDate = LocalDate.now()): Problems {
        val d = try { LocalDate.parse(date.trim()) } catch (_: DateTimeParseException) { null }
        return Problems(
            date = when {
                d == null -> "Enter your birth date as YYYY-MM-DD."
                d.isAfter(today) -> "Your birth date cannot be in the future."
                d.year < 1900 -> "Birth years from 1900 are supported."
                else -> null
            },
            time = if (!timeUnknown && !TIME.matches(time.trim())) "Enter the time as HH:MM, or tick that you do not know it." else null,
            place = if (placeId.isNullOrBlank()) "Choose your birth place from the list." else null,
        )
    }

    fun body(date: String, time: String, timeUnknown: Boolean, placeId: String): JsonObject = buildJsonObject {
        put("birth_date", date.trim())
        if (!timeUnknown) put("birth_time", time.trim())
        put("city_id", placeId)
    }

    /** "Moon: Makara, nakshatra Shravana" with both options named when a birth time would settle it. */
    fun describe(label: String, placement: JsonObject?): String {
        if (placement == null) return "$label: needs a birth time"
        val rashis = placement.strs("rashi_options").ifEmpty { listOfNotNull(placement.str("rashi")) }
        val naks = placement.strs("nakshatra_options").ifEmpty { listOfNotNull(placement.str("nakshatra")?.takeIf { it.isNotBlank() }) }
        val base = "$label: ${rashis.joinToString(" or ")}" + if (naks.isNotEmpty()) ", nakshatra ${naks.joinToString(" or ")}" else ""
        return when {
            rashis.size > 1 || naks.size > 1 -> "$base. A birth time would settle it."
            placement.bool("cusp") == true -> "$base, on the cusp"
            else -> base
        }
    }
}
