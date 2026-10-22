package `in`.heybubbles.app.data

import kotlin.math.roundToInt

/** Unit helpers for the body form: the server always stores metric, the person may type in pounds and feet. */
object FitnessCalc {
    private const val LB_PER_KG = 2.2046226218
    const val CM_PER_IN = 2.54

    fun kgToLb(kg: Double) = kg * LB_PER_KG
    fun lbToKg(lb: Double) = lb / LB_PER_KG

    /** Weight as the text shown in a field for the chosen units (one decimal), or "" when there is none. */
    fun weightText(kg: Double?, imperial: Boolean): String {
        if (kg == null || kg <= 0.0) return ""
        val v = if (imperial) kgToLb(kg) else kg
        return ((v * 10).roundToInt() / 10.0).toString().removeSuffix(".0")
    }

    /** The typed weight in kilograms, or null when it is empty or not a number. */
    fun weightKg(text: String, imperial: Boolean): Double? {
        val v = text.trim().replace(',', '.').toDoubleOrNull() ?: return null
        return if (imperial) lbToKg(v) else v
    }

    fun cmToFtIn(cm: Double): Pair<Int, Int> {
        val totalIn = (cm / CM_PER_IN).roundToInt()
        return totalIn / 12 to totalIn % 12
    }

    fun ftInToCm(ft: Int, inch: Int): Double = ((ft * 12 + inch) * CM_PER_IN * 10).roundToInt() / 10.0
}
