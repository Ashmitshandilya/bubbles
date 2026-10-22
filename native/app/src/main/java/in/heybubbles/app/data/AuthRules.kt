package `in`.heybubbles.app.data

/** Pure rules for creating an account, held to the website's sign-up (frontend/app/login/page.tsx). */
object AuthRules {
    /** Must equal POLICY_VERSION in backend/consent.py and PRIVACY_NOTICE_VERSION on the website. */
    const val NOTICE_VERSION = "2026-10-16"

    /** Confirmation and reset links open in the browser on the real site, like the website's own. */
    const val CALLBACK_URL = "https://heybubbles.in/callback"
    const val RESET_URL = "$CALLBACK_URL?next=password"

    const val MIN_PASSWORD = 6

    private val EMAIL = Regex("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")

    fun looksLikeEmail(text: String): Boolean = EMAIL.matches(text.trim())

    /** The first thing to fix before an account can be made, in plain words, or null when the form is ready. */
    fun signUpProblem(name: String, email: String, password: String, acknowledged: Boolean): String? = when {
        name.isBlank() -> "Tell Bubbles what to call you."
        !looksLikeEmail(email) -> "That email doesn't look right."
        password.length < MIN_PASSWORD -> "Use at least $MIN_PASSWORD characters for your password."
        !acknowledged -> "Please tick that you have read the Terms and the Privacy notice."
        else -> null
    }
}
