package `in`.heybubbles.app.ui.screens

import android.content.Intent
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.PartnerCalc
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.int
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
import `in`.heybubbles.app.ui.screens.fitness.FitnessPage
import `in`.heybubbles.app.ui.screens.fitness.LoadGate
import `in`.heybubbles.app.ui.screens.fitness.rememberLoad
import `in`.heybubbles.app.ui.screens.fitness.rememberSender
import `in`.heybubbles.app.ui.theme.Bubbles

/**
 * Partner sharing: the owner chooses, category by category, what ONE trusted person sees (default nothing), connects them with a one-time
 * code or a quick link, and can stop at once. Every rule (consent, 48-hour single-use codes, one partner, summaries only) is the server's.
 */
@Composable
fun PartnerScreen(api: Api, onBack: () -> Unit, onOpenChoices: () -> Unit = {}) {
    val status = rememberLoad(api, "/partner-sharing")
    val mine = rememberLoad(api, "/partner-sharing/shared-with-me")
    val reload = { status.reload(); mine.reload() }
    FitnessPage("Share a little, safely", "Partner sharing", onBack) {
        Text(
            "Choose exactly what one trusted person can see, connect them to Bubbles, and stop whenever you like. Nothing is shared until you say so.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        LoadGate(mine) { m -> SharedWithYou(api, m, reload) }
        LoadGate(status) { s -> YourSharing(api, s, reload, onOpenChoices) }
    }
}

@Composable
private fun SharedWithYou(api: Api, data: JsonObject, reload: () -> Unit) {
    val send = rememberSender(api)
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var said by remember { mutableStateOf<String?>(null) }
    var leaving by remember { mutableStateOf<JsonObject?>(null) }
    val shares = data.objs("shares")

    Eyebrow("Shared with you")
    if (shares.isEmpty()) Text("Nobody is sharing with you yet. If someone gave you a code, enter it below.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    shares.forEach { share ->
        BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintPink) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("From ${share.str("from_name").orEmpty()}", style = MaterialTheme.typography.titleMedium)
                val sections = share.objs("sections")
                if (sections.isEmpty()) Text("There is nothing to show right now.", style = MaterialTheme.typography.bodyMedium)
                sections.forEach { Section(it) }
                share.str("notice")?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Pill("Leave", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { leaving = share }
            }
        }
    }
    BubbleCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Got a code from someone?", style = MaterialTheme.typography.titleSmall)
            FieldRow("Invite code", code, { code = PartnerCalc.formatCode(it); said = null }, hint = "Like ABCD-EFGH", maxLength = 9)
            FieldRow("Your name (they will see it)", name, { name = it }, maxLength = PartnerCalc.NAME_MAX)
            send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            said?.let { Text(it, color = Bubbles.MintDeep, style = MaterialTheme.typography.bodyMedium) }
            val ready = PartnerCalc.codeComplete(code)
            Pill(if (send.busy.value) "Connecting…" else "Connect", if (ready) Bubbles.Pink else MaterialTheme.colorScheme.surfaceVariant, if (ready) Bubbles.White else MaterialTheme.colorScheme.onSurfaceVariant) {
                if (!ready) return@Pill
                send.send("POST", "/partner-sharing/connect", buildJsonObject { put("code", code); put("name", name) }) {
                    code = ""; said = "You're connected. ${it.str("from_name").orEmpty()} can stop sharing at any time, and so can you."; reload()
                }
            }
        }
    }
    leaving?.let { share ->
        AlertDialog(
            onDismissRequest = { leaving = null },
            title = { Text("Stop seeing their summary?") },
            text = { Text("They can see in their settings that you left.") },
            confirmButton = { TextButton({ val id = share.str("id").orEmpty(); leaving = null; send.send("DELETE", "/partner-sharing/shared-with-me/$id") { said = "You've left."; reload() } }) { Text("Leave", color = Bubbles.Urgent) } },
            dismissButton = { TextButton({ leaving = null }) { Text("Stay") } },
        )
    }
}

