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
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.FitnessCalc
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.fmtNum
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.CheckRow
import `in`.heybubbles.app.ui.components.ChoiceChips
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.FieldRow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles

/** Pure rule the UI leans on: only these two server decisions may ever lead to a start button. Everything else is a refusal or an incomplete screen. */
fun canStartTransform(decision: String?): Boolean = decision == "allowed" || decision == "allowed_with_cautions"

/**
 * Strict transformation: a structured plan toward a target weight, behind a screening for disordered eating, recent loss of periods,
 * pregnancy and the like. The questions, every refusal and the calorie floors are the server's. The app never decides a person is safe:
 * it asks, shows the verdict and the gentler alternative, and only offers Start when the server says allowed. The server re-checks on start.
 */
@Composable
fun TransformScreen(api: Api, onBack: () -> Unit, open: (String) -> Unit = {}) {
    val plan = rememberLoad(api, "/fitness/transform/plan")
    FitnessPage("A structured plan, carefully", "Strict transformation", onBack) {
        LoadGate(plan) { doc ->
            val p = doc.obj("plan")
            if (doc.bool("exists") == true && p != null && p.str("status") != "completed") Dashboard(api, p, plan.reload)
            else StartFlow(api, finished = p?.str("status") == "completed", onStarted = plan.reload, open = open)
            ClinicalNote(doc.obj("review"))
            Disclaimer()
        }
    }
}

// ---- before a plan: screening, preview, start ---------------------------------------------------------------------------------------

@Composable
private fun StartFlow(api: Api, finished: Boolean, onStarted: () -> Unit, open: (String) -> Unit) {
    val body = rememberLoad(api, "/profile/body")
    LoadGate(body) { b ->
        val questions = b.strs("scoff_questions")
        val profile = b.obj("profile")
        val imperial = profile?.str("units") == "imperial"
        val send = rememberSender(api)
        var target by remember { mutableStateOf(FitnessCalc.weightText(profile?.num("target_weight_kg"), imperial)) }
        var answers by remember { mutableStateOf<List<Boolean?>>(List(questions.size) { null }) }
        var surgery by remember { mutableStateOf(false) }
        var days by remember { mutableStateOf("4") }
        var equipment by remember { mutableStateOf("none") }
        var result by remember { mutableStateOf<JsonObject?>(null) }
        var ack by remember { mutableStateOf(false) }

        if (finished) Text("Your last plan is finished. You can screen again whenever you like.", style = MaterialTheme.typography.bodyMedium)
        Text(
            "This is a careful, structured plan. It starts with a short screening, because strict plans are not right for everyone, and Bubbles would rather say so than guess.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        FieldRow("Target weight", target, { target = it; result = null }, number = true, suffix = if (imperial) "lb" else "kg", maxLength = 6)

        Eyebrow("A few honest questions")
        Text("There are no wrong answers. They help Bubbles decide whether a strict plan is a kind choice for you right now.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        questions.forEachIndexed { i, q ->
            BubbleCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(q, style = MaterialTheme.typography.bodyLarge)
                    ChoiceChips("", listOf("yes" to "Yes", "no" to "No"), when (answers[i]) { true -> "yes"; false -> "no"; else -> "" }, { v ->
                        answers = answers.toMutableList().also { it[i] = v == "yes" }; result = null
                    })
                }
            }
        }
        CheckRow("I recently had surgery or an injury", surgery) { surgery = it; result = null }
        ChoiceChips("Training days a week", (1..6).map { it.toString() to it.toString() }, days, { days = it; result = null })
        ChoiceChips("What can you use?", listOf("none" to "Nothing", "home" to "Home basics", "gym" to "Gym", "pool" to "Pool"), equipment, { equipment = it; result = null })

        val complete = answers.none { it == null } && FitnessCalc.weightKg(target, imperial) != null
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        if (!complete) Text("Answer every question and add a target weight to continue.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

        fun request(): JsonObject = buildJsonObject {
            put("scoff", JsonArray(answers.map { JsonPrimitive(it == true) }))
            put("target_weight_kg", FitnessCalc.weightKg(target, imperial) ?: 0.0)
            put("recent_surgery_or_injury", surgery)
            put("selections", buildJsonObject { put("days_per_week", days.toInt()); put("equipment", equipment) })
        }
        Pill(if (send.busy.value) "Checking…" else "Check and preview", if (complete) Bubbles.Pink else MaterialTheme.colorScheme.surfaceVariant, if (complete) Bubbles.White else MaterialTheme.colorScheme.onSurfaceVariant) {
            if (complete) send.send("POST", "/fitness/transform/preview", request()) { result = it; ack = false }
        }

        result?.let { r ->
            val screening = r.obj("screening")
            val decision = screening?.str("decision")
            Verdict(screening, send, open) { send.send("POST", "/fitness/transform/preview", request()) { result = it; ack = false } }
            if (canStartTransform(decision)) {
                r.obj("preview")?.let { pv -> Preview(pv) }
                CheckRow("I have read this and I understand I can pause at any time", ack) { ack = it }
                Pill(if (send.busy.value) "Starting…" else "Start my plan", if (ack) Bubbles.Pink else MaterialTheme.colorScheme.surfaceVariant, if (ack) Bubbles.White else MaterialTheme.colorScheme.onSurfaceVariant) {
                    if (ack) send.send("POST", "/fitness/transform/start", request().let { JsonObject(it + ("acknowledged" to JsonPrimitive(true))) }) { onStarted() }
                }
            }
        }
    }
}

