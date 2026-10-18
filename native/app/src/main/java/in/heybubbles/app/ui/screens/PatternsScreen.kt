package `in`.heybubbles.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Association
import `in`.heybubbles.app.data.WeeklyItem
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Dot
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles

data class PatternsState(
    val loading: Boolean = true,
    val links: List<Association> = emptyList(),
    val week: List<WeeklyItem> = emptyList(),
    val gaps: List<String> = emptyList(),
    val notices: List<String> = emptyList(),
    val error: String? = null,
)

class PatternsViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(PatternsState())
    val state: StateFlow<PatternsState> = _state

    init { load() }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            val assoc = async { runCatching { api.associations() } }
            val week = async { runCatching { api.weekly() } }
            val a = assoc.await()
            val w = week.await()
            if (a.isFailure && w.isFailure) {
                _state.update { it.copy(loading = false, error = (a.exceptionOrNull() ?: w.exceptionOrNull())!!.friendly()) }
                return@launch
            }
            _state.update {
                PatternsState(
                    loading = false,
                    links = a.getOrNull()?.insights.orEmpty(),
                    week = w.getOrNull().orEmpty().take(6),
                    gaps = a.getOrNull()?.gaps.orEmpty().mapNotNull { g -> g.readable() }.distinct(),
                    notices = a.getOrNull()?.notices.orEmpty().mapNotNull { n -> n.readable() }.distinct(),
                )
            }
        }
    }
}

@Composable
fun PatternsScreen(api: Api, onBack: () -> Unit) {
    val vm = viewModel<PatternsViewModel>(key = "patterns${`in`.heybubbles.app.ui.LocalEpoch.current}") { PatternsViewModel(api) }
    val s by vm.state.collectAsState()
    BackHandler { onBack() }

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle("Patterns", "What your logs say")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            s.error?.let {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, onClick = vm::load)
                }
            }
            if (s.loading) Text("Looking through your logs…", style = MaterialTheme.typography.bodyLarge)
            if (s.links.isNotEmpty()) {
                Eyebrow("Links between your logs", color = Bubbles.GrapeDeep)
                s.links.forEach { p ->
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
            }
            if (s.week.isNotEmpty()) {
                Eyebrow("This week", Modifier.padding(top = 6.dp), color = Bubbles.PinkDeep)
                s.week.forEach { w ->
                    BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintPink) {
                        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(w.title, style = MaterialTheme.typography.titleMedium, color = Bubbles.PinkDeep)
                            Text(w.description, style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink)
                            if (w.confidenceLabel.isNotBlank()) Text("Confidence: ${w.confidenceLabel}", style = MaterialTheme.typography.labelSmall, color = Bubbles.InkSoft)
                        }
                    }
                }
            }
            // Missing data is a gap, never "healthy": say what Bubbles still can't compare.
            if (s.gaps.isNotEmpty()) {
                BubbleCard(Modifier.fillMaxWidth(), tint = MaterialTheme.colorScheme.surfaceVariant) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Eyebrow("Not enough yet", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        s.gaps.forEach { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
            }
            if (!s.loading && s.error == null && s.links.isEmpty() && s.week.isEmpty() && s.gaps.isEmpty()) {
                Text(
                    "Nothing to compare yet. Log for a couple of weeks and links between your sleep, mood and more will show up here.",
                    style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            s.notices.forEach { Text(it, Modifier.padding(horizontal = 4.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}
