package `in`.heybubbles.app.data

import java.time.Instant

/** Small pure rules for partner sharing, kept the same as the website's (frontend/app/lib/partner-sharing.ts). */
object PartnerCalc {
    const val NOTE_MAX = 500
    const val NAME_MAX = 40
    val EXPIRY_DAYS = listOf(7, 30, 90)

    /** Letters and digits only, upper case, shown as XXXX-XXXX. */
    fun formatCode(raw: String): String {
        val clean = raw.uppercase().filter { it in 'A'..'Z' || it in '0'..'9' }.take(8)
        return if (clean.length > 4) clean.take(4) + "-" + clean.drop(4) else clean
    }

    fun codeComplete(code: String) = code.count { it.isLetterOrDigit() } == 8

    /** At least one thing is picked, a note exists whenever the note is picked, and the note fits. */
    fun canSave(categories: Set<String>, note: String): Boolean {
        if (categories.isEmpty()) return false
        if ("support_note" in categories && note.isBlank()) return false
        return note.length <= NOTE_MAX
    }

    /** The message sent with an invite code. It carries the code and where to type it, never any health data. */
    fun inviteMessage(code: String) =
        "I'd like to share a few things with you on Bubbles. Sign in at https://heybubbles.in/partner and enter this code: $code (it works for 48 hours)."

    fun linkMessage(token: String) = "I'm sharing a few things with you on Bubbles: https://heybubbles.in/partner/$token"

    fun hoursLeft(expiresAt: String?, nowMs: Long = System.currentTimeMillis()): Int? = left(expiresAt, nowMs, 3_600_000L)
    fun daysLeft(expiresAt: String?, nowMs: Long = System.currentTimeMillis()): Int? = left(expiresAt, nowMs, 86_400_000L)

    private fun left(expiresAt: String?, nowMs: Long, unit: Long): Int? {
        val end = runCatching { Instant.parse(expiresAt ?: return null).toEpochMilli() }.getOrNull() ?: return null
        return maxOf(0L, Math.ceil((end - nowMs).toDouble() / unit).toLong()).toInt()
    }
}
