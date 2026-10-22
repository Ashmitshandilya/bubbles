package `in`.heybubbles.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.sp
import `in`.heybubbles.app.R

@OptIn(ExperimentalTextApi::class)
private fun family(res: Int, vararg weights: FontWeight) = FontFamily(
    weights.map { w -> Font(res, w, variationSettings = FontVariation.Settings(FontVariation.weight(w.weight))) }
)

val Fredoka = family(R.font.fredoka, FontWeight.Medium, FontWeight.SemiBold, FontWeight.Bold)
val Nunito = family(R.font.nunito, FontWeight.Normal, FontWeight.Medium, FontWeight.SemiBold, FontWeight.Bold)

private fun heading(size: Int, weight: FontWeight, line: Int) =
    TextStyle(fontFamily = Fredoka, fontWeight = weight, fontSize = size.sp, lineHeight = line.sp, letterSpacing = (-0.2).sp)
private fun body(size: Int, weight: FontWeight, line: Int) =
    TextStyle(fontFamily = Nunito, fontWeight = weight, fontSize = size.sp, lineHeight = line.sp)

val BubblesTypography = Typography(
    displayLarge = heading(48, FontWeight.SemiBold, 52),
    displayMedium = heading(40, FontWeight.SemiBold, 44),
    headlineLarge = heading(32, FontWeight.Bold, 36),
    headlineMedium = heading(28, FontWeight.SemiBold, 32),
    headlineSmall = heading(24, FontWeight.SemiBold, 28),
    titleLarge = heading(22, FontWeight.SemiBold, 28),
    titleMedium = heading(17, FontWeight.SemiBold, 24),
    titleSmall = heading(15, FontWeight.Medium, 20),
    bodyLarge = body(16, FontWeight.Normal, 24),
    bodyMedium = body(14, FontWeight.Normal, 21),
    bodySmall = body(12, FontWeight.Normal, 17),
    labelLarge = body(15, FontWeight.SemiBold, 20),
    labelMedium = body(13, FontWeight.SemiBold, 18),
    labelSmall = body(11, FontWeight.SemiBold, 16),
)
