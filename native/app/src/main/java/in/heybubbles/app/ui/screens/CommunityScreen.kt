package `in`.heybubbles.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.CommunityPost
import `in`.heybubbles.app.data.CommunityStatus
import `in`.heybubbles.app.data.CommunityText
import `in`.heybubbles.app.data.Support
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.Duration
import java.time.OffsetDateTime

data class CommunityState(
    val status: CommunityStatus? = null,
    val loading: Boolean = true,
    val posts: List<CommunityPost> = emptyList(),
    val cursor: String? = null,
    val topic: String? = null,
    val mine: Boolean = false,
    val error: String? = null,
    val busy: Boolean = false,
    val open: CommunityPost? = null,
    val comments: List<CommunityPost> = emptyList(),
    val support: Support? = null,
    val notice: String? = null,
)

class CommunityViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(CommunityState())
    val state: StateFlow<CommunityState> = _state

    init { load() }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val status = api.communityStatus()
                if (!status.enabled || !status.canRead) { _state.update { it.copy(loading = false, status = status) }; return@launch }
                val s = _state.value
                val feed = api.communityPosts(s.topic, s.mine, null)
                _state.update { it.copy(loading = false, status = status, posts = feed.posts, cursor = feed.nextCursor) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.friendly()) }
            }
        }
    }

    fun filter(topic: String?, mine: Boolean) { _state.update { it.copy(topic = topic, mine = mine) }; load() }

    fun more() {
        val c = _state.value.cursor ?: return
        if (_state.value.busy) return
        _state.update { it.copy(busy = true) }
        viewModelScope.launch {
            try {
                val s = _state.value
                val feed = api.communityPosts(s.topic, s.mine, c)
                _state.update { it.copy(busy = false, posts = it.posts + feed.posts, cursor = feed.nextCursor) }
            } catch (e: Exception) { _state.update { it.copy(busy = false, error = e.friendly()) } }
        }
    }

    /** "Yes" to showing a nickname: records the Community choice with the wording the person saw. */
    fun enable() {
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                val p = api.consents().firstOrNull { it.id == "community_visibility" }
                api.setConsent("community_visibility", true, p?.textHash, "settings")
                _state.update { it.copy(busy = false) }
                load()
            } catch (e: Exception) { _state.update { it.copy(busy = false, error = e.friendly()) } }
        }
    }

    fun post(topic: String, body: String, anonymous: Boolean, done: (Boolean) -> Unit) {
        _state.update { it.copy(busy = true, error = null, support = null) }
        viewModelScope.launch {
            try {
                val r = api.createPost(topic, body, anonymous)
                _state.update { it.copy(busy = false, support = r.support, notice = r.post?.note) }
                done(r.support == null)
                load()
            } catch (e: Exception) { _state.update { it.copy(busy = false, error = e.friendly()) }; done(false) }
        }
    }

    fun clearSupport() { _state.update { it.copy(support = null) } }

    fun openPost(p: CommunityPost?) {
        _state.update { it.copy(open = p, comments = emptyList(), support = null) }
        if (p != null) viewModelScope.launch {
            try { _state.update { it.copy(comments = api.communityComments(p.id)) } } catch (e: Exception) { _state.update { it.copy(error = e.friendly()) } }
        }
    }

    fun comment(text: String, anonymous: Boolean, done: () -> Unit) {
        val p = _state.value.open ?: return
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                val r = api.createComment(p.id, text, anonymous)
                val fresh = runCatching { api.communityComments(p.id) }.getOrDefault(_state.value.comments)
                _state.update { it.copy(busy = false, support = r.support, comments = fresh) }
                done()
            } catch (e: Exception) { _state.update { it.copy(busy = false, error = e.friendly()) } }
        }
    }

    /** Toggles one reaction. The screen updates at once and is put back if the server says no. */
    fun react(target: String, p: CommunityPost, kind: String, isComment: Boolean) {
        fun flip(x: CommunityPost): CommunityPost {
            val on = kind in x.myReactions
            val delta = if (on) -1 else 1
            val r = if (kind == "me_too") x.reactions.copy(meToo = (x.reactions.meToo + delta).coerceAtLeast(0)) else x.reactions.copy(helpful = (x.reactions.helpful + delta).coerceAtLeast(0))
            return x.copy(reactions = r, myReactions = if (on) x.myReactions - kind else x.myReactions + kind)
        }
        fun apply() = _state.update { s ->
            s.copy(
                posts = s.posts.map { if (it.id == p.id && !isComment) flip(it) else it },
                comments = s.comments.map { if (it.id == p.id && isComment) flip(it) else it },
                open = if (s.open?.id == p.id && !isComment) flip(s.open) else s.open,
            )
        }
        apply()
        viewModelScope.launch { try { api.react(target, kind) } catch (e: Exception) { apply(); _state.update { it.copy(error = e.friendly()) } } }
    }

    fun report(target: String, reason: String) {
        viewModelScope.launch {
            try { api.report(target, reason); _state.update { it.copy(notice = "Thank you. A person will take a look.") } }
            catch (e: Exception) { _state.update { it.copy(error = e.friendly()) } }
        }
    }

    fun block(target: String) {
        viewModelScope.launch {
            try { api.block(target); _state.update { it.copy(notice = "You won't see their posts any more.") }; load() }
            catch (e: Exception) { _state.update { it.copy(error = e.friendly()) } }
        }
    }

    fun delete(kind: String, id: String) {
        viewModelScope.launch {
            try { api.deleteCommunityItem(kind, id); _state.update { it.copy(open = if (kind == "post") null else it.open) }; load() }
            catch (e: Exception) { _state.update { it.copy(error = e.friendly()) } }
        }
    }

    fun dismissNotice() { _state.update { it.copy(notice = null, error = null) } }
}

