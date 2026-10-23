package `in`.heybubbles.app.ui.screens.orbit

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.net.Uri
import android.view.WindowManager
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.OrbitLogic
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.ChoiceChips
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.MultiChips
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.screens.TalkScreen
import `in`.heybubbles.app.ui.screens.fitness.FitnessPage
import `in`.heybubbles.app.ui.screens.fitness.LoadGate
import `in`.heybubbles.app.ui.screens.fitness.Loader
import `in`.heybubbles.app.ui.screens.fitness.rememberLoad
import `in`.heybubbles.app.ui.screens.fitness.rememberSender
import `in`.heybubbles.app.ui.theme.Bubbles

private val DuskBg = Color(0xFF1B1626)
private val DuskSoft = Color(0xFF2A2238)
private val DuskText = Color(0xFFF3ECE6)
private val DuskAccent = Color(0xFFE9C98B)

/** Heart-to-heart and the Orbit hero: a late-night conversation, clearly different from Talk. Text on the plum background is AA. */
@Composable
private fun Dusk(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            background = DuskBg, surface = DuskSoft, surfaceVariant = DuskSoft, onBackground = DuskText, onSurface = DuskText, onSurfaceVariant = Color(0xFFC9BFD6),
            primary = DuskAccent, onPrimary = DuskBg, primaryContainer = Color(0xFF3B2F52), onPrimaryContainer = DuskText, outlineVariant = Color(0xFF43385A),
        ),
        typography = MaterialTheme.typography, shapes = MaterialTheme.shapes,
    ) { Box(Modifier.fillMaxSize().background(DuskBg)) { content() } }
}

/** No screenshots and a blank recent-apps card while Orbit is open (plan 7.6.2). Cleared when the screen is left. */
@Composable
private fun SecureWindow() {
    val view = LocalView.current
    DisposableEffect(Unit) {
        val window = view.context.activity()?.window
        window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose { window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
    }
}

private tailrec fun Context.activity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.activity()
    else -> null
}

/** Orbit: the relationship space. Everything private stays private; the server decides what a connected partner can ever see. */
@Composable
fun OrbitScreen(api: Api, onBack: () -> Unit) {
    var page by rememberSaveable { mutableStateOf("home") }
    SecureWindow()
    val back = { page = "home" }
    when (page) {
        "talk" -> Dusk { TalkScreen(api, mode = "orbit", onBack = back) }
        "reply" -> ReplyPage(api, back)
        "text" -> TextPage(api, back)
        "ritual" -> RitualPage(api, back)
        "fight" -> FightPage(api, back)
        "map" -> MapPage(api, back)
        "harbor" -> HarborPage(api, back)
        else -> OrbitHome(api, onBack) { page = it }
    }
}

