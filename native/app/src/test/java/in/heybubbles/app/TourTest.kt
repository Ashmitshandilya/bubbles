package `in`.heybubbles.app

import `in`.heybubbles.app.ui.screens.TOUR_STEPS
import `in`.heybubbles.app.ui.screens.nextTourIndex
import `in`.heybubbles.app.ui.screens.tourPosition
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

class TourTest {
    @Test fun nextMovesOnAndTheLastStopFinishes() {
        assertEquals(1, nextTourIndex(0, 5))
        assertNull(nextTourIndex(4, 5))
        assertEquals("1 of 5", tourPosition(0, 5))
    }

    @Test fun copyFollowsTheHouseRules() {
        TOUR_STEPS.forEach { s ->
            assertFalse("no em-dash in ${s.title}", (s.title + s.body).contains('—'))
            assertFalse("no diagnosis wording in ${s.title}", Regex("diagnos|dose|treat", RegexOption.IGNORE_CASE).containsMatchIn(s.body))
        }
    }
}
