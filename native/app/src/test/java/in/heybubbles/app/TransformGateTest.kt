package `in`.heybubbles.app

import `in`.heybubbles.app.ui.screens.fitness.canStartTransform
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TransformGateTest {
    @Test fun onlyTheTwoAllowedVerdictsEverOfferAStart() {
        assertTrue(canStartTransform("allowed"))
        assertTrue(canStartTransform("allowed_with_cautions"))
    }

    @Test fun refusedIncompleteMissingOrUnknownNeverStart() {
        assertFalse(canStartTransform("refused"))
        assertFalse(canStartTransform("incomplete"))
        assertFalse(canStartTransform(null))
        assertFalse(canStartTransform(""))
        assertFalse(canStartTransform("ALLOWED"))
        assertFalse(canStartTransform("something_new"))
    }
}
