package `in`.heybubbles.app

import `in`.heybubbles.app.data.OrbitLogic
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OrbitLogicTest {
    private fun obj(s: String) = Json.parseToJsonElement(s) as JsonObject

    @Test fun ledePrefersTheWeatherLine() {
        assertEquals("Ask how their day really was.", OrbitLogic.lede(obj("""{"weather":"Ask how their day really was.","profile":{"status":"dating"}}""")))
    }

    @Test fun ledeAsksFirstThenFitsTheRelationship() {
        assertTrue(OrbitLogic.lede(obj("""{"profile":{}}""")).contains("where you are"))
        assertTrue(OrbitLogic.lede(obj("""{"profile":{"status":"single"}}""")).contains("everyone you hold close"))
        assertTrue(OrbitLogic.lede(obj("""{"profile":{"status":"married"},"paired":true,"question":{"answered":false,"state":"waiting"}}""")).contains("waiting for you both"))
        assertTrue(OrbitLogic.lede(obj("""{"profile":{"status":"married"},"paired":true,"question":{"answered":true,"state":"revealed"}}""")).contains("both answered"))
        assertTrue(OrbitLogic.lede(null).isNotEmpty())
    }

    @Test fun onlyShortNumbersGetACallButton() {
        assertEquals("112", OrbitLogic.dial("112"))
        assertEquals("14416", OrbitLogic.dial("14416"))
        assertEquals("", OrbitLogic.dial("1-800-891-4416"))
        assertEquals("", OrbitLogic.dial("javascript:alert(1)"))
        assertEquals("", OrbitLogic.dial(""))
    }

    @Test fun aSafetyAnswerCarriesItsNumbersAndAnOrdinaryAnswerDoesNot() {
        val s = OrbitLogic.safety(obj("""{"status":"safety","kind":"safe_harbor","message":"I'm here.","harbor":{"resources":[{"name":"Emergency services","number":"112","note":"Free"},{"x":1}]}}"""))!!
        assertEquals("safe_harbor", s.kind)
        assertEquals(1, s.help.size)
        assertEquals("112", s.help[0].number)
        assertNull(OrbitLogic.safety(obj("""{"status":"success"}""")))
        assertEquals("emergency", OrbitLogic.safety(obj("""{"status":"safety","kind":"emergency","message":"m"}"""))!!.kind)
    }

    @Test fun theSafetyPlanKeepsOnlyKnownItemsInOrder() {
        assertEquals(setOf("bag", "numbers"), OrbitLogic.planFrom("bag,made-up,numbers"))
        assertEquals("numbers,bag", OrbitLogic.planToStore(setOf("bag", "numbers", "other")))
        assertEquals(emptySet<String>(), OrbitLogic.planFrom(null))
        assertTrue(OrbitLogic.PLAN.size >= 6)
    }
}
