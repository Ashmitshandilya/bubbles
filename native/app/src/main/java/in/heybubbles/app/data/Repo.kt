package `in`.heybubbles.app.data

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * The one place tracker entries live in the app, so Today, Track and anything later always show the same numbers.
 * It holds no rules of its own: the server decides what an entry means.
 */
class Repo(private val api: Api, private val queue: OfflineQueue? = null) {
    /** How many entries are saved on this phone and waiting for a connection. */
    val pending: StateFlow<Int> get() = queue?.count ?: MutableStateFlow(0)

    /**
     * Saves one entry. Returns true when the server has it, false when it was kept on this phone because the request never reached the
     * server (it is sent later, in order, with the time it was logged). Any other failure is thrown so the person sees it and can retry.
     */
    suspend fun save(slug: String, body: JsonObject): Boolean {
        try {
            api.saveEntry(slug, body)
            return true
        } catch (e: Exception) {
            val q = queue
            if (q == null || !QueueRules.neverReachedServer(e)) throw e
            val stamped = JsonObject(body + ("date" to JsonPrimitive(java.time.Instant.now().toString())))
            q.add(Pending(java.util.UUID.randomUUID().toString(), slug, stamped.toString(), System.currentTimeMillis()))
            return false
        }
    }

    private val syncLock = kotlinx.coroutines.sync.Mutex()

    /** Sends what is waiting, oldest first. Stops at the first failure that may pass (offline, server busy); drops what the server refuses for good. Returns how many were sent. */
    suspend fun sync(): Int {
        val q = queue ?: return 0
        if (!syncLock.tryLock()) return 0
        var sent = 0
        try {
            for (item in q.all()) {
                val body = runCatching { api.json.parseToJsonElement(item.body) as JsonObject }.getOrNull()
                if (body == null) { q.remove(item.id); continue }
                try {
                    api.saveEntry(item.slug, body)
                    q.remove(item.id); sent++
                } catch (e: Exception) {
                    if (QueueRules.isPermanentRefusal(e)) { q.remove(item.id); continue }
                    break
                }
            }
        } finally { syncLock.unlock() }
        if (sent > 0) loadAll()
        return sent
    }

    private val _entries = MutableStateFlow<Map<String, List<Entry>>>(emptyMap())
    val entries: StateFlow<Map<String, List<Entry>>> = _entries

    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading

    /** Loads every tracker; returns true if at least one answered. A tracker that fails keeps what it had. */
    suspend fun loadAll(days: Int = WINDOW_DAYS): Boolean = coroutineScope {
        _loading.value = true
        val results = (Trackers.all + Trackers.records).map { spec -> async { spec.slug to runCatching { api.entries(spec.slug, days) }.getOrNull() } }.awaitAll()
        val ok = results.filter { it.second != null }
        _entries.update { it + ok.associate { (slug, list) -> slug to list!! } }
        _loading.value = false
        ok.isNotEmpty()
    }

    suspend fun reload(slug: String) {
        runCatching { api.entries(slug, WINDOW_DAYS) }.onSuccess { list -> _entries.update { it + (slug to list) } }
    }

    private val _sections = MutableStateFlow<Set<String>?>(null)

    /** Which sections this person should see; null until known. */
    val sections: StateFlow<Set<String>?> = _sections

    private val _communityOpen = MutableStateFlow(false)

    /** True once the server says Community is on and this person may read it (it is off until the owner sets it up). */
    val communityOpen: StateFlow<Boolean> = _communityOpen

    suspend fun loadSections() {
        runCatching { api.visibleSections() }.onSuccess { _sections.value = it }
        runCatching { api.communityStatus() }.onSuccess { _communityOpen.value = it.enabled && it.canRead }
    }

    fun clear() { queue?.clear(); _entries.value = emptyMap(); _loading.value = true; _sections.value = null; _communityOpen.value = false }

    companion object { const val WINDOW_DAYS = 30 }
}