private fun ago(iso: String): String {
    val t = runCatching { OffsetDateTime.parse(iso) }.getOrNull() ?: return ""
    val d = Duration.between(t, OffsetDateTime.now())
    return when {
        d.toMinutes() < 1 -> "just now"
        d.toMinutes() < 60 -> "${d.toMinutes()} min ago"
        d.toHours() < 24 -> "${d.toHours()} h ago"
        d.toDays() < 7 -> "${d.toDays()} d ago"
        else -> t.toLocalDate().toString()
    }
}

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun CommunityScreen(api: Api, onBack: () -> Unit) {
    val vm = viewModel<CommunityViewModel>(key = "community${`in`.heybubbles.app.ui.LocalEpoch.current}") { CommunityViewModel(api) }
    val s by vm.state.collectAsState()
    var composing by remember { mutableStateOf(false) }
    BackHandler { if (s.open != null) vm.openPost(null) else onBack() }

    Column(Modifier.fillMaxWidth()) {
        Box(Modifier.padding(start = 12.dp, top = 12.dp).size(48.dp).clickable(role = Role.Button, onClickLabel = "Back") { if (s.open != null) vm.openPost(null) else onBack() }, contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back")
        }
        ScreenTitle("Community", if (s.open != null) "Replies" else "Ask or share")
        val st = s.status
        (s.notice ?: s.error)?.let { msg ->
            Row(Modifier.padding(horizontal = 20.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(msg, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = if (s.error != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                Pill("OK", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer, onClick = vm::dismissNotice)
            }
        }
        when {
            st == null && s.loading -> Text("Loading…", Modifier.padding(24.dp), style = MaterialTheme.typography.bodyLarge)
            st == null -> Row(Modifier.padding(20.dp)) { Pill("Try again", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary, onClick = vm::load) }
            !st.enabled || !st.canRead -> Notice(
                when (st.reason) {
                    "adults_only" -> "Community is for people 18 and over."
                    else -> "Community isn't open yet. We'll tell you when it is."
                },
            )
            s.open != null -> PostDetail(s, st, vm)
            else -> Feed(s, st, vm, onCompose = { composing = true })
        }
    }

    if (composing && s.status != null) {
        ModalBottomSheet(onDismissRequest = { composing = false; vm.clearSupport() }, containerColor = MaterialTheme.colorScheme.background) {
            Composer(s, s.status!!, vm) { composing = false }
        }
    }
}

@Composable
private fun Notice(text: String) {
    BubbleCard(Modifier.fillMaxWidth().padding(horizontal = 20.dp), tint = MaterialTheme.colorScheme.surfaceVariant) {
        Text(text, Modifier.padding(20.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Feed(s: CommunityState, st: CommunityStatus, vm: CommunityViewModel, onCompose: () -> Unit) {
    LazyColumn(contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 120.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text(st.disclaimer.ifBlank { "Shared by people, not medical advice." }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("Everyone", if (!s.mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface, if (!s.mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface) { vm.filter(s.topic, false) }
                Pill("My posts", if (s.mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface, if (s.mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface) { vm.filter(null, true) }
            }
        }
        if (!s.mine) item {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Pill("All topics", if (s.topic == null) Bubbles.TintGrape else MaterialTheme.colorScheme.surface, if (s.topic == null) Bubbles.GrapeDeep else MaterialTheme.colorScheme.onSurface) { vm.filter(null, false) } }
                items(st.topics) { t -> Pill(CommunityText.topic(t), if (s.topic == t) Bubbles.TintGrape else MaterialTheme.colorScheme.surface, if (s.topic == t) Bubbles.GrapeDeep else MaterialTheme.colorScheme.onSurface) { vm.filter(t, false) } }
            }
        }
        if (st.reason == "consent_needed") item {
            BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintGrape) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Want to join in?", style = MaterialTheme.typography.titleMedium, color = Bubbles.GrapeDeep)
                    Text("You can read without joining. To post or react, turn on Community. Posts show a made-up nickname unless you choose otherwise, and never your name or email.", style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink)
                    Pill(if (s.busy) "Turning on…" else "Turn on Community", Bubbles.GrapeDeep, Color.White) { if (!s.busy) vm.enable() }
                }
            }
        }
        if (s.loading) item { Text("Loading…", style = MaterialTheme.typography.bodyLarge) }
        if (!s.loading && s.posts.isEmpty()) item {
            Text(if (s.mine) "You haven't posted yet." else "No posts here yet. Be the first to ask or share.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(s.posts, key = { it.id }) { p -> PostCard(p, vm, onOpen = { vm.openPost(p) }, isComment = false, canReact = st.canPost) }
        if (s.cursor != null) item { Pill(if (s.busy) "Loading…" else "Show more", MaterialTheme.colorScheme.surface, MaterialTheme.colorScheme.primary) { vm.more() } }
        if (st.canPost) item {
            Box(
                Modifier.fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp)).clickable(role = Role.Button, onClickLabel = "Ask or share", onClick = onCompose),
                contentAlignment = Alignment.Center,
            ) { Text("Ask or share", style = MaterialTheme.typography.titleMedium, color = Color.White) }
        }
    }
}

@Composable
private fun PostCard(p: CommunityPost, vm: CommunityViewModel, onOpen: (() -> Unit)?, isComment: Boolean, canReact: Boolean) {
    var menu by remember { mutableStateOf(false) }
    var reporting by remember { mutableStateOf(false) }
    val kind = if (isComment) "comment" else "post"
    BubbleCard(Modifier.fillMaxWidth(), onClick = onOpen) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(p.alias.ifBlank { "Someone" }, style = MaterialTheme.typography.titleSmall)
                    Text(listOfNotNull(p.topic?.let { CommunityText.topic(it) }, ago(p.createdAt).ifBlank { null }).joinToString(" · "), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Box {
                    Box(Modifier.size(44.dp).clickable(role = Role.Button, onClickLabel = "More options") { menu = true }, contentAlignment = Alignment.Center) { Icon(Icons.Rounded.MoreVert, contentDescription = "More options") }
                    DropdownMenu(menu, { menu = false }) {
                        if (p.mine) DropdownMenuItem({ Text("Delete") }, onClick = { menu = false; vm.delete(kind, p.id) })
                        else {
                            DropdownMenuItem({ Text("Report") }, onClick = { menu = false; reporting = true })
                            DropdownMenuItem({ Text("Block this person") }, onClick = { menu = false; vm.block("$kind:${p.id}") })
                        }
                    }
                }
            }
            Text(p.body, style = MaterialTheme.typography.bodyLarge)
            if (p.mine && p.status != null && p.status != "visible") {
                Text(p.note ?: "This is waiting for a quick review.", style = MaterialTheme.typography.bodyMedium, color = Bubbles.SunDeep, modifier = Modifier.background(Bubbles.TintSun, RoundedCornerShape(14.dp)).padding(12.dp))
            }
            if (p.status == null || p.status == "visible") Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                ReactPill("Me too", p.reactions.meToo, "me_too" in p.myReactions, canReact) { vm.react("$kind:${p.id}", p, "me_too", isComment) }
                ReactPill("Helpful", p.reactions.helpful, "helpful" in p.myReactions, canReact) { vm.react("$kind:${p.id}", p, "helpful", isComment) }
                if (!isComment) Text("${p.commentCount} ${if (p.commentCount == 1) "reply" else "replies"}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    if (reporting) {
        AlertDialog(
            onDismissRequest = { reporting = false },
            title = { Text("Why are you reporting this?") },
            text = {
                Column {
                    CommunityText.reasons.forEach { (id, label) ->
                        TextButton({ reporting = false; vm.report("$kind:${p.id}", id) }) { Text(label) }
                    }
                }
            },
            confirmButton = {},
            dismissButton = { TextButton({ reporting = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun ReactPill(label: String, count: Int, on: Boolean, enabled: Boolean, onClick: () -> Unit) {
    Pill(
        if (count > 0) "$label $count" else label,
        if (on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
        if (on) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
        Modifier.semantics { contentDescription = "$label, $count. ${if (on) "You marked this" else ""}" },
    ) { if (enabled) onClick() }
}

@Composable
private fun PostDetail(s: CommunityState, st: CommunityStatus, vm: CommunityViewModel) {
    val p = s.open ?: return
    var text by remember { mutableStateOf("") }
    var anon by remember { mutableStateOf(true) }
    LazyColumn(contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 120.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { PostCard(p, vm, onOpen = null, isComment = false, canReact = st.canPost) }
        items(s.comments, key = { it.id }) { c -> PostCard(c, vm, onOpen = null, isComment = true, canReact = st.canPost) }
        if (s.comments.isEmpty()) item { Text("No replies yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        s.support?.let { item { SupportCard(it) { vm.clearSupport() } } }
        if (st.canPost) item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(text, { text = it.take(3000) }, Modifier.fillMaxWidth(), label = { Text("Write a kind reply") }, shape = MaterialTheme.shapes.medium, minLines = 2)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Show a nickname, not my name", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                    Switch(anon, { anon = it })
                }
                Pill(if (s.busy) "Posting…" else "Reply", MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.onPrimary) { if (!s.busy && text.isNotBlank()) vm.comment(text, anon) { text = "" } }
            }
        }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun Composer(s: CommunityState, st: CommunityStatus, vm: CommunityViewModel, close: () -> Unit) {
    var topic by remember { mutableStateOf(st.topics.firstOrNull().orEmpty()) }
    var text by remember { mutableStateOf("") }
    var anon by remember { mutableStateOf(true) }
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(horizontal = 24.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Ask or share", style = MaterialTheme.typography.headlineSmall)
        Text("Don't share names, phone numbers or places. Never post anything that needs urgent help here: call your local emergency number.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            st.topics.forEach { t -> Pill(CommunityText.topic(t), if (topic == t) Bubbles.TintGrape else MaterialTheme.colorScheme.surface, if (topic == t) Bubbles.GrapeDeep else MaterialTheme.colorScheme.onSurface) { topic = t } }
        }
        OutlinedTextField(text, { text = it.take(5000) }, Modifier.fillMaxWidth(), label = { Text("What's on your mind?") }, shape = MaterialTheme.shapes.medium, minLines = 4)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Show a nickname, not my name", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            Switch(anon, { anon = it })
        }
        s.support?.let { SupportCard(it) { vm.clearSupport(); close() } }
        s.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
        if (s.support == null) Box(
            Modifier.fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp))
                .clickable(enabled = !s.busy && text.isNotBlank() && topic.isNotBlank(), role = Role.Button, onClickLabel = "Post") { vm.post(topic, text, anon) { ok -> if (ok) close() } },
            contentAlignment = Alignment.Center,
        ) { Text(if (s.busy) "Posting…" else "Post", style = MaterialTheme.typography.titleMedium, color = Color.White) }
    }
}

/** Shown when the server finds a post may be urgent or a crisis: plain support first, with the real help lines. */
@Composable
private fun SupportCard(support: Support, onClose: () -> Unit) {
    BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintUrgent) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Eyebrow(if (support.kind == "crisis") "You're not alone" else "Please don't wait", color = Bubbles.Urgent)
            Text(support.message, style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink)
            if (support.lines.isNotBlank()) Text(support.lines, style = MaterialTheme.typography.bodyMedium, color = Bubbles.Ink)
            Pill("OK", Bubbles.Urgent, Color.White, onClick = onClose)
        }
    }
}
