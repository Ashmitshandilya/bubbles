package `in`.heybubbles.app

import `in`.heybubbles.app.data.Flow
import `in`.heybubbles.app.data.Rule
import `in`.heybubbles.app.data.ScreenKind
import `in`.heybubbles.app.data.parseBank
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/** The first-run rules must match backend/onboarding.py and frontend/app/onboarding/flow.ts: the server re-checks, but the phone must not show what it would refuse. */
class OnboardingFlowTest {
    private val today = LocalDate.of(2026, 10, 18)
    private fun a(vararg p: Pair<String, JsonElement>): Map<String, JsonElement> = mapOf(*p)
    private fun s(v: String) = JsonPrimitive(v)

    private val bank = parseBank(
        Json.parseToJsonElement(
            """{"version":"v","min_age":18,"screens":{"about":"About you","cycle":"Your cycle"},"titles_hi":{"body":"Aap kaun hain?"},
            "questions":[
              {"id":"birth_date","step":"core","type":"date","title":"Born?","required":true,"screen":"about"},
              {"id":"body","step":"core","type":"single","title":"Which?","required":true,"screen":"about","options":[{"id":"female","label":"Female"},{"id":"male","label":"Male"}]},
              {"id":"periods","step":"core","type":"single","title":"Periods?","required":false,"required_if":{"body_in":["female"]},"show_if":{"body_in":["female"],"age_gte":18,"age_lt":56},"options":[{"id":"regular","label":"Regular"}]},
              {"id":"last_period","step":"extras","type":"date","title":"Last?","required":false,"screen":"cycle","show_if":{"answers":{"periods":["regular"]}}},
              {"id":"screen_hours","step":"later","type":"slider","title":"Screens?","required":false}
            ]}""",
        ) as JsonObject,
    )

    @Test fun countryStartsAsIndiaOnlyForAnIndianTimeZone() {
        assertEquals("in", Flow.countryFromTimeZone("Asia/Kolkata"))
        assertEquals("in", Flow.countryFromTimeZone("Asia/Calcutta"))
        assertNull(Flow.countryFromTimeZone("America/New_York"))
        assertNull(Flow.countryFromTimeZone(null))
    }

    @Test fun ageIsWholeYearsAndRejectsFutureDates() {
        assertEquals(27, Flow.ageOn(s("1999-03-14"), today))
        assertEquals(26, Flow.ageOn(s("1999-12-31"), today))      // birthday not reached yet this year
        assertNull(Flow.ageOn(s("2030-01-01"), today))
        assertNull(Flow.ageOn(s("not a date"), today))
    }

    @Test fun periodsAppearOnlyForTheRightBodyAndAge() {
        val female = a("birth_date" to s("1999-03-14"), "body" to s("female"))
        val male = a("birth_date" to s("1999-03-14"), "body" to s("male"))
        val tooOld = a("birth_date" to s("1960-01-01"), "body" to s("female"))
        val ids = { m: Map<String, JsonElement> -> Flow.visibleQuestions(bank, m, today).map { it.id } }
        assertTrue("periods" in ids(female))
        assertFalse("periods" in ids(male))
        assertFalse("periods" in ids(tooOld))
    }

    @Test fun aRuleThatDependsOnAnUnansweredQuestionDoesNotHold() {
        assertFalse(Flow.matches(Rule(ageGte = 18), emptyMap(), today))
        assertTrue(Flow.matches(Rule(notAnswers = mapOf("x" to listOf("y"))), emptyMap(), today))   // not_answers is the exception
    }

    @Test fun requiredIfMakesPeriodsRequiredForFemaleOnly() {
        val periods = bank.questions.first { it.id == "periods" }
        assertTrue(Flow.isRequired(periods, a("body" to s("female"), "birth_date" to s("1999-03-14")), today))
        assertFalse(Flow.isRequired(periods, a("body" to s("male")), today))
    }

