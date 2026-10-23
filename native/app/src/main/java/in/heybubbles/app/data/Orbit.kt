package `in`.heybubbles.app.data

import kotlinx.serialization.json.JsonObject

/**
 * Orbit's small pure rules on the phone (the website mirrors them in app/orbit/orbit.ts). The server owns everything that matters: who may see
 * what, safety, consent. This file only chooses words and checks what is safe to put behind a call button.
 */
object OrbitLogic {
    val STATUS = listOf("single" to "Single", "dating" to "Dating someone", "situationship" to "It's undefined", "committed" to "In a relationship", "married" to "Married",
        "separated" to "Separated", "complicated" to "It's complicated", "prefer_not" to "Prefer not to say")
    val CARED = listOf("words" to "Kind words", "time" to "Time together", "help" to "Help with things", "touch" to "A hug or touch", "gifts" to "Thoughtful gifts")
    val CONFLICT = listOf("pursues" to "I want to talk it through right away", "withdraws" to "I need some space first", "balanced" to "Somewhere in between")
    val TONE = mapOf("gentle" to "Gentle", "light" to "Light", "clear" to "Clear")

    /** The line under the title: the partner's weather if there is one, else a warm line that fits where the person is. */
    fun lede(home: JsonObject?): String {
        if (home == null) return "A quiet place for the people closest to you."
        home.str("weather")?.takeIf { it.isNotBlank() }?.let { return it }
        val status = home.obj("profile")?.str("status")
        val paired = home.bool("paired") == true
        val q = home.obj("question")
        return when {
            status == null -> "Tell me a little about where you are, and I'll fit Orbit to you."
            paired && q?.str("state") == "revealed" -> "You both answered today's question. Worth a look together."
            paired && q?.bool("answered") != true -> "Today's question is waiting for you both."
            status == "single" -> "Orbit is for everyone you hold close, not only a partner."
            else -> "A small moment of attention goes a long way. What would help today?"
        }
    }

    /** A number that is safe to put behind a call button: 2 to 6 digits and an optional leading +; anything else is shown as text. */
    fun dial(raw: String): String {
        val compact = raw.replace(Regex("[\\s().-]"), "")
        return if (Regex("^\\+?\\d{2,6}$").matches(compact)) compact else ""
    }

    class Help(val name: String, val number: String, val note: String)
    class Safety(val kind: String, val message: String, val help: List<Help>)

    /** The server answered a free-text input with a fixed safety message instead of doing the thing: show it, nothing was saved. */
    fun safety(o: JsonObject): Safety? {
        if (o.str("status") != "safety") return null
        val help = o.obj("harbor")?.objs("resources").orEmpty().mapNotNull { r -> r.str("name")?.let { Help(it, r.str("number").orEmpty(), r.str("note").orEmpty()) } }
        return Safety(if (o.str("kind") == "emergency") "emergency" else "safe_harbor", o.str("message").orEmpty(), help)
    }

    /** The checklist behind "Feeling unsafe at home?": ticked items stay on this phone only. */
    val PLAN = listOf(
        "numbers" to "Save the numbers you may need under a neutral name in your phone.",
        "person" to "Choose one person you trust who knows you may need help.",
        "word" to "Agree a code word with them that means please call for help.",
        "bag" to "Keep a small bag ready: ID, some money, medicines, a charger, spare keys.",
        "documents" to "Keep copies of important documents somewhere safe outside your home.",
        "place" to "Know the nearest safe place you can go, and how to get there at night.",
        "phone" to "Keep your phone charged and your locked screen free of anything private.",
        "exit" to "Notice which room in your home has an exit and no weapons or tight spaces.",
    )

    fun planFrom(stored: String?): Set<String> = stored.orEmpty().split(",").filter { id -> PLAN.any { it.first == id } }.toSet()
    fun planToStore(ids: Set<String>): String = PLAN.map { it.first }.filter { it in ids }.joinToString(",")
}
