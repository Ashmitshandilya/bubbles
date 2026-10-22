package `in`.heybubbles.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.CycleDate
import `in`.heybubbles.app.data.CycleFlag
import `in`.heybubbles.app.data.CycleOverview
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

data class CycleState(val loading: Boolean = true, val data: CycleOverview? = null, val error: String? = null, val saving: Boolean = false)

class CycleViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(CycleState())
    val state: StateFlow<CycleState> = _state

    init { load() }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try { _state.update { it.copy(loading = false, data = api.cycleOverview(LocalDate.now())) } }
            catch (e: Exception) { _state.update { it.copy(loading = false, error = e.friendly()) } }
        }
    }

    fun periodStarted() {
        _state.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            try {
                api.logPeriodStart()
                _state.update { it.copy(saving = false, data = api.cycleOverview(LocalDate.now())) }
            } catch (e: Exception) {
                _state.update { it.copy(saving = false, error = e.friendly()) }
            }
        }
    }
}

private val shortDate = DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH)
private fun day(s: String?): String? = s?.let { runCatching { LocalDate.parse(it.take(10)).format(shortDate) }.getOrNull() }
private fun range(d: CycleDate?): String? {
    d ?: return null
    val main = day(d.date) ?: return null
    val lo = day(d.earliest); val hi = day(d.latest)
    return if (lo != null && hi != null && lo != hi) "$main (likely $lo–$hi)" else main
}

@Composable
fun CycleScreen(api: Api, onBack: () -> Unit) {
    val vm = viewModel<CycleViewModel>(key = "cycle${`in`.heybubbles.app.ui.LocalEpoch.current}") { CycleViewModel(api) }
    val s by vm.state.collectAsState()
    var confirm by remember { mutableStateOf(false) }
    BackHandler { onBack() }

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle("Cycle", s.data?.modeLabel?.ifBlank { null } ?: "Your cycle")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            s.error?.let {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, onClick = vm::load)
                }
            }
            if (s.loading && s.data == null) Text("Getting your cycle ready…", style = MaterialTheme.typography.bodyLarge)
            s.data?.let { d ->
                // Urgent first: a plain, calm card, never buried below predictions.
                d.urgent?.let { FlagCard(it, urgent = true) }

                BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintPink, shape = MaterialTheme.shapes.extraLarge) {
                    Column(Modifier.fillMaxWidth().padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        if (d.hasData && d.cycleDay != null) {
                            CycleRing(d.cycleDay, d.stats?.averageLength ?: 28, d.phase?.label.orEmpty(), Modifier.size(220.dp))
                            d.phase?.takeIf { it.summary.isNotBlank() }?.let {
                                Text(it.summary + if (it.estimated) " (an estimate)" else "", Modifier.padding(top = 14.dp), style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink, textAlign = TextAlign.Center)
                            }
                        } else {
                            Text("Not enough logged yet", style = MaterialTheme.typography.titleLarge, color = Bubbles.PinkDeep)
                            Text("Log when a period starts and Bubbles will start to show where you are in your cycle. Until then nothing is guessed.", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink, textAlign = TextAlign.Center)
                        }
                        Box(
                            Modifier.padding(top = 16.dp).fillMaxWidth().height(52.dp).background(BubbleGradient, androidx.compose.foundation.shape.RoundedCornerShape(26.dp))
                                .clickable(enabled = !s.saving, role = Role.Button, onClickLabel = "Log that your period started today") { confirm = true },
                            contentAlignment = Alignment.Center,
                        ) { Text(if (s.saving) "Saving…" else "My period started today", style = MaterialTheme.typography.titleMedium, color = Color.White) }
                    }
                }

                val next = range(d.nextPeriod)
                if (d.hasData && next != null) {
                    InfoCard("Next period", next, d.nextPeriod?.let { n ->
                        when {
                            n.status == "late" || (n.lateByDays ?: 0) > 0 -> "Running ${n.lateByDays ?: 0} days later than expected."
                            n.inDays != null -> if (n.inDays == 0) "Expected today." else "In about ${n.inDays} days."
                            else -> null
                        }
                    }, Bubbles.TintGrape, Bubbles.GrapeDeep)
                }
                d.fertileWindow?.takeIf { d.hasData && day(it.start) != null && day(it.end) != null }?.let {
                    InfoCard("Fertile window (estimate)", "${day(it.start)} – ${day(it.end)}", if (it.activeToday) "Today falls in this window." else null, Bubbles.TintMint, Bubbles.MintDeep)
                }
                d.pms?.text?.takeIf { it.isNotBlank() }?.let { InfoCard("Before your period", null, it, Bubbles.TintPeach, Bubbles.PeachDeep) }
                d.stats?.takeIf { it.cyclesUsed > 0 }?.let { st ->
                    InfoCard("Your pattern", listOfNotNull(st.averageLength?.let { "About $it days" }, st.regularity?.label).joinToString(" · ").ifBlank { null }, "Based on your last ${st.cyclesUsed} cycles.", MaterialTheme.colorScheme.surface, MaterialTheme.colorScheme.onSurface)
                }
                d.confidenceNote?.takeIf { it.isNotBlank() }?.let { Text(it, Modifier.padding(horizontal = 4.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                d.flags.filter { it.id != d.urgent?.id }.forEach { FlagCard(it, urgent = false) }
                d.notices.forEach { Text(it, Modifier.padding(horizontal = 4.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }

    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text("Log your period?") },
            text = { Text("This saves that your period started today. You can remove it from the Track tab history.") },
            confirmButton = { TextButton({ confirm = false; vm.periodStarted() }) { Text("Yes, log it") } },
            dismissButton = { TextButton({ confirm = false }) { Text("Not now") } },
        )
    }
}

@Composable
private fun InfoCard(title: String, big: String?, note: String?, tint: Color, ink: Color) {
    BubbleCard(Modifier.fillMaxWidth(), tint = tint) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Eyebrow(title, color = ink)
            if (big != null) Text(big, style = MaterialTheme.typography.titleLarge, color = ink)
            if (note != null) Text(note, style = MaterialTheme.typography.bodyMedium, color = ink)
        }
    }
}

