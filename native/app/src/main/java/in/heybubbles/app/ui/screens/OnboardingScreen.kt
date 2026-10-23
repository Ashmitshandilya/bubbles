package `in`.heybubbles.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
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
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import `in`.heybubbles.app.data.Answers
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Bank
import `in`.heybubbles.app.data.Flow
import `in`.heybubbles.app.data.Purpose
import `in`.heybubbles.app.data.Question
import `in`.heybubbles.app.data.Screen
import `in`.heybubbles.app.data.ScreenKind
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Mascot
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/** Purposes the setup offers. Partner sharing and Community are asked where they are used, never here. */
private val OFFERED = listOf("ai_chat_processing", "health_memory_from_chat", "push_notifications", "email_reminders")

enum class Phase { Loading, Failed, Under18, Asking, Creating, Done }

data class OnbState(
    val phase: Phase = Phase.Loading,
    val bank: Bank? = null,
    val answers: Answers = emptyMap(),
    val screens: List<Screen> = emptyList(),
    val index: Int = 0,
    val purposes: List<Purpose>? = null,
    val on: Set<String> = emptySet(),
    val busy: Boolean = false,
    val error: String? = null,
    val applied: List<String> = emptyList(),
)

class OnboardingViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(OnbState())
    val state: StateFlow<OnbState> = _state
    private var saved: Answers = emptyMap()
    private val today get() = LocalDate.now()

    init { load() }

    /** Returns to the app if setup is already finished (see [onFinished]). */
    var onFinished: () -> Unit = {}

    fun load() {
        _state.update { it.copy(phase = Phase.Loading, error = null) }
        viewModelScope.launch {
            try {
                val bank = api.onboardingBank()
                val st = api.onboardingState()
                if (st.complete) { onFinished(); return@launch }
                if (st.under18) { _state.update { it.copy(phase = Phase.Under18) }; return@launch }
                saved = st.answers
                val start = Flow.countryFromTimeZone(java.util.TimeZone.getDefault().id)?.takeIf { st.answers["country"] == null }
                    ?.let { st.answers + ("country" to JsonPrimitive(it)) } ?: st.answers
                val screens = Flow.buildScreens(bank, start, today)
                _state.update { it.copy(phase = Phase.Asking, bank = bank, answers = start, screens = screens, index = Flow.resumeIndex(screens, bank, start, today)) }
            } catch (e: Exception) {
                _state.update { it.copy(phase = Phase.Failed, error = e.friendly()) }
            }
        }
    }

    private fun rebuild(answers: Answers, keepScreenId: String?) {
        val bank = _state.value.bank ?: return
        val screens = Flow.buildScreens(bank, answers, today)
        val idx = screens.indexOfFirst { it.id == keepScreenId }.takeIf { it >= 0 } ?: _state.value.index.coerceAtMost(screens.lastIndex)
        _state.update { it.copy(answers = answers, screens = screens, index = idx) }
    }

    fun answer(qid: String, value: JsonElement?) {
        val s = _state.value
        val keep = s.screens.getOrNull(s.index)?.id
        val next = if (value == null) s.answers - qid else s.answers + (qid to value)
        _state.update { it.copy(error = null) }
        rebuild(next, keep)
    }

    /** Tapping a single-choice answer moves on when every other question on the screen already has one. */
    fun pickSingle(q: Question, optionId: String) {
        answer(q.id, JsonPrimitive(optionId))
        val s = _state.value
        val screen = s.screens.getOrNull(s.index) ?: return
        val bank = s.bank ?: return
        if (screen.kind == ScreenKind.Questions && Flow.screenQuestions(screen, bank).all { Flow.isAnswered(s.answers[it.id]) }) next()
    }

    fun back() { _state.update { it.copy(index = (it.index - 1).coerceAtLeast(0), error = null) } }

    fun next() {
        val s = _state.value
        val bank = s.bank ?: return
        val screen = s.screens.getOrNull(s.index) ?: return
        if (s.busy) return
        if (screen.kind == ScreenKind.Questions) {
            val missing = Flow.missingRequired(Flow.screenQuestions(screen, bank), s.answers, today)
            if (missing.isNotEmpty()) { _state.update { it.copy(error = "Please answer this one to carry on.") }; return }
            val age = Flow.ageOn(s.answers["birth_date"], today)
            if (age != null && age < bank.minAge) { _state.update { it.copy(phase = Phase.Under18) }; return }   // nothing is saved for under-18s
            val patch = Flow.pendingPatch(s.screens, s.index, bank, s.answers, saved, today)
            if (!patch.isNullOrEmpty()) {
                _state.update { it.copy(busy = true, error = null) }
                viewModelScope.launch {
                    try {
                        api.saveAnswers(patch, s.index)
                        saved = s.answers
                        _state.update { it.copy(busy = false) }
                        advance()
                    } catch (e: Exception) {
                        _state.update { it.copy(busy = false, error = e.friendly()) }
                    }
                }
                return
            }
        }
        advance()
    }

    private fun advance() {
        val s = _state.value
        if (s.index >= s.screens.lastIndex) complete() else {
            val entering = s.screens[s.index + 1]
            _state.update { it.copy(index = it.index + 1, error = null) }
            if (entering.kind == ScreenKind.Choices && s.purposes == null) loadPurposes()
        }
    }

    /** Optional questions can be skipped: their answers are cleared and we move on. */
    fun skip() {
        val s = _state.value
        val bank = s.bank ?: return
        val screen = s.screens.getOrNull(s.index) ?: return
        val cleared = s.answers.filterKeys { k -> Flow.screenQuestions(screen, bank).none { it.id == k && !Flow.isRequired(it, s.answers, today) } }
        _state.update { it.copy(answers = cleared) }
        next()
    }

    private fun loadPurposes() {
        viewModelScope.launch {
            try {
                val all = api.consents()
                _state.update { it.copy(purposes = OFFERED.mapNotNull { id -> all.firstOrNull { p -> p.id == id && p.available } }) }
            } catch (_: Exception) {
                _state.update { it.copy(purposes = emptyList(), error = "Your choices couldn't load just now. You can set them any time in Me.") }
            }
        }
    }

    fun toggle(id: String) { _state.update { it.copy(on = if (id in it.on) it.on - id else it.on + id) } }

    /** Writes one ledger row per offered choice: what was left off is recorded as a no. */
    fun finishChoices(allOff: Boolean) {
        val s = _state.value
        val ps = s.purposes ?: emptyList()
        _state.update { it.copy(busy = true, error = null, on = if (allOff) emptySet() else it.on) }
        viewModelScope.launch {
            try {
                val on = if (allOff) emptySet() else s.on
                ps.forEach { p -> api.setConsent(p.id, p.id in on, p.textHash, "onboarding") }
                _state.update { it.copy(busy = false) }
                advance()
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, error = e.friendly()) }
            }
        }
    }

    fun skipExtras() = complete()

    fun complete() {
        _state.update { it.copy(phase = Phase.Creating, error = null) }
        viewModelScope.launch {
            try {
                val lines = api.completeOnboarding()
                _state.update { it.copy(phase = Phase.Done, applied = lines) }
            } catch (e: Exception) {
                _state.update { it.copy(phase = Phase.Asking, error = e.friendly()) }
            }
        }
    }
}

