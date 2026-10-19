package `in`.heybubbles.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Association
import `in`.heybubbles.app.data.DailyCompanion
import `in`.heybubbles.app.data.Entry
import `in`.heybubbles.app.data.Repo
import `in`.heybubbles.app.data.TrackerSpec
import `in`.heybubbles.app.data.Trackers
import `in`.heybubbles.app.data.dayLabel
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Dot
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.components.Skeleton
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.LocalDate
import java.util.Calendar

data class TodayState(
    val loading: Boolean = true,
    val daily: DailyCompanion? = null,
    val patterns: List<Association> = emptyList(),
    val gaps: List<String> = emptyList(),
    val error: String? = null,
)

class TodayViewModel(private val api: Api, val repo: Repo) : ViewModel() {
    private val _state = MutableStateFlow(TodayState())
    val state: StateFlow<TodayState> = _state

    init {
        load()
        viewModelScope.launch { if (repo.entries.value.isEmpty()) repo.loadAll() }
    }

    /** Pull to refresh: today's check-in, the patterns and every tracker. */
    fun refresh() {
        load()
        viewModelScope.launch { repo.loadAll() }
    }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val daily = api.daily().companion
                // Patterns are a bonus: if they fail, Today still works.
                val assoc = runCatching { api.associations() }.getOrNull()
                _state.update {
                    TodayState(
                        loading = false, daily = daily,
                        patterns = assoc?.insights.orEmpty().take(3),
                        gaps = (assoc?.gaps.orEmpty() + daily.dataGaps).mapNotNull { g -> g.readable() }.distinct().take(4),
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.friendly()) }
            }
        }
    }
}

/** Server text for one item can be a plain string or a small object; show the first readable field. */
internal fun JsonElement.readable(): String? = when (this) {
    is JsonPrimitive -> content.takeIf { it.isNotBlank() }
    is JsonObject -> listOf("title", "label", "text", "message", "summary", "reason", "name").firstNotNullOfOrNull { k -> (this[k] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() } }
    else -> null
}

private fun greeting(): String = when (Calendar.getInstance().get(Calendar.HOUR_OF_DAY)) {
    in 5..11 -> "Good morning"
    in 12..16 -> "Good afternoon"
    in 17..21 -> "Good evening"
    else -> "Hello"
}

private class Tile(val spec: TrackerSpec, val big: String?, val unit: String, val caption: String)

