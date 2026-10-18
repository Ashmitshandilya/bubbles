package `in`.heybubbles.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import `in`.heybubbles.app.ui.AppRoot
import `in`.heybubbles.app.ui.theme.BubblesTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as BubblesApp
        `in`.heybubbles.app.push.Push.launchKind.value = intent?.getStringExtra("kind")
        setContent { BubblesTheme { AppRoot(app.api, app.session, app.repo) } }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        `in`.heybubbles.app.push.Push.launchKind.value = intent.getStringExtra("kind")
    }
}
