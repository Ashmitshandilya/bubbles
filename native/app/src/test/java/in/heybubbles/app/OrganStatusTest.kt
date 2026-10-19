package `in`.heybubbles.app

import `in`.heybubbles.app.data.OrganStatus
import `in`.heybubbles.app.data.effectiveStatus
import `in`.heybubbles.app.data.safetyText
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class OrganStatusTest {
    private fun organ(s: String) = Json.parseToJsonElement(s).jsonObject

    @Test fun anUnknownStatusIsNoDataNeverSteady() {
        assertEquals(OrganStatus.NoData, OrganStatus.of("something_new"))
        assertEquals(OrganStatus.NoData, OrganStatus.of(null))
        assertEquals(OrganStatus.Steady, OrganStatus.of("steady"))
    }

    @Test fun theMapIsNeverCalmerThanItsSafetyMessage() {
        assertEquals(OrganStatus.TalkToDoctor, effectiveStatus(organ("""{"status":"steady","safety":"Please get this checked today."}""")))
        assertEquals(OrganStatus.TalkToDoctor, effectiveStatus(organ("""{"status":"no_data","safety":{"message":"Call 112."}}""")))
        assertEquals(OrganStatus.Steady, effectiveStatus(organ("""{"status":"steady","safety":null}""")))
        assertEquals(OrganStatus.Steady, effectiveStatus(organ("""{"status":"steady","safety":"   "}""")))
    }

    @Test fun safetyTextReadsStringsAndObjectsAndIgnoresBlank() {
        assertEquals("a", organ("""{"safety":"a"}""").safetyText())
        assertEquals("b", organ("""{"safety":{"message":"b"}}""").safetyText())
        assertNull(organ("""{"safety":null}""").safetyText())
        assertNull(organ("""{}""").safetyText())
    }
}