/**
 * The screening verdict in the server's own words, including why and what to do instead. Never softened, never hidden. [alternative] is a
 * code from the server ("support", "clinician", anything else means a gentle plan), so it is turned into words here, never printed raw.
 */
@Composable
private fun Verdict(screening: JsonObject?, send: Sender, open: (String) -> Unit, recheck: () -> Unit) {
    if (screening == null) return
    val decision = screening.str("decision")
    val tint = when (decision) { "allowed" -> Bubbles.TintMint; "allowed_with_cautions" -> Bubbles.TintSun; else -> Bubbles.TintUrgent }
    BubbleCard(Modifier.fillMaxWidth(), tint = tint) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                when (decision) { "allowed" -> "You can go ahead"; "allowed_with_cautions" -> "You can go ahead, with some care"; "incomplete" -> "A few details are missing"; else -> "A strict plan is not the right fit right now" },
                style = MaterialTheme.typography.titleMedium,
            )
            screening.str("message")?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            screening.objs("exclusions").forEach { e ->
                Text(e.str("label").orEmpty(), style = MaterialTheme.typography.titleSmall)
                Text(e.str("message").orEmpty(), style = MaterialTheme.typography.bodyMedium)
            }
            screening.strs("cautions").forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
        }
    }
    if (canStartTransform(decision) || decision == "incomplete") return
    val alt = screening.str("alternative")
    BubbleCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("What Bubbles can do instead", style = MaterialTheme.typography.titleSmall)
            Text(
                when (alt) {
                    "support" -> "Food can feel heavy sometimes, and you do not have to carry that alone. Talking to a doctor, a counsellor or someone you trust can really help. In India, Tele-MANAS (14416) is free and open day and night, and 112 is there for an emergency."
                    "clinician" -> "Please check with your doctor first. When they say a structured plan is fine, come back and Bubbles will be ready. Meanwhile a gentle plan is available."
                    else -> "A gentle plan without strict targets fits you well right now: steady meals and easy movement."
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (screening.bool("gentle_available") == true || alt == "gentle" || alt == "clinician") {
                    Pill("Gentle diet plan", Bubbles.Pink, Bubbles.White) { open("diet") }
                    Pill("Gentle workouts", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { open("workouts") }
                }
            }
        }
    }
    // A clinician's agreement can lift an exclusion only when the server marks every one of them clearable for a named area.
    val ex = screening.objs("exclusions")
    val clearable = ex.isNotEmpty() && ex.all { it.bool("clearable") == true && !it.str("area").isNullOrBlank() }
    if (clearable) {
        var ok by remember { mutableStateOf(false) }
        BubbleCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Has your clinician already agreed to this plan?", style = MaterialTheme.typography.titleSmall)
                CheckRow("My clinician has approved a structured weight-loss plan for me", ok) { ok = it }
                send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
                if (ok) Pill(if (send.busy.value) "Saving\u2026" else "Record this and check again", Bubbles.Pink, Bubbles.White) {
                    val areas = ex.mapNotNull { it.str("area") }.distinct()
                    send.send("PUT", "/profile/body", buildJsonObject {
                        put("clinician_clearance", buildJsonObject {
                            put("cleared", true); put("date", java.time.LocalDate.now().toString()); put("areas", JsonArray(areas.map(::JsonPrimitive)))
                        })
                    }) { recheck() }
                }
            }
        }
    }
}

