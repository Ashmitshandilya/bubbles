package `in`.heybubbles.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Entry
import `in`.heybubbles.app.data.Field
import `in`.heybubbles.app.data.Repo
import `in`.heybubbles.app.data.Kind
import `in`.heybubbles.app.data.TrackerSpec
import `in`.heybubbles.app.data.Trackers
import `in`.heybubbles.app.data.dayLabel
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.components.Skeleton
import `in`.heybubbles.app.ui.components.Sparkline
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.LocalDate
import java.util.Locale

private val SUMMED = setOf("hydration", "activity", "nutrition")

data class TrackState(
    val loading: Boolean = true,
    val entries: Map<String, List<Entry>> = emptyMap(),
    val error: String? = null,
    val saving: Boolean = false,
    val formError: String? = null,
    val notice: String? = null,
    val pending: Int = 0,
)

class TrackViewModel(private val api: Api, private val repo: Repo) : ViewModel() {
    private val _state = MutableStateFlow(TrackState())
    val state: StateFlow<TrackState> = _state

    init {
        viewModelScope.launch { repo.entries.collect { e -> _state.update { it.copy(entries = e) } } }
        viewModelScope.launch { repo.loading.collect { l -> _state.update { it.copy(loading = l) } } }
        viewModelScope.launch { repo.pending.collect { n -> _state.update { it.copy(pending = n, notice = if (n == 0) null else it.notice) } } }
        if (repo.entries.value.isEmpty()) loadAll()
    }

    fun loadAll() {
        _state.update { it.copy(error = null) }
        viewModelScope.launch {
            if (!repo.loadAll()) _state.update { it.copy(error = "Can't reach Bubbles. Check your connection.") }
        }
    }

    fun clearFormError() = _state.update { it.copy(formError = null) }

    fun clearNotice() = _state.update { it.copy(notice = null) }

    /** Validates against the field limits, then saves. [done] runs only after the server accepted it. */
    fun save(spec: TrackerSpec, values: Map<String, String>, done: () -> Unit) {
        val body = HashMap<String, kotlinx.serialization.json.JsonElement>()
        for (f in spec.fields) {
            val raw = values[f.key]?.trim().orEmpty()
            if (raw.isEmpty()) {
                if (f.required) return fail("Please fill in “${f.label}”.")
                continue
            }
            when (val k = f.kind) {
                is Kind.Number -> {
                    val n = raw.replace(',', '.').toDoubleOrNull() ?: return fail("“${f.label}” needs a number.")
                    if (n < k.min || n > k.max) return fail("“${f.label}” should be between ${fmtNum(k.min)} and ${fmtNum(k.max)}.")
                    body[f.key] = JsonPrimitive(spec.toServer(f.key, if (k.whole) Math.round(n).toDouble() else n))
                }
                else -> body[f.key] = JsonPrimitive(raw)
            }
        }
        _state.update { it.copy(saving = true, formError = null) }
        viewModelScope.launch {
            try {
                val sent = repo.save(spec.slug, JsonObject(body))
                if (sent) repo.reload(spec.slug)
                _state.update { it.copy(saving = false, notice = if (sent) null else "Saved on this phone. It will go to Bubbles when you are back online.") }
                done()
                if (sent) repo.sync()   // a working connection is a good moment to send anything that was waiting
            } catch (e: Exception) {
                _state.update { it.copy(saving = false, formError = e.friendly()) }
            }
        }
    }

    private fun fail(msg: String) { _state.update { it.copy(formError = msg) } }

    fun delete(spec: TrackerSpec, id: String) {
        viewModelScope.launch {
            try { api.deleteEntry(spec.slug, id); repo.reload(spec.slug) } catch (e: Exception) { _state.update { it.copy(error = e.friendly()) } }
        }
    }
}

internal fun fmtNum(v: Double) = if (v % 1.0 == 0.0) v.toLong().toString() else String.format(Locale.US, "%.1f", v)

/** One value per calendar day, oldest first: sums for things you add up (water, minutes, calories), averages for the rest. */
internal fun daily(spec: TrackerSpec, entries: List<Entry>, days: Int = 14): List<Pair<LocalDate, Double>> {
    val valueOf = spec.value ?: return emptyList()
    val from = LocalDate.now().minusDays(days - 1L)
    return entries.mapNotNull { e -> val d = e.day; val v = valueOf(e); if (d != null && v != null && !d.isBefore(from)) d to v else null }
        .groupBy({ it.first }, { it.second })
        .map { (d, vs) -> d to if (spec.slug in SUMMED) vs.sum() else vs.average() }
        .sortedBy { it.first }
}

