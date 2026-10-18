package `in`.heybubbles.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import java.time.LocalDate

/**
 * The first-run setup, on the phone. The question bank and every rule live on the server (backend/onboarding.py); this file reads
 * the bank and mirrors only the small rules needed to decide what to show next, exactly like frontend/app/onboarding/flow.ts.
 * The server stays the authority and re-checks every answer.
 */
typealias Answers = Map<String, JsonElement>

class Rule(
    val ageGte: Int? = null,
    val ageLt: Int? = null,
    val bodyIn: List<String>? = null,
    val answers: Map<String, List<String>> = emptyMap(),
    val notAnswers: Map<String, List<String>> = emptyMap(),
)

class Option(val id: String, val label: String, val showIf: Rule?)

class Question(
    val id: String,
    val step: String,
    val type: String,
    val title: String,
    val why: String,
    val required: Boolean,
    val requiredIf: Rule?,
    val screen: String?,
    val options: List<Option>,
    val showIf: Rule?,
    val exclusive: List<String>,
    val maxPicks: Int?,
    val maxLength: Int?,
    val min: Double?,
    val max: Double?,
    val increment: Double?,
    val unit: String?,
)

class Bank(
    val version: String,
    val questions: List<Question>,
    val screenTitles: Map<String, String>,
    val titlesHi: Map<String, String>,
    val minAge: Int,
)

class OnboardingState(
    val complete: Boolean,
    val under18: Boolean,
    val answers: Answers,
    val step: Int,
)

enum class ScreenKind { Questions, Choices, ExtrasIntro }

class Screen(val id: String, val kind: ScreenKind, val stage: String, val title: String, val ids: MutableList<String>, var followUp: Boolean)

