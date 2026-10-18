package `in`.heybubbles.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable data class Safety(val level: String = "GREEN")

@Serializable data class ChatReply(
    val response: String = "",
    val kind: String = "reply",
    val safety: Safety = Safety(),
    @SerialName("message_id") val messageId: String? = null,
    @SerialName("conversation_id") val conversationId: String? = null,
    @SerialName("consent_ask") val consentAsk: Boolean = false,
)

@Serializable data class StoredMessage(
    val id: String,
    val role: String,
    val content: String,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("safety_level") val safetyLevel: String? = null,
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
