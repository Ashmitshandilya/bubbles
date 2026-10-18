package `in`.heybubbles.app.ui.screens

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.ChatBubbleIcon
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.ScreenTitle
import `in`.heybubbles.app.ui.theme.Bubbles
import java.util.UUID

data class Msg(val id: String, val fromUser: Boolean, val text: String, val urgent: Boolean = false, val consentAsk: Boolean = false, val failed: Boolean = false)

data class TalkState(
    val loading: Boolean = true,
    val msgs: List<Msg> = emptyList(),
    val sending: Boolean = false,
    val notice: String? = null,
)

class TalkViewModel(private val api: Api) : ViewModel() {
    private val _state = MutableStateFlow(TalkState())
    val state: StateFlow<TalkState> = _state
    private var conversationId: String? = null
    private var lastUserText: String? = null

    init { load() }

    fun load() = viewModelScope.launch {
        try {
            val latest = api.latestChat()
            conversationId = latest.conversation?.id?.ifBlank { null }
            _state.update { it.copy(loading = false, notice = null, msgs = latest.messages.map { m ->
                Msg(m.id, m.role == "user", m.content, urgent = m.safetyLevel == "RED")
            }) }
        } catch (e: Exception) {
            _state.update { it.copy(loading = false, notice = e.friendly()) }
        }
    }

    fun send(text: String, again: Boolean = false) {
        val clean = text.trim()
        if (clean.isEmpty() || _state.value.sending) return
        lastUserText = clean
        if (!again) _state.update { it.copy(msgs = it.msgs + Msg(UUID.randomUUID().toString(), true, clean)) }
        _state.update { it.copy(sending = true, notice = null) }
        viewModelScope.launch {
            try {
                val r = api.chat(clean, UUID.randomUUID().toString(), conversationId)
                conversationId = r.conversationId ?: conversationId
                val urgent = r.safety.level == "RED" || r.kind == "emergency"
                _state.update { it.copy(sending = false, msgs = it.msgs + Msg(r.messageId ?: UUID.randomUUID().toString(), false, r.response, urgent, r.consentAsk)) }
            } catch (e: Exception) {
                _state.update { it.copy(sending = false, notice = e.friendly()) }
            }
        }
    }

    /** "Yes" to the outside-AI ask: record it with the server, then ask the same question again. */
    fun answerConsent(yes: Boolean) {
        _state.update { s -> s.copy(msgs = s.msgs.map { if (it.consentAsk) it.copy(consentAsk = false) else it }) }
        if (!yes) return
        viewModelScope.launch {
            try {
                api.setConsent("ai_chat_processing", true)
                lastUserText?.let { send(it, again = true) }
            } catch (e: Exception) {
                _state.update { it.copy(notice = e.friendly()) }
            }
        }
    }
}

@Composable
fun TalkScreen(api: Api) {
    val vm = viewModel<TalkViewModel> { TalkViewModel(api) }
    val s by vm.state.collectAsState()
    val list = rememberLazyListState()
    val haptic = LocalHapticFeedback.current
    var draft by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }

    LaunchedEffect(s.msgs.size, s.sending) {
        val last = s.msgs.size + (if (s.sending) 1 else 0) - 1
        if (last >= 0) list.animateScrollToItem(last)
    }

    Column(Modifier.fillMaxWidth().imePadding()) {
        ScreenTitle("Talk", "How are you today?")
        Box(Modifier.weight(1f).fillMaxWidth()) {
            when {
                s.loading -> Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { Typing() }
                s.msgs.isEmpty() && s.notice == null -> EmptyTalk { draft = it }
                else -> LazyColumn(state = list, contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(s.msgs, key = { it.id }) { m ->
                        Bubble(m)
                        if (m.consentAsk) ConsentRow(onYes = { vm.answerConsent(true) }, onNo = { vm.answerConsent(false) })
                    }
                    if (s.sending) item { Row(Modifier.padding(start = 4.dp)) { Typing() } }
                }
            }
        }
        s.notice?.let {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).semantics { liveRegion = LiveRegionMode.Polite }, verticalAlignment = Alignment.CenterVertically) {
                Text(it, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
                Pill("Try again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer) { if (s.msgs.isEmpty()) vm.load() else vm.send(s.msgs.last { m -> m.fromUser }.text, again = true) }
            }
        }
        Composer(draft, { draft = it }, enabled = !s.sending) {
            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
            vm.send(draft); draft = ""
        }
    }
}

