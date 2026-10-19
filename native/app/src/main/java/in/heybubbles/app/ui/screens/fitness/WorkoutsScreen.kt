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
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
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
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.CheckRow
import `in`.heybubbles.app.ui.components.ChoiceChips
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.LocalDate

/**
 * Safety questions first, then a weekly plan. The questions, what counts as a "see a clinician first" answer and the gentle fallback
 * plan all come from the server; this screen asks, sends, and shows what it answers.
 */
@Composable
fun WorkoutsScreen(api: Api, onBack: () -> Unit) {
    val body = rememberLoad(api, "/profile/body")
    val plan = rememberLoad(api, "/fitness/workouts/plan")
    var redo by remember { mutableStateOf(false) }

    FitnessPage("Move in a way that suits you", "Workouts", onBack) {
        Text("A short safety check first, then a weekly plan you can bend to your day.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        LoadGate(body) { b ->
            ClinicalNote(b.obj("review"))
            LoadGate(plan) { doc ->
                val screen = doc.obj("screen")
                val answered = screen != null && screen.str("mode") != "incomplete"
                val refresh = { redo = false; plan.reload() }
                if (!answered || redo) Screening(api, b.objs("parq_questions"), screen?.obj("answers"), refresh, if (redo) ({ redo = false }) else null)
                else {
                    if (screen?.str("mode") == "clinician_first") ClinicianFirst(api, doc, b.obj("profile")?.obj("clinician_clearance") != null, refresh)
                    else screen?.str("message")?.takeIf { it.isNotBlank() }?.let { Note("Safety check done", it, Bubbles.TintMint) }
                    PlanSection(api, doc, b, plan.reload)
                    Pill("Redo the safety questions", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { redo = true }
                }
                Disclaimer()
            }
        }
    }
}

@Composable
private fun Note(title: String, text: String, tint: androidx.compose.ui.graphics.Color) {
    BubbleCard(Modifier.fillMaxWidth(), tint = tint) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun Screening(api: Api, questions: List<JsonObject>, initial: JsonObject?, onDone: () -> Unit, onCancel: (() -> Unit)?) {
    val send = rememberSender(api)
    var answers by remember { mutableStateOf(questions.associate { q -> val k = q.str("key").orEmpty(); k to initial?.bool(k) }) }
    Eyebrow("Before you start")
    Text("Answer each one honestly. A yes never stops you, it just means Bubbles keeps things gentle or suggests checking with a doctor first.", style = MaterialTheme.typography.bodyMedium)
    questions.forEach { q ->
        val key = q.str("key").orEmpty()
        BubbleCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(q.str("text").orEmpty(), style = MaterialTheme.typography.bodyLarge)
                ChoiceChips("", listOf("yes" to "Yes", "no" to "No"), when (answers[key]) { true -> "yes"; false -> "no"; else -> "" }, { answers = answers + (key to (it == "yes")) })
            }
        }
    }
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    val missing = answers.values.any { it == null }
    if (missing) Text("Please answer every question.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Pill(if (send.busy.value) "Saving…" else "Continue", if (missing) MaterialTheme.colorScheme.surfaceVariant else Bubbles.Pink, if (missing) MaterialTheme.colorScheme.onSurfaceVariant else Bubbles.White) {
            if (missing) return@Pill
            val body = buildJsonObject { put("answers", JsonObject(answers.mapValues { JsonPrimitive(it.value == true) })) }
            send.send("POST", "/fitness/workouts/screen", body) { onDone() }
        }
        onCancel?.let { Pill("Cancel", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface, onClick = it) }
    }
}