@Composable
private fun FlagCard(f: CycleFlag, urgent: Boolean) {
    BubbleCard(Modifier.fillMaxWidth(), tint = if (urgent) Bubbles.TintUrgent else Bubbles.TintSun) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Eyebrow(if (urgent) "Please don't wait" else "Worth mentioning to a clinician", color = if (urgent) Bubbles.Urgent else Bubbles.SunDeep)
            Text(f.title, style = MaterialTheme.typography.titleMedium, color = Bubbles.Ink)
            Text(f.message, style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink)
        }
    }
}

/**
 * The cycle as a ring: four phases drawn in proportion to the person's average length, solid up to today. The split is an
 * illustration of an estimate (menstrual about 5 days, ovulation about 14 days before the next period), so the description says so.
 */
@Composable
fun CycleRing(day: Int, average: Int, phaseLabel: String, modifier: Modifier = Modifier) {
    val len = average.coerceIn(21, 45)
    val ov = (len - 14).coerceAtLeast(7)
    // phase day ranges, 1-based inclusive: menstrual, follicular, ovulatory, luteal
    val segs = listOf(
        Triple(1, 5, Bubbles.Pink), Triple(6, ov - 2, Bubbles.Mint), Triple(ov - 1, ov + 1, Bubbles.Sun), Triple(ov + 2, len, Bubbles.Grape),
    )
    val shown = day.coerceIn(1, len)
    Box(modifier.semantics { contentDescription = "Cycle day $day of about $len. $phaseLabel, an estimate." }, contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxWidth().height(220.dp)) {
            val stroke = 22.dp.toPx()
            val inset = stroke / 2 + 4.dp.toPx()
            val dia = size.minDimension - inset * 2
            val topLeft = Offset((size.width - dia) / 2, (size.height - dia) / 2)
            val arcSize = Size(dia, dia)
            val gap = 3f
            fun angle(d: Float) = -90f + d / len * 360f
            for ((a, b, c) in segs) {
                val start = angle((a - 1).toFloat()) + gap / 2
                val sweep = (b - a + 1).toFloat() / len * 360f - gap
                drawArc(c.copy(alpha = 0.28f), start, sweep, false, topLeft, arcSize, style = Stroke(stroke, cap = StrokeCap.Round))
                if (shown >= a) {
                    val done = (minOf(shown, b) - a + 1).toFloat() / len * 360f - gap
                    drawArc(c, start, done.coerceAtLeast(1f), false, topLeft, arcSize, style = Stroke(stroke, cap = StrokeCap.Round))
                }
            }
            // today's marker
            val a = Math.toRadians(angle(shown - 0.5f).toDouble())
            val r = dia / 2
            val p = Offset(topLeft.x + r + (r * Math.cos(a)).toFloat(), topLeft.y + r + (r * Math.sin(a)).toFloat())
            drawCircle(Color.White, stroke * 0.62f, p)
            drawCircle(Bubbles.PinkDeep, stroke * 0.3f, p)
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Day", style = MaterialTheme.typography.labelMedium, color = Bubbles.InkSoft)
            Text("$day", style = MaterialTheme.typography.displayMedium, color = Bubbles.PinkDeep)
            if (phaseLabel.isNotBlank()) Text(phaseLabel, style = MaterialTheme.typography.labelLarge, color = Bubbles.Ink)
        }
    }
}