@Composable
private fun Bubble(m: Msg) {
    val mine = m.fromUser
    val shape = if (mine) RoundedCornerShape(22.dp, 22.dp, 6.dp, 22.dp) else RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp)
    val bg = when {
        m.urgent -> Modifier.background(MaterialTheme.colorScheme.errorContainer, shape)
        mine -> Modifier.background(BubbleGradient, shape)
        else -> Modifier.background(MaterialTheme.colorScheme.surface, shape)
    }
    val ink = when {
        m.urgent -> MaterialTheme.colorScheme.onErrorContainer
        mine -> Color.White
        else -> MaterialTheme.colorScheme.onSurface
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
        Text(
            m.text,
            Modifier.widthIn(max = 320.dp).then(bg).padding(horizontal = 16.dp, vertical = 12.dp)
                .semantics { contentDescription = (if (mine) "You said: " else if (m.urgent) "Urgent, Bubbles said: " else "Bubbles said: ") + m.text },
            style = MaterialTheme.typography.bodyLarge, color = ink,
        )
    }
}

@Composable
private fun ConsentRow(onYes: () -> Unit, onNo: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(top = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Pill("Yes, use outside AI", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer, onClick = onYes)
        Pill("Not now", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant, onClick = onNo)
    }
}

@Composable
private fun Composer(value: String, onChange: (String) -> Unit, enabled: Boolean, onSend: () -> Unit) {
    val can = enabled && value.isNotBlank()
    Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 6.dp, bottom = 8.dp), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextField(
            value, onChange, Modifier.weight(1f).heightIn(min = 52.dp),
            placeholder = { Text("Tell me anything…", style = MaterialTheme.typography.bodyLarge) },
            shape = RoundedCornerShape(26.dp), maxLines = 5,
            colors = TextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surface, unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent,
            ),
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Default),
        )
        Box(
            Modifier.size(52.dp).background(if (can) BubbleGradient else androidx.compose.ui.graphics.SolidColor(MaterialTheme.colorScheme.surfaceVariant), CircleShape)
                .clickable(enabled = can, role = Role.Button, onClickLabel = "Send", onClick = onSend),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.AutoMirrored.Rounded.Send, contentDescription = "Send", tint = if (can) Color.White else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun Typing() {
    val t = rememberInfiniteTransition(label = "typing")
    Row(
        Modifier.background(MaterialTheme.colorScheme.surface, RoundedCornerShape(22.dp)).padding(horizontal = 16.dp, vertical = 16.dp)
            .semantics { contentDescription = "Bubbles is typing" },
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        repeat(3) { i ->
            val a by t.animateFloat(0.25f, 1f, infiniteRepeatable(tween(600, delayMillis = i * 150), RepeatMode.Reverse), label = "dot$i")
            Box(Modifier.size(8.dp).background(Bubbles.Pink.copy(alpha = a), CircleShape))
        }
    }
}

@Composable
private fun EmptyTalk(onPick: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Box(Modifier.size(72.dp).background(MaterialTheme.colorScheme.primaryContainer, CircleShape), contentAlignment = Alignment.Center) {
            Icon(ChatBubbleIcon, null, Modifier.size(34.dp), tint = MaterialTheme.colorScheme.primary)
        }
        Text("Start with whatever's on your mind", Modifier.padding(top = 16.dp), style = MaterialTheme.typography.titleLarge)
        Text("Log in plain words, in English, Hinglish or Hindi.", Modifier.padding(top = 4.dp, bottom = 16.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        listOf("Slept 7 hours", "2 rotis, dal and curd", "Cramps since morning", "Drank 2 glasses of water").forEach {
            Pill(it, MaterialTheme.colorScheme.surface, MaterialTheme.colorScheme.onSurface, Modifier.padding(vertical = 4.dp)) { onPick(it) }
        }
    }
}