private fun JsonObject.str(k: String) = (this[k] as? JsonPrimitive)?.contentOrNull
private fun JsonObject.num(k: String) = (this[k] as? JsonPrimitive)?.doubleOrNull
private fun JsonObject.strings(k: String) = (this[k] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()

private fun parseRule(e: JsonElement?): Rule? {
    val o = e as? JsonObject ?: return null
    fun map(k: String) = (o[k] as? JsonObject)?.mapValues { (_, v) -> (v as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty() }.orEmpty()
    return Rule(
        ageGte = (o["age_gte"] as? JsonPrimitive)?.intOrNull, ageLt = (o["age_lt"] as? JsonPrimitive)?.intOrNull,
        bodyIn = (o["body_in"] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull },
        answers = map("answers"), notAnswers = map("not_answers"),
    )
}

fun parseBank(root: JsonObject): Bank {
    val qs = (root["questions"] as? JsonArray).orEmpty().mapNotNull { el ->
        val o = el as? JsonObject ?: return@mapNotNull null
        Question(
            id = o.str("id") ?: return@mapNotNull null, step = o.str("step").orEmpty(), type = o.str("type").orEmpty(),
            title = o.str("title").orEmpty(), why = o.str("why").orEmpty(), required = (o["required"] as? JsonPrimitive)?.booleanOrNull == true,
            requiredIf = parseRule(o["required_if"]), screen = o.str("screen"),
            options = (o["options"] as? JsonArray).orEmpty().mapNotNull { oe ->
                val oo = oe as? JsonObject ?: return@mapNotNull null
                Option(oo.str("id") ?: return@mapNotNull null, oo.str("label").orEmpty(), parseRule(oo["show_if"]))
            },
            showIf = parseRule(o["show_if"]), exclusive = o.strings("exclusive"), maxPicks = (o["max_picks"] as? JsonPrimitive)?.intOrNull,
            maxLength = (o["maxlength"] as? JsonPrimitive)?.intOrNull, min = o.num("min"), max = o.num("max"), increment = o.num("increment"), unit = o.str("unit"),
        )
    }
    fun strMap(k: String) = (root[k] as? JsonObject)?.mapNotNull { (key, v) -> (v as? JsonPrimitive)?.contentOrNull?.let { key to it } }?.toMap().orEmpty()
    return Bank(root.str("version").orEmpty(), qs, strMap("screens"), strMap("titles_hi"), (root["min_age"] as? JsonPrimitive)?.intOrNull ?: 18)
}

object Flow {
    /** Whole years on [today] for a YYYY-MM-DD birth date, or null when it is not a real past day. */
    fun ageOn(birth: JsonElement?, today: LocalDate): Int? {
        val s = (birth as? JsonPrimitive)?.contentOrNull ?: return null
        val d = runCatching { LocalDate.parse(s) }.getOrNull() ?: return null
        if (d.isAfter(today)) return null
        return java.time.Period.between(d, today).years
    }

    fun picked(v: JsonElement?): List<String> = when (v) {
        null, JsonNull -> emptyList()
        is JsonArray -> v.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
        is JsonPrimitive -> listOfNotNull(v.contentOrNull?.takeIf { it.isNotEmpty() })
        else -> emptyList()
    }

    /** Every part of the rule must hold. A part that depends on an unanswered question does not hold, except `notAnswers`. */
    fun matches(rule: Rule?, a: Answers, today: LocalDate): Boolean {
        if (rule == null) return true
        val age = ageOn(a["birth_date"], today)
        if (rule.ageGte != null && (age == null || age < rule.ageGte)) return false
        if (rule.ageLt != null && (age == null || age >= rule.ageLt)) return false
        if (rule.bodyIn != null && (a["body"] as? JsonPrimitive)?.contentOrNull !in rule.bodyIn) return false
        for ((q, ids) in rule.answers) if (picked(a[q]).none { it in ids }) return false
        for ((q, ids) in rule.notAnswers) if (picked(a[q]).any { it in ids }) return false
        return true
    }

    fun visibleOptions(q: Question, a: Answers, today: LocalDate) = q.options.filter { matches(it.showIf, a, today) }
    fun visibleQuestions(bank: Bank, a: Answers, today: LocalDate) = bank.questions.filter { matches(it.showIf, a, today) }

    fun isAnswered(v: JsonElement?): Boolean = when (v) {
        null, JsonNull -> false
        is JsonArray -> v.isNotEmpty()
        is JsonObject -> v.isNotEmpty()
        is JsonPrimitive -> !v.contentOrNull.isNullOrEmpty()
    }

    fun isRequired(q: Question, a: Answers, today: LocalDate) = q.required || (q.requiredIf != null && matches(q.requiredIf, a, today))

    fun missingRequired(qs: List<Question>, a: Answers, today: LocalDate) = qs.filter { isRequired(it, a, today) && !isAnswered(a[it.id]) }.map { it.id }

    /** The screens of a run in order: the required core, "Your choices", a stage intro, then the optional extras. */
    fun buildScreens(bank: Bank, a: Answers, today: LocalDate): List<Screen> {
        val out = mutableListOf<Screen>()
        val byKey = HashMap<String, Screen>()
        for (q in visibleQuestions(bank, a, today)) {
            if (q.step == "later") continue
            val key = q.screen ?: q.id
            val have = byKey[key]
            if (have != null) { have.ids += q.id; have.followUp = have.followUp && q.showIf?.answers?.isNotEmpty() == true; continue }
            val s = Screen(key, ScreenKind.Questions, q.step, bank.screenTitles[key].orEmpty(), mutableListOf(q.id), q.showIf?.answers?.isNotEmpty() == true)
            byKey[key] = s; out += s
        }
        val firstExtra = out.indexOfFirst { it.stage != "core" }
        val at = if (firstExtra < 0) out.size else firstExtra
        val extras = out.drop(at)
        val lead = mutableListOf(Screen("choices", ScreenKind.Choices, "core", "Your choices", mutableListOf(), false))
        if (extras.isNotEmpty()) lead += Screen("extras-intro", ScreenKind.ExtrasIntro, "extras", "A little more", mutableListOf(), false)
        return out.take(at) + lead + extras
    }

    fun screenQuestions(s: Screen, bank: Bank) = s.ids.mapNotNull { id -> bank.questions.firstOrNull { it.id == id } }

    /** The answer after tapping [optionId]: single replaces, multi adds or removes, and "None of these" options stand alone. */
    fun pick(q: Question, current: JsonElement?, optionId: String): JsonElement? {
        if (q.type == "single") return JsonPrimitive(optionId)
        val now = picked(current)
        if (optionId in now) return (now - optionId).takeIf { it.isNotEmpty() }?.let { JsonArray(it.map(::JsonPrimitive)) }
        if (optionId in q.exclusive) return JsonArray(listOf(JsonPrimitive(optionId)))
        val without = now.filter { it !in q.exclusive }
        if (q.maxPicks != null && without.size >= q.maxPicks) return JsonArray(without.map(::JsonPrimitive))
        return JsonArray((without + optionId).map(::JsonPrimitive))
    }

    /** The title in the person's language when the bank has one (Hinglish), else English. */
    fun titleFor(q: Question, a: Answers, bank: Bank): String {
        val lang = (a["language"] as? JsonPrimitive)?.contentOrNull
        return if (lang == "hinglish" || lang == "hindi") bank.titlesHi[q.id] ?: q.title else q.title
    }

    /** New or changed answers for the screens up to [upTo], and null for an optional answer that was cleared. Nothing is saved before the age is known. */
    fun pendingPatch(screens: List<Screen>, upTo: Int, bank: Bank, a: Answers, saved: Answers, today: LocalDate): Map<String, JsonElement>? {
        if (ageOn(a["birth_date"], today) == null) return null
        val patch = LinkedHashMap<String, JsonElement>()
        for (s in screens.take(upTo + 1)) for (q in screenQuestions(s, bank)) {
            val v = a[q.id]
            if (isAnswered(v)) { if (saved[q.id] != v) patch[q.id] = v!! }
            else if (isAnswered(saved[q.id]) && !isRequired(q, a, today)) patch[q.id] = JsonNull
        }
        return patch
    }

    /** Where to pick up: the first core screen with a required question still open, else the choices step. */
    fun resumeIndex(screens: List<Screen>, bank: Bank, a: Answers, today: LocalDate): Int {
        val open = screens.indexOfFirst { it.kind == ScreenKind.Questions && it.stage == "core" && missingRequired(screenQuestions(it, bank), a, today).isNotEmpty() }
        if (open >= 0) return open
        return screens.indexOfFirst { it.kind == ScreenKind.Choices }.coerceAtLeast(0)
    }
}
