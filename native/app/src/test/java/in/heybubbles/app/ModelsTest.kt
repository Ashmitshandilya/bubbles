package `in`.heybubbles.app

import `in`.heybubbles.app.data.AssociationsResponse
import `in`.heybubbles.app.data.ChatReply
import `in`.heybubbles.app.data.LatestChat
import `in`.heybubbles.app.data.ConsentsResponse
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The API grows fields all the time; the app must read what it knows and ignore the rest. */
class ModelsTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true }

    @Test fun chatReplyReadsSafetyAndConsentAsk() {
        val r = json.decodeFromString<ChatReply>("""{"response":"Hi","kind":"emergency","safety":{"level":"RED","state":"URGENT"},"consent_ask":true,"message_id":"m1","brand_new_field":1}""")
        assertEquals("RED", r.safety.level)
        assertTrue(r.consentAsk)
        assertEquals("m1", r.messageId)
    }

    @Test fun chatReplyDefaultsAreSafeWhenFieldsAreMissing() {
        val r = json.decodeFromString<ChatReply>("""{"response":"Hi"}""")
        assertEquals("GREEN", r.safety.level)
        assertFalse(r.consentAsk)
    }

    @Test fun chatReplyReadsQuickRepliesAndIsEmptyWithoutThem() {
        val r = json.decodeFromString<ChatReply>("""{"response":"Hi","suggestions":["Help me work out what to say","Open it up gently"]}""")
        assertEquals(listOf("Help me work out what to say", "Open it up gently"), r.suggestions)
        assertTrue(json.decodeFromString<ChatReply>("""{"response":"Hi"}""").suggestions.isEmpty())
    }

    @Test fun latestChatReadsMessagesAndConversation() {
        val l = json.decodeFromString<LatestChat>("""{"messages":[{"id":"1","role":"user","content":"x","created_at":"t","safety_level":null}],"has_more":false,"conversation":{"id":"c1","user_id":"u"}}""")
        assertEquals("c1", l.conversation?.id)
        assertEquals(1, l.messages.size)
    }

    @Test fun associationsKeepTheirCaveatsInTheText() {
        val a = json.decodeFromString<AssociationsResponse>("""{"insights":[{"id":"a","text":"It tended to be higher. An association in your own logs; it does not show that one thing causes the other.","strength":"moderate"}],"gaps":["Not enough cycle data"]}""")
        assertTrue(a.insights.single().text.contains("does not show that one thing causes the other"))
        assertEquals(1, a.gaps.size)
    }

    @Test fun consentsReadTextHashForGrants() {
        val c = json.decodeFromString<ConsentsResponse>("""{"purposes":[{"id":"ai_chat_processing","title":"t","description":"d","text_hash":"abc","available":true,"granted":false}]}""")
        assertEquals("abc", c.purposes.single().textHash)
    }
}
