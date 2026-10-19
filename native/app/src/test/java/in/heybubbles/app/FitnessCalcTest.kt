package `in`.heybubbles.app

import `in`.heybubbles.app.data.FitnessCalc
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FitnessCalcTest {
    @Test fun poundsRoundTripThroughKilograms() {
        assertEquals("154.3", FitnessCalc.weightText(70.0, true))
        assertEquals(70.0, FitnessCalc.weightKg("154.3", true)!!, 0.05)
        assertEquals("70", FitnessCalc.weightText(70.0, false))
    }

    @Test fun emptyOrBadWeightIsNullNotZero() {
        assertNull(FitnessCalc.weightKg("", false))
        assertNull(FitnessCalc.weightKg("abc", true))
        assertEquals("", FitnessCalc.weightText(null, false))
        assertEquals(60.5, FitnessCalc.weightKg("60,5", false)!!, 0.001)
    }

    @Test fun heightConvertsBothWays() {
        assertEquals(5 to 7, FitnessCalc.cmToFtIn(170.0))
        assertEquals(170.2, FitnessCalc.ftInToCm(5, 7), 0.01)
    }
}
