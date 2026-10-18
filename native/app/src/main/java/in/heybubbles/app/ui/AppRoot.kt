package `in`.heybubbles.app.ui

import androidx.compose.animation.Crossfade
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.ui.draw.shadow
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Repo
import `in`.heybubbles.app.data.Session
import `in`.heybubbles.app.ui.components.BubblesBackground
import `in`.heybubbles.app.ui.screens.CareScreen
import `in`.heybubbles.app.ui.screens.CycleScreen
import `in`.heybubbles.app.ui.screens.LoginScreen
import `in`.heybubbles.app.ui.screens.PatternsScreen
import `in`.heybubbles.app.ui.screens.MeScreen
import `in`.heybubbles.app.ui.screens.OnboardingScreen
import `in`.heybubbles.app.ui.screens.TalkScreen
import `in`.heybubbles.app.ui.screens.TodayScreen
import `in`.heybubbles.app.ui.screens.TrackScreen
import `in`.heybubbles.app.ui.theme.Bubbles
import `in`.heybubbles.app.ui.theme.LocalDark

private enum class Tab(val label: String, val icon: ImageVector) {
    Today("Today", Icons.Rounded.Home),
    Talk("Talk", ChatBubbleIcon),
    Track("Track", TrackIcon),
    Me("Me", Icons.Rounded.Person),
}

@Composable
fun AppRoot(api: Api, session: Session, repo: Repo) {
    val signedIn by session.signedIn.collectAsState()
    val epoch = session.epoch
    androidx.compose.runtime.LaunchedEffect(signedIn) { if (!signedIn) repo.clear() }
    androidx.compose.runtime.CompositionLocalProvider(LocalEpoch provides epoch) {
        BubblesBackground {
            Crossfade(signedIn, label = "auth") { yes ->
                if (!yes) LoginScreen(api) else Gate(api, repo)
            }
        }
    }
}

/** Changes on every sign-out; screens use it as a view-model key so one person's data is never shown to the next. */
val LocalEpoch = androidx.compose.runtime.compositionLocalOf { 0 }

/** After sign-in: finished setup goes to the app, an unfinished one to first-run setup (the same rule as the website). */
@Composable
private fun Gate(api: Api, repo: Repo) {
    var done by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf<Boolean?>(null) }
    var failed by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    var attempt by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(0) }
    androidx.compose.runtime.LaunchedEffect(attempt) {
        failed = false
        try { done = api.onboardingState().complete } catch (_: Exception) { failed = true }
    }
    when {
        done == true -> Home(api, repo)
        done == false -> OnboardingScreen(api, onFinished = { done = true }, onSignOut = { api.signOut() })
        failed -> Column(Modifier.fillMaxSize().statusBarsPadding().padding(32.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Can't reach Bubbles. Check your connection.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.error)
            `in`.heybubbles.app.ui.components.Pill("Try again", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, Modifier.padding(top = 16.dp)) { attempt++ }
        }
        else -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Getting your day ready…", style = MaterialTheme.typography.titleLarge) }
    }
}

@Composable
private fun Home(api: Api, repo: Repo) {
    var tab by rememberSaveable { mutableStateOf(Tab.Today) }
    var startSlug by rememberSaveable { mutableStateOf<String?>(null) }
    var section by rememberSaveable { mutableStateOf<String?>(null) }
    androidx.compose.runtime.LaunchedEffect(Unit) { repo.loadSections() }
    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding()) {
            Box(Modifier.weight(1f)) {
                // Screens are kept alive when you switch (state is held in each screen's own view model), only one is shown.
                when {
                    section == "cycle" -> CycleScreen(api, onBack = { section = null })
                    section == "patterns" -> PatternsScreen(api, onBack = { section = null })
                    section == "care" -> CareScreen(api, repo, onBack = { section = null })
                    else -> when (tab) {
                    Tab.Today -> TodayScreen(api, repo, onTalk = { tab = Tab.Talk }, onOpenTracker = { startSlug = it; tab = Tab.Track }, onOpenSection = { section = it })
                    Tab.Talk -> TalkScreen(api)
                    Tab.Track -> TrackScreen(api, repo, startSlug, onStartUsed = { startSlug = null })
                    Tab.Me -> MeScreen(api)
                    }
                }
            }
            // Room for the floating bar below the content.
            Box(Modifier.navigationBarsPadding().padding(bottom = 88.dp))
        }
        FloatingBar(tab, onSelect = { section = null; tab = it }, Modifier.align(Alignment.BottomCenter))
    }
}

@Composable
private fun FloatingBar(selected: Tab, onSelect: (Tab) -> Unit, modifier: Modifier = Modifier) {
    val dark = LocalDark.current
    val shape = RoundedCornerShape(32.dp)
    Row(
        modifier.navigationBarsPadding().padding(horizontal = 24.dp, vertical = 12.dp).fillMaxWidth()
            .shadow(if (dark) 0.dp else 12.dp, shape, ambientColor = Bubbles.Pink.copy(alpha = 0.3f), spotColor = Bubbles.Grape.copy(alpha = 0.3f))
            .background(MaterialTheme.colorScheme.surface, shape)
            .padding(6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Tab.entries.forEach { t ->
            val on = t == selected
            Row(
                Modifier.weight(if (on) 1.5f else 1f)
                    .background(if (on) MaterialTheme.colorScheme.primaryContainer else androidx.compose.ui.graphics.Color.Transparent, RoundedCornerShape(26.dp))
                    .clickable(role = Role.Tab) { onSelect(t) }
                    .padding(vertical = 12.dp)
                    .semantics { role = Role.Tab; this.selected = on; contentDescription = t.label },
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(t.icon, contentDescription = null, tint = if (on) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant)
                if (on) Text(t.label, Modifier.padding(start = 8.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
        }
    }
}
