package `in`.heybubbles.app

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import `in`.heybubbles.app.data.StarsLogic
import `in`.heybubbles.app.data.str
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class StarsLogicTest {
    private val today = LocalDate.of(2026, 10, 24)

    @Test fun aGoodFormHasNoProblems() {
        assertFalse(StarsLogic.problems("1999-03-14", "06:30", false, "000-delhi", today).any)
        assertFalse(StarsLogic.problems("1999-03-14", "", true, "000-delhi", today).any)   // an unknown time is allowed
    }

    @Test fun eachProblemIsNamedInPlainWords() {
        val p = StarsLogic.problems("2999-01-01", "7pm", false, null, today)
        assertTrue(p.date!!.contains("future"))
        assertTrue(p.time!!.contains("HH:MM"))
        assertTrue(p.place!!.contains("Choose"))
        assertTrue(StarsLogic.problems("1800-01-01", "06:30", false, "x", today).date!!.contains("1900"))
        assertTrue(StarsLogic.problems("not a date", "06:30", false, "x", today).date!!.contains("YYYY-MM-DD"))
        assertNull(StarsLogic.problems("1999-03-14", "23:59", false, "x", today).time)
        assertTrue(StarsLogic.problems("1999-03-14", "24:00", false, "x", today).time != null)
    }

    @Test fun theBodyOmitsTheTimeWhenItIsUnknown() {
        assertEquals("06:30", StarsLogic.body("1999-03-14", "06:30", false, "000-delhi").str("birth_time"))
        assertNull(StarsLogic.body("1999-03-14", "06:30", true, "000-delhi").str("birth_time"))
        assertEquals("000-delhi", StarsLogic.body(" 1999-03-14 ", "", true, "000-delhi").str("city_id"))
    }

    @Test fun placementsAreDescribedWithBothOptionsWhenUnsure() {
        val moon = Json.parseToJsonElement("""{"rashi":"Makara","nakshatra":"Shravana","rashi_options":["Makara"],"nakshatra_options":["Uttara Ashadha","Shravana"],"cusp":true}""").jsonObject
        assertEquals("Moon: Makara, nakshatra Uttara Ashadha or Shravana. A birth time would settle it.", StarsLogic.describe("Moon", moon))
        val sun = Json.parseToJsonElement("""{"rashi":"Kumbha","nakshatra":"","cusp":true}""").jsonObject
        assertEquals("Sun: Kumbha, on the cusp", StarsLogic.describe("Sun", sun))
        assertEquals("Ascendant: needs a birth time", StarsLogic.describe("Ascendant", null))
    }
}
