package `in`.heybubbles.app

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import `in`.heybubbles.app.data.parseToday
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TodayBundleTest {
    private fun parse(text: String) = parseToday(Json.parseToJsonElement(text).jsonObject)

    @Test fun readsTheLedeAndWhatElseTodayNeeds() {
        val b = parse("""{"lede":{"kind":"pattern","text":"Sleep and mood moved together."},
            "brief":{"state":{"data_gaps":{"gaps":["No sleep logged this week","No sleep logged this week",{"text":"No water yet"}]}},"companion":{"safety_note":"Patterns, not diagnoses."}},
            "orbit":{"question":{"text":"What made you smile?","answered":false}},
            "profile":{"profile":{"display_name":"Riya"}}}""")
        assertEquals("Sleep and mood moved together.", b.lede)
        assertEquals("pattern", b.ledeKind)
        assertEquals(listOf("No sleep logged this week", "No water yet"), b.gaps)
        assertEquals("Patterns, not diagnoses.", b.safetyNote)
        assertTrue(b.orbitQuestionWaiting)
        assertEquals("Riya", b.displayName)
    }

    @Test fun aPartThatCouldNotBeReadIsAGapNotAGuess() {
        val b = parse("""{"lede":null,"brief":null,"orbit":null,"profile":null}""")
        assertNull(b.lede)
        assertEquals(emptyList<String>(), b.gaps)
        assertEquals("", b.safetyNote)
        assertFalse(b.orbitQuestionWaiting)
        assertNull(b.displayName)
    }

    @Test fun anAnsweredQuestionIsNotWaitingAndJunkIsIgnored() {
        assertFalse(parse("""{"orbit":{"question":{"answered":true}}}""").orbitQuestionWaiting)
        assertFalse(parse("""{"orbit":{"question":{}}}""").orbitQuestionWaiting)   // unknown is not "waiting"
        assertNull(parse("""{"lede":{"text":"   "}}""").lede)
        assertNull(parse("""{"lede":"not an object"}""").lede)
    }

    @Test fun theProfileMayComeInEitherShape() {
        assertEquals("Asha", parse("""{"profile":{"display_name":"Asha"}}""").displayName)
    }

    @Test fun theTrackerEntriesTodayAlreadyReadAreKeptNewestFirst() {
        val b = parse("""{"trackers":{"sleep":{"entries":[{"id":"a","date":"2026-10-22","duration":6.5},{"id":"b","date":"2026-10-23","duration":7.0},{"date":"2026-10-24"}]},
            "mood":null,"hydration":{"entries":[]}}}""")
        assertEquals(setOf("sleep", "hydration"), b.trackers.keys)                 // a tracker the server could not read is absent, never empty
        assertEquals(listOf("b", "a"), b.trackers["sleep"]!!.map { it.id })       // newest first; a row without an id is skipped
        assertEquals(7.0, b.trackers["sleep"]!!.first().number("duration")!!, 0.0)
        assertTrue(b.trackers["hydration"]!!.isEmpty())                           // read, and nothing logged: that is an answer
    }

    @Test fun theCheckedGuessIsKeptWordForWordAndAbsentWhenBlank() {
        assertEquals("Bubbles guessed it, and it held.", parse("""{"learned":{"checked":"Bubbles guessed it, and it held."}}""").checked)
        assertNull(parse("""{"learned":{"checked":""}}""").checked)
        assertNull(parse("""{}""").checked)
    }
}
