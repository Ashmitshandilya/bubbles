package `in`.heybubbles.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles

data class TourStep(val title: String, val body: String)

/** The same five stops as the website tour, worded for the app's own layout. Kept pure so a test can hold it to the rules. */
val TOUR_STEPS = listOf(
    TourStep("Ask anything", "Type a question on Today, or open Talk to chat. Bubbles keeps it short and kind."),
    TourStep("Log in a tap", "Water, mood, sleep and more. One tap each in Track, no typing needed."),
    TourStep("Your week", "The tiles on Today show how the last seven days went. Tap one to see more."),
    TourStep("Care and cycle", "Open Care to prepare for a doctor visit. Cycle and Patterns are under Today."),
    TourStep("You, and your choices", "Me holds your reminders and privacy choices. You can replay this tour there."),
)

/** Next moves forward; Next on the last stop finishes. Returns null when the tour is over. */
fun nextTourIndex(index: Int, total: Int): Int? = if (index + 1 >= total) null else index + 1

fun tourPosition(index: Int, total: Int) = "${index + 1} of $total"

/** A full-screen walk-through over the app. [onDone] gets true when the person skipped, false when they reached the end. */
@Composable
fun TourOverlay(onDone: (skipped: Boolean) -> Unit) {
    var index by remember { mutableIntStateOf(0) }
    val step = TOUR_STEPS[index]
    BackHandler { onDone(true) }
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.55f)).clickable(enabled = false) {}, contentAlignment = Alignment.BottomCenter) {
        BubbleCard(Modifier.fillMaxWidth().navigationBarsPadding().padding(20.dp)) {
            Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Eyebrow(tourPosition(index, TOUR_STEPS.size))
                Column(Modifier.semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(step.title, style = MaterialTheme.typography.headlineSmall)
                    Text(step.body, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Row(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    TOUR_STEPS.indices.forEach { i ->
                        Box(
                            Modifier.size(if (i == index) 10.dp else 8.dp)
                                .background(if (i == index) Bubbles.Pink else MaterialTheme.colorScheme.outlineVariant, CircleShape)
                                .semantics { contentDescription = "" },
                        )
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    Pill("Skip", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant) { onDone(true) }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (index > 0) Pill("Back", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { index-- }
                        val last = nextTourIndex(index, TOUR_STEPS.size) == null
                        Pill(if (last) "Done" else "Next", Bubbles.Pink, Bubbles.White) {
                            val n = nextTourIndex(index, TOUR_STEPS.size)
                            if (n == null) onDone(false) else index = n
                        }
                    }
                }
            }
        }
    }
}
