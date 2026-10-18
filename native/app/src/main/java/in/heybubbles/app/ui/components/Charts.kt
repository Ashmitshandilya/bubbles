package `in`.heybubbles.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * A soft line chart with a gradient fill, drawn on Canvas. [values] run oldest to newest; fewer than two points shows just the dot
 * (one reading is a fact, not a trend). It carries no numbers: the screen around it says what it shows.
 */
@Composable
fun Sparkline(values: List<Double>, color: Color, modifier: Modifier = Modifier, height: Dp = 56.dp, strokeWidth: Dp = 3.dp) {
    Canvas(modifier.fillMaxWidth().height(height)) {
        if (values.isEmpty()) return@Canvas
        val pad = strokeWidth.toPx() * 1.5f
        val w = size.width - pad * 2
        val h = size.height - pad * 2
        // A small wobble must look small: never stretch less than a quarter of the top value over the full height.
        val rawLo = values.min()
        val rawHi = values.max()
        val minSpan = maxOf(kotlin.math.abs(rawHi) * 0.25, 1e-6)
        val pad2 = if (rawHi - rawLo < minSpan) (minSpan - (rawHi - rawLo)) / 2 else 0.0
        val lo = rawLo - pad2
        val hi = rawHi + pad2
        val span = (hi - lo).takeIf { it > 1e-9 } ?: 1.0
        fun x(i: Int) = pad + if (values.size == 1) w / 2 else w * i / (values.size - 1)
        fun y(v: Double): Float = if (hi - lo < 1e-9) pad + h / 2 else pad + h - (h * ((v - lo) / span)).toFloat()
        val pts = values.mapIndexed { i, v -> Offset(x(i), y(v)) }
        if (pts.size >= 2) {
            val line = Path().apply {
                moveTo(pts[0].x, pts[0].y)
                for (i in 1 until pts.size) {
                    val a = pts[i - 1]; val b = pts[i]
                    val mid = (a.x + b.x) / 2
                    cubicTo(mid, a.y, mid, b.y, b.x, b.y)
                }
            }
            val fill = Path().apply {
                addPath(line); lineTo(pts.last().x, size.height); lineTo(pts.first().x, size.height); close()
            }
            drawPath(fill, Brush.verticalGradient(listOf(color.copy(alpha = 0.28f), Color.Transparent)))
            drawPath(line, color, style = Stroke(strokeWidth.toPx(), cap = StrokeCap.Round))
        }
        drawCircle(color, strokeWidth.toPx() * 1.6f, pts.last())
        drawCircle(Color.White, strokeWidth.toPx() * 0.7f, pts.last())
    }
}