@Composable
fun OnboardingScreen(api: Api, onFinished: () -> Unit, onSignOut: () -> Unit) {
    val vm = viewModel<OnboardingViewModel>(key = "onb${`in`.heybubbles.app.ui.LocalEpoch.current}") { OnboardingViewModel(api) }
    vm.onFinished = onFinished
    val s by vm.state.collectAsState()
    BackHandler(enabled = s.phase == Phase.Asking && s.index > 0) { vm.back() }

    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
        when (s.phase) {
            Phase.Loading -> Centered { Text("Getting things ready…", style = MaterialTheme.typography.titleLarge) }
            Phase.Failed -> Centered {
                Text(s.error ?: "Something went wrong.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
                Pill("Try again", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, Modifier.padding(top = 16.dp), onClick = vm::load)
            }
            Phase.Under18 -> Centered {
                Text("Bubbles is for people 18 and over for now", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
                Text("We can't set up an account for you yet. If you're worried about your health, please talk to a trusted adult or a doctor.", Modifier.padding(top = 12.dp), style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Pill("Sign out", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, Modifier.padding(top = 20.dp), onClick = onSignOut)
            }
            Phase.Creating -> Centered {
                Text("Setting things up for you…", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
            }
            Phase.Done -> Done(s.applied, onFinished)
            Phase.Asking -> Asking(s, vm)
        }
    }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
    Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { content() }
}

@Composable
private fun Done(lines: List<String>, onFinished: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Mascot(150.dp, title = "Bubbles the unicorn")
        Text("You're all set", Modifier.padding(top = 20.dp), style = MaterialTheme.typography.headlineMedium)
        lines.forEach { Text(it, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center) }
        Box(
            Modifier.padding(top = 28.dp).fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp)).clickable(role = Role.Button, onClickLabel = "Start", onClick = onFinished),
            contentAlignment = Alignment.Center,
        ) { Text("Start with Bubbles", style = MaterialTheme.typography.titleMedium, color = Color.White) }
    }
}

