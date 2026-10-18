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