@Composable
private fun Preview(pv: JsonObject) {
    val t = pv.obj("targets")
    Eyebrow("Your plan, before you start")
    BubbleCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("About ${fmtNum(t?.num("kcal"))} kcal a day", style = MaterialTheme.typography.titleMedium)
            Text("Protein ${fmtNum(t?.num("protein_g"))} g, water about ${"%.1f".format((t?.num("water_ml") ?: 0.0) / 1000.0)} L, steps ${fmtNum(t?.num("steps"))}", style = MaterialTheme.typography.bodyMedium)
            t?.num("pace_kg_per_week")?.let { Text("Pace about ${"%.2f".format(it)} kg a week, never faster than Bubbles allows", style = MaterialTheme.typography.bodyMedium) }
            if (t?.bool("at_floor") == true) Text("This is already at the lowest safe amount, so the plan will not go lower.", style = MaterialTheme.typography.bodyMedium, color = Bubbles.PinkInk)
            t?.strs("notes").orEmpty().forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
    pv.strs("good_day").takeIf { it.isNotEmpty() }?.let { g ->
        Text("A good day looks like", style = MaterialTheme.typography.titleSmall)
        g.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
    }
    pv.strs("pause_symptoms").takeIf { it.isNotEmpty() }?.let { s ->
        BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintUrgent) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Pause and talk to a doctor if you notice", style = MaterialTheme.typography.titleSmall)
                s.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
            }
        }
    }
    pv.strs("commit_text").forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
}

// ---- a plan in progress ---------------------------------------------------------------------------------------------------------------

