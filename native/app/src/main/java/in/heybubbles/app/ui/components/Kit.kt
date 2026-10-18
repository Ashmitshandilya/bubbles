package `in`.heybubbles.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import `in`.heybubbles.app.ui.theme.Bubbles
import `in`.heybubbles.app.ui.theme.LocalDark
import `in`.heybubbles.app.ui.theme.Space

/** The app's ground: the blush colour with two soft colour glows, so screens have depth without any image. */
@Composable
fun BubblesBackground(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    val dark = LocalDark.current
    val base = MaterialTheme.colorScheme.background
    val glowA = if (dark) Bubbles.Grape.copy(alpha = 0.22f) else Bubbles.Pink.copy(alpha = 0.16f)
    val glowB = if (dark) Bubbles.Pink.copy(alpha = 0.14f) else Bubbles.Grape.copy(alpha = 0.10f)
    Box(modifier.fillMaxSize().background(base)) {
        Canvas(Modifier.fillMaxSize()) {
            drawCircle(Brush.radialGradient(listOf(glowA, Color.Transparent), center = Offset(size.width * 0.95f, 0f), radius = size.width * 0.85f), radius = size.width * 0.85f, center = Offset(size.width * 0.95f, 0f))
            drawCircle(Brush.radialGradient(listOf(glowB, Color.Transparent), center = Offset(0f, size.height * 0.7f), radius = size.width * 0.9f), radius = size.width * 0.9f, center = Offset(0f, size.height * 0.7f))
        }
        content()
    }
}

/** A calm card: big radius, hairline border, a soft tinted shadow. Pass [tint] for a coloured card; one accent per card. */
@Composable
fun BubbleCard(
    modifier: Modifier = Modifier,
    tint: Color? = null,
    shape: Shape = MaterialTheme.shapes.large,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val dark = LocalDark.current
    val fill = tint ?: MaterialTheme.colorScheme.surface
    val border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    val shadow = Modifier.shadow(if (dark) 0.dp else 6.dp, shape, ambientColor = Bubbles.Pink.copy(alpha = 0.25f), spotColor = Bubbles.Grape.copy(alpha = 0.25f))
    val base = modifier.then(shadow)
    if (onClick != null) {
        Surface(onClick = onClick, modifier = base, shape = shape, color = fill, border = border) { content() }
    } else {
        Surface(modifier = base, shape = shape, color = fill, border = border) { content() }
    }
}

/** A pill with the gradient used for the primary action and the person's own chat bubbles. */
val BubbleGradient: Brush = Brush.linearGradient(listOf(Bubbles.PinkInk, Bubbles.Pink))
val GrapeGradient: Brush = Brush.linearGradient(listOf(Bubbles.GrapeDeep, Bubbles.Grape))

@Composable
fun Eyebrow(text: String, modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.primary) {
    Text(text.uppercase(), modifier, style = MaterialTheme.typography.labelSmall, color = color, letterSpacing = androidx.compose.ui.unit.TextUnit(1.2f, androidx.compose.ui.unit.TextUnitType.Sp))
}

@Composable
fun Dot(color: Color, size: Dp = 10.dp, modifier: Modifier = Modifier) {
    Box(modifier.size(size).background(color, CircleShape))
}

/** Section heading used on every screen: small coloured eyebrow over a Fredoka title. */
@Composable
fun ScreenTitle(eyebrow: String, title: String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(horizontal = Space.xl, vertical = Space.lg)) {
        Eyebrow(eyebrow)
        Text(title, style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onBackground)
    }
}

@Composable
fun Pill(text: String, tint: Color, ink: Color, modifier: Modifier = Modifier, onClick: (() -> Unit)? = null) {
    val m = modifier.then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier)
    Box(m.background(tint, RoundedCornerShape(50)).padding(horizontal = 14.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
        Text(text, style = MaterialTheme.typography.labelMedium, color = ink)
    }
}
