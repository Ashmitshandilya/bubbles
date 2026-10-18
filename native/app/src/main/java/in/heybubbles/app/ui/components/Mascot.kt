package `in`.heybubbles.app.ui.components

import android.provider.Settings
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.scale
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import `in`.heybubbles.app.R

/**
 * Bubbles, the brand character, as drawn in the approved design (docs/brand). It is the app icon's artwork, so every place
 * that shows her shows the same unicorn. She breathes gently unless the phone has animations turned off. Never shown in urgent
 * safety states: the caller decides.
 */
@Composable
fun Mascot(size: Dp, modifier: Modifier = Modifier, title: String? = null, animated: Boolean = true) {
    val context = LocalContext.current
    val motionOk = remember { Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) > 0f }
    val breathe = if (animated && motionOk) {
        val t = rememberInfiniteTransition(label = "breathe")
        val s by t.animateFloat(1f, 1.045f, infiniteRepeatable(tween(2600), RepeatMode.Reverse), label = "scale")
        s
    } else 1f
    // The icon artwork has a safe-zone margin around the head; scale it up so she fills the box.
    Box(
        modifier.size(size).clipToBounds().then(if (title != null) Modifier.semantics { contentDescription = title } else Modifier),
    ) {
        Image(painterResource(R.drawable.mascot), contentDescription = null, modifier = Modifier.size(size).scale(1.45f * breathe), contentScale = ContentScale.Fit)
    }
}