@Composable
private fun ClinicianFirst(api: Api, doc: JsonObject, hasClearance: Boolean, onChanged: () -> Unit) {
    val send = rememberSender(api)
    var ok by remember { mutableStateOf(false) }
    Note("Please talk to a clinician first", doc.obj("screen")?.str("message").orEmpty() + "\n\nUntil then Bubbles only suggests easy walking and gentle stretching, which are below. Nothing here is a reason to worry, it just means a doctor should look at the full picture.", Bubbles.TintSun)
    BubbleCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Already checked with a doctor?", style = MaterialTheme.typography.titleSmall)
            CheckRow("A doctor has said I can start exercising", ok) { ok = it }
            send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            if (ok) Pill(if (send.busy.value) "Saving…" else "Record this", Bubbles.Pink, Bubbles.White) {
                // A dated record limited to exercise, so it can never stand in for a strict-plan sign-off; an existing record is never overwritten.
                val record = {
                    send.send("POST", "/fitness/workouts/screen", buildJsonObject {
                        put("answers", doc.obj("screen")?.obj("answers") ?: JsonObject(emptyMap())); put("clinician_cleared", true)
                    }) { onChanged() }
                }
                if (hasClearance) record() else send.send("PUT", "/profile/body", buildJsonObject {
                    put("clinician_clearance", buildJsonObject { put("cleared", true); put("date", LocalDate.now().toString()); put("areas", JsonArray(listOf(JsonPrimitive("exercise")))) })
                }) { record() }
            }
        }
    }
}

@Composable
private fun PlanSection(api: Api, doc: JsonObject, body: JsonObject, reload: () -> Unit) {
    var making by remember { mutableStateOf(false) }
    val plan = doc.obj("plan")
    if (doc.bool("exists") != true || plan == null || making) MakePlan(api, doc, body, { making = false; reload() }, if (doc.bool("exists") == true) ({ making = false }) else null)
    else PlanView(api, plan, reload) { making = true }
}

@Composable
private fun MakePlan(api: Api, doc: JsonObject, body: JsonObject, onDone: () -> Unit, onCancel: (() -> Unit)?) {
    val send = rememberSender(api)
    val p = doc.obj("params")
    var days by remember { mutableStateOf((p?.int("days_per_week") ?: 3).toString()) }
    var minutes by remember { mutableStateOf((p?.int("minutes") ?: 40).toString()) }
    var equipment by remember { mutableStateOf(p?.str("equipment") ?: "none") }
    var level by remember { mutableStateOf((p?.int("level") ?: 1).toString()) }
    Eyebrow(if (doc.bool("exists") == true) "Make a new plan" else "Build your first week")
    ChoiceChips("Days a week", (1..6).map { it.toString() to it.toString() }, days, { days = it }, hint = "Three is a great start. Rest days are part of the plan.")
    ChoiceChips("Time per session", listOf(20, 30, 40, 45, 60, 75).map { it.toString() to "$it min" }, minutes, { minutes = it })
    ChoiceChips("What can you use?", listOf("none" to "Nothing", "home" to "Home basics", "gym" to "Gym", "pool" to "Pool"), equipment, { equipment = it })
    ChoiceChips("Where are you now?", listOf("1" to "Just starting", "2" to "Some experience", "3" to "Quite experienced"), level, { level = it })
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Pill(if (send.busy.value) "Planning…" else "Make my plan", Bubbles.Pink, Bubbles.White) {
            send.send("POST", "/fitness/workouts/plan", buildJsonObject { put("days_per_week", days.toInt()); put("minutes", minutes.toInt()); put("equipment", equipment); put("level", level.toInt()) }) { onDone() }
        }
        onCancel?.let { Pill("Keep my current plan", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface, onClick = it) }
    }
}

