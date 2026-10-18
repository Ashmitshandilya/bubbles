package `in`.heybubbles.app.ui.screens

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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Purpose
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles

data class ChoicesState(
    val loading: Boolean = true,
    val purposes: List<Purpose> = emptyList(),
    val error: String? = null,
    val busy: Set<String> = emptySet(),
    val deleting: Boolean = false,
    val deleted: Boolean = false,
)

class ChoicesViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(ChoicesState())
    val state: StateFlow<ChoicesState> = _state

    init { load() }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try { _state.update { it.copy(loading = false, purposes = api.consents()) } }
            catch (e: Exception) { _state.update { it.copy(loading = false, error = e.friendly()) } }
        }
    }

    /** Applies the change only after the server accepted it, so the switch always shows what is really on record. */
    fun set(p: Purpose, granted: Boolean) {
        if (p.id in _state.value.busy) return
        _state.update { it.copy(busy = it.busy + p.id, error = null) }
        viewModelScope.launch {
            try {
                api.setConsent(p.id, granted, p.textHash)
                _state.update { s -> s.copy(busy = s.busy - p.id, purposes = s.purposes.map { if (it.id == p.id) it.copy(granted = granted) else it }) }
            } catch (e: Exception) {
                _state.update { it.copy(busy = it.busy - p.id, error = e.friendly()) }
            }
        }
    }

    fun deleteData() {
        _state.update { it.copy(deleting = true, error = null) }
        viewModelScope.launch {
            try {
                api.deleteMyData()
                _state.update { it.copy(deleting = false, deleted = true) }
                load()   // every choice is switched off by the server: show the truth
            } catch (e: Exception) {
                _state.update { it.copy(deleting = false, error = e.friendly()) }
            }
        }
    }
}

@Composable
fun ChoicesScreen(api: Api, onBack: () -> Unit) {
    val vm = viewModel<ChoicesViewModel>(key = "choices${`in`.heybubbles.app.ui.LocalEpoch.current}") { ChoicesViewModel(api) }
    val s by vm.state.collectAsState()
    var confirmDelete by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { vm.load() }

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle("Me", "Your choices")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "Nothing here is on until you say so. You can change any of it at any time, and Bubbles keeps working with everything off.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            s.error?.let {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    if (s.purposes.isEmpty()) Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, onClick = vm::load)
                }
            }
            if (s.loading && s.purposes.isEmpty()) Text("Loading your choices…", style = MaterialTheme.typography.bodyLarge)
            s.purposes.filter { it.available }.forEach { p -> PurposeCard(p, p.id in s.busy) { vm.set(p, it) } }

            if (s.purposes.isNotEmpty() || !s.loading) {
                Eyebrow("Your data", Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintUrgent) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Delete my data", style = MaterialTheme.typography.titleMedium, color = Bubbles.Urgent)
                        Text(
                            "Removes your Fitness, Cycle and plan data and any Community posts, and switches every choice off. " +
                                "Your tracker entries (sleep, weight and so on) stay until you delete them in Track. This can't be undone.",
                            style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink,
                        )
                        if (s.deleted) Text("Done. Your data has been deleted.", style = MaterialTheme.typography.labelLarge, color = Bubbles.MintDeep)
                        Pill(if (s.deleting) "Deleting…" else "Delete my data…", Bubbles.Urgent, Bubbles.White, Modifier.padding(top = 6.dp)) { if (!s.deleting) confirmDelete = true }
                    }
                }
            }
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete your data?") },
            text = { Text("This removes your Fitness, Cycle, plan and Community data and can't be undone.") },
            confirmButton = { TextButton({ confirmDelete = false; vm.deleteData() }) { Text("Delete", color = Bubbles.Urgent) } },
            dismissButton = { TextButton({ confirmDelete = false }) { Text("Keep my data") } },
        )
    }
}

@Composable
private fun PurposeCard(p: Purpose, busy: Boolean, onChange: (Boolean) -> Unit) {
    BubbleCard(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(p.title, style = MaterialTheme.typography.titleMedium)
                Text(p.description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(
                checked = p.granted, onCheckedChange = { if (!busy) onChange(it) },
                modifier = Modifier.semantics { contentDescription = p.title; stateDescription = if (p.granted) "On" else "Off" },
                colors = SwitchDefaults.colors(checkedTrackColor = MaterialTheme.colorScheme.primary),
            )
        }
    }
}