private fun progressLabel(screens: List<Screen>, index: Int, answers: Answers): String {
    val s = screens.getOrNull(index) ?: return ""
    if (s.kind == ScreenKind.Choices) return "Your choices"
    if (s.kind == ScreenKind.ExtrasIntro || s.stage == "extras") return "A few extras (skip any)"
    if (s.followUp) return "A quick follow-up"
    val numbered = screens.filter { it.kind == ScreenKind.Questions && it.stage == "core" && !it.followUp }
    val n = numbered.indexOf(s) + 1
    return if (index == 0 && answers["body"] == null) "Question $n" else "Question $n of ${numbered.size}"
}

@Composable
private fun androidx.compose.foundation.layout.ColumnScope.Asking(s: OnbState, vm: OnboardingViewModel) {
    val bank = s.bank ?: return
    val screen = s.screens.getOrNull(s.index) ?: return
    val haptic = LocalHapticFeedback.current

    // Progress: a thin gradient bar, so the length of the setup is always visible.
    val frac = (s.index + 1).toFloat() / s.screens.size.coerceAtLeast(1)
    Canvas(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 16.dp).height(6.dp)) {
        drawRoundRect(Bubbles.Line, size = Size(size.width, size.height), cornerRadius = androidx.compose.ui.geometry.CornerRadius(size.height / 2))
        drawRoundRect(BubbleGradient, size = Size(size.width * frac, size.height), cornerRadius = androidx.compose.ui.geometry.CornerRadius(size.height / 2))
    }
    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Eyebrow(progressLabel(s.screens, s.index, s.answers))
        when (screen.kind) {
            ScreenKind.Choices -> ChoicesStep(s, vm)
            ScreenKind.ExtrasIntro -> {
                Box(Modifier.fillMaxWidth().padding(top = 12.dp), contentAlignment = Alignment.Center) { Mascot(160.dp, title = "Bubbles the unicorn") }
                Text("A little more?", style = MaterialTheme.typography.headlineMedium)
                Text("The next few questions make Bubbles fit you better. Every one is optional, and you can stop any time.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            ScreenKind.Questions -> Flow.screenQuestions(screen, bank).forEach { q -> QuestionView(q, s, vm) }
        }
        s.error?.let { Text(it, Modifier.semantics { contentDescription = "Error: $it" }, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        Spacer(Modifier.height(8.dp))
    }

    // Bottom bar: Back, then the one thing to do next.
    val isChoices = screen.kind == ScreenKind.Choices
    val isIntro = screen.kind == ScreenKind.ExtrasIntro
    val optional = screen.kind == ScreenKind.Questions && screen.stage != "core" && Flow.screenQuestions(screen, bank).none { Flow.isRequired(it, s.answers, java.time.LocalDate.now()) }
    Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        if (s.index > 0) TextButton({ vm.back() }) { Text("Back") }
        Spacer(Modifier.weight(1f))
        when {
            isChoices -> {
                TextButton({ vm.finishChoices(allOff = true) }, enabled = !s.busy) { Text("Not now") }
                Primary(if (s.busy) "Saving…" else "Continue", !s.busy) { vm.finishChoices(allOff = false) }
            }
            isIntro -> {
                TextButton({ vm.skipExtras() }) { Text("Skip the extras") }
                Primary("Continue", true) { haptic.performHapticFeedback(HapticFeedbackType.ContextClick); vm.next() }
            }
            else -> {
                if (optional) TextButton({ vm.skip() }) { Text("Skip") }
                Primary(if (s.busy) "Saving…" else "Next", !s.busy) { vm.next() }
            }
        }
    }
}

@Composable
private fun Primary(text: String, enabled: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.height(52.dp).background(if (enabled) BubbleGradient else androidx.compose.ui.graphics.SolidColor(Bubbles.LineStrong), RoundedCornerShape(26.dp))
            .clickable(enabled = enabled, role = Role.Button, onClickLabel = text, onClick = onClick).padding(horizontal = 28.dp),
        contentAlignment = Alignment.Center,
    ) { Text(text, style = MaterialTheme.typography.titleMedium, color = Color.White) }
}