/** One shared summary as the partner sees it: a title, then only the words the server chose to share. */
@Composable
private fun Section(s: JsonObject) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp), modifier = Modifier.padding(top = 4.dp)) {
        Text(s.str("title").orEmpty(), style = MaterialTheme.typography.titleSmall)
        s.obj("range")?.let { r -> Text("Between ${r.str("earliest").orEmpty()} and ${r.str("latest").orEmpty()}", style = MaterialTheme.typography.bodyLarge) }
        s.str("text")?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
        s.str("detail")?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
        val tips = s.strs("tips")
        if (tips.isNotEmpty()) {
            Text("Ways to help", style = MaterialTheme.typography.labelLarge)
            tips.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
            s.str("tips_caveat")?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
        s.str("caveat")?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
private fun YourSharing(api: Api, data: JsonObject, reload: () -> Unit, onOpenChoices: () -> Unit) {
    val context = LocalContext.current
    val send = rememberSender(api)
    var picked by remember { mutableStateOf(data.strs("categories").toSet()) }
    var note by remember { mutableStateOf(data.str("note").orEmpty()) }
    var name by remember { mutableStateOf(data.str("owner_name").orEmpty()) }
    var days by remember { mutableStateOf("30") }
    var said by remember { mutableStateOf<String?>(null) }
    var revealed by remember { mutableStateOf<Pair<String, String>?>(null) }   // (what it is, text to share)
    var confirm by remember { mutableStateOf<Triple<String, String, String>?>(null) }   // (question, path, done message)

    // Sharing is a privacy choice that starts off. Until it is on, the server refuses everything below, so say so instead of showing dead buttons.
    if (data.bool("consent") != true) {
        Eyebrow("What you share")
        BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintSun) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Partner sharing is off", style = MaterialTheme.typography.titleSmall)
                Text("Turn it on in Your choices first. Nothing is shared until you also pick what, and you can switch it off again at any time.", style = MaterialTheme.typography.bodyMedium)
                Pill("Open Your choices", Bubbles.Pink, Bubbles.White, onClick = onOpenChoices)
            }
        }
        return
    }

    fun share(text: String) = context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text), "Send with"))

    Eyebrow("What you share")
    data.objs("available").forEach { c ->
        val key = c.str("key").orEmpty()
        BubbleCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                CheckRow(c.str("label").orEmpty(), key in picked) { on -> picked = if (on) picked + key else picked - key; said = null }
                Text(c.str("description").orEmpty(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 48.dp, bottom = 8.dp))
            }
        }
    }
    FieldRow("Your name (they will see it)", name, { name = it; said = null }, maxLength = PartnerCalc.NAME_MAX)
    if ("support_note" in picked) OutlinedTextField(
        note, { note = it.take(PartnerCalc.NOTE_MAX); said = null }, Modifier.fillMaxWidth(), label = { Text("A note from you") },
        supportingText = { Text("${note.length}/${PartnerCalc.NOTE_MAX}") }, minLines = 3, shape = MaterialTheme.shapes.medium,
    )
    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    said?.let { Text(it, color = Bubbles.MintDeep, style = MaterialTheme.typography.bodyMedium) }
    val ok = PartnerCalc.canSave(picked, note)
    Pill(if (send.busy.value) "Saving…" else "Save what I share", if (ok) Bubbles.Pink else MaterialTheme.colorScheme.surfaceVariant, if (ok) Bubbles.White else MaterialTheme.colorScheme.onSurfaceVariant) {
        if (!ok) return@Pill
        send.send("PUT", "/partner-sharing/settings", buildJsonObject {
            put("categories", JsonArray(picked.map(::JsonPrimitive))); put("note", note); put("owner_name", name)
        }) { said = "Saved. This applies straight away to anyone connected."; reload() }
    }

    if (data.bool("configured") == true) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Eyebrow("Who can see it", Modifier.weight(1f))
            Pill(if (data.bool("sharing") == true) "Sharing is on" else "Not shared with anyone yet", if (data.bool("sharing") == true) Bubbles.TintMint else MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface)
        }
        revealed?.let { (what, text) ->
            BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintSun) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Your $what is ready", style = MaterialTheme.typography.titleSmall)
                    Text(text, style = MaterialTheme.typography.bodyLarge)
                    Text("It is shown only now. Send it to the one person you chose.", style = MaterialTheme.typography.bodySmall)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Pill("Share…", Bubbles.Pink, Bubbles.White) { share(text) }
                        Pill("Done", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { revealed = null }
                    }
                }
            }
        }
        val connection = data.obj("connection")
        val invite = data.obj("invite")
        val link = data.obj("link")
        BubbleCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Connect their Bubbles account (recommended)", style = MaterialTheme.typography.titleSmall)
                if (connection != null) {
                    Text("Connected with ${connection.str("name").orEmpty()} (the name they typed). They see only what you chose above.", style = MaterialTheme.typography.bodyMedium)
                    Pill("Disconnect", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { confirm = Triple("Disconnect ${connection.str("name").orEmpty()}? They stop seeing your summary straight away.", "/partner-sharing/connection", "Disconnected.") }
                } else {
                    Text("They sign in to their own Bubbles account and enter a one-time code. You can disconnect them at any time, and they can leave too.", style = MaterialTheme.typography.bodyMedium)
                    if (invite?.bool("active") == true) Text("An invite is waiting" + (PartnerCalc.hoursLeft(invite.str("expires_at"))?.let { " (about $it hours left)" } ?: "") + ". Codes work once.", style = MaterialTheme.typography.bodySmall)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Pill(if (invite?.bool("active") == true) "Make a new code" else "Make an invite code", Bubbles.Pink, Bubbles.White) {
                            send.send("POST", "/partner-sharing/invite") { r -> r.str("code")?.let { revealed = "invite code" to PartnerCalc.inviteMessage(it) }; reload() }
                        }
                        if (invite?.bool("active") == true) Pill("Cancel code", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { confirm = Triple("Cancel the invite code?", "/partner-sharing/invite", "Invite code cancelled.") }
                    }
                }
            }
        }
        BubbleCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Or a quick link (no account needed)", style = MaterialTheme.typography.titleSmall)
                Text("Anyone who has the link can see your summary until it expires, so send it only to someone you trust.", style = MaterialTheme.typography.bodyMedium)
                if (link?.bool("active") == true) {
                    val views = link.obj("views")?.int("count") ?: 0
                    Text("Link on, ${PartnerCalc.daysLeft(link.str("expires_at")) ?: 0} days left, opened $views time${if (views == 1) "" else "s"} (we never record who).", style = MaterialTheme.typography.bodySmall)
                }
                if (link?.bool("expired") == true) Text("Your last link expired.", style = MaterialTheme.typography.bodySmall)
                ChoiceChips("Works for", PartnerCalc.EXPIRY_DAYS.map { it.toString() to "$it days" }, days, { days = it })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill(if (link?.bool("active") == true) "Make a new link" else "Make a link", Bubbles.Pink, Bubbles.White) {
                        send.send("POST", "/partner-sharing/link", buildJsonObject { put("expires_in_days", days.toInt()) }) { r -> r.str("token")?.let { revealed = "link" to PartnerCalc.linkMessage(it) }; reload() }
                    }
                    if (link?.bool("active") == true) Pill("Turn it off", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface) { confirm = Triple("Turn the link off? It stops working straight away.", "/partner-sharing/link", "Link turned off.") }
                }
            }
        }
        Pill("Stop all sharing", Bubbles.Urgent, Bubbles.White) {
            confirm = Triple("Stop all sharing? Every link, code and connection stops working straight away, and your choices are cleared.", "/partner-sharing", "All sharing has stopped.")
        }
    }

    BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintSky) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("If sharing ever feels unsafe", style = MaterialTheme.typography.titleSmall)
            Text(
                "You can stop everything with one tap above, and it takes effect immediately. If you are worried about your safety, call 112 (emergency) or the Women Helpline 181. For emotional support, Tele-MANAS is free on 14416.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
    val never = data.strs("never_shared")
    if (never.isNotEmpty()) {
        Text("What can never be shared", style = MaterialTheme.typography.titleSmall)
        never.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        Text("The person you share with sees short summaries, never your logs.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    confirm?.let { (question, path, done) ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("Are you sure?") },
            text = { Text(question) },
            confirmButton = { TextButton({ confirm = null; revealed = null; send.send("DELETE", path) { said = done; reload() } }) { Text("Yes", color = Bubbles.Urgent) } },
            dismissButton = { TextButton({ confirm = null }) { Text("No") } },
        )
    }
}
