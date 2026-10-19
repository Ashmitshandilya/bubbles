package `in`.heybubbles.app.ui.screens.fitness

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.components.Skeleton
import `in`.heybubbles.app.ui.theme.Bubbles

/** What a server read looks like to a screen: still loading, failed (with plain words), or here. */
sealed interface Load {
    data object Loading : Load
    data class Failed(val message: String) : Load
    data class Ready(val data: JsonObject) : Load
}

class Loader(val state: Load, val reload: () -> Unit)

/** Reads one JSON document and re-reads when [reload] is called. Failures never show server text, only the friendly line. */
@Composable
fun rememberLoad(api: Api, path: String): Loader {
    var tick by remember { mutableIntStateOf(0) }
    val state by produceState<Load>(Load.Loading, path, tick) {
        value = Load.Loading
        value = try { Load.Ready(api.getJson(path)) } catch (e: Exception) { Load.Failed(e.friendly()) }
    }
    return Loader(state) { tick++ }
}

/** A page inside Fitness: back arrow, title, scrolling body. Back goes to the previous Fitness page, not out of the app. */
@Composable
fun FitnessPage(title: String, eyebrow: String = "Fitness", onBack: () -> Unit, content: @Composable () -> Unit) {
    BackHandler { onBack() }
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle(eyebrow, title)
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { content() }
    }
}

/** Shows skeletons while loading, a retry card on failure, and [ready] with the document otherwise. */
@Composable
fun LoadGate(loader: Loader, ready: @Composable (JsonObject) -> Unit) {
    when (val s = loader.state) {
        Load.Loading -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Skeleton(Modifier.fillMaxWidth().size(width = 0.dp, height = 120.dp).fillMaxWidth())
            Skeleton(Modifier.fillMaxWidth().size(width = 0.dp, height = 160.dp).fillMaxWidth())
        }
        is Load.Failed -> BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintUrgent) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(s.message, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.error)
                Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, onClick = loader.reload)
            }
        }
        is Load.Ready -> ready(s.data)
    }
}

/** The "waiting for a clinician's review" note the website shows under every set of numbers, from the server's own text. */
@Composable
fun ClinicalNote(review: JsonObject?) {
    if (review == null || review.str("status") == "reviewed" || review["reviewed"].toString() == "true") return
    BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintSky) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Waiting for a clinician's review", style = MaterialTheme.typography.titleSmall)
            Text(
                "Bubbles's targets are general estimates and have not yet been checked by a clinician. Treat them as a starting point.",
                style = MaterialTheme.typography.bodyMedium,
            )
            review.str("notice")?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

@Composable
fun Disclaimer() {
    Text("Estimates, not medical advice. Talk to a doctor or dietitian before big changes.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

/** Runs a server write, reports plain-language failure, and hands back the reply on success. */
class Sender(private val scopeLaunch: (suspend () -> Unit) -> Unit, private val api: Api) {
    val busy: MutableState<Boolean> = mutableStateOf(false)
    val error: MutableState<String?> = mutableStateOf(null)

    fun send(method: String, path: String, body: JsonObject? = null, onOk: (JsonObject) -> Unit = {}) {
        if (busy.value) return
        busy.value = true; error.value = null
        scopeLaunch {
            try { onOk(api.sendJson(method, path, body)) } catch (e: Exception) { error.value = e.friendly() }
            busy.value = false
        }
    }
}

@Composable
fun rememberSender(api: Api): Sender {
    val scope = rememberCoroutineScope()
    return remember(api) { Sender({ block -> scope.launch { block() } }, api) }
}