@Composable
private fun OrbitRow(label: String, value: String? = null, onClick: () -> Unit) {
    Column {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable(role = Role.Button, onClick = onClick).padding(vertical = 12.dp, horizontal = 2.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(label, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            if (value != null) Text(value, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun OrbitHome(api: Api, onHide: () -> Unit, go: (String) -> Unit) {
    val home = rememberLoad(api, "/orbit")
    FitnessPage("Orbit", eyebrow = "Your closest people", onBack = onHide) {
        LoadGate(home) { h ->
            Dusk {
                Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Eyebrow("Orbit", color = DuskAccent)
                    Text(OrbitLogic.lede(h), style = MaterialTheme.typography.titleLarge, color = DuskText)
                    h.str("partner_name")?.let { Text("With $it", style = MaterialTheme.typography.bodyMedium, color = Color(0xFFC9BFD6)) }
                }
            }
            if (h.obj("profile")?.str("status") == null) ProfileForm(api, null) { home.reload() }
            else {
                Eyebrow("Together")
                OrbitRow("Heart-to-heart", "Talk it through") { go("talk") }
                OrbitRow("Help me reply", "Find the words") { go("reply") }
                OrbitRow("Before I text them", "Pause, then say it softly") { go("text") }
                OrbitRow("Today's question", if (h.obj("question")?.bool("answered") == true) "Answered" else "Waiting") { go("ritual") }
                OrbitRow("After a fight", "Repair") { go("fight") }
                OrbitRow("Understand them") { go("map") }
                if (h.bool("weather_paused") == true) Text("Gentle nudges to your partner are paused for now. Nothing changes on their side.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton(onClick = { go("harbor") }, Modifier.heightIn(min = 48.dp)) { Text("Feeling unsafe at home?") }
        }
    }
}

@Composable
private fun ProfileForm(api: Api, initial: JsonObject?, onSaved: () -> Unit) {
    val send = rememberSender(api)
    var status by remember { mutableStateOf(initial?.str("status").orEmpty()) }
    var cared by remember { mutableStateOf(initial?.strs("cared_for_by").orEmpty().toSet()) }
    var conflict by remember { mutableStateOf(initial?.str("conflict_style").orEmpty()) }
    var word by remember { mutableStateOf(initial?.str("partner_word").orEmpty()) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Eyebrow("Where are you right now?")
        Text("Pick what fits. You can change it any time, and Orbit works whatever you choose.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        ChoiceChips("", OrbitLogic.STATUS, status, onSelect = { status = it })
        OutlinedTextField(word, { word = it.take(20) }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("What do you call them? (optional)") }, shape = MaterialTheme.shapes.medium)
        MultiChips("What makes you feel cared for? (optional)", OrbitLogic.CARED, cared, { cared = it })
        ChoiceChips("In a disagreement, you tend to (optional)", OrbitLogic.CONFLICT, conflict, onSelect = { conflict = if (conflict == it) "" else it })
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        Pill(if (send.busy.value) "Saving…" else "Save", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) {
            if (status.isNotEmpty()) send.send("PUT", "/orbit/profile", buildJsonObject {
                put("status", status); put("partner_word", word)
                put("cared_for_by", JsonArray(cared.map { JsonPrimitive(it) }))
                if (conflict.isNotEmpty()) put("conflict_style", conflict)
            }) { onSaved() }
        }
    }
}

@Composable
private fun Field(label: String, value: String, max: Int, lines: Int = 3, onChange: (String) -> Unit) {
    OutlinedTextField(value, { onChange(it.take(max)) }, Modifier.fillMaxWidth(), label = { Text(label) }, minLines = lines, shape = MaterialTheme.shapes.medium)
}

/** What the server said instead of doing the thing: plain, with call buttons. Nothing typed was saved. */
@Composable
private fun SafetyBox(s: OrbitLogic.Safety) {
    val context = LocalContext.current
    BubbleCard(Modifier.fillMaxWidth().semantics { contentDescription = "Support information" }, tint = Bubbles.TintUrgent) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(s.message, style = MaterialTheme.typography.bodyLarge, color = Color(0xFF1E1B2E))
            s.help.forEach { h ->
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text(h.name, style = MaterialTheme.typography.titleSmall, color = Color(0xFF1E1B2E))
                        if (h.note.isNotBlank()) Text(h.note, style = MaterialTheme.typography.bodySmall, color = Color(0xFF5E5873))
                    }
                    val dial = OrbitLogic.dial(h.number)
                    if (dial.isNotEmpty()) Pill("Call ${h.number}", Color.White, Color(0xFF1E1B2E), Modifier.heightIn(min = 48.dp)) { context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$dial"))) }
                    else if (h.number.isNotBlank()) Text(h.number, color = Color(0xFF1E1B2E))
                }
            }
            Text("Nothing you typed here was saved.", style = MaterialTheme.typography.bodySmall, color = Color(0xFF5E5873))
        }
    }
}

@Composable
private fun Quote(tone: String?, text: String, why: String? = null, onCopy: (() -> Unit)? = null) {
    Column(Modifier.fillMaxWidth().padding(start = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        tone?.let { Eyebrow(it) }
        Text(text, style = MaterialTheme.typography.titleMedium)
        why?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (onCopy != null) TextButton(onClick = onCopy, Modifier.heightIn(min = 48.dp)) { Text("Copy") }
    }
}

@Composable
private fun ReplyPage(api: Api, back: () -> Unit) {
    val send = rememberSender(api)
    val clip = LocalClipboardManager.current
    var theirs by remember { mutableStateOf("") }
    var context by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<JsonObject?>(null) }
    fun ask(extra: String = "") = send.send("POST", "/orbit/reply-helper", buildJsonObject { put("their_message", theirs); put("context", listOf(context, extra).filter { it.isNotBlank() }.joinToString(" ")) }) { result = it }
    FitnessPage("Help me reply", eyebrow = "Orbit", onBack = back) {
        Text("Paste what they said, and I'll suggest how they may be feeling and three ways to answer. Nothing is saved.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Field("What they said", theirs, 1500, 5) { theirs = it }
        Field("Anything I should know? (optional)", context, 600, 2) { context = it }
        Pill(if (send.busy.value) "Thinking…" else "Help me reply", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) { if (theirs.isNotBlank()) ask() }
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        result?.let outer@{ r ->
            OrbitLogic.safety(r)?.let { SafetyBox(it); return@outer }
            if (r.str("status") == "declined") { Text(r.str("message").orEmpty(), style = MaterialTheme.typography.bodyLarge); return@outer }
            val feelings = r.strs("feelings")
            if (feelings.isNotEmpty()) { Eyebrow("What may be underneath"); feelings.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) } }
            r.objs("replies").forEach { x -> Quote(OrbitLogic.TONE[x.str("tone")] ?: x.str("tone"), x.str("text").orEmpty(), x.str("why")) { clip.setText(AnnotatedString(x.str("text").orEmpty())) } }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { ask("Make the replies softer.") }, Modifier.heightIn(min = 48.dp)) { Text("Softer") }
                TextButton(onClick = { ask("Make the replies shorter.") }, Modifier.heightIn(min = 48.dp)) { Text("Shorter") }
                TextButton(onClick = { ask("Write the replies in Hinglish.") }, Modifier.heightIn(min = 48.dp)) { Text("More Hinglish") }
            }
            Text(if (r.str("source") == "ai") "Written for you by Bubbles." else "Bubbles could not reach its writing helper just now, so these are gentle starting points.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun TextPage(api: Api, back: () -> Unit) {
    val send = rememberSender(api)
    val clip = LocalClipboardManager.current
    var draft by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<JsonObject?>(null) }
    var left by remember { mutableIntStateOf(-1) }
    LaunchedEffect(left) { if (left > 0) { delay(1000); left -= 1 } }
    FitnessPage("Before I text them", eyebrow = "Orbit", onBack = back) {
        Text("Write the message you want to send. If it sounds heated, take a breath before it goes.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Field("Your message", draft, 1500, 5) { draft = it }
        Pill(if (send.busy.value) "Reading…" else "Check it", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) {
            if (draft.isNotBlank()) { left = -1; send.send("POST", "/orbit/cooldown", buildJsonObject { put("draft", draft) }) { result = it } }
        }
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        result?.let outer@{ r ->
            OrbitLogic.safety(r)?.let { SafetyBox(it); return@outer }
            if (r.bool("heated") != true) { Text("This reads calm. Send it when you are ready.", style = MaterialTheme.typography.bodyLarge); return@outer }
            Text("This sounds heated. A short pause usually helps.", style = MaterialTheme.typography.titleMedium)
            when {
                left < 0 -> Pill("Start a 20-minute pause", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer, Modifier.heightIn(min = 48.dp)) { left = 20 * 60 }
                left > 0 -> Text("%d:%02d".format(left / 60, left % 60), style = MaterialTheme.typography.displaySmall, modifier = Modifier.semantics { contentDescription = "${left / 60} minutes left in your pause" })
                else -> Text("Pause done. Take a slow breath, then read the softer version.", style = MaterialTheme.typography.bodyLarge)
            }
            r.str("rewrite")?.let { w -> Quote("A softer way to say it", w) { clip.setText(AnnotatedString(w)) } }
        }
    }
}

@Composable
private fun RitualPage(api: Api, back: () -> Unit) {
    val q = rememberLoad(api, "/orbit/question")
    val c = rememberLoad(api, "/orbit/checkin")
    FitnessPage("Today's question", eyebrow = "Orbit", onBack = back) {
        Text("One small question a day. Answer for yourself, or with someone you are connected with.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        LoadGate(q) { QuestionBlock(api, it) { q.reload() } }
        LoadGate(c) { CheckinBlock(api, it) { c.reload() } }
    }
}

@Composable
private fun QuestionBlock(api: Api, d: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    var answer by remember { mutableStateOf("") }
    var safety by remember { mutableStateOf<OrbitLogic.Safety?>(null) }
    Text(d.str("text").orEmpty(), style = MaterialTheme.typography.titleLarge)
    safety?.let { SafetyBox(it) }
    if (d.bool("answered") == true) {
        Quote(null, d.str("my_answer").orEmpty())
        d.str("partner_answer")?.let { Quote("Their answer", it) }
        if (d.bool("paired") == true && d.str("state") != "revealed") Text("Their answer appears here once you have both answered and both switched shared questions on.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    } else {
        Field("Your answer", answer, 500, 3) { answer = it }
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Pill(if (send.busy.value) "Saving…" else "Save", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) {
            if (answer.isNotBlank()) send.send("POST", "/orbit/question", buildJsonObject { put("answer", answer) }) { r -> OrbitLogic.safety(r)?.let { safety = it } ?: reload() }
        }
    }
}

@Composable
private fun CheckinBlock(api: Api, d: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    val prompts = d.obj("prompts")
    var answers by remember { mutableStateOf(mapOf<String, String>()) }
    var safety by remember { mutableStateOf<OrbitLogic.Safety?>(null) }
    Eyebrow("This week")
    safety?.let { SafetyBox(it) }
    if (d.bool("answered") == true) {
        d.obj("my_answers")?.entries.orEmpty().forEach { (k, v) -> Quote(prompts?.str(k) ?: k, (v as? JsonPrimitive)?.content.orEmpty()) }
        val theirs = d.obj("partner_answers")
        if (theirs != null) { Eyebrow("Theirs"); theirs.entries.forEach { (k, v) -> Quote(prompts?.str(k) ?: k, (v as? JsonPrimitive)?.content.orEmpty()) } }
        else if (d.bool("paired") == true) Text("Waiting for them. You will both see everything at the same time.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    } else {
        Text("Three short questions. Skip any you like.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        prompts?.entries.orEmpty().forEach { (k, v) -> Field((v as? JsonPrimitive)?.content ?: k, answers[k].orEmpty(), 300, 2) { answers = answers + (k to it) } }
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Pill(if (send.busy.value) "Saving…" else "Save my check-in", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) {
            val given = answers.filterValues { it.isNotBlank() }
            if (given.isNotEmpty()) send.send("POST", "/orbit/checkin", buildJsonObject { put("answers", buildJsonObject { given.forEach { (k, v) -> put(k, v) } }) }) { r -> OrbitLogic.safety(r)?.let { safety = it } ?: reload() }
        }
    }
}

@Composable
private fun FightPage(api: Api, back: () -> Unit) {
    val send = rememberSender(api)
    val clip = LocalClipboardManager.current
    var parts by remember { mutableStateOf(mapOf("happened" to "", "felt" to "", "needed" to "", "own" to "")) }
    var result by remember { mutableStateOf<JsonObject?>(null) }
    var kept by remember { mutableStateOf(false) }
    FitnessPage("After a fight", eyebrow = "Orbit", onBack = back) {
        Text("Four short answers, just for you. I'll turn them into a calm message you can send, change or throw away.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        listOf("happened" to "What happened", "felt" to "What I felt", "needed" to "What I needed", "own" to "What I can own").forEach { (k, label) ->
            Field(label, parts[k].orEmpty(), 400, if (k == "happened") 3 else 2) { parts = parts + (k to it) }
        }
        send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Pill(if (send.busy.value) "Writing…" else "Write a repair message", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) {
            if (parts.values.all { it.isNotBlank() }) { kept = false; send.send("POST", "/orbit/repair", buildJsonObject { parts.forEach { (k, v) -> put(k, v) } }) { result = it } }
        }
        result?.let outer@{ r ->
            OrbitLogic.safety(r)?.let { SafetyBox(it); return@outer }
            val draft = r.str("draft") ?: return@outer
            Quote("A draft you can change", draft) { clip.setText(AnnotatedString(draft)) }
            TextButton(onClick = { if (!kept) send.send("POST", "/orbit/notes", buildJsonObject { put("kind", "repair"); put("text", draft) }) { kept = true } }, Modifier.heightIn(min = 48.dp)) { Text(if (kept) "Kept in your private notes" else "Keep it") }
        }
    }
}

@Composable
private fun MapPage(api: Api, back: () -> Unit) {
    val map = rememberLoad(api, "/orbit/love-map")
    FitnessPage("Understand them", eyebrow = "Orbit", onBack = back) {
        Text("The small things you know about someone make them feel known. Here is what you have told me, and what could be worth asking.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        LoadGate(map) { d -> MapBody(api, d) { map.reload() } }
    }
}

@Composable
private fun MapBody(api: Api, d: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    var open by remember { mutableStateOf<String?>(null) }
    var text by remember { mutableStateOf("") }
    var safety by remember { mutableStateOf<OrbitLogic.Safety?>(null) }
    Eyebrow("What you know")
    val known = d.objs("known")
    if (known.isEmpty()) Text("Nothing yet. Tell me about them in a chat, or answer a question below.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    known.forEach { Text(it.str("text").orEmpty(), style = MaterialTheme.typography.bodyLarge); HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant) }
    safety?.let { SafetyBox(it) }
    val ask = d.objs("ask")
    if (ask.isNotEmpty()) Eyebrow("Worth asking tonight")
    ask.forEach { qn ->
        val id = qn.str("id").orEmpty()
        OrbitRow(qn.str("text").orEmpty()) { open = if (open == id) null else id; text = "" }
        if (open == id) {
            Field("What you learned (only you can see this)", text, 600, 2) { text = it }
            Pill(if (send.busy.value) "Saving…" else "Keep it", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) {
                if (text.isNotBlank()) send.send("POST", "/orbit/notes", buildJsonObject { put("kind", "love_map"); put("text", text); put("question_id", id) }) { r -> OrbitLogic.safety(r)?.let { safety = it } ?: run { open = null; reload() } }
            }
        }
    }
}

@Composable
private fun HarborPage(api: Api, back: () -> Unit) {
    val harbor = rememberLoad(api, "/orbit/harbor")
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("orbit_safety_plan", Context.MODE_PRIVATE) }
    var checked by remember { mutableStateOf(OrbitLogic.planFrom(prefs.getString("done", null))) }
    FitnessPage("Feeling unsafe at home?", eyebrow = "Help", onBack = back) {
        Text("You do not have to explain anything here. These lines are free and private.", style = MaterialTheme.typography.titleMedium)
        LoadGate(harbor) { d ->
            Eyebrow("People who can help")
            d.objs("resources").forEach { r ->
                val dial = OrbitLogic.dial(r.str("number").orEmpty())
                Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text(r.str("name").orEmpty(), style = MaterialTheme.typography.titleSmall)
                        Text(r.str("note").orEmpty(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (dial.isNotEmpty()) Pill("Call ${r.str("number")}", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer, Modifier.heightIn(min = 48.dp)) { context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$dial"))) }
                    else r.str("number")?.takeIf { it.isNotBlank() }?.let { Text(it) }
                }
            }
            d.str("note")?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        Eyebrow("A safety plan")
        Text("Tick what you have done. This list stays only on this phone. It is not sent anywhere or saved to your account.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        OrbitLogic.PLAN.forEach { (id, text) ->
            val on = id in checked
            Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Checkbox) {
                checked = if (on) checked - id else checked + id
                prefs.edit().putString("done", OrbitLogic.planToStore(checked)).apply()
            }, verticalAlignment = Alignment.CenterVertically) {
                androidx.compose.material3.Checkbox(on, null)
                Text(text, Modifier.padding(start = 8.dp), style = MaterialTheme.typography.bodyLarge)
            }
        }
        TextButton(onClick = { prefs.edit().clear().apply(); checked = emptySet() }, Modifier.heightIn(min = 48.dp)) { Text("Clear this list from this phone") }
    }
}