@Composable
private fun QuestionView(q: Question, s: OnbState, vm: OnboardingViewModel) {
    val bank = s.bank ?: return
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(Flow.titleFor(q, s.answers, bank), style = MaterialTheme.typography.headlineSmall)
        if (q.why.isNotBlank()) Text(q.why, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val value = s.answers[q.id]
        when (q.type) {
            "single", "multi" -> {
                val chosen = Flow.picked(value)
                Flow.visibleOptions(q, s.answers, LocalDate.now()).forEach { o ->
                    OptionRow(o.label, o.id in chosen, multi = q.type == "multi") { if (q.type == "single") vm.pickSingle(q, o.id) else vm.answer(q.id, Flow.pick(q, value, o.id)) }
                }
            }
            "text" -> {
                var text by remember(q.id) { mutableStateOf((value as? JsonPrimitive)?.content.orEmpty()) }
                OutlinedTextField(
                    text, { t -> text = t.take(q.maxLength ?: 200); vm.answer(q.id, text.takeIf { it.isNotBlank() }?.let(::JsonPrimitive)) }, Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.medium, singleLine = q.maxLength != null && q.maxLength <= 80, minLines = if ((q.maxLength ?: 0) > 80) 3 else 1,
                )
            }
            "date" -> DateField(q, (value as? JsonPrimitive)?.content) { vm.answer(q.id, JsonPrimitive(it.toString())) }
            "slider" -> {
                val lo = (q.min ?: 0.0).toFloat(); val hi = (q.max ?: 10.0).toFloat()
                val v = ((value as? JsonPrimitive)?.doubleOrNull ?: ((lo + hi) / 2).toDouble()).toFloat()
                val steps = q.increment?.let { ((hi - lo) / it.toFloat()).toInt() - 1 }?.coerceAtLeast(0) ?: 0
                Text("${"%.1f".format(v).removeSuffix(".0")} ${q.unit.orEmpty()}", style = MaterialTheme.typography.titleLarge)
                Slider(v, { vm.answer(q.id, JsonPrimitive((it * 2).toInt() / 2.0)) }, valueRange = lo..hi, steps = steps)
            }
            "number_pair" -> NumberPair(value as? JsonObject) { vm.answer(q.id, it) }
        }
    }
}

