package `in`.heybubbles.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import `in`.heybubbles.app.BuildConfig
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.ScreenTitle

@Composable
fun MeScreen(api: Api) {
    var choices by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf(false) }
    androidx.activity.compose.BackHandler(enabled = choices) { choices = false }
    if (choices) { ChoicesScreen(api, onBack = { choices = false }); return }
    val context = LocalContext.current
    fun open(url: String) = context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
        ScreenTitle("Me", "Your space")
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row("Your choices", "What Bubbles may do with your data, and Delete my data") { choices = true }
            Row("Privacy policy", "How your health data is handled") { open("https://heybubbles.in/privacy") }
            Row("Terms", "The rules of using Bubbles") { open("https://heybubbles.in/terms") }
            Row("Sign out", "You can sign back in any time") { api.signOut() }
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
