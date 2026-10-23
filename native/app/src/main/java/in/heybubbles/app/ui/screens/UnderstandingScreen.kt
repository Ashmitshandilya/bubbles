package `in`.heybubbles.app.ui.screens

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
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.screens.fitness.FitnessPage
import `in`.heybubbles.app.ui.screens.fitness.LoadGate
import `in`.heybubbles.app.ui.screens.fitness.rememberLoad
import `in`.heybubbles.app.ui.screens.fitness.rememberSender

/**
 * How Bubbles understands you: every trait it holds, with the reason and a word for how sure it is. "That's me" and "Not me" change it for good,
 * and "Start fresh" wipes the lot. The server owns the rules (confidence, what is used); this screen only shows and sends the two choices.
 */
@Composable
fun UnderstandingScreen(api: Api, onBack: () -> Unit) {
    val load = rememberLoad(api, "/me/understanding")
    FitnessPage("How Bubbles understands you", eyebrow = "Me", onBack = onBack) {
        Text(
            "What Bubbles has noticed about how you like to be talked to. It is only ever used to choose words, and you can correct any line.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        LoadGate(load) { d -> Body(api, d) { load.reload() } }
    }
}

@Composable
private fun Body(api: Api, d: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    var clearing by remember { mutableStateOf(false) }
    val traits = d.objs("traits")
    if (traits.isEmpty()) {
        Text(d.str("intro") ?: "Bubbles is still getting to know you.", style = MaterialTheme.typography.titleLarge)
        val would = d.strs("would_use")
        if (would.isNotEmpty()) Text("As you chat, it will pick up ${would.dropLast(1).joinToString(", ").let { if (it.isEmpty()) would.last() else "$it and ${would.last()}" }}.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    traits.forEach { t ->
        val id = t.str("id").orEmpty()
        Column(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(t.str("line").orEmpty(), style = MaterialTheme.typography.titleMedium)
            Text("${t.str("confidence").orEmpty()}.${t.str("why")?.takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (t.str("state") == "confirmed") Text("You said this is right", Modifier.heightIn(min = 48.dp).padding(top = 12.dp), style = MaterialTheme.typography.labelLarge)
                else TextButton(onClick = { send.send("PUT", "/me/understanding/$id", buildJsonObject { put("action", "confirm") }) { reload() } }, Modifier.heightIn(min = 48.dp)) { Text("That's me") }
                TextButton(onClick = { send.send("PUT", "/me/understanding/$id", buildJsonObject { put("action", "reject") }) { reload() } }, Modifier.heightIn(min = 48.dp)) { Text("Not me") }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    Eyebrow("Start fresh")
    if (clearing) {
        Text("Clear everything Bubbles has learned, including the lines you said were not you?", style = MaterialTheme.typography.bodyMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("Yes, clear it", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, Modifier.heightIn(min = 48.dp)) { send.send("DELETE", "/me/understanding") { clearing = false; reload() } }
            Pill("Keep it", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant, Modifier.heightIn(min = 48.dp)) { clearing = false }
        }
    } else TextButton(onClick = { clearing = true }, Modifier.heightIn(min = 48.dp)) { Text("Clear what Bubbles has learned") }
}
