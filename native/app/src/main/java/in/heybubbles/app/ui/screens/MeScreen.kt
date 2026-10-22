package `in`.heybubbles.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import `in`.heybubbles.app.BuildConfig
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Session
import `in`.heybubbles.app.push.Push
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.ScreenTitle

@Composable
fun MeScreen(api: Api, session: Session, repo: `in`.heybubbles.app.data.Repo, onReplayTour: () -> Unit = {}) {
    var page by rememberSaveable { mutableStateOf<String?>(null) }
    BackHandler(enabled = page != null) { page = null }
    when (page) {
        "choices" -> { ChoicesScreen(api, onBack = { page = null }, onSignedOut = { api.signOut() }); return }
        "reminders" -> { RemindersScreen(api, session, onBack = { page = null }); return }
        "partner" -> { PartnerScreen(api, onBack = { page = null }, onOpenChoices = { page = "choices" }); return }
    }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    fun open(url: String) = context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
        ScreenTitle("Me", "Your space")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row("Reminders", "Gentle nudges on this phone") { page = "reminders" }
            Row("Partner sharing", "Choose what one trusted person can see") { page = "partner" }
            Row("Your choices", "What Bubbles may do with your data, and Delete my data") { page = "choices" }
            Row("Replay the tour", "A quick look at what is where") { onReplayTour() }
            Row("Privacy policy", "How your health data is handled") { open("https://heybubbles.in/privacy") }
            Row("Terms", "The rules of using Bubbles") { open("https://heybubbles.in/terms") }
            val waiting by repo.pending.collectAsState()
            var confirmSignOut by remember { mutableStateOf(false) }
            fun signOut() {
                // Take this phone off the server's list first, so the next person on a shared phone gets nothing of yours.
                scope.launch { Push.disconnect(context.applicationContext, api, session); api.signOut() }
            }
            Row("Sign out", if (waiting > 0) "$waiting entries have not reached Bubbles yet" else "You can sign back in any time") {
                if (waiting > 0) confirmSignOut = true else signOut()
            }
            if (confirmSignOut) androidx.compose.material3.AlertDialog(
                onDismissRequest = { confirmSignOut = false },
                title = { Text("Sign out with entries waiting?") },
                text = { Text("$waiting ${if (waiting == 1) "entry has" else "entries have"} not reached Bubbles yet. Signing out removes them from this phone. Connect to the internet and wait a moment if you want to keep them.") },
                confirmButton = { androidx.compose.material3.TextButton({ confirmSignOut = false; signOut() }) { Text("Sign out anyway") } },
                dismissButton = { androidx.compose.material3.TextButton({ confirmSignOut = false }) { Text("Stay signed in") } },
            )
            Text(
                "Bubbles ${BuildConfig.VERSION_NAME}",
                Modifier.padding(top = 8.dp, start = 4.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun Row(title: String, subtitle: String, onClick: () -> Unit) {
    BubbleCard(Modifier.fillMaxWidth(), onClick = onClick) {
        Column(Modifier.padding(horizontal = 20.dp, vertical = 16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(subtitle, Modifier.padding(top = 2.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
