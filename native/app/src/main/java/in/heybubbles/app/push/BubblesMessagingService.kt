package `in`.heybubbles.app.push

import android.app.PendingIntent
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import `in`.heybubbles.app.BubblesApp
import `in`.heybubbles.app.MainActivity
import `in`.heybubbles.app.R

/** Receives reminders while the app is open (the system shows them itself when it is closed) and keeps the server's token fresh. */
class BubblesMessagingService : FirebaseMessagingService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        val app = application as BubblesApp
        // Only a phone the person connected is kept connected; a new token never turns reminders on by itself.
        if (!app.session.signedIn.value || app.session.pushToken == null) return
        scope.launch { runCatching { app.api.registerDevice(token); app.session.pushToken = token } }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val n = message.notification ?: return
        Push.ensureChannel(this)
        val open = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            message.data["kind"]?.let { putExtra("kind", it) }
        }
        val pending = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(this, Push.CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_bubbles)
            .setContentTitle(n.title ?: "Bubbles")
            .setContentText(n.body.orEmpty())
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setAutoCancel(true).setContentIntent(pending).build()
        runCatching { NotificationManagerCompat.from(this).notify(System.currentTimeMillis().toInt(), notification) }   // no permission: nothing to show
    }
}
