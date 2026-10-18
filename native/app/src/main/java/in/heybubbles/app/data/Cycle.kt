package `in`.heybubbles.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** GET /cycle/overview. Only what the screen shows; the server owns every estimate and its wording. */
@Serializable data class CyclePhase(val id: String = "", val label: String = "", val summary: String = "", val estimated: Boolean = true)

@Serializable data class CycleDate(
    val date: String? = null,
    val earliest: String? = null,
    val latest: String? = null,
    @SerialName("in_days") val inDays: Int? = null,
    val status: String? = null,
    @SerialName("late_by_days") val lateByDays: Int? = null,
)

@Serializable data class FertileWindow(val start: String? = null, val end: String? = null, @SerialName("active_today") val activeToday: Boolean = false)

@Serializable data class Regularity(val label: String? = null)
@Serializable data class CycleStatsFull(
    @SerialName("average_length") val averageLength: Int? = null,
    @SerialName("cycles_used") val cyclesUsed: Int = 0,
    val regularity: Regularity? = null,
)

@Serializable data class Pms(val text: String = "")
@Serializable data class CycleFlag(val id: String = "", val severity: String = "", val title: String = "", val message: String = "")
@Serializable data class Weather(val label: String = "", val line: String = "")

@Serializable data class CycleOverview(
    val mode: String = "track",
    @SerialName("mode_label") val modeLabel: String = "",
    @SerialName("has_data") val hasData: Boolean = false,
    @SerialName("cycle_day") val cycleDay: Int? = null,
    val phase: CyclePhase? = null,
    @SerialName("last_period_start") val lastPeriodStart: String? = null,
    @SerialName("next_period") val nextPeriod: CycleDate? = null,
    val ovulation: CycleDate? = null,
    @SerialName("fertile_window") val fertileWindow: FertileWindow? = null,
    val confidence: String? = null,
    @SerialName("confidence_note") val confidenceNote: String? = null,
    val stats: CycleStatsFull? = null,
    val pms: Pms? = null,
    val flags: List<CycleFlag> = emptyList(),
    val urgent: CycleFlag? = null,
    val weather: Weather? = null,
    val notices: List<String> = emptyList(),
)
