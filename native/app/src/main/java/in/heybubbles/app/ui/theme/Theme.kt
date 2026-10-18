package `in`.heybubbles.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val Light = lightColorScheme(
    primary = Bubbles.PinkInk, onPrimary = Bubbles.White, primaryContainer = Bubbles.TintPink, onPrimaryContainer = Bubbles.PinkDeep,
    secondary = Bubbles.Grape, onSecondary = Bubbles.White, secondaryContainer = Bubbles.TintGrape, onSecondaryContainer = Bubbles.GrapeDeep,
    tertiary = Bubbles.MintDeep, onTertiary = Bubbles.White, tertiaryContainer = Bubbles.TintMint, onTertiaryContainer = Bubbles.MintDeep,
    background = Bubbles.Blush, onBackground = Bubbles.Ink,
    surface = Bubbles.White, onSurface = Bubbles.Ink, surfaceVariant = Bubbles.TintPink, onSurfaceVariant = Bubbles.InkSoft,
    surfaceContainerLowest = Bubbles.White, surfaceContainerLow = Bubbles.SurfaceSoft, surfaceContainer = Bubbles.SurfaceSoft,
    surfaceContainerHigh = Bubbles.TintPink, surfaceContainerHighest = Bubbles.TintGrape,
    outline = Bubbles.LineStrong, outlineVariant = Bubbles.Line,
    error = Bubbles.Urgent, errorContainer = Bubbles.TintUrgent, onError = Bubbles.White, onErrorContainer = Bubbles.Urgent,
)

private val Dark = darkColorScheme(
    primary = Bubbles.NightPink, onPrimary = Bubbles.Ink, primaryContainer = Color(0xFF4B1F37), onPrimaryContainer = Bubbles.TintPink,
    secondary = Color(0xFFB49BFF), onSecondary = Bubbles.Ink, secondaryContainer = Color(0xFF3A2B66), onSecondaryContainer = Bubbles.TintGrape,
    tertiary = Bubbles.Mint, onTertiary = Bubbles.Ink, tertiaryContainer = Color(0xFF0F4A3B), onTertiaryContainer = Bubbles.TintMint,
    background = Bubbles.NightGround, onBackground = Bubbles.NightInk,
    surface = Bubbles.NightSurface, onSurface = Bubbles.NightInk, surfaceVariant = Bubbles.NightRaised, onSurfaceVariant = Bubbles.NightInkSoft,
    surfaceContainerLowest = Bubbles.NightGround, surfaceContainerLow = Bubbles.NightSurface, surfaceContainer = Bubbles.NightSurface,
    surfaceContainerHigh = Bubbles.NightRaised, surfaceContainerHighest = Bubbles.NightLine,
    outline = Bubbles.NightLine, outlineVariant = Bubbles.NightLine,
    error = Color(0xFFFF8A95), errorContainer = Color(0xFF55202A), onError = Bubbles.Ink, onErrorContainer = Bubbles.TintUrgent,
)

/** Generous, soft shapes: this is what makes the app feel like bubbles and not like boxes. */
val BubblesShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp), small = RoundedCornerShape(16.dp), medium = RoundedCornerShape(22.dp),
    large = RoundedCornerShape(28.dp), extraLarge = RoundedCornerShape(36.dp),
)

/** Spacing scale in dp, used everywhere instead of ad-hoc numbers. */
object Space { val xs = 4.dp; val sm = 8.dp; val md = 12.dp; val lg = 16.dp; val xl = 24.dp; val xxl = 32.dp }

val LocalDark = staticCompositionLocalOf { false }

@Composable
fun BubblesTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    androidx.compose.runtime.CompositionLocalProvider(LocalDark provides dark) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, typography = BubblesTypography, shapes = BubblesShapes, content = content)
    }
}
