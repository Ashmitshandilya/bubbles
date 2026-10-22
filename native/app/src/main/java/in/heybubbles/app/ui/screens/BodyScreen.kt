package `in`.heybubbles.app.ui.screens

import android.annotation.SuppressLint
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.background
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.webkit.WebViewAssetLoader
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.GENERAL_EMERGENCY_LINE
import `in`.heybubbles.app.data.OrganStatus
import `in`.heybubbles.app.data.effectiveStatus
import `in`.heybubbles.app.data.fmtNum
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.objs
import `in`.heybubbles.app.data.safetyText
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.screens.fitness.FitnessPage
import `in`.heybubbles.app.ui.screens.fitness.LoadGate
import `in`.heybubbles.app.ui.screens.fitness.rememberLoad
import `in`.heybubbles.app.ui.theme.Bubbles

private fun statusTint(s: OrganStatus): Color = when (s) {
    OrganStatus.TalkToDoctor -> Bubbles.TintUrgent
    OrganStatus.WorthWatching -> Bubbles.TintSun
    OrganStatus.Steady -> Bubbles.TintMint
    OrganStatus.NoData -> Color(0xFFF1ECF8)
}

private fun statusDot(s: OrganStatus): Color = when (s) {
    OrganStatus.TalkToDoctor -> Color(0xFF9A3A12)
    OrganStatus.WorthWatching -> Color(0xFFFFC83D)
    OrganStatus.Steady -> Color(0xFF22C39A)
    OrganStatus.NoData -> Color(0xFFB9AFCB)
}

/**
 * The body map: a 3D body you can turn and tap, over a plain list that has everything the 3D view has. The picture only reflects what has
 * been logged; it is never a diagnosis, and an area with no entries is shown as a gap. If 3D can't start on this phone, the list stands alone.
 */