@Composable
private fun PlanView(api: Api, plan: JsonObject, reload: () -> Unit, onRemake: () -> Unit) {
    val send = rememberSender(api)
    var feeling by remember { mutableStateOf<Pair<Int, JsonObject>?>(null) }
    var logging by remember { mutableStateOf<JsonObject?>(null) }
    var result by remember { mutableStateOf<JsonObject?>(null) }
    var logged by remember { mutableStateOf<String?>(null) }
    val sessions = plan.objs("sessions")
    val summary = plan.obj("summary")

    Eyebrow("Week ${plan.int("week_index") ?: 1}" + if (plan.bool("deload") == true) " · easier week" else "")
    plan.strs("notes").forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
    summary?.let {
        Text(
            "About ${fmtNum(it.num("moderate_equivalent_minutes"))} active minutes and ${fmtNum(it.num("strength_days"))} strength days" + if (it.bool("meets_who") == true) ", in line with general guidance." else ".",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    sessions.forEachIndexed { i, s ->
        BubbleCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Eyebrow(s.str("day").orEmpty())
                        Text("${s.str("label").orEmpty()} · ${fmtNum(s.num("minutes"))} min", style = MaterialTheme.typography.titleMedium)
                    }
                }
                listOf("warmup" to "Warm up", "main" to "Main", "cooldown" to "Cool down").forEach { (k, title) ->
                    val moves = s.objs(k)
                    if (moves.isNotEmpty()) {
                        Text(title, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 6.dp))
                        moves.forEach { m ->
                            val dose = listOfNotNull(m.int("sets")?.let { "$it sets" }, m.int("reps")?.let { "$it reps" }, m.int("seconds")?.let { "$it s" }).joinToString(" x ")
                            Text(m.str("name").orEmpty() + if (dose.isNotEmpty()) "  ·  $dose" else "", style = MaterialTheme.typography.bodyMedium)
                            m.str("cue")?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                    }
                }
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill("How do I feel?", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer) { feeling = i to s }
                    Pill("Log it", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { logging = s }
                }
            }
        }
    }
    logged?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = Bubbles.MintDeep) }
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    result?.let { r ->
        // "stop" is the server's call: pain, chest pain or feeling faint means rest, not a smaller workout.
        Note(if (r.bool("stop") == true) "Rest today" else "Adjusted for today", r.strs("messages").joinToString("\n"), if (r.bool("stop") == true) Bubbles.TintUrgent else Bubbles.TintSun)
    }
    Pill("Make a new plan", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface, onClick = onRemake)

    feeling?.let { (index, _) -> FeelingDialog(onDismiss = { feeling = null }) { fb ->
        feeling = null
        send.send("POST", "/fitness/workouts/adapt", buildJsonObject { put("session", index); put("feedback", fb) }) { result = it }
    } }
    logging?.let { s -> LogDialog(s, onDismiss = { logging = null }) { minutes, rpe ->
        logging = null
        send.send("POST", "/fitness/workouts/log", buildJsonObject { put("title", s.str("label").orEmpty().ifBlank { "Workout" }); put("minutes", minutes); if (rpe != null) put("rpe", rpe) }) {
            logged = "Logged. Nice work."; reload()
        }
    } }
}

@Composable
private fun FeelingDialog(onDismiss: () -> Unit, onSend: (JsonObject) -> Unit) {
    var pain by remember { mutableStateOf(false) }
    var chest by remember { mutableStateOf(false) }
    var dizzy by remember { mutableStateOf(false) }
    var sleep by remember { mutableStateOf(false) }
    var energy by remember { mutableStateOf(false) }
    var period by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("How do you feel today?") },
        text = {
            Column {
                CheckRow("Something hurts", pain) { pain = it }
                CheckRow("Chest pain or pressure", chest) { chest = it }
                CheckRow("Dizzy or faint", dizzy) { dizzy = it }
                CheckRow("I slept badly", sleep) { sleep = it }
                CheckRow("Low energy", energy) { energy = it }
                CheckRow("Heavy period", period) { period = it }
            }
        },
        confirmButton = {
            TextButton({
                onSend(buildJsonObject {
                    if (pain) put("pain", true); if (chest) put("chest_pain", true); if (dizzy) { put("dizzy", true); put("fainting", true) }
                    if (sleep) put("poor_sleep", true); if (energy) put("low_energy", true); if (period) put("heavy_period", true)
                })
            }) { Text("Adjust my session") }
        },
        dismissButton = { TextButton(onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun LogDialog(session: JsonObject, onDismiss: () -> Unit, onSave: (Int, Int?) -> Unit) {
    var minutes by remember { mutableStateOf((session.int("minutes") ?: 30).toString()) }
    var rpe by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Log ${session.str("label").orEmpty()}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                `in`.heybubbles.app.ui.components.FieldRow("Minutes", minutes, { minutes = it.filter(Char::isDigit) }, number = true, maxLength = 3)
                `in`.heybubbles.app.ui.components.FieldRow("How hard, 0 to 10 (optional)", rpe, { rpe = it.filter(Char::isDigit) }, number = true, maxLength = 2)
            }
        },
        confirmButton = { TextButton({ val m = minutes.toIntOrNull() ?: 0; if (m > 0) onSave(m, rpe.toIntOrNull()?.coerceIn(0, 10)) }) { Text("Save") } },
        dismissButton = { TextButton(onDismiss) { Text("Cancel") } },
    )
}