@Composable
fun TrackScreen(api: Api, repo: Repo, startSlug: String?, onStartUsed: () -> Unit) {
    val vm = viewModel<TrackViewModel>(key = "track${`in`.heybubbles.app.ui.LocalEpoch.current}") { TrackViewModel(api, repo) }
    val s by vm.state.collectAsState()
    var open by rememberSaveable { mutableStateOf<String?>(null) }
    androidx.compose.runtime.LaunchedEffect(startSlug) { if (startSlug != null) { open = startSlug; onStartUsed() } }
    BackHandler(enabled = open != null) { open = null }

    val spec = open?.let { slug -> Trackers.all.firstOrNull { it.slug == slug } }
    if (spec == null) Overview(s, onOpen = { open = it.slug }, onRetry = vm::loadAll)
    else Detail(spec, s, vm, onBack = { open = null })
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Overview(s: TrackState, onOpen: (TrackerSpec) -> Unit, onRetry: () -> Unit) {
    PullToRefreshBox(isRefreshing = s.loading && s.entries.isNotEmpty(), onRefresh = onRetry) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        ScreenTitle("Track", "What's your day like?")
        if (s.error != null) {
            Row(Modifier.padding(horizontal = 20.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(s.error, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
                Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, onClick = onRetry)
            }
        }
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Trackers.all.chunked(2).forEach { row ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    row.forEach { spec -> if (s.loading && s.entries[spec.slug] == null) Skeleton(Modifier.weight(1f).height(150.dp)) else TrackerCard(spec, s.entries[spec.slug], false, Modifier.weight(1f)) { onOpen(spec) } }
                    if (row.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
    }
    }
}

@Composable
private fun TrackerCard(spec: TrackerSpec, entries: List<Entry>?, loading: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val series = if (entries != null) daily(spec, entries) else emptyList()
    val last = series.lastOrNull()
    val whenText = when {
        loading -> "Loading…"
        last == null -> "Nothing yet"
        last.first == LocalDate.now() -> "Today"
        else -> entries?.firstOrNull { it.day == last.first }?.dayLabel().orEmpty()
    }
    BubbleCard(modifier.semantics { contentDescription = "${spec.title}. ${if (last != null) fmtNum(last.second) + " " + spec.valueUnit + ", " + whenText else whenText}. Opens details." }, tint = spec.tint, onClick = onClick) {
        Column(Modifier.padding(16.dp)) {
            Eyebrow(spec.title, color = spec.ink)
            Text(
                if (last != null) fmtNum(last.second) else "—",
                Modifier.padding(top = 6.dp), style = MaterialTheme.typography.headlineMedium, color = spec.ink,
            )
            Text(
                if (last != null && spec.valueUnit.isNotEmpty()) "${spec.valueUnit} · $whenText" else whenText,
                style = MaterialTheme.typography.labelMedium, color = spec.ink.copy(alpha = 0.8f),
            )
            Spacer(Modifier.height(8.dp))
            if (series.size >= 2) Sparkline(series.map { it.second }, spec.ink, height = 44.dp) else Spacer(Modifier.height(44.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun Detail(spec: TrackerSpec, s: TrackState, vm: TrackViewModel, onBack: () -> Unit, eyebrow: String = "Track") {
    val entries = s.entries[spec.slug].orEmpty()
    val series = daily(spec, entries)
    var sheet by rememberSaveable { mutableStateOf(false) }
    var toDelete by remember { mutableStateOf<Entry?>(null) }
    val haptic = LocalHapticFeedback.current

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        Row(Modifier.padding(start = 12.dp, top = 12.dp, end = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() },
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back") }
        }
        ScreenTitle(eyebrow, spec.title)
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            if (spec.value != null) BubbleCard(Modifier.fillMaxWidth(), tint = spec.tint, shape = MaterialTheme.shapes.extraLarge) {
                Column(Modifier.padding(20.dp)) {
                    Eyebrow("Last 14 days", color = spec.ink)
                    if (series.size >= 2) {
                        Spacer(Modifier.height(8.dp))
                        Sparkline(series.map { it.second }, spec.ink, height = 96.dp)
                        val lo = series.minOf { it.second }; val hi = series.maxOf { it.second }
                        Text("Low ${fmtNum(lo)} · High ${fmtNum(hi)} ${spec.valueUnit}", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.labelMedium, color = spec.ink)
                    } else {
                        // One reading is not a trend, and no reading is a gap, never a "normal".
                        Text(
                            if (series.isEmpty()) "Nothing logged in the last 14 days." else "One day logged so far. A line appears once there are two.",
                            Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyLarge, color = spec.ink,
                        )
                    }
                }
            }
            if (s.notice != null || s.pending > 0) BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintSun) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    s.notice?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    if (s.pending > 0) Text(
                        "${s.pending} ${if (s.pending == 1) "entry is" else "entries are"} waiting to go to Bubbles. They are kept safely on this phone until you are online.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (s.notice != null) Pill("OK", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { vm.clearNotice() }
                }
            }
            Box(
                Modifier.fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp))
                    .clickable(role = Role.Button, onClickLabel = "Add a ${spec.title.lowercase()} entry") { sheet = true },
                contentAlignment = Alignment.Center,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.Add, null, tint = androidx.compose.ui.graphics.Color.White)
                    Text(spec.ask, Modifier.padding(start = 8.dp), style = MaterialTheme.typography.titleMedium, color = androidx.compose.ui.graphics.Color.White)
                }
            }
            if (entries.isNotEmpty()) Eyebrow("History", Modifier.padding(top = 6.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            entries.take(60).forEach { e ->
                BubbleCard(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(start = 18.dp, top = 12.dp, bottom = 12.dp, end = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(e.dayLabel(), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(spec.line(e).ifBlank { "Logged" }, style = MaterialTheme.typography.bodyLarge)
                        }
                        Box(Modifier.size(48.dp).clickable(role = Role.Button, onClickLabel = "Delete this entry") { toDelete = e }, contentAlignment = Alignment.Center) {
                            Icon(Icons.Rounded.Delete, contentDescription = "Delete entry", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }

    toDelete?.let { e ->
        AlertDialog(
            onDismissRequest = { toDelete = null },
            title = { Text("Delete this entry?") },
            text = { Text("${e.dayLabel()}: ${spec.line(e)}") },
            confirmButton = { TextButton({ vm.delete(spec, e.id); toDelete = null }) { Text("Delete") } },
            dismissButton = { TextButton({ toDelete = null }) { Text("Keep it") } },
        )
    }

    if (sheet) {
        ModalBottomSheet(onDismissRequest = { sheet = false; vm.clearFormError() }, containerColor = MaterialTheme.colorScheme.background) {
            EntryForm(spec, s.saving, s.formError) { values ->
                vm.save(spec, values) { haptic.performHapticFeedback(HapticFeedbackType.Confirm); sheet = false }
            }
        }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun EntryForm(spec: TrackerSpec, saving: Boolean, error: String?, onSave: (Map<String, String>) -> Unit) {
    val values = remember { mutableStateMapOf<String, String>() }
    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(horizontal = 24.dp).padding(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(spec.ask, style = MaterialTheme.typography.headlineSmall)
        spec.fields.forEach { f -> FieldInput(f, values[f.key].orEmpty()) { values[f.key] = it } }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        Box(
            Modifier.fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp))
                .clickable(enabled = !saving, role = Role.Button, onClickLabel = "Save") { onSave(values.toMap()) },
            contentAlignment = Alignment.Center,
        ) { Text(if (saving) "Saving…" else "Save", style = MaterialTheme.typography.titleMedium, color = androidx.compose.ui.graphics.Color.White) }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun FieldInput(f: Field, value: String, onChange: (String) -> Unit) {
    when (val k = f.kind) {
        is Kind.Choice -> Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(f.label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                k.options.forEach { opt ->
                    val on = value == opt
                    Pill(
                        opt.replaceFirstChar { it.uppercase() },
                        if (on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
                        if (on) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                    ) { onChange(if (on) "" else opt) }
                }
            }
        }
        is Kind.Number -> OutlinedTextField(
            value, { onChange(it.filter { c -> c.isDigit() || c == '.' || c == ',' }) }, Modifier.fillMaxWidth(),
            label = { Text(f.label + if (f.required) "" else " (optional)") }, singleLine = true, shape = MaterialTheme.shapes.medium,
            suffix = { if (k.unit.isNotEmpty()) Text(k.unit) },
            keyboardOptions = KeyboardOptions(keyboardType = if (k.whole) KeyboardType.Number else KeyboardType.Decimal),
        )
        Kind.Text -> OutlinedTextField(
            value, onChange, Modifier.fillMaxWidth(), label = { Text(f.label + if (f.required) "" else " (optional)") },
            placeholder = f.hint?.let { { Text(it) } }, shape = MaterialTheme.shapes.medium, maxLines = 3,
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
        )
    }
}