@Composable
fun BodyScreen(api: Api, onBack: () -> Unit) {
    val map = rememberLoad(api, "/organs/map")
    val info by produceState<Pair<Boolean, String>?>(null) { value = runCatching { api.bodyMapInfo() }.getOrNull() }
    var selected by remember { mutableStateOf<String?>(null) }
    var ready by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    // A slow phone can switch 3D off; the choice is remembered. The list below always has the same information.
    val ctx = LocalContext.current
    val prefs = remember { ctx.getSharedPreferences("bubbles_ui", android.content.Context.MODE_PRIVATE) }
    var show3d by remember { mutableStateOf(prefs.getBoolean("body3d", true)) }
    var view by remember { mutableStateOf("front") }
    var web by remember { mutableStateOf<WebView?>(null) }

    FitnessPage("Your body, as logged", "Body map", onBack) {
        if (info?.first == false) {
            Text("The body map is not shown for your profile. Everything else in Bubbles works the same.", style = MaterialTheme.typography.bodyMedium)
            return@FitnessPage
        }
        LoadGate(map) { data ->
            val organs = data.objs("organs")
            // Push the data into the 3D page once it says it is ready, and again whenever it changes.
            LaunchedEffect(ready, organs, info) {
                val w = web ?: return@LaunchedEffect
                if (!ready) return@LaunchedEffect
                val list = JsonArray(organs.map { o -> buildJsonObject { put("id", o.str("organ_id").orEmpty()); put("status", effectiveStatus(o).id) } })
                w.evaluateJavascript("bodyApi.setOrgans($list)", null)
                w.evaluateJavascript("bodyApi.setAnatomy('${info?.second.orEmpty().filter { it.isLetter() }}')", null)
            }
            LaunchedEffect(selected, ready) { if (ready) web?.evaluateJavascript("bodyApi.select(${selected?.let { "'${it.filter { c -> c.isLetterOrDigit() || c == '_' }}'" } ?: "null"})", null) }
            LaunchedEffect(view, ready) { if (ready) web?.evaluateJavascript("bodyApi.setView('$view')", null) }

            if (!failed && show3d) {
                Box(
                    Modifier.fillMaxWidth().height(380.dp).clip(RoundedCornerShape(28.dp)).background(Color(0xFFFFF7FA))
                        .semantics { contentDescription = "3D body map. Turn it with one finger and tap a part to read about it. The same list is below." },
                ) {
                    BodyWebView(onCreated = { web = it }, onReady = { ready = true }, onPick = { selected = it }, onError = { failed = true })
                    if (!ready) Text("Getting your body ready…", Modifier.padding(20.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("front" to "Front", "side" to "Side", "back" to "Back").forEach { (id, label) ->
                        Pill(label, if (view == id) Bubbles.Pink else MaterialTheme.colorScheme.surfaceVariant, if (view == id) Bubbles.White else MaterialTheme.colorScheme.onSurface) { view = id }
                    }
                    Pill("Hide 3D", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant) { show3d = false; ready = false; web = null; prefs.edit().putBoolean("body3d", false).apply() }
                }
            } else {
                Text(
                    if (failed) "The 3D view isn't available on this phone, so here is the same information as a list." else "3D is off. Here is the same information as a list.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (!failed) Pill("Show 3D", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer) { show3d = true; prefs.edit().putBoolean("body3d", true).apply() }
            }

            Text(data.str("notice").orEmpty(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            val current = organs.firstOrNull { it.str("organ_id") == selected }
            if (current != null) OrganDetail(current) else Text("Tap a part of the body, or choose from the list.", style = MaterialTheme.typography.bodyMedium)

            Eyebrow("All areas")
            organs.forEach { o ->
                val st = effectiveStatus(o)
                BubbleCard(Modifier.fillMaxWidth(), tint = if (o.str("organ_id") == selected) statusTint(st) else null, onClick = { selected = o.str("organ_id") }) {
                    Row(Modifier.padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        `in`.heybubbles.app.ui.components.Dot(statusDot(st), 12.dp)
                        Column(Modifier.weight(1f)) {
                            Text(o.str("name").orEmpty(), style = MaterialTheme.typography.titleMedium)
                            Text(st.label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OrganDetail(o: JsonObject) {
    val st = effectiveStatus(o)
    BubbleCard(Modifier.fillMaxWidth(), tint = statusTint(st)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(o.str("name").orEmpty(), style = MaterialTheme.typography.titleLarge)
            Text(st.label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurface)
            // Safety wording leads, in the server's own words; otherwise a general emergency line.
            if (st == OrganStatus.TalkToDoctor) {
                Text("${o.str("name").orEmpty()}: please check this with a doctor.", style = MaterialTheme.typography.titleSmall)
                Text(o.safetyText() ?: GENERAL_EMERGENCY_LINE, style = MaterialTheme.typography.bodyMedium)
            }
            o.str("summary")?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
            o.strs("reasons").filter { it != o.str("summary") }.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
            o.objs("evidence").take(5).takeIf { it.isNotEmpty() }?.let { ev ->
                Text("From your entries", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 4.dp))
                ev.forEach { e ->
                    val value = e.num("value")?.let { " ${fmtNum(it)} ${e.str("unit").orEmpty()}".trimEnd() }.orEmpty()
                    Text("${e.str("date").orEmpty()}: ${e.str("label").orEmpty()}$value", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(st.meaning, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("Next step: ${st.nextStep}", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/**
 * The 3D page runs from the app's own assets (three.js and the model ship inside the app) and is not allowed to touch the network or
 * any file. It reports only "ready", a tapped organ id, or an error; it never receives anything but organ ids and statuses.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun BodyWebView(onCreated: (WebView) -> Unit, onReady: () -> Unit, onPick: (String) -> Unit, onError: () -> Unit) {
    val context = LocalContext.current
    val main = remember { Handler(Looper.getMainLooper()) }
    val loader = remember { WebViewAssetLoader.Builder().addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(context)).build() }
    var created by remember { mutableStateOf<WebView?>(null) }
    DisposableEffect(Unit) { onDispose { created?.let { it.removeJavascriptInterface("Bubbles"); it.destroy() } } }
    AndroidView(
        modifier = Modifier.fillMaxWidth().height(380.dp),
        factory = { ctx ->
            runCatching {
                WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.blockNetworkLoads = true
                    setBackgroundColor(0)
                    webChromeClient = object : android.webkit.WebChromeClient() {
                        override fun onConsoleMessage(m: android.webkit.ConsoleMessage): Boolean {
                            android.util.Log.d("BodyMap", "${m.message()} (${m.sourceId().substringAfterLast('/')}:${m.lineNumber()})")
                            return true
                        }
                    }
                    webViewClient = object : WebViewClient() {
                        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                            val r = loader.shouldInterceptRequest(request.url)
                            android.util.Log.d("BodyMap", "load ${request.url.path} -> ${if (r == null) "NOT FOUND" else "ok"}")
                            return r
                        }
                        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: android.webkit.WebResourceError) {
                            android.util.Log.d("BodyMap", "error ${request.url.path}: ${error.description}")
                        }
                        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = true
                    }
                    addJavascriptInterface(object {
                        @JavascriptInterface fun onReady() { main.post { onReady() } }
                        @JavascriptInterface fun onPick(id: String) { main.post { onPick(id) } }
                        @JavascriptInterface fun onError(message: String) { android.util.Log.d("BodyMap", "page error: $message"); main.post { onError() } }
                    }, "Bubbles")
                    loadUrl("https://appassets.androidplatform.net/assets/body/index.html")
                    created = this
                    onCreated(this)
                }
            }.getOrElse { main.post { onError() }; View(ctx) }
        },
    )
}
