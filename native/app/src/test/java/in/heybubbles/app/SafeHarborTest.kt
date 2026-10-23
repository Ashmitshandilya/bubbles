package `in`.heybubbles.app

import `in`.heybubbles.app.data.ChatReply
import `in`.heybubbles.app.data.LatestChat
import `in`.heybubbles.app.data.dialNumber
import `in`.heybubbles.app.ui.screens.Msg
import `in`.heybubbles.app.ui.screens.keepsSecret
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The Safe Harbor payload is read exactly as the backend sends it, and anything odd still draws something safe. */
class SafeHarborTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true }

    private val served = """{"response":"I'm so sorry.","kind":"safe_harbor","safety":{"level":"GREEN"},"message_id":"m1","harbor":{"tier":3,"mode":"disclosure","step":"options",
        "resources":[{"name":"Emergency services","number":"112","note":"Free."},{"name":"Women Helpline","number":"181","note":"Free."},{"name":"NCW women helpline","number":"14490","note":"Free."}],
        "actions":[{"id":"talk_more","label":"I want to talk more"},{"id":"safety_plan","label":"Help me make a safety plan"},{"id":"show_help","label":"Show me who can help"},{"id":"okay_for_now","label":"I'm okay for now"}]}}"""

    @Test fun readsTheServedPayload() {
        val h = json.decodeFromString<ChatReply>(served).harbor!!.shown()
        assertEquals(3, h.tierLevel)
        assertEquals(listOf("112", "181", "14490"), h.resources.map { it.number })
        assertEquals(listOf("talk_more", "safety_plan", "show_help", "okay_for_now"), h.actions.map { it.id })
    }

    @Test fun anOrdinaryReplyHasNoHarbor() {
        assertNull(json.decodeFromString<ChatReply>("""{"response":"Hi"}""").harbor)
    }

    @Test fun zeroResourcesShowsOnly112() {
        val h = json.decodeFromString<ChatReply>("""{"response":"x","harbor":{"tier":2,"resources":[],"actions":[]}}""").harbor!!.shown()
        assertEquals(listOf("112"), h.resources.map { it.number })
        val missing = json.decodeFromString<ChatReply>("""{"response":"x","harbor":{}}""").harbor!!.shown()
        assertEquals(listOf("112"), missing.resources.map { it.number })
    }

    @Test fun anUnknownTierIsShownAsTier2() {
        for (tier in listOf("0", "1", "4", "\"3\"", "\"high\"", "null", "{}", "[]", "2.5")) {
            val h = json.decodeFromString<ChatReply>("""{"response":"x","harbor":{"tier":$tier}}""").harbor!!.shown()
            assertEquals("tier $tier", 2, h.tierLevel)
        }
    }

    @Test fun aResourceWithNoNumberIsWordsOnly() {
        val h = json.decodeFromString<ChatReply>("""{"response":"x","harbor":{"resources":[{"name":"your local emergency number","number":"","note":"n"}]}}""").harbor!!.shown()
        assertEquals("", h.resources.single().number)
        assertEquals("your local emergency number", h.resources.single().name)
    }

    @Test fun actionsThatCannotBeSentAreDroppedAndTheListIsCapped() {
        val many = (0..8).joinToString(",") { """{"id":"x$it","label":"Label $it"}""" }
        val h = json.decodeFromString<ChatReply>("""{"response":"x","harbor":{"actions":[{"id":"a"},{"label":"b"},$many]}}""").harbor!!.shown()
        assertEquals(5, h.actions.size)
        assertEquals("x0", h.actions.first().id)
    }

    @Test fun aReloadedMessageKeepsItsHarbor() {
        val l = json.decodeFromString<LatestChat>("""{"messages":[{"id":"1","role":"assistant","content":"x","harbor":{"tier":2,"resources":[{"name":"Emergency services","number":"112"}]}}]}""")
        assertNotNull(l.messages.single().harbor)
    }

    @Test fun onlyRealNumbersAreDialled() {
        assertEquals("112", dialNumber(" 112 "))
        assertEquals("14490", dialNumber("14490"))
        assertEquals("+91112", dialNumber("+91 112"))
        for (bad in listOf("", "call me", "112; rm", "tel:112", "1", "1234567", null)) assertEquals("", dialNumber(bad))
    }

    @Test fun theScreenIsSecretOnlyWhileAHarborReplyIsThere() {
        val plain = Msg("1", false, "Hello")
        val harbor = json.decodeFromString<ChatReply>(served).harbor!!.shown()
        assertFalse(keepsSecret(listOf(plain)))
        assertFalse(keepsSecret(emptyList()))
        assertTrue(keepsSecret(listOf(plain, Msg("2", false, "I'm so sorry.", harbor = harbor))))
    }
}
