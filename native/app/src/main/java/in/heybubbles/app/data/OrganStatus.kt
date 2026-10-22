package `in`.heybubbles.app.data

import kotlinx.serialization.json.JsonObject

/** The four statuses of the body map, with the same words as the website (app/lib/organ-map.ts). Missing data is never read as healthy. */
enum class OrganStatus(val id: String, val label: String, val meaning: String, val nextStep: String) {
    TalkToDoctor("talk_to_doctor", "Talk to a doctor", "Your entries include something a doctor should look at.", "Book a visit with a doctor and bring these entries with you."),
    WorthWatching("worth_watching", "Worth watching", "Something in your entries is worth keeping an eye on.", "Keep logging for the next week so Bubbles can see whether it settles."),
    Steady("steady", "Steady", "Your recent entries don't point to a change. That is not an all-clear.", "Keep logging as you do now. Bubbles will tell you if something shifts."),
    NoData("no_data", "No data yet", "Bubbles has nothing recent to go on. Missing data is never read as healthy.", "Log anything that relates to this part of the body, and Bubbles will start a picture.");

    companion object {
        /** An unknown status from a newer server is shown as "no data", never as steady. */
        fun of(id: String?): OrganStatus = entries.firstOrNull { it.id == id } ?: NoData
    }
}

/** The map is never calmer than its own safety message: a safety text forces "Talk to a doctor". */
fun effectiveStatus(organ: JsonObject): OrganStatus {
    val safety = organ.safetyText()
    return if (safety != null) OrganStatus.TalkToDoctor else OrganStatus.of(organ.str("status"))
}

/** The server's safety wording: a plain string, or an object with a "message". Blank means none. */
fun JsonObject.safetyText(): String? {
    val raw = this["safety"] ?: return null
    val text = (raw as? JsonObject)?.str("message") ?: (raw as? kotlinx.serialization.json.JsonPrimitive)?.takeIf { it !is kotlinx.serialization.json.JsonNull }?.content
    return text?.takeIf { it.isNotBlank() }
}

const val GENERAL_EMERGENCY_LINE =
    "If you feel severely unwell right now, for example chest pain, trouble breathing or fainting, call 112 or go to the nearest emergency department."
