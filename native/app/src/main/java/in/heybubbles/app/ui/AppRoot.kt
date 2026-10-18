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
import `in`.heybubbles.app.data.Session
import `in`.heybubbles.app.ui.components.BubblesBackground
import `in`.heybubbles.app.ui.screens.LoginScreen
import `in`.heybubbles.app.ui.screens.MeScreen
import `in`.heybubbles.app.ui.screens.TalkScreen
import `in`.heybubbles.app.ui.screens.TodayScreen
import `in`.heybubbles.app.ui.theme.Bubbles
import `in`.heybubbles.app.ui.theme.LocalDark

private enum class Tab(val label: String, val icon: ImageVector) {
    Today("Today", Icons.Rounded.Home),
    Talk("Talk", ChatBubbleIcon),
    Me("Me", Icons.Rounded.Person),
}

@Composable
fun AppRoot(api: Api, session: Session) {
    val signedIn by session.signedIn.collectAsState()
    BubblesBackground {
        Crossfade(signedIn, label = "auth") { yes ->
            if (!yes) LoginScreen(api) else Home(api)
        }
    }
}

@Composable
private fun Home(api: Api) {
    var tab by rememberSaveable { mutableStateOf(Tab.Talk) }
    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding()) {
            Box(Modifier.weight(1f)) {
                // Screens are kept alive when you switch (state is held in each screen's own view model), only one is shown.
                when (tab) {
                    Tab.Today -> TodayScreen(api, onTalk = { tab = Tab.Talk })
                    Tab.Talk -> TalkScreen(api)
                    Tab.Me -> MeScreen(api)
                }
            }
            // Room for the floating bar below the content.
            Box(Modifier.navigationBarsPadding().padding(bottom = 88.dp))
        }
        FloatingBar(tab, onSelect = { tab = it }, Modifier.align(Alignment.BottomCenter))
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
