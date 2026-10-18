package `in`.heybubbles.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import `in`.heybubbles.app.data.DailyCompanion
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Dot
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles
import java.util.Calendar

data class TodayState(val loading: Boolean = true, val daily: DailyCompanion? = null, val error: String? = null)

class TodayViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(TodayState())
    val state: StateFlow<TodayState> = _state

    init { load() }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                _state.update { TodayState(loading = false, daily = api.daily().companion) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.friendly()) }
            }
        }
    }
}

/** Server text for one focus item can be a plain string or a small object; show the first readable field. */
private fun JsonElement.readable(): String? = when (this) {
    is JsonPrimitive -> content.takeIf { it.isNotBlank() }
    is JsonObject -> listOf("title", "label", "text", "message", "summary", "name").firstNotNullOfOrNull { k -> (this[k] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() } }
    else -> null
}

private fun greeting(): String = when (Calendar.getInstance().get(Calendar.HOUR_OF_DAY)) {
    in 5..11 -> "Good morning"
    in 12..16 -> "Good afternoon"
    in 17..21 -> "Good evening"
    else -> "Hello"
}

@Composable
fun TodayScreen(api: Api, onTalk: () -> Unit) {
    val vm = viewModel<TodayViewModel> { TodayViewModel(api) }
    val s by vm.state.collectAsState()
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
        ScreenTitle("Today", greeting())
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            BubbleCard(Modifier.fillMaxWidth(), tint = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.extraLarge) {
                Column(Modifier.padding(22.dp)) {
                    Eyebrow("Your check-in")
                    when {
                        s.loading -> Text("Getting your day ready…", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.titleLarge)
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
            val focus = s.daily?.focus?.mapNotNull { it.readable() }.orEmpty()
            if (focus.isNotEmpty()) {
                BubbleCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Eyebrow("Worth a look today", color = Bubbles.GrapeDeep)
                        focus.take(4).forEach {
                            Row(verticalAlignment = Alignment.Top) {
                                Dot(Bubbles.Grape, 8.dp, Modifier.padding(top = 8.dp, end = 12.dp))
                                Text(it, style = MaterialTheme.typography.bodyLarge)
                            }
                        }
                    }
                }
            }
            // Missing data is a gap, never "healthy": say what Bubbles doesn't know yet.
            val gaps = s.daily?.dataGaps?.mapNotNull { it.readable() }.orEmpty()
            if (gaps.isNotEmpty()) {
                BubbleCard(Modifier.fillMaxWidth(), tint = MaterialTheme.colorScheme.surfaceVariant) {
                    Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Eyebrow("Not logged yet", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        gaps.take(4).forEach { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
            }
            s.daily?.takeIf { it.safetyNote.isNotBlank() || it.disclaimer.isNotBlank() }?.let {
                Text(
                    listOf(it.safetyNote, it.disclaimer).filter { t -> t.isNotBlank() }.joinToString(" "),
                    Modifier.padding(horizontal = 4.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