/** Today's three facts. A missing one says "Not logged", never a made-up zero or a "normal". */
private fun tiles(entries: Map<String, List<Entry>>): List<Tile> {
    val today = LocalDate.now()
    fun spec(slug: String) = Trackers.bySlug(slug)
    val sleep = entries["sleep"].orEmpty().firstOrNull { (it.number("duration") ?: 0.0) > 0 }
    val water = entries["hydration"].orEmpty().filter { it.day == today }.mapNotNull { it.number("volume") }
    val mood = entries["mood"].orEmpty().firstOrNull { it.number("mood") != null }
    return listOf(
        Tile(spec("sleep"), sleep?.number("duration")?.let { fmtNum(it) }, "h", sleep?.let { if (it.day == today || it.day == today.minusDays(1)) "last night" else it.dayLabel() } ?: "Not logged"),
        Tile(spec("hydration"), if (water.isEmpty()) null else fmtNum(water.sum()), "ml", if (water.isEmpty()) "Not logged today" else "today"),
        Tile(spec("mood"), mood?.number("mood")?.let { fmtNum(it) }, "/10", mood?.dayLabel() ?: "Not logged"),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TodayScreen(api: Api, repo: Repo, onTalk: () -> Unit, onOpenTracker: (String) -> Unit, onOpenSection: (String) -> Unit) {
    val vm = viewModel<TodayViewModel>(key = "today${`in`.heybubbles.app.ui.LocalEpoch.current}") { TodayViewModel(api, repo) }
    val s by vm.state.collectAsState()
    val entries by repo.entries.collectAsState()
    val sections by repo.sections.collectAsState()
    val communityOpen by repo.communityOpen.collectAsState()
    val bodyMapOpen by repo.bodyMapOpen.collectAsState()

    val refreshing by repo.loading.collectAsState()
    PullToRefreshBox(isRefreshing = refreshing && entries.isNotEmpty(), onRefresh = { vm.refresh() }) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
        ScreenTitle("Today", greeting())

        BubbleCard(Modifier.fillMaxWidth().padding(horizontal = 20.dp), tint = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.extraLarge) {
            Column(Modifier.padding(22.dp)) {
                Eyebrow("Your check-in")
                when {
                    s.loading -> Text("Getting your day ready…", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                    s.error != null -> {
                        Text(s.error!!, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.error)
                        Pill("Try again", MaterialTheme.colorScheme.surface, MaterialTheme.colorScheme.primary, Modifier.padding(top = 12.dp)) { vm.load() }
                    }
                    else -> {
                        Text(s.daily?.headline.orEmpty().ifBlank { "Your Bubbles daily check-in" }, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                        Pill("Tell Bubbles how you are", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, Modifier.padding(top = 16.dp), onClick = onTalk)
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        Row(Modifier.padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (entries.isEmpty() && refreshing) repeat(3) { Skeleton(Modifier.weight(1f).height(96.dp)) } else tiles(entries).forEach { t ->
                BubbleCard(
                    Modifier.weight(1f).semantics { contentDescription = "${t.spec.title}: ${t.big?.let { it + " " + t.unit + ", " } ?: ""}${t.caption}. Opens details." },
                    tint = if (t.big != null) t.spec.tint else MaterialTheme.colorScheme.surface, onClick = { onOpenTracker(t.spec.slug) },
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Eyebrow(t.spec.title, color = if (t.big != null) t.spec.ink else MaterialTheme.colorScheme.onSurfaceVariant)
                        if (t.big != null) {
                            Row(verticalAlignment = Alignment.Bottom, modifier = Modifier.padding(top = 4.dp)) {
                                Text(t.big, style = MaterialTheme.typography.headlineSmall, color = t.spec.ink)
                                Text(t.unit, Modifier.padding(start = 3.dp, bottom = 3.dp), style = MaterialTheme.typography.labelMedium, color = t.spec.ink)
                            }
                        } else {
                            Text("—", Modifier.padding(top = 4.dp), style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(t.caption, style = MaterialTheme.typography.labelSmall, color = if (t.big != null) t.spec.ink else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }

        Spacer(Modifier.height(18.dp))
        Eyebrow("Quick log", Modifier.padding(horizontal = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        LazyRow(Modifier.padding(top = 8.dp), contentPadding = PaddingValues(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(Trackers.all, key = { it.slug }) { spec -> Pill(spec.title, spec.tint, spec.ink) { onOpenTracker(spec.slug) } }
        }

        // Explore: the server decides which sections this person sees (Cycle is hidden for some profiles). Until it answers, Cycle stays hidden.
        Spacer(Modifier.height(20.dp))
        Eyebrow("Explore", Modifier.padding(horizontal = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        val explore = buildList {
            if (sections?.contains("cycle") == true) add(Triple("cycle", "Cycle" to "Where you are in it", Bubbles.TintPink to Bubbles.PinkDeep))
            add(Triple("patterns", "Patterns" to "What your logs say", Bubbles.TintGrape to Bubbles.GrapeDeep))
            if (sections?.contains("care") == true) add(Triple("care", "Care" to "Get ready for a visit", Bubbles.TintMint to Bubbles.MintDeep))
            if (sections?.contains("fitness") == true) add(Triple("fitness", "Fitness" to "Food, meals, workouts", Bubbles.TintSky to Bubbles.SkyDeep))
            if (bodyMapOpen) add(Triple("body", "Body map" to "See it in 3D", Bubbles.TintGrape to Bubbles.GrapeDeep))
            if (communityOpen) add(Triple("community", "Community" to "Ask or share, kindly", Bubbles.TintSun to Bubbles.SunDeep))
        }
        Column(Modifier.padding(horizontal = 20.dp).padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            explore.chunked(2).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    row.forEach { (id, text, colors) -> ExploreCard(text.first, text.second, colors.first, colors.second, Modifier.weight(1f)) { onOpenSection(id) } }
                    if (row.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }

        if (s.patterns.isNotEmpty()) {
            Spacer(Modifier.height(20.dp))
            Eyebrow("Patterns in your logs", Modifier.padding(horizontal = 24.dp), color = MaterialTheme.colorScheme.secondary)
            Column(Modifier.padding(horizontal = 20.dp).padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                s.patterns.forEach { p -> PatternCard(p) }
            }
        }

        // Missing data is a gap, never "healthy": say what Bubbles doesn't know yet.
        if (s.gaps.isNotEmpty()) {
            Spacer(Modifier.height(16.dp))
            BubbleCard(Modifier.fillMaxWidth().padding(horizontal = 20.dp), tint = MaterialTheme.colorScheme.surfaceVariant) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Eyebrow("Not enough yet", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    s.gaps.forEach { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        }

        s.daily?.takeIf { it.safetyNote.isNotBlank() || it.disclaimer.isNotBlank() }?.let {
            Text(
                listOf(it.safetyNote, it.disclaimer).filter { t -> t.isNotBlank() }.joinToString(" "),
                Modifier.padding(horizontal = 24.dp, vertical = 16.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }    }
}

@Composable
private fun PatternCard(p: Association) {
    BubbleCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Dot(Bubbles.Grape, 8.dp, Modifier.padding(end = 8.dp))
                if (p.strength.isNotBlank()) Pill(p.strength.replaceFirstChar { it.uppercase() } + " link", Bubbles.TintGrape, Bubbles.GrapeDeep)
            }
            Text(p.text, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun ExploreCard(title: String, subtitle: String, tint: androidx.compose.ui.graphics.Color, ink: androidx.compose.ui.graphics.Color, modifier: Modifier, onClick: () -> Unit) {
    BubbleCard(modifier, tint = tint, onClick = onClick) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = ink)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = ink)
        }
    }
}
