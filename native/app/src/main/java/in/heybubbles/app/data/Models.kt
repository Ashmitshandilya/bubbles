package `in`.heybubbles.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

@Serializable data class Safety(val level: String = "GREEN")

/** One person to call: the number is digits only, or empty when there is nothing to dial ("your local emergency number"). */
@Serializable data class HarborResource(val name: String = "", val number: String = "", val note: String = "")

/** A choice under a Safe Harbor reply. Its label is also the message sent when it is tapped (the server reads the choice from it). */
@Serializable data class HarborAction(val id: String = "", val label: String = "")

/** What sits next to a Safe Harbor reply (backend safe_harbor.payload). Read it through [shown]: the raw tier can be anything. */
@Serializable data class Harbor(
    val tier: JsonElement? = null,
    val mode: String = "disclosure",
    val step: String? = null,
    val resources: List<HarborResource> = emptyList(),
    val actions: List<HarborAction> = emptyList(),
) {
    /** 3 only for the number 3; anything else (a missing, odd or unknown tier) is shown as tier 2. */
    val tierLevel: Int get() = if ((tier as? JsonPrimitive)?.let { !it.isString && it.intOrNull == 3 } == true) 3 else 2

    /** The same payload made safe to draw: clean numbers, no empty rows, at most 5 choices, and 112 when no resource came at all. */
    fun shown(): Harbor = copy(
        tier = JsonPrimitive(tierLevel),
        resources = resources.filter { it.name.isNotBlank() }.map { it.copy(name = it.name.trim(), number = dialNumber(it.number), note = it.note.trim()) }
            .take(8).ifEmpty { listOf(EMERGENCY_112) },
        actions = actions.filter { it.id.isNotBlank() && it.label.isNotBlank() }.map { it.copy(label = it.label.trim()) }.take(5),
    )
}

private val EMERGENCY_112 = HarborResource("Emergency services", "112", "Police, fire and ambulance. Free, open day and night.")
private val DIALABLE = Regex("""^\+?\d{2,6}$""")
private val DIAL_NOISE = Regex("""[\s\-().]""")

/** Digits only (2 to 6, an optional leading +) or "". Anything else is not a number to dial. */
fun dialNumber(raw: String?): String {
    val compact = (raw ?: "").trim().replace(DIAL_NOISE, "")
    return if (DIALABLE.matches(compact)) compact else ""
}

@Serializable data class ChatReply(
    val response: String = "",
    val kind: String = "reply",
    val safety: Safety = Safety(),
    @SerialName("message_id") val messageId: String? = null,
    @SerialName("conversation_id") val conversationId: String? = null,
    @SerialName("consent_ask") val consentAsk: Boolean = false,
    val harbor: Harbor? = null,
)

@Serializable data class StoredMessage(
    val id: String,
    val role: String,
    val content: String,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("safety_level") val safetyLevel: String? = null,
    val harbor: Harbor? = null,
)

@Serializable data class ConversationRef(val id: String = "")

@Serializable data class LatestChat(
    val messages: List<StoredMessage> = emptyList(),
    @SerialName("has_more") val hasMore: Boolean = false,
    val conversation: ConversationRef? = null,
)

@Serializable data class DailyCompanion(
    val headline: String = "",
    @SerialName("safety_note") val safetyNote: String = "",
    val disclaimer: String = "",
    val focus: List<JsonElement> = emptyList(),
    @SerialName("data_gaps") val dataGaps: List<JsonElement> = emptyList(),
)

@Serializable data class DailyResponse(val companion: DailyCompanion = DailyCompanion())

@Serializable data class Association(
    val id: String = "",
    val text: String = "",
    val strength: String = "",
    val limitations: List<String> = emptyList(),
)

@Serializable data class AssociationsResponse(
    val insights: List<Association> = emptyList(),
    val gaps: List<JsonElement> = emptyList(),
    val notices: List<JsonElement> = emptyList(),
)

@Serializable data class Purpose(
    val id: String,
    val title: String = "",
    val description: String = "",
    @SerialName("text_hash") val textHash: String? = null,
    val available: Boolean = true,
    val granted: Boolean = false,
)

@Serializable data class ConsentsResponse(val purposes: List<Purpose> = emptyList())

@Serializable data class WeeklyItem(
    val id: String = "",
    val title: String = "",
    val description: String = "",
    @SerialName("confidence_label") val confidenceLabel: String = "",
)
@Serializable data class WeeklyBody(val insights: List<WeeklyItem> = emptyList())
@Serializable data class WeeklyResponse(val insights: WeeklyBody = WeeklyBody())

class VisitPrep(val questions: List<String>, val bring: List<String>)

class ReminderSettings(
    val push: Boolean,
    val pushAvailable: Boolean,
    val water: Boolean,
    val med: Boolean,
    val winddown: Boolean,
    val quiet: String?,
)
