package `in`.heybubbles.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.StarsLogic
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.ui.components.CheckRow
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.FieldRow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.screens.fitness.FitnessPage
import `in`.heybubbles.app.ui.screens.fitness.LoadGate
import `in`.heybubbles.app.ui.screens.fitness.rememberLoad
import `in`.heybubbles.app.ui.screens.fitness.rememberSender

/**
 * The Stars lens: a traditional lens, off until the person says yes. The server works out the chart from its own city list and checks each
 * traditional word against what Bubbles has seen; this screen only asks for the birth details and shows the answer.
 */
@Composable
fun StarsScreen(api: Api, onBack: () -> Unit) {
    val load = rememberLoad(api, "/me/stars")
    FitnessPage("Stars lens", eyebrow = "Me", onBack = onBack) {
        LoadGate(load) { d -> Body(api, d) { load.reload() } }
    }
}

@Composable
private fun Body(api: Api, d: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    val scope = rememberCoroutineScope()
    var editing by remember { mutableStateOf(false) }
    var consentBusy by remember { mutableStateOf(false) }
    var consentError by remember { mutableStateOf<String?>(null) }
    val consent = d.bool("consent") == true
    val enabled = d.bool("enabled") == true

    Text(d.str("intro").orEmpty(), style = MaterialTheme.typography.titleMedium)
    (consentError ?: send.error.value)?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }

    if (!consent) {
        Text(
            "Lets Bubbles keep your birth date, an optional birth time and a birth place from its own list. It never predicts anything and is never used for health, safety or relationship decisions.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Pill(if (consentBusy) "Saving…" else "Turn on the Stars lens", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, Modifier.heightIn(min = 48.dp)) {
            if (consentBusy) return@Pill
            consentBusy = true; consentError = null
            scope.launch {
                try {
                    val purpose = api.consents().firstOrNull { it.id == "stars_lens" }
                    api.setConsent("stars_lens", true, purpose?.textHash)
                    reload()
                } catch (e: Exception) { consentError = e.friendly() } finally { consentBusy = false }
            }
        }
        return
    }

    if (!enabled || editing) {
        BirthForm(api, d.obj("birth"), onSaved = { editing = false; reload() }, onCancel = if (enabled) ({ editing = false }) else null)
        return
    }

    val chart = d.obj("chart")
    Eyebrow("Your lens")
    listOf(StarsLogic.describe("Moon", chart?.obj("moon")), StarsLogic.describe("Sun", chart?.obj("sun")),
        StarsLogic.describe("Ascendant", if (chart?.bool("time_known") == true) chart.obj("ascendant") else null)).forEach {
        Text(it, style = MaterialTheme.typography.bodyLarge)
    }
    d.obj("birth")?.let { b ->
        Text("Born ${b.str("date").orEmpty()}${b.str("time")?.let { " at $it" } ?: ", time not known"}${b.obj("place")?.str("name")?.let { ", $it" }.orEmpty()}.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    Eyebrow("Traditional words, checked against what Bubbles has seen")
    d.objs("items").forEach { item ->
        Column(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(item.str("text").orEmpty(), style = MaterialTheme.typography.titleMedium)
            Text("${item.str("source").orEmpty()}${if (item.bool("uncertain") == true) " (one of two it could be)" else ""} · ${item.str("match").orEmpty()}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = { editing = true }, Modifier.heightIn(min = 48.dp)) { Text("Change my details") }
        TextButton(onClick = { send.send("DELETE", "/me/stars") { reload() } }, Modifier.heightIn(min = 48.dp)) { Text("Turn off and delete") }
    }
    Text("Turning it off deletes your birth date, time and place, and what the lens added to how Bubbles understands you.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun BirthForm(api: Api, birth: JsonObject?, onSaved: () -> Unit, onCancel: (() -> Unit)?) {
    val send = rememberSender(api)
    var date by remember { mutableStateOf(birth?.str("date").orEmpty()) }
    var time by remember { mutableStateOf(birth?.str("time").orEmpty()) }
    var timeUnknown by remember { mutableStateOf(birth != null && birth.str("time") == null) }
    var query by remember { mutableStateOf(birth?.obj("place")?.str("name").orEmpty()) }
    var placeId by remember { mutableStateOf<String?>(null) }
    var places by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var problems by remember { mutableStateOf(StarsLogic.Problems()) }

    LaunchedEffect(query, placeId) {
        if (placeId != null || query.trim().length < 2) { places = emptyList(); return@LaunchedEffect }
        delay(250)
        places = try { api.getJson("/me/stars/places?q=${java.net.URLEncoder.encode(query.trim(), "UTF-8")}").objs("places") } catch (_: Exception) { emptyList() }
    }

    Eyebrow("Your birth details")
    FieldRow("Birth date (YYYY-MM-DD)", date, { date = it }, error = problems.date, maxLength = 10)
    FieldRow("Birth time (HH:MM)", time, { time = it }, error = problems.time, maxLength = 5)
    CheckRow("I do not know my birth time", timeUnknown) { timeUnknown = it }
    FieldRow("Birth place", query, { query = it; placeId = null }, error = problems.place, hint = "Indian cities of about 100,000 people or more and world capitals. Nothing leaves Bubbles to look it up.", maxLength = 40)
    places.forEach { p ->
        Text(
            "${p.str("name").orEmpty()}, ${p.str("region").orEmpty()}",
            Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Button) { placeId = p.str("id"); query = p.str("name").orEmpty(); places = emptyList() }.padding(vertical = 12.dp),
            style = MaterialTheme.typography.bodyLarge,
        )
    }
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Pill(if (send.busy.value) "Saving…" else "Show my lens", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, Modifier.heightIn(min = 48.dp)) {
            problems = StarsLogic.problems(date, time, timeUnknown, placeId)
            if (!problems.any) send.send("PUT", "/me/stars", StarsLogic.body(date, time, timeUnknown, placeId!!)) { onSaved() }
        }
        if (onCancel != null) Pill("Cancel", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant, Modifier.heightIn(min = 48.dp), onClick = onCancel)
    }
}
