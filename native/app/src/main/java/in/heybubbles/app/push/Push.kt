package `in`.heybubbles.app.push

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.suspendCancellableCoroutine
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Session
import kotlin.coroutines.resume

/**
 * Phone reminders through Firebase Cloud Messaging (docs/FIREBASE.md). Dormant unless this build has the Firebase config.
 * The server only sends fixed, plain reminder templates and refuses a token until the person's yes is on record.
 */
object Push {
    /** The channel the server names in every message (backend/push_fcm.py). */
    const val CHANNEL = "reminders"

    /** Where a tapped reminder should go: set by the activity, read by the app shell. Only the kind travels, never anything about the person. */
    val launchKind = MutableStateFlow<String?>(null)

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = context.getSystemService(NotificationManager::class.java)
        // Private on the lock screen: the text is plain anyway.
        val ch = NotificationChannel(CHANNEL, "Reminders", NotificationManager.IMPORTANCE_DEFAULT).apply {
            description = "Plain reminders from Bubbles"
            lockscreenVisibility = android.app.Notification.VISIBILITY_PRIVATE
        }
        nm.createNotificationChannel(ch)
    }

    fun configured(context: Context): Boolean = runCatching { FirebaseApp.getApps(context).isNotEmpty() }.getOrDefault(false)

    /** This phone's notification token, or null if Firebase isn't set up or the request failed. */
    suspend fun token(context: Context): String? {
        if (!configured(context)) return null
        return suspendCancellableCoroutine { cont ->
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task -> cont.resume(if (task.isSuccessful) task.result else null) }
        }
    }

    /** Gives this phone's token to the server (the person's yes must already be saved). Returns false if it couldn't. */
    suspend fun connect(context: Context, api: Api, session: Session): Boolean {
        val token = token(context) ?: return false
        return try {
            api.registerDevice(token)
            session.pushToken = token
            true
        } catch (_: Exception) {
            false
        }
    }

    /** Takes the token back from the server when it can, and deletes it on the phone so nothing more can arrive. Never throws. */
    suspend fun disconnect(context: Context, api: Api, session: Session) {
        val saved = session.pushToken
        if (saved != null) runCatching { api.removeDevice(saved) }
        session.pushToken = null
        if (configured(context)) runCatching { FirebaseMessaging.getInstance().deleteToken() }
    }

    /** After sign-in: if this phone was connected before, hand the server the (possibly new) token without asking again. */
    suspend fun refresh(context: Context, api: Api, session: Session) {
        if (session.pushToken == null || !configured(context)) return
        val token = token(context) ?: return
        if (token == session.pushToken) return
        runCatching { api.registerDevice(token); session.pushToken = token }
    }
}