@Composable
private fun Dashboard(api: Api, plan: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    val status = plan.str("status")
    val paused = status == "paused"
    var confirmFinish by remember { mutableStateOf(false) }
    var checkin by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<JsonObject?>(null) }

    BubbleCard(Modifier.fillMaxWidth(), tint = if (paused) Bubbles.TintSun else Bubbles.TintGrape) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(if (paused) "Paused" else "In progress", style = MaterialTheme.typography.titleMedium)
            Text("Week ${plan.num("weeks_on_plan")?.toInt()?.plus(1) ?: 1}. Started at ${fmtNum(plan.num("start_weight_kg"))} kg, target ${fmtNum(plan.num("target_weight_kg"))} kg.", style = MaterialTheme.typography.bodyMedium)
            plan.obj("paused")?.str("reason")?.takeIf { paused && it.isNotBlank() }?.let { Text("Reason: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }

    if (!paused) {
        val today = rememberLoad(api, "/fitness/transform/today")
        LoadGate(today) { t ->
            val v = t.obj("view")
            v?.str("message")?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
            v?.obj("budget")?.let { b -> Text("About ${fmtNum(b.num("remaining_kcal"))} kcal left today (${fmtNum(b.num("eaten_kcal"))} of ${fmtNum(b.num("budget_kcal"))})", style = MaterialTheme.typography.bodyMedium) }
            v?.obj("protein")?.let { Text("Protein ${fmtNum(it.num("eaten_g"))} of ${fmtNum(it.num("target_g"))} g", style = MaterialTheme.typography.bodyMedium) }
            v?.obj("water")?.let { Text("Water ${fmtNum(it.num("drunk_ml"))} of ${fmtNum(it.num("target_ml"))} ml", style = MaterialTheme.typography.bodyMedium) }
            t.obj("meals")?.objs("meals")?.takeIf { it.isNotEmpty() }?.let { meals ->
                Eyebrow("Today's meals")
                meals.forEach { m -> Text("${m.str("label").orEmpty()}: ${m.str("name").orEmpty()}", style = MaterialTheme.typography.bodyMedium) }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("Weekly check-in", Bubbles.Pink, Bubbles.White) { checkin = true }
            Pill("Pause", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) {
                send.send("POST", "/fitness/transform/pause", buildJsonObject { put("reason", "I chose to pause") }) { reload() }
            }
        }
    } else {
        Text("While paused, nothing here asks anything of you. When you are ready, Bubbles checks again that a strict plan is still a kind choice.", style = MaterialTheme.typography.bodyMedium)
        Pill(if (send.busy.value) "Checking…" else "Resume", Bubbles.Pink, Bubbles.White) { send.send("POST", "/fitness/transform/resume", JsonObject(emptyMap())) { reload() } }
    }
    Pill("Finish my plan", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { confirmFinish = true }

    result?.let { r -> CheckinResult(r, send, onApplied = { result = null; reload() }) }

    if (checkin) CheckinDialog(onDismiss = { checkin = false }) { body ->
        checkin = false
        send.send("POST", "/fitness/transform/checkin", body) { result = it; if (it.bool("applied") == true) reload() }
    }
    if (confirmFinish) AlertDialog(
        onDismissRequest = { confirmFinish = false },
        title = { Text("Finish this plan?") },
        text = { Text("Bubbles will help you move to maintenance, easing up gradually.") },
        confirmButton = { TextButton({ confirmFinish = false; send.send("POST", "/fitness/transform/finish", JsonObject(emptyMap())) { reload() } }) { Text("Finish") } },
        dismissButton = { TextButton({ confirmFinish = false }) { Text("Not yet") } },
    )
}

@Composable
private fun CheckinResult(r: JsonObject, send: Sender, onApplied: () -> Unit) {
    val decision = r.str("decision")
    val tint: Color = if (decision == "pause") Bubbles.TintUrgent else Bubbles.TintSun
    BubbleCard(Modifier.fillMaxWidth(), tint = tint) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                when (decision) { "pause" -> "Your plan is paused for your safety"; "adjust" -> "A small change is suggested"; "continue" -> "Keep going as you are"; else -> "Not enough to go on yet" },
                style = MaterialTheme.typography.titleMedium,
            )
            r.strs("messages").forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
            r.strs("reasoning").forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            if ((decision == "adjust" || decision == "continue") && r.bool("applied") != true) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("Accept", Bubbles.Pink, Bubbles.White) { send.send("POST", "/fitness/transform/checkin/apply", buildJsonObject { put("accept", true) }) { onApplied() } }
                Pill("Not this week", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { send.send("POST", "/fitness/transform/checkin/apply", buildJsonObject { put("accept", false) }) { onApplied() } }
            }
        }
    }
}

@Composable
private fun CheckinDialog(onDismiss: () -> Unit, onSend: (JsonObject) -> Unit) {
    var dizzy by remember { mutableStateOf(false) }
    var faint by remember { mutableStateOf(false) }
    var palp by remember { mutableStateOf(false) }
    var chest by remember { mutableStateOf(false) }
    var luteal by remember { mutableStateOf(false) }
    var note by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Weekly check-in") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("Have you had any of these this week?", style = MaterialTheme.typography.bodyMedium)
                CheckRow("Dizziness", dizzy) { dizzy = it }
                CheckRow("Fainting", faint) { faint = it }
                CheckRow("Racing or fluttering heart", palp) { palp = it }
                CheckRow("Chest pain", chest) { chest = it }
                CheckRow("I am near my period (weight can be higher)", luteal) { luteal = it }
                OutlinedTextField(note, { note = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text("Anything you want to say (optional)") }, minLines = 2)
            }
        },
        confirmButton = {
            TextButton({
                onSend(buildJsonObject {
                    put("symptoms", buildJsonObject { put("dizzy", dizzy); put("fainting", faint); put("palpitations", palp); put("chest_pain", chest) })
                    put("in_luteal_or_period", luteal)
                    if (note.isNotBlank()) put("note", note)
                })
            }) { Text("Check in") }
        },
        dismissButton = { TextButton(onDismiss) { Text("Cancel") } },
    )
}
