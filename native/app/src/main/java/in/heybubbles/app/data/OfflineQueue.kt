package `in`.heybubbles.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.io.IOException
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/** One tracker entry saved on this phone while offline, waiting to be sent. [body] is the JSON the server expects, with the real time in "date". */
@Serializable
data class Pending(val id: String, val slug: String, val body: String, val at: Long)

/** The queue's file format and the "did this request ever reach the server" rule. Pure, so tests can hold them. */
object QueueRules {
    private val json = Json { ignoreUnknownKeys = true }

    fun encode(list: List<Pending>): String = json.encodeToString(ListSerializer(Pending.serializer()), list)

    /** A damaged or empty store decodes to an empty queue, never a crash. */
    fun decode(raw: String?): List<Pending> =
        if (raw.isNullOrBlank()) emptyList() else runCatching { json.decodeFromString(ListSerializer(Pending.serializer()), raw) }.getOrDefault(emptyList())

    /**
     * True only when the request could not have reached the server (no DNS, no route, connection refused, or the connection itself timed
     * out). A read timeout or a dropped answer may mean the server DID save it, so those are not queued: queueing them could log it twice.
     */
    fun neverReachedServer(e: Throwable): Boolean = when (e) {
        is UnknownHostException, is ConnectException, is NoRouteToHostException -> true
        is SocketTimeoutException -> e.message?.contains("failed to connect", ignoreCase = true) == true
        is IOException -> false
        else -> false
    }

    /** Entries the server would refuse for good (a 4xx other than "sign in again" or "slow down") are dropped instead of retried forever. */
    fun isPermanentRefusal(e: Throwable): Boolean = e is ApiError && e.code in 400..499 && e.code != 401 && e.code != 408 && e.code != 429
}

/** Encrypted, app-private storage (never backed up), like the sign-in tokens, because these are health entries. */
class OfflineQueue(context: Context) {
    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context, "bubbles_offline",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )
    private val _count = MutableStateFlow(read().size)
    val count: StateFlow<Int> = _count

    private fun read(): List<Pending> = QueueRules.decode(prefs.getString("items", null))

    @Synchronized fun all(): List<Pending> = read()

    @Synchronized fun add(item: Pending) = write(read() + item)

    @Synchronized fun remove(id: String) = write(read().filterNot { it.id == id })

    @Synchronized fun clear() = write(emptyList())

    private fun write(list: List<Pending>) {
        prefs.edit().putString("items", QueueRules.encode(list)).apply()
        _count.value = list.size
    }
}
