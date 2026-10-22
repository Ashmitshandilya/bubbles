package `in`.heybubbles.app.ui.screens

import android.content.Intent
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Entry
import `in`.heybubbles.app.data.Repo
import `in`.heybubbles.app.data.Trackers
import `in`.heybubbles.app.data.VisitPrep
import `in`.heybubbles.app.data.dayLabel
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Dot
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.LocalDate

data class PrepState(val loading: Boolean = false, val prep: VisitPrep? = null, val error: String? = null)

class CareViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(PrepState())
    val state: StateFlow<PrepState> = _state

    fun prepare(concern: String) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try { _state.update { PrepState(prep = api.visitPrep(concern)) } }
            catch (e: Exception) { _state.update { it.copy(loading = false, error = e.friendly()) } }
        }
    }
}

/** Plain text a person can send to their doctor or keep: only what they logged, no diagnosis, nothing invented. */
internal fun summaryText(concern: String, prep: VisitPrep?, entries: Map<String, List<Entry>>): String = buildString {
    appendLine("My summary for a doctor visit (${LocalDate.now()})")
    if (concern.isNotBlank()) appendLine("\nWhat I want to talk about: ${concern.trim()}")
    for (spec in Trackers.records) {
        val rows = entries[spec.slug].orEmpty()
        appendLine("\n${spec.title}:")
        if (rows.isEmpty()) appendLine("- none added yet") else rows.take(30).forEach { appendLine("- ${spec.line(it)}") }
    }
    val recent = entries["symptoms"].orEmpty().take(8)
    if (recent.isNotEmpty()) {
        appendLine("\nRecent symptoms I logged:")
        recent.forEach { appendLine("- ${it.dayLabel()}: ${Trackers.bySlug("symptoms").line(it)}") }
    }
    if (prep != null && prep.questions.isNotEmpty()) {
        appendLine("\nQuestions I'd like to ask:")
        prep.questions.forEach { appendLine("- $it") }
    }
    appendLine("\nMade from what I logged in Bubbles. It is not a diagnosis.")
}

@Composable
fun CareScreen(api: Api, repo: Repo, onBack: () -> Unit) {
    val epoch = `in`.heybubbles.app.ui.LocalEpoch.current
    val vm = viewModel<CareViewModel>(key = "care$epoch") { CareViewModel(api) }
    val tvm = viewModel<TrackViewModel>(key = "track$epoch") { TrackViewModel(api, repo) }
    val prep by vm.state.collectAsState()
    val ts by tvm.state.collectAsState()
    var open by rememberSaveable { mutableStateOf<String?>(null) }
    var concern by rememberSaveable { mutableStateOf("") }
    val context = LocalContext.current
    BackHandler { if (open != null) open = null else onBack() }

    val spec = open?.let { slug -> Trackers.records.firstOrNull { it.slug == slug } }
    if (spec != null) { Detail(spec, ts, tvm, onBack = { open = null }, eyebrow = "Care"); return }

    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp)) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle("Care", "Get ready for your visit")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintPink, shape = MaterialTheme.shapes.extraLarge) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Eyebrow("Before your visit")
                    Text("What do you want to talk about?", style = MaterialTheme.typography.titleMedium, color = Bubbles.Ink)
                    OutlinedTextField(
                        concern, { concern = it.take(300) }, Modifier.fillMaxWidth(), placeholder = { Text("e.g. headaches before my period") },
                        shape = MaterialTheme.shapes.medium, maxLines = 3,
                    )
                    Box(
                        Modifier.fillMaxWidth().height(52.dp).background(BubbleGradient, RoundedCornerShape(26.dp))
                            .clickable(enabled = !prep.loading, role = Role.Button, onClickLabel = "Prepare my questions") { vm.prepare(concern) },
                        contentAlignment = Alignment.Center,
                    ) { Text(if (prep.loading) "Preparing…" else "Prepare my questions", style = MaterialTheme.typography.titleMedium, color = Color.White) }
                    prep.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
                }
            }

            prep.prep?.let { p ->
                if (p.questions.isNotEmpty()) ListCard("Questions you could ask", p.questions, Bubbles.TintGrape, Bubbles.GrapeDeep)
                if (p.bring.isNotEmpty()) ListCard("What to bring", p.bring, Bubbles.TintMint, Bubbles.MintDeep)
            }

            Eyebrow("Your records", Modifier.padding(top = 6.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Trackers.records.forEach { r ->
                val rows = ts.entries[r.slug].orEmpty()
                BubbleCard(Modifier.fillMaxWidth(), tint = if (rows.isEmpty()) MaterialTheme.colorScheme.surface else r.tint, onClick = { open = r.slug }) {
                    Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(r.title, style = MaterialTheme.typography.titleMedium, color = if (rows.isEmpty()) MaterialTheme.colorScheme.onSurface else r.ink)
                            // Nothing added is not the same as none: say it plainly.
                            Text(
                                if (rows.isEmpty()) "None added yet" else "${rows.size} added · ${r.line(rows.first())}",
                                style = MaterialTheme.typography.bodyMedium, color = if (rows.isEmpty()) MaterialTheme.colorScheme.onSurfaceVariant else r.ink, maxLines = 2,
                            )
                        }
                    }
                }
            }

            Box(
                Modifier.padding(top = 4.dp).fillMaxWidth().height(56.dp).background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(28.dp))
                    .clickable(role = Role.Button, onClickLabel = "Share my summary") {
                        val send = Intent(Intent.ACTION_SEND).apply { type = "text/plain"; putExtra(Intent.EXTRA_TEXT, summaryText(concern, prep.prep, ts.entries)) }
                        context.startActivity(Intent.createChooser(send, "Share my summary"))
                    },
                contentAlignment = Alignment.Center,
            ) { Text("Share my summary", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onPrimaryContainer) }
            Text(
                "Only what you added is included. Chats, notes and Community posts are never part of it.",
                Modifier.padding(horizontal = 4.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ListCard(title: String, items: List<String>, tint: Color, ink: Color) {
    BubbleCard(Modifier.fillMaxWidth(), tint = tint) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Eyebrow(title, color = ink)
            items.forEach {
                Row(verticalAlignment = Alignment.Top) {
                    Dot(ink, 7.dp, Modifier.padding(top = 9.dp, end = 12.dp))
                    Text(it, style = MaterialTheme.typography.bodyLarge, color = Bubbles.Ink)
                }
            }
        }
    }
}
