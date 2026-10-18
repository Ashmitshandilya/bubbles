package `in`.heybubbles.app.ui.screens

import android.Manifest
import android.content.Context
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.ReminderSettings
import `in`.heybubbles.app.data.Session
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.push.Push
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle

data class RemindersState(
    val loading: Boolean = true,
    val settings: ReminderSettings? = null,
    val busy: Boolean = false,
    val message: String? = null,
    val error: String? = null,
)

class RemindersViewModel(private val api: Api, private val session: Session, private val app: Context) : ViewModel() {
    private val _state = MutableStateFlow(RemindersState())
    val state: StateFlow<RemindersState> = _state

    init { load() }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try { _state.update { it.copy(loading = false, settings = api.notificationSettings()) } }
            catch (e: Exception) { _state.update { it.copy(loading = false, error = e.friendly()) } }
        }
    }

    private suspend fun refresh() { _state.update { it.copy(settings = api.notificationSettings()) } }

    /** Turn phone reminders on: save the yes, then connect this phone. If the phone can't connect, the yes is withdrawn again. */
    fun enable() {
        if (!Push.configured(app)) {
            _state.update { it.copy(message = "Phone reminders aren't available in this version of the app.") }
            return
        }
        _state.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            try {
                api.saveReminderSettings(push = true)
                if (Push.connect(app, api, session)) {
                    refresh()
                    _state.update { it.copy(busy = false, message = "Reminders are on for this phone.") }
                } else {
                    api.saveReminderSettings(push = false)
                    refresh()
                    _state.update { it.copy(busy = false, message = "Couldn't connect this phone. Check your connection and try again.") }
                }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, error = e.friendly()) }
            }
        }
    }

    fun denied() { _state.update { it.copy(message = "Notifications are off for Bubbles on this phone. Turn them on in your phone's settings, then try again.") } }

    fun disable() {
        _state.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            try {
                api.saveReminderSettings(push = false)
                Push.disconnect(app, api, session)
                refresh()
                _state.update { it.copy(busy = false, message = "Reminders are off for this phone.") }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, error = e.friendly()) }
            }
        }
    }

    fun setType(key: String, on: Boolean) {
        viewModelScope.launch {
            try { api.saveReminderSettings(types = mapOf(key to on)); refresh() }
            catch (e: Exception) { _state.update { it.copy(error = e.friendly()) } }
        }
    }

    fun test() {
        _state.update { it.copy(busy = true, message = null, error = null) }
        viewModelScope.launch {
            try { val m = api.pushTest(); _state.update { it.copy(busy = false, message = m) } }
            catch (e: Exception) { _state.update { it.copy(busy = false, error = e.friendly()) } }
        }
    }
}

@Composable
fun RemindersScreen(api: Api, session: Session, onBack: () -> Unit) {
    val context = LocalContext.current
    val vm = viewModel<RemindersViewModel>(key = "reminders${`in`.heybubbles.app.ui.LocalEpoch.current}") { RemindersViewModel(api, session, context.applicationContext) }
    val s by vm.state.collectAsState()
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) vm.enable() else vm.denied() }

    fun turnOn() {
        // Android 13+ asks only now, from a tap on the switch, never at start-up.
        val needs = Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
        if (needs) ask.launch(Manifest.permission.POST_NOTIFICATIONS) else vm.enable()
    }

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle("Me", "Reminders")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "Plain nudges for water, medicines and winding down. They never include health details, and they stay quiet at night.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            s.error?.let {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    if (s.settings == null) Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, onClick = vm::load)
                }
            }
            s.message?.let { Text(it, Modifier.semantics { contentDescription = it }, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary) }
            if (s.loading && s.settings == null) Text("Loading…", style = MaterialTheme.typography.bodyLarge)
            s.settings?.let { st ->
                BubbleCard(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("Reminders on this phone", style = MaterialTheme.typography.titleMedium)
                            Text(
                                if (!st.pushAvailable) "Phone notifications aren't set up on the server yet." else "Gentle reminders that show on your lock screen without details.",
                                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Switch(
                            checked = st.push, onCheckedChange = { if (!s.busy) { if (it) turnOn() else vm.disable() } },
                            enabled = st.pushAvailable || st.push,
                            modifier = Modifier.semantics { contentDescription = "Reminders on this phone"; stateDescription = if (st.push) "On" else "Off" },
                        )
                    }
                }
                if (st.push) {
                    Eyebrow("Which reminders", Modifier.padding(top = 6.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    TypeRow("Drink some water", st.water) { vm.setType("water", it) }
                    TypeRow("Take your medicines", st.med) { vm.setType("med", it) }
                    TypeRow("Wind down for sleep", st.winddown) { vm.setType("winddown", it) }
                    st.quiet?.let { Text("Quiet hours: $it. Nothing is sent then.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    Pill(if (s.busy) "Sending…" else "Send a test reminder", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer, Modifier.padding(top = 4.dp)) { if (!s.busy) vm.test() }
                }
            }
        }
    }
}

@Composable
private fun TypeRow(label: String, on: Boolean, onChange: (Boolean) -> Unit) {
    BubbleCard(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(horizontal = 18.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
            Switch(on, onChange, Modifier.semantics { contentDescription = label; stateDescription = if (on) "On" else "Off" })
        }
    }
}
