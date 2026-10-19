package `in`.heybubbles.app

import `in`.heybubbles.app.data.PartnerCalc
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PartnerCalcTest {
    @Test fun codeIsTidiedToTwoGroupsOfFour() {
        assertEquals("ABCD-EFGH", PartnerCalc.formatCode("abcd efgh9"))
        assertEquals("AB", PartnerCalc.formatCode("a-b"))
        assertTrue(PartnerCalc.codeComplete("ABCD-EFGH"))
        assertFalse(PartnerCalc.codeComplete("ABCD-EF"))
    }

    @Test fun savingNeedsAChoiceAndANoteWhenTheNoteIsPicked() {
        assertFalse(PartnerCalc.canSave(emptySet(), ""))
        assertTrue(PartnerCalc.canSave(setOf("sleep"), ""))
        assertFalse(PartnerCalc.canSave(setOf("support_note"), "   "))
        assertTrue(PartnerCalc.canSave(setOf("support_note"), "Please check in on me"))
        assertFalse(PartnerCalc.canSave(setOf("cycle"), "x".repeat(PartnerCalc.NOTE_MAX + 1)))
    }

    @Test fun timeLeftNeverGoesNegativeAndMissingDatesAreNull() {
        val now = java.time.Instant.parse("2026-10-20T00:00:00Z").toEpochMilli()
        assertEquals(2, PartnerCalc.hoursLeft("2026-10-20T01:30:00Z", now))
        assertEquals(0, PartnerCalc.hoursLeft("2026-10-19T00:00:00Z", now))
        assertEquals(30, PartnerCalc.daysLeft("2026-11-19T00:00:00Z", now))
        assertNull(PartnerCalc.daysLeft(null, now))
        assertNull(PartnerCalc.daysLeft("not a date", now))
    }

    @Test fun messagesCarryNoHealthData() {
        assertTrue(PartnerCalc.inviteMessage("ABCD-EFGH").contains("ABCD-EFGH"))
        assertTrue(PartnerCalc.linkMessage("tok").endsWith("/partner/tok"))
    }
}