    @Test fun screensRunCoreThenChoicesThenExtrasAndSkipLaterQuestions() {
        val answers = a("birth_date" to s("1999-03-14"), "body" to s("female"), "periods" to s("regular"))
        val screens = Flow.buildScreens(bank, answers, today)
        val kinds = screens.map { it.kind }
        assertEquals(listOf(ScreenKind.Questions, ScreenKind.Questions, ScreenKind.Choices, ScreenKind.ExtrasIntro, ScreenKind.Questions), kinds)
        assertFalse(screens.any { "screen_hours" in it.ids })     // "later" questions are not part of first run
    }

    @Test fun questionsSharingAScreenAreAskedTogether() {
        val screens = Flow.buildScreens(bank, a("birth_date" to s("1999-03-14"), "body" to s("female")), today)
        assertEquals(listOf("birth_date", "body"), screens.first().ids)
    }

    @Test fun singleReplacesAndMultiAddsAndExclusiveStandsAlone() {
        val single = bank.questions.first { it.id == "body" }
        assertEquals(s("male"), Flow.pick(single, s("female"), "male"))
        val multi = parseBank(
            Json.parseToJsonElement(
                """{"questions":[{"id":"m","step":"core","type":"multi","title":"t","exclusive":["none"],"max_picks":2,
                "options":[{"id":"a","label":"A"},{"id":"b","label":"B"},{"id":"c","label":"C"},{"id":"none","label":"None"}]}]}""",
            ) as JsonObject,
        ).questions.single()
        assertEquals(JsonArray(listOf(s("a"), s("b"))), Flow.pick(multi, JsonArray(listOf(s("a"))), "b"))
        assertEquals(JsonArray(listOf(s("a"), s("b"))), Flow.pick(multi, JsonArray(listOf(s("a"), s("b"))), "c"))   // capped
        assertEquals(JsonArray(listOf(s("none"))), Flow.pick(multi, JsonArray(listOf(s("a"))), "none"))
        assertNull(Flow.pick(multi, JsonArray(listOf(s("a"))), "a"))                                          // untapping the last one clears it
    }

    @Test fun nothingIsSavedBeforeTheBirthDateIsKnown() {
        val screens = Flow.buildScreens(bank, emptyMap(), today)
        assertNull(Flow.pendingPatch(screens, 0, bank, a("body" to s("female")), emptyMap(), today))
    }

    @Test fun patchHoldsOnlyWhatChangedAndClearsSkippedOptionals() {
        val answers = a("birth_date" to s("1999-03-14"), "body" to s("female"), "periods" to s("regular"))
        val screens = Flow.buildScreens(bank, answers, today)
        val saved = a("birth_date" to s("1999-03-14"), "body" to s("female"))
        assertEquals(mapOf("periods" to s("regular")), Flow.pendingPatch(screens, 1, bank, answers, saved, today))
        // an optional answer that was cleared is sent as null so the server forgets it
        val saved2 = answers + ("last_period" to s("2026-10-05"))
        val cleared = Flow.pendingPatch(screens, screens.lastIndex, bank, answers, saved2, today)
        assertEquals(JsonNull, cleared?.get("last_period"))
    }

    @Test fun hinglishTitlesAreUsedWhenAvailable() {
        val q = bank.questions.first { it.id == "body" }
        assertEquals("Aap kaun hain?", Flow.titleFor(q, a("language" to s("hinglish")), bank))
        assertEquals("Which?", Flow.titleFor(q, a("language" to s("english")), bank))
    }

    @Test fun resumeGoesToTheFirstOpenRequiredScreenElseChoices() {
        val partial = a("birth_date" to s("1999-03-14"), "body" to s("female"))
        val screens = Flow.buildScreens(bank, partial, today)
        assertEquals(1, Flow.resumeIndex(screens, bank, partial, today))   // periods still open
        val full = a("birth_date" to s("1999-03-14"), "body" to s("female"), "periods" to s("regular"))
        val s2 = Flow.buildScreens(bank, full, today)
        assertEquals(ScreenKind.Choices, s2[Flow.resumeIndex(s2, bank, full, today)].kind)
    }
}
