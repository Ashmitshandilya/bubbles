package `in`.heybubbles.app.ui.screens.fitness

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.fmtNum
import `in`.heybubbles.app.data.int
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.ChoiceChips
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles

/** A week of meals built by the server from the person's numbers, food style and allergies; the app shows it, swaps a meal, and lists groceries. */
@Composable
fun DietScreen(api: Api, onBack: () -> Unit) {
    val loader = rememberLoad(api, "/fitness/diet/plan")
    val send = rememberSender(api)
    var meals by remember { mutableStateOf("4") }
    var day by remember { mutableStateOf(1) }
    var swapping by remember { mutableStateOf<Pair<Int, JsonObject>?>(null) }
    var options by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var grocery by remember { mutableStateOf<JsonObject?>(null) }

    FitnessPage("Your week of meals", "Diet planner", onBack) {
        LoadGate(loader) { doc ->
            val days = doc.obj("plan")?.objs("days").orEmpty()
            send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            if (doc.bool("exists") != true || days.isEmpty()) {
                Text("Bubbles builds a week that fits your food style, allergies and numbers. You can swap any meal.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                ChoiceChips("Meals a day", listOf("3" to "3", "4" to "4", "5" to "5"), meals, { meals = it })
                Pill(if (send.busy.value) "Planning…" else "Make my week", Bubbles.Pink, Bubbles.White) {
                    send.send("POST", "/fitness/diet/plan", buildJsonObject { put("meals_per_day", meals.toInt()) }) { loader.reload() }
                }
            } else {
                val d = days.getOrNull(day - 1) ?: days.first()
                ChoiceChips("Day", days.indices.map { (it + 1).toString() to "Day ${it + 1}" }, day.toString(), { day = it.toInt() })
                BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintMint) {
                    Column(Modifier.padding(16.dp)) {
                        Text("About ${fmtNum(d.obj("totals")?.num("kcal"))} kcal, aim ${fmtNum(d.num("target_kcal"))}", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Protein ${fmtNum(d.obj("totals")?.num("protein_g"))} g" + if (d.bool("protein_ok") == false) " (a little under the aim)" else "",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                d.objs("meals").forEach { m ->
                    BubbleCard(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Eyebrow(m.str("label") ?: m.str("slot").orEmpty())
                                    Text(m.str("name").orEmpty(), style = MaterialTheme.typography.titleMedium)
                                }
                                Pill("Swap", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer) {
                                    swapping = day to m
                                    options = emptyList()
                                    send.send("POST", "/fitness/diet/swap-options", buildJsonObject { put("day", day); put("slot", m.str("slot").orEmpty()) }) { options = it.objs("options") }
                                }
                            }
                            m.objs("items").forEach { i -> Text("${fmtNum(i.num("quantity"))} ${i.str("unit").orEmpty()} ${i.str("food").orEmpty()}", style = MaterialTheme.typography.bodyMedium) }
                            Text("About ${fmtNum(m.obj("totals")?.num("kcal"))} kcal", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill("Grocery list", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) {
                        grocery = null
                        send.send("GET", "/fitness/diet/grocery?people=1") { grocery = it }
                    }
                    Pill("New week", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) {
                        send.send("POST", "/fitness/diet/plan", buildJsonObject { put("meals_per_day", doc.int("meals_per_day") ?: 4); put("seed", (System.currentTimeMillis() % 1000).toInt()) }) { loader.reload() }
                    }
                }
                grocery?.let { g ->
                    Eyebrow("Grocery list")
                    // The server sends aisles as an object: aisle name -> list of items.
                    (g.obj("aisles") ?: JsonObject(emptyMap())).forEach { (aisle, list) ->
                        BubbleCard(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp)) {
                                Text(aisle, style = MaterialTheme.typography.titleSmall)
                                (list as? kotlinx.serialization.json.JsonArray).orEmpty().mapNotNull { it as? JsonObject }.forEach { i ->
                                    Text("${i.str("food").orEmpty()}  ${i.str("quantity").orEmpty()}", style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                    g.str("note")?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
            ClinicalNote(doc.obj("review"))
            Disclaimer()
        }
    }

    swapping?.let { (d, current) ->
        AlertDialog(
            onDismissRequest = { swapping = null },
            title = { Text("Swap ${current.str("label") ?: "meal"}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (options.isEmpty()) Text(if (send.busy.value) "Looking for swaps…" else "No safe swaps right now.")
                    options.forEach { o ->
                        TextButton({
                            val id = o.str("template_id").orEmpty()
                            swapping = null
                            send.send("POST", "/fitness/diet/swap", buildJsonObject { put("day", d); put("slot", current.str("slot").orEmpty()); put("template_id", id) }) { loader.reload() }
                        }) { Text("${o.str("name").orEmpty()}  ·  about ${fmtNum(o.obj("totals")?.num("kcal"))} kcal") }
                    }
                }
            },
            confirmButton = {},
            dismissButton = { TextButton({ swapping = null }) { Text("Cancel") } },
        )
    }
}
