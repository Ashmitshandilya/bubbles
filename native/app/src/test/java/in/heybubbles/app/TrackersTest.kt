package `in`.heybubbles.app

import `in`.heybubbles.app.data.Entry
import `in`.heybubbles.app.data.Trackers
import `in`.heybubbles.app.data.dayLabel
import `in`.heybubbles.app.ui.screens.daily
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

private fun entry(date: String, json: String): Entry = Entry("id-$date", date, Json.parseToJsonElement(json) as JsonObject)

class TrackersTest {
    private val today = LocalDate.now().toString()

    @Test fun sleepLineShowsHoursAndRestedScore() {
        val e = entry(today, """{"duration":7.5,"quality":4}""")
        assertEquals("7.5 h · rested 4/10", Trackers.bySlug("sleep").line(e))
    }

    @Test fun missingFieldsAreLeftOutNeverZero() {
        val e = entry(today, """{"duration":6}""")
        assertEquals("6 h", Trackers.bySlug("sleep").line(e))
        assertNull(entry(today, """{}""").number("duration"))
    }

    @Test fun weightIsShownInKilogramsAndSentInPounds() {
        val spec = Trackers.bySlug("weight")
        val e = entry(today, """{"weight":132.3}""")            // the server stores pounds
        assertEquals(60.0, spec.value!!(e)!!, 0.05)
        assertEquals(132.28, spec.toServer("weight", 60.0), 0.01)
        assertEquals(5.0, spec.toServer("notes", 5.0), 0.0)        // only weight is converted
    }

    @Test fun serverFormKeysMatchTheBackend() {
        // backend/health_logs.py reads these exact keys; a rename here would save nothing.
        val keys = Trackers.all.associate { it.slug to it.fields.map { f -> f.key } }
        assertTrue(keys["sleep"]!!.containsAll(listOf("duration", "quality")))
        assertTrue(keys["hydration"]!!.containsAll(listOf("volume", "type")))
        assertTrue(keys["nutrition"]!!.containsAll(listOf("description", "meal_type", "calories")))
        assertTrue(keys["activity"]!!.containsAll(listOf("type", "duration", "intensity")))
        assertTrue(keys["symptoms"]!!.containsAll(listOf("symptom", "severity")))
        assertTrue(keys["vitals"]!!.containsAll(listOf("heart_rate", "blood_pressure")))
        assertEquals(listOf("mood", "stress", "anxiety", "notes"), keys["mood"])
    }

    @Test fun waterIsSummedPerDayButSleepIsAveraged() {
        val water = listOf(entry(today, """{"volume":250}"""), entry(today, """{"volume":500}"""))
        assertEquals(750.0, daily(Trackers.bySlug("hydration"), water).single().second, 0.0)
        val sleep = listOf(entry(today, """{"duration":6}"""), entry(today, """{"duration":8}"""))
        assertEquals(7.0, daily(Trackers.bySlug("sleep"), sleep).single().second, 0.0)
    }

    @Test fun dayLabelsAreFriendly() {
        val t = LocalDate.of(2026, 10, 18)
        assertEquals("Today", entry("2026-10-18", "{}").dayLabel(t))
        assertEquals("Yesterday", entry("2026-10-17", "{}").dayLabel(t))
        assertEquals("Fri 16 Oct", entry("2026-10-16", "{}").dayLabel(t))
    }
}
