package `in`.heybubbles.app.ui.screens.fitness

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import `in`.heybubbles.app.data.fmtNum
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.ChoiceChips
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles

private val MEALS = listOf("" to "Any", "breakfast" to "Breakfast", "lunch" to "Lunch", "dinner" to "Dinner", "snack" to "Snack")

/** "2 rotis, dal and curd" in, an estimate out. Nothing is saved until the person confirms the preview. */
@Composable
fun FoodLogScreen(api: Api, onBack: () -> Unit) {
    val loader = rememberLoad(api, "/fitness/food-log")
    val send = rememberSender(api)
    var text by remember { mutableStateOf("") }
    var meal by remember { mutableStateOf("") }
    var preview by remember { mutableStateOf<JsonObject?>(null) }
    var deleting by remember { mutableStateOf<JsonObject?>(null) }

    FitnessPage("Say what you ate", "Calorie calculator", onBack) {
        Text(
            "Type it the way you would say it. Bubbles turns it into an estimate and you confirm it. Estimates are never exact, and close is good enough.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            text, { text = it.take(2000); preview = null }, Modifier.fillMaxWidth(), label = { Text("What did you eat?") },
            placeholder = { Text("2 rotis, dal and curd") }, shape = MaterialTheme.shapes.medium, minLines = 2,
        )
        ChoiceChips("Meal", MEALS, meal, { meal = it })
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        Pill(if (send.busy.value) "Working…" else "Estimate it", Bubbles.Pink, Bubbles.White) {
            if (text.isBlank()) return@Pill
            send.send("POST", "/fitness/meal/parse", buildJsonObject { put("text", text) }) { preview = it }
        }

        preview?.let { p ->
            PreviewCard(p) {
                send.send("POST", "/fitness/food-log", buildJsonObject { put("text", text); if (meal.isNotEmpty()) put("meal", meal) }) {
                    text = ""; preview = null; loader.reload()
                }
            }
        }

        Eyebrow("Today")
        LoadGate(loader) { log ->
            val entries = log.objs("entries")
            val totals = log.obj("totals")
            val budget = log.obj("budget")
            if (entries.isEmpty()) Text("Nothing logged today yet. That is not the same as eating nothing.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            else {
                BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintMint) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("About ${fmtNum(totals?.num("kcal"))} kcal so far", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Protein ${fmtNum(totals?.num("protein_g"))} g, carbs ${fmtNum(totals?.num("carbs_g"))} g, fat ${fmtNum(totals?.num("fat_g"))} g",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        budget?.num("remaining_kcal")?.let { Text(if (it >= 0) "About ${fmtNum(it)} kcal left today" else "A little over today, and that is fine", style = MaterialTheme.typography.bodyMedium) }
                    }
                }
                entries.forEach { e ->
                    BubbleCard(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Column(Modifier.weight(1f)) {
                                Text(e.str("text").orEmpty(), style = MaterialTheme.typography.bodyLarge)
                                Text(
                                    listOfNotNull(e.str("meal")?.replaceFirstChar { it.uppercase() }, "about ${fmtNum(e.obj("totals")?.num("kcal"))} kcal").joinToString(" · "),
                                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Pill("Delete", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant) { deleting = e }
                        }
                    }
                }
            }
            Disclaimer()
        }
    }

    deleting?.let { e ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Delete this entry?") },
            text = { Text(e.str("text").orEmpty()) },
            confirmButton = { TextButton({ val id = e.str("id").orEmpty(); deleting = null; send.send("DELETE", "/fitness/food-log/$id") { loader.reload() } }) { Text("Delete", color = Bubbles.Urgent) } },
            dismissButton = { TextButton({ deleting = null }) { Text("Keep it") } },
        )
    }
}

@Composable
private fun PreviewCard(p: JsonObject, onConfirm: () -> Unit) {
    val totals = p.obj("totals")
    BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintSun) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Here is what Bubbles heard", style = MaterialTheme.typography.titleSmall)
            p.objs("items").forEach { i ->
                Text("${fmtNum(i.num("quantity"))} ${i.str("unit").orEmpty()} ${i.str("food").orEmpty()}  ·  about ${fmtNum(i.num("kcal"))} kcal", style = MaterialTheme.typography.bodyMedium)
            }
            val low = totals?.num("kcal_low"); val high = totals?.num("kcal_high")
            Text(
                "About ${fmtNum(totals?.num("kcal"))} kcal" + if (low != null && high != null) " (somewhere between ${fmtNum(low)} and ${fmtNum(high)})" else "",
                style = MaterialTheme.typography.titleMedium,
            )
            p.strs("unrecognised").takeIf { it.isNotEmpty() }?.let { Text("Not recognised, so not counted: ${it.joinToString(", ")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            // Allergy and diet conflicts, and the gentle note when the wording sounds like food feels hard, come from the server and are always shown.
            p.strs("warnings").forEach { Text(it, style = MaterialTheme.typography.bodyMedium, color = Bubbles.PinkInk) }
            p.strs("notes").forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            p.str("support")?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = Bubbles.GrapeDeep) }
            if (p.objs("items").isNotEmpty()) Pill("Add to my day", Bubbles.Pink, Bubbles.White, onClick = onConfirm)
        }
    }
}
