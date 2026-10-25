package `in`.heybubbles.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** The signed-in person's tokens, kept in encrypted app-private storage (never backed up: see data_extraction_rules). */
class Session(context: Context) {
    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context, "bubbles_session",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )
    private val _signedIn = MutableStateFlow(prefs.getString("access", null) != null)
    val signedIn: StateFlow<Boolean> = _signedIn

    /** Bumps on every sign-out, so screens keyed to it start fresh for the next person. */
    var epoch: Int = 0
        private set

    val access: String? get() = prefs.getString("access", null)
    val refresh: String? get() = prefs.getString("refresh", null)

    /** The notification token this phone gave the server, so it can be taken back. Cleared with everything else on sign-out. */
    var pushToken: String?
        get() = prefs.getString("push_token", null)
        set(v) { prefs.edit().apply { if (v == null) remove("push_token") else putString("push_token", v) }.apply() }

    /** The notice version the person ticked at sign-up, kept until the server has recorded it (the account may need an email confirmation first). */
    var pendingAck: String?
        get() = prefs.getString("pending_ack", null)
        set(v) { prefs.edit().apply { if (v == null) remove("pending_ack") else putString("pending_ack", v) }.apply() }

    /** The last answer to GET /today, so Today opens instantly with the last known day while the fresh one loads. Encrypted here and wiped on sign-out. */
    var todayCache: String?
        get() = prefs.getString("today_cache", null)
        set(v) { prefs.edit().apply { if (v == null) remove("today_cache") else putString("today_cache", v) }.apply() }

    fun save(access: String, refresh: String?) {
        prefs.edit().putString("access", access).putString("refresh", refresh).apply()
        _signedIn.value = true
    }

    fun clear() {
        prefs.edit().clear().apply()
        epoch++
        _signedIn.value = false
    }
}
