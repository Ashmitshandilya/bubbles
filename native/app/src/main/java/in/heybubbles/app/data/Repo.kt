package `in`.heybubbles.app.data

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

/**
 * The one place tracker entries live in the app, so Today, Track and anything later always show the same numbers.
 * It holds no rules of its own: the server decides what an entry means.
 */
class Repo(private val api: Api) {
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

    suspend fun loadSections() { runCatching { api.visibleSections() }.onSuccess { _sections.value = it } }

    fun clear() { _entries.value = emptyMap(); _loading.value = true; _sections.value = null }

    companion object { const val WINDOW_DAYS = 30 }
}