@Composable
private fun OptionRow(label: String, on: Boolean, multi: Boolean, onClick: () -> Unit) {
    val shape = RoundedCornerShape(20.dp)
    Row(
        Modifier.fillMaxWidth().background(if (on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface, shape)
            .border(1.5.dp, if (on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, shape)
            .clickable(role = if (multi) Role.Checkbox else Role.RadioButton, onClick = onClick)
            .semantics { selected = on; stateDescription = if (on) "Selected" else "Not selected" }
            .padding(horizontal = 18.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(
            Modifier.size(22.dp).border(2.dp, if (on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline, if (multi) RoundedCornerShape(7.dp) else CircleShape)
                .background(if (on) MaterialTheme.colorScheme.primary else Color.Transparent, if (multi) RoundedCornerShape(7.dp) else CircleShape),
        )
        Text(label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateField(q: Question, current: String?, onPick: (LocalDate) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val isBirth = q.id == "birth_date" || q.id == "baby_birth_date"
    val shown = current?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
    Box(
        Modifier.fillMaxWidth().border(1.5.dp, MaterialTheme.colorScheme.outline, MaterialTheme.shapes.medium).clickable(role = Role.Button, onClickLabel = "Choose a date") { open = true }.padding(horizontal = 18.dp, vertical = 18.dp),
    ) { Text(shown?.format(java.time.format.DateTimeFormatter.ofPattern("d MMMM yyyy", java.util.Locale.ENGLISH)) ?: "Choose a date", style = MaterialTheme.typography.bodyLarge, color = if (shown == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface) }
    if (open) {
        val start = shown ?: if (q.id == "birth_date") LocalDate.of(LocalDate.now().year - 25, 1, 1) else LocalDate.now()
        val state = rememberDatePickerState(initialSelectedDateMillis = start.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli())
        DatePickerDialog(
            onDismissRequest = { open = false },
            confirmButton = { TextButton({ state.selectedDateMillis?.let { onPick(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()) }; open = false }) { Text("OK") } },
            dismissButton = { TextButton({ open = false }) { Text("Cancel") } },
        ) { DatePicker(state) }
    }
}

@Composable
private fun NumberPair(current: JsonObject?, onChange: (JsonElement?) -> Unit) {
    var h by remember { mutableStateOf((current?.get("height_cm") as? JsonPrimitive)?.content.orEmpty()) }
    var w by remember { mutableStateOf((current?.get("weight_kg") as? JsonPrimitive)?.content.orEmpty()) }
    fun push() {
        val map = buildMap<String, JsonElement> {
            h.replace(',', '.').toDoubleOrNull()?.takeIf { it in 120.0..230.0 }?.let { put("height_cm", JsonPrimitive(it)) }
            w.replace(',', '.').toDoubleOrNull()?.takeIf { it in 30.0..300.0 }?.let { put("weight_kg", JsonPrimitive(it)) }
        }
        onChange(if (map.isEmpty()) null else JsonObject(map))
    }
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        OutlinedTextField(h, { h = it.filter { c -> c.isDigit() || c == '.' }; push() }, Modifier.weight(1f), label = { Text("Height") }, suffix = { Text("cm") }, singleLine = true, shape = MaterialTheme.shapes.medium, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        OutlinedTextField(w, { w = it.filter { c -> c.isDigit() || c == '.' }; push() }, Modifier.weight(1f), label = { Text("Weight") }, suffix = { Text("kg") }, singleLine = true, shape = MaterialTheme.shapes.medium, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
    }
}

@Composable
private fun ChoicesStep(s: OnbState, vm: OnboardingViewModel) {
    Text("Your choices", style = MaterialTheme.typography.headlineMedium)
    Text("Everything is off until you turn it on. You can change any of it later in Me → Your choices.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    val ps = s.purposes
    if (ps == null) Text("Getting your choices…", style = MaterialTheme.typography.bodyMedium)
    ps?.forEach { p ->
        BubbleCard(Modifier.fillMaxWidth()) {
            Row(Modifier.padding(18.dp), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(p.title, style = MaterialTheme.typography.titleMedium)
                    Text(p.description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(p.id in s.on, { vm.toggle(p.id) }, Modifier.semantics { contentDescription = p.title; stateDescription = if (p.id in s.on) "On" else "Off" })
            }
        }
    }
}
