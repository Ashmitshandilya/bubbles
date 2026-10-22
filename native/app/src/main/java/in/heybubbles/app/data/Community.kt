package `in`.heybubbles.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** The Community endpoints (backend/community_api.py). Moderation, rate limits and crisis handling all stay on the server. */
@Serializable data class CommunityStatus(
    val enabled: Boolean = false,
    @SerialName("can_read") val canRead: Boolean = false,
    @SerialName("can_post") val canPost: Boolean = false,
    val reason: String? = null,
    val topics: List<String> = emptyList(),
    val disclaimer: String = "",
)

@Serializable data class Reactions(@SerialName("me_too") val meToo: Int = 0, val helpful: Int = 0)

@Serializable data class CommunityPost(
    val id: String,
    val alias: String = "",
    val anonymous: Boolean = true,
    val body: String = "",
    @SerialName("created_at") val createdAt: String = "",
    val mine: Boolean = false,
    val reactions: Reactions = Reactions(),
    @SerialName("my_reactions") val myReactions: List<String> = emptyList(),
    val topic: String? = null,
    @SerialName("comment_count") val commentCount: Int = 0,
    val status: String? = null,
    val note: String? = null,
)

@Serializable data class FeedResponse(
    val posts: List<CommunityPost> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
)

@Serializable data class CommentsResponse(
    val comments: List<CommunityPost> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
)

@Serializable data class Support(val kind: String = "", val message: String = "", val lines: String = "")

@Serializable data class PostResult(val post: CommunityPost? = null, val support: Support? = null)

@Serializable data class PostBody(val topic: String, val body: String, val anonymous: Boolean)
@Serializable data class CommentBody(val body: String, val anonymous: Boolean)
@Serializable data class ReactBody(val target: String, val kind: String)
@Serializable data class ReportBody(val target: String, val reason: String)
@Serializable data class TargetBody(val target: String)

/** Wording for the topics and report reasons the server accepts. */
object CommunityText {
    val topics = mapOf(
        "cycle" to "Cycle", "sleep" to "Sleep", "mind" to "Mind", "food" to "Food",
        "fitness" to "Fitness", "skin_hair" to "Skin and hair", "talk" to "Just talking",
    )
    val reasons = listOf(
        "unkind" to "Unkind or hurtful", "unsafe_advice" to "Unsafe advice", "spam" to "Spam",
        "private_info" to "Shares private information", "sexual" to "Sexual content", "other" to "Something else",
    )
    fun topic(id: String?): String = topics[id] ?: id.orEmpty()
}
