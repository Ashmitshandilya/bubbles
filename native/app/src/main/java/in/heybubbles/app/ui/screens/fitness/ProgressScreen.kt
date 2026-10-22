package `in`.heybubbles.app.ui.screens.fitness

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.fmtNum
import `in`.heybubbles.app.data.int
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.FieldRow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.Sparkline
import `in`.heybubbles.app.ui.theme.Bubbles

private val SITES = listOf("waist_cm" to "Waist", "hip_cm" to "Hip", "chest_cm" to "Chest", "arm_cm" to "Arm", "thigh_cm" to "Thigh")

/** Weight trend and body measurements. A trend line is smoothed on the server, so one heavy day never reads as a result. */
@Composable
fun ProgressScreen(api: Api, onBack: () -> Unit) {
    val loader = rememberLoad(api, "/fitness/progress")
    val send = rememberSender(api)
    var values by remember { mutableStateOf(SITES.associate { it.first to "" }) }
    var saved by remember { mutableStateOf(false) }

    FitnessPage("How it is going", "Progress", onBack) {
        LoadGate(loader) { p ->
            val trend = p.objs("trend").mapNotNull { it.num("trend_kg") }
            val weights = p.objs("weights")
            BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintGrape) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Weight trend", style = MaterialTheme.typography.titleSmall)
                    if (trend.size >= 2) Sparkline(trend, Bubbles.GrapeDeep, height = 72.dp)
                    Text(
                        weights.lastOrNull()?.let { "Latest ${fmtNum(it.num("weight_kg"))} kg on ${it.str("date").orEmpty()}" } ?: "No weigh-ins yet. Add one in Track, under Weight.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    p.num("rate_kg_per_week")?.let { Text("Recent change about ${"%.2f".format(it)} kg a week", style = MaterialTheme.typography.bodyMedium) }
                    p.str("luteal_note")?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
            p.obj("adherence")?.let { a ->
                Text("Logged food on ${a.int("days_logged_28") ?: 0} of the last 28 days. ${a.str("label").orEmpty().replaceFirstChar { it.uppercase() }}.", style = MaterialTheme.typography.bodyMedium)
            }
            Eyebrow("Measurements")
            val ms = p.objs("measurements")
            if (ms.isEmpty()) Text("Nothing recorded yet. Measuring is optional.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            ms.take(6).forEach { m ->
                Text(
                    m.str("date").orEmpty() + ": " + SITES.mapNotNull { (k, label) -> m.num(k)?.let { "$label ${fmtNum(it)} cm" } }.joinToString(", "),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Text("Add today's (any you like, in cm)", style = MaterialTheme.typography.titleSmall)
            SITES.chunked(2).forEach { pair ->
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    pair.forEach { (k, label) -> FieldRow(label, values.getValue(k), { values = values + (k to it.filter { c -> c.isDigit() || c == '.' || c == ',' }); saved = false }, Modifier.weight(1f), number = true, suffix = "cm", maxLength = 5) }
                }
            }
            send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            if (saved) Text("Saved.", color = Bubbles.MintDeep, style = MaterialTheme.typography.bodyMedium)
            Pill(if (send.busy.value) "Saving…" else "Save measurements", Bubbles.Pink, Bubbles.White) {
                val body: JsonObject = buildJsonObject { values.forEach { (k, v) -> v.replace(',', '.').toDoubleOrNull()?.let { put(k, it) } } }
                if (body.isEmpty()) return@Pill
                send.send("POST", "/fitness/measurements", body) { saved = true; values = SITES.associate { it.first to "" }; loader.reload() }
            }
            Disclaimer()
        }
    }
}
