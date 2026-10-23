package `in`.heybubbles.app.data

import `in`.heybubbles.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

class ApiError(val code: Int, message: String) : IOException(message)

/** Plain-language reasons the UI can show; never raw server text or stack traces. */
fun Throwable.friendly(): String = when {
    this is ApiError && code == 401 -> message ?: "Please sign in again."
    this is ApiError && code == 429 -> "Too many tries. Give it a minute."
    this is ApiError && code >= 500 -> "Bubbles is waking up. Try again in a moment."
    this is ApiError -> message ?: "That didn't work."
    else -> "Can't reach Bubbles. Check your connection."
}

@Serializable private data class Credentials(val email: String, val password: String)
@Serializable private data class RefreshBody(val refresh_token: String)
@Serializable private data class ChatBody(val message: String, val message_id: String, val conversation_id: String? = null, val mode: String? = null)
@Serializable private data class ConsentBody(val granted: Boolean, val source: String = "settings", val text_hash: String? = null)
@Serializable private data class ChatConsentBody(val ai_chat: Boolean, val source: String = "chat_card")

/** One client for the existing FastAPI. The server owns safety, consent and memory; this only carries requests. */
class Api(private val session: Session) {
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true; encodeDefaults = true }
    // Today and Track ask for about 18 tracker lists at once; OkHttp's default of 5 per host would queue the rest behind them.
    private val http = OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(90, TimeUnit.SECONDS)
        .dispatcher(okhttp3.Dispatcher().apply { maxRequestsPerHost = 16; maxRequests = 32 }).build()

    /** One quiet GET /health at app start: the free API host sleeps when idle, and this lets it start while the app opens. No sign-in, no data. */
    fun wake() {
        Thread {
            runCatching { http.newCall(Request.Builder().url(BuildConfig.API_URL + "/health").get().build()).execute().close() }
        }.apply { isDaemon = true }.start()
    }
    private val jsonType = "application/json".toMediaType()

    private class Raw(val code: Int, val body: String)

    suspend fun signIn(email: String, password: String) = withContext(Dispatchers.IO) {
        if (BuildConfig.SUPABASE_URL.isBlank()) throw ApiError(500, "This build has no sign-in server set up.")
        val res = authCall("password", json.encodeToString(Credentials.serializer(), Credentials(email.trim(), password)))
        if (res.code == 400 || res.code == 401) throw ApiError(401, "That email and password don't match.")
        keep(res)
        recordAcknowledgement()   // a sign-up made before the email was confirmed
    }

    /**
     * Creates the account (the same Supabase call as the website). With "Confirm email" on, no session comes back: the person opens the
     * link we emailed (in their browser) and then signs in. The Terms and Privacy tick is kept until the first signed-in request can record it.
     * Returns true when the person is already signed in.
     */
    suspend fun signUp(name: String, email: String, password: String): Boolean = withContext(Dispatchers.IO) {
        if (BuildConfig.SUPABASE_URL.isBlank()) throw ApiError(500, "This build has no sign-in server set up.")
        val body = buildJsonObject {
            put("email", email.trim()); put("password", password)
            put("data", buildJsonObject { put("display_name", name.trim().take(80)) })
        }
        val res = authPost("signup", AuthRules.CALLBACK_URL, json.encodeToString(JsonObject.serializer(), body))
        when {
            res.code == 429 -> throw ApiError(429, "Too many tries. Give it a minute.")
            res.code in 400..499 -> throw ApiError(res.code, "Bubbles couldn't create that account. Check the email and use at least ${AuthRules.MIN_PASSWORD} characters.")
            res.code !in 200..299 -> throw ApiError(res.code, "Bubbles is waking up. Try again in a moment.")
        }
        session.pendingAck = AuthRules.NOTICE_VERSION
        val signedIn = runCatching { json.parseToJsonElement(res.body).jsonObject["access_token"]?.jsonPrimitive?.contentOrNull }.getOrNull() != null
        if (signedIn) { keep(res); recordAcknowledgement() }
        signedIn
    }

    /** Sends the confirmation email again. The answer never says whether the address has an account. */
    suspend fun resendConfirmation(email: String) = withContext(Dispatchers.IO) {
        val res = authPost("resend", AuthRules.CALLBACK_URL, json.encodeToString(JsonObject.serializer(), buildJsonObject { put("type", "signup"); put("email", email.trim()) }))
        if (res.code == 429) throw ApiError(429, "Too many tries. Give it a minute.")
    }

    /** Sends a link to set a new password (it opens in the browser). Also works for accounts that never set one. */
    suspend fun sendPasswordLink(email: String) = withContext(Dispatchers.IO) {
        val res = authPost("recover", AuthRules.RESET_URL, json.encodeToString(JsonObject.serializer(), buildJsonObject { put("email", email.trim()) }))
        if (res.code == 429) throw ApiError(429, "Too many tries. Give it a minute.")
    }

    /** Records "read the Terms and the Privacy notice" once the new account can call the server. Kept for the next try when it fails. */
    private fun recordAcknowledgement() {
        val version = session.pendingAck ?: return
        runCatching {
            call("POST", "/consents/acknowledgements", json.encodeToString(JsonObject.serializer(), buildJsonObject { put("version", version) }))
            session.pendingAck = null
        }
    }

    /** Test builds only (debug and qa): the local preview server accepts the token "preview". */
    fun useDemo() {
        check(BuildConfig.DEMO)
        session.save("preview", null)
    }

    fun signOut() = session.clear()

    private fun authCall(grant: String, body: String): Raw {
        val req = Request.Builder().url("${BuildConfig.SUPABASE_URL}/auth/v1/token?grant_type=$grant")
            .header("apikey", BuildConfig.SUPABASE_KEY).post(body.toRequestBody(jsonType)).build()
        http.newCall(req).execute().use { return Raw(it.code, it.body?.string().orEmpty()) }
    }

    private fun authPost(path: String, redirectTo: String, body: String): Raw {
        val url = "${BuildConfig.SUPABASE_URL}/auth/v1/$path?redirect_to=${java.net.URLEncoder.encode(redirectTo, "UTF-8")}"
        val req = Request.Builder().url(url).header("apikey", BuildConfig.SUPABASE_KEY).post(body.toRequestBody(jsonType)).build()
        http.newCall(req).execute().use { return Raw(it.code, it.body?.string().orEmpty()) }
    }

    private fun keep(res: Raw) {
        if (res.code !in 200..299) throw ApiError(res.code, "Sign-in failed. Try again.")
        val o: JsonObject = json.parseToJsonElement(res.body).jsonObject
        val access = o["access_token"]?.jsonPrimitive?.contentOrNull ?: throw ApiError(500, "Sign-in failed. Try again.")
        session.save(access, o["refresh_token"]?.jsonPrimitive?.contentOrNull)
    }

    private fun refreshToken(): Boolean {
        val rt = session.refresh ?: return false
        return try {
            keep(authCall("refresh_token", json.encodeToString(RefreshBody.serializer(), RefreshBody(rt))))
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun call(method: String, path: String, body: String?): String {
        fun once(): Raw {
            val b = Request.Builder().url(BuildConfig.API_URL + path).header("Authorization", "Bearer ${session.access.orEmpty()}")
            if (method == "GET") b.get() else b.method(method, (body ?: "{}").toRequestBody(jsonType))
            http.newCall(b.build()).execute().use { return Raw(it.code, it.body?.string().orEmpty()) }
        }
        var r = once()
        if (r.code == 401 && refreshToken()) r = once()
        if (r.code == 401) {
            session.clear()
            throw ApiError(401, "Please sign in again.")
        }
        if (r.code !in 200..299) throw ApiError(r.code, detail(r.body))
        return r.body
    }

    private fun detail(raw: String): String = runCatching {
        val d = json.parseToJsonElement(raw).jsonObject["detail"]
        if (d is JsonPrimitive) d.content else d?.jsonObject?.get("message")?.jsonPrimitive?.content
    }.getOrNull() ?: "That didn't work."

    private suspend fun get(path: String): String = withContext(Dispatchers.IO) { call("GET", path, null) }
    private suspend fun send(method: String, path: String, body: String): String = withContext(Dispatchers.IO) { call(method, path, body) }

    /** [mode] is "orbit" for a Heart-to-heart thread (its own voice and rules on the server); null for ordinary Talk. */
    suspend fun chat(message: String, messageId: String, conversationId: String?, mode: String? = null): ChatReply =
        json.decodeFromString(send("POST", "/chat", json.encodeToString(ChatBody.serializer(), ChatBody(message, messageId, conversationId, mode))))

    /** GET /health/<slug>?days=N, newest first. */
    suspend fun entries(slug: String, days: Int): List<Entry> {
        val root = json.parseToJsonElement(get("/health/$slug?days=$days")).jsonObject
        val rows = root["entries"] as? kotlinx.serialization.json.JsonArray ?: return emptyList()
        return rows.mapNotNull { el ->
            val o = el as? JsonObject ?: return@mapNotNull null
            val id = (o["id"] as? JsonPrimitive)?.content ?: return@mapNotNull null
            Entry(id, (o["date"] as? JsonPrimitive)?.content.orEmpty(), o)
        }.sortedByDescending { it.date }
    }

    /** POST /health/<slug>. No date is sent, so the server stamps "now". */
    suspend fun saveEntry(slug: String, body: JsonObject) { send("POST", "/health/$slug", json.encodeToString(JsonObject.serializer(), body)) }

    suspend fun deleteEntry(slug: String, id: String) { send("DELETE", "/health/$slug/$id", "{}") }

    suspend fun onboardingBank(): Bank = parseBank(json.parseToJsonElement(get("/onboarding/questions")).jsonObject)

    /** Whether this person has already seen (or skipped) the first-run tour. */
    suspend fun tourSeen(): Boolean = (json.parseToJsonElement(get("/onboarding/tour")).jsonObject["seen"] as? JsonPrimitive)?.booleanOrNull == true

    suspend fun finishTour(skipped: Boolean) { send("PUT", "/onboarding/tour", """{"skipped":$skipped}""") }

    suspend fun onboardingState(): OnboardingState {
        val o = json.parseToJsonElement(get("/onboarding/state")).jsonObject
        return OnboardingState(
            complete = (o["complete"] as? JsonPrimitive)?.booleanOrNull == true,
            under18 = (o["under_18"] as? JsonPrimitive)?.booleanOrNull == true,
            answers = (o["answers"] as? JsonObject) ?: JsonObject(emptyMap()),
            step = (o["step"] as? JsonPrimitive)?.intOrNull ?: 0,
        )
    }

    suspend fun saveAnswers(patch: Map<String, kotlinx.serialization.json.JsonElement>, step: Int) {
        val body = JsonObject(mapOf("answers" to JsonObject(patch), "step" to JsonPrimitive(step)))
        send("PUT", "/onboarding/answers", json.encodeToString(JsonObject.serializer(), body))
    }

    /** Finishes setup and returns the plain lines describing what Bubbles set up from the answers. */
    suspend fun completeOnboarding(): List<String> {
        val o = json.parseToJsonElement(send("POST", "/onboarding/complete", "{}")).jsonObject
        return (o["applied"] as? kotlinx.serialization.json.JsonArray).orEmpty().mapNotNull { ((it as? JsonObject)?.get("label") as? JsonPrimitive)?.contentOrNull }
    }

    suspend fun cycleOverview(today: java.time.LocalDate): CycleOverview = json.decodeFromString(get("/cycle/overview?today=$today"))

    /** Logs that a period started today (the same call the website's Cycle page makes). */
    suspend fun logPeriodStart() { send("POST", "/health/cycle", "{\"phase\":\"period\"}") }

    suspend fun weekly(): List<WeeklyItem> = json.decodeFromString<WeeklyResponse>(get("/insights/weekly")).insights.insights

    /** The sections the server says this person should see (it hides Cycle for some profiles). Null if the profile isn't built yet. */
    suspend fun visibleSections(): Set<String>? {
        val exp = json.parseToJsonElement(get("/experience")).jsonObject["experience"] as? JsonObject ?: return null
        val sections = exp["sections"] as? JsonObject ?: return null
        return (sections["visible"] as? kotlinx.serialization.json.JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }?.toSet()
    }

    /** Whether the body map is shown for this profile (not for some), and which body model it uses ("female", "male" or a general one). */
    suspend fun bodyMapInfo(): Pair<Boolean, String> {
        val exp = getJson("/experience").obj("experience")
        val bm = exp?.obj("body_map")
        return (bm?.bool("visible") != false) to (bm?.str("anatomy") ?: "neutral")
    }

    /** POST /doctor/prepare: the questions to ask and what to bring, from the last six months of logs. */
    suspend fun visitPrep(concern: String?): VisitPrep {
        val body = JsonObject(buildMap {
            put("days", JsonPrimitive(180))
            if (!concern.isNullOrBlank()) put("concern", JsonPrimitive(concern.trim()))
        })
        val visit = json.parseToJsonElement(send("POST", "/doctor/prepare", json.encodeToString(JsonObject.serializer(), body))).jsonObject["visit"] as? JsonObject
        fun list(k: String) = (visit?.get(k) as? kotlinx.serialization.json.JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()
        return VisitPrep(list("questions"), list("bring"))
    }

    suspend fun notificationSettings(): ReminderSettings {
        val o = json.parseToJsonElement(get("/notifications/settings")).jsonObject
        val st = o["settings"] as? JsonObject
        val ch = o["channels"] as? JsonObject
        fun flag(obj: JsonObject?, k: String) = (obj?.get(k) as? JsonPrimitive)?.booleanOrNull == true
        val types = st?.get("types") as? JsonObject
        val quiet = st?.get("quiet_hours") as? JsonObject
        return ReminderSettings(
            push = flag(st?.get("channels") as? JsonObject, "push"),
            pushAvailable = flag(ch?.get("push") as? JsonObject, "available"),
            water = flag(types, "water"), med = flag(types, "med"), winddown = flag(types, "winddown"),
            quiet = if (flag(quiet, "enabled")) "${(quiet?.get("start") as? JsonPrimitive)?.contentOrNull}–${(quiet?.get("end") as? JsonPrimitive)?.contentOrNull}" else null,
        )
    }

    /** A partial update: only the keys given change. The server records the push yes or no in the consent ledger. */
    suspend fun saveReminderSettings(push: Boolean? = null, types: Map<String, Boolean> = emptyMap()) {
        val body = JsonObject(buildMap {
            if (push != null) put("channels", JsonObject(mapOf("push" to JsonPrimitive(push))))
            if (types.isNotEmpty()) put("types", JsonObject(types.mapValues { JsonPrimitive(it.value) }))
        })
        send("PUT", "/notifications/settings", json.encodeToString(JsonObject.serializer(), body))
    }

    suspend fun registerDevice(token: String) {
        send("POST", "/notifications/devices", json.encodeToString(JsonObject.serializer(), JsonObject(mapOf("token" to JsonPrimitive(token), "platform" to JsonPrimitive("android")))))
    }

    suspend fun removeDevice(token: String) {
        send("POST", "/notifications/devices/remove", json.encodeToString(JsonObject.serializer(), JsonObject(mapOf("token" to JsonPrimitive(token)))))
    }

    /** Sends one test reminder and returns a plain sentence for the person. */
    suspend fun pushTest(): String {
        val o = json.parseToJsonElement(send("POST", "/notifications/push/test", "{}")).jsonObject
        val sent = (o["sent"] as? JsonPrimitive)?.intOrNull ?: 0
        val removed = (o["removed"] as? JsonPrimitive)?.intOrNull ?: 0
        val reason = (o["reason"] as? JsonPrimitive)?.contentOrNull
        return when {
            reason == "wait" -> "A test was just sent. Try again in a minute."
            sent > 0 -> "Test sent. It can take a few seconds to arrive."
            reason == "no_devices" || removed > 0 -> "This phone isn't connected. Turn phone reminders off and on again."
            else -> "Couldn't send the test right now. Your reminders still show in Bubbles."
        }
    }

    suspend fun communityStatus(): CommunityStatus = json.decodeFromString(get("/community/status"))

    suspend fun communityPosts(topic: String?, mine: Boolean, cursor: String?): FeedResponse {
        val q = buildList {
            if (topic != null) add("topic=$topic")
            if (mine) add("mine=true")
            if (cursor != null) add("cursor=" + java.net.URLEncoder.encode(cursor, "UTF-8"))
        }.joinToString("&")
        return json.decodeFromString(get("/community/posts" + if (q.isEmpty()) "" else "?$q"))
    }

    suspend fun communityComments(postId: String): List<CommunityPost> = json.decodeFromString<CommentsResponse>(get("/community/posts/$postId/comments")).comments

    suspend fun createPost(topic: String, body: String, anonymous: Boolean): PostResult =
        json.decodeFromString(send("POST", "/community/posts", json.encodeToString(PostBody.serializer(), PostBody(topic, body, anonymous))))

    suspend fun createComment(postId: String, body: String, anonymous: Boolean): PostResult =
        json.decodeFromString(send("POST", "/community/posts/$postId/comments", json.encodeToString(CommentBody.serializer(), CommentBody(body, anonymous))))

    suspend fun react(target: String, kind: String) { send("POST", "/community/reactions", json.encodeToString(ReactBody.serializer(), ReactBody(target, kind))) }
    suspend fun report(target: String, reason: String) { send("POST", "/community/reports", json.encodeToString(ReportBody.serializer(), ReportBody(target, reason))) }
    suspend fun block(target: String) { send("POST", "/community/blocks", json.encodeToString(TargetBody.serializer(), TargetBody(target))) }
    suspend fun deleteCommunityItem(kind: String, id: String) { send("DELETE", "/community/$kind/$id", "{}") }

    suspend fun latestChat(): LatestChat = json.decodeFromString(get("/chat/latest?limit=100"))
    suspend fun associations(): AssociationsResponse = json.decodeFromString(get("/wellness/associations"))
    suspend fun daily(): DailyResponse = json.decodeFromString(send("POST", "/companion/daily", "{}"))
    /** Everything Today shows, in one call (the server reads the parts side by side and chooses the lede sentence). */
    suspend fun today(): TodayBundle = parseToday(getJson("/today?days=14"))
    suspend fun setConsent(purpose: String, granted: Boolean, textHash: String? = null, source: String = "settings") {
        send("PUT", "/consents/$purpose", json.encodeToString(ConsentBody.serializer(), ConsentBody(granted, source, textHash)))
    }

    /** The answer to the "use an outside AI?" card in chat. A yes goes through the same endpoint the website uses, which records the wording the person was shown. */
    suspend fun answerChatConsent(yes: Boolean) {
        if (yes) send("PUT", "/me/consent", json.encodeToString(ChatConsentBody.serializer(), ChatConsentBody(true)))
        else setConsent("ai_chat_processing", false, null, "chat_card")
    }

    suspend fun consents(): List<Purpose> = json.decodeFromString<ConsentsResponse>(get("/consents")).purposes

    /** Deletes Fitness, Cycle, plan and Community data. Tracker entries are separate (the server says so in its reply). */
    suspend fun deleteMyData() { send("DELETE", "/me/whole-health/data?confirm=true", "{}") }

    /** Erases the whole account (every record and the sign-in). The server answers success only when both steps worked. */
    /** Fitness speaks plain JSON documents whose shape the server owns; these two calls carry them without a model per screen. */
    suspend fun getJson(path: String): JsonObject = json.parseToJsonElement(get(path)).jsonObject

    suspend fun sendJson(method: String, path: String, body: JsonObject? = null): JsonObject {
        val text = send(method, path, body?.toString() ?: "{}")
        return if (text.isBlank()) JsonObject(emptyMap()) else json.parseToJsonElement(text).jsonObject
    }

    suspend fun deleteAccount() { send("DELETE", "/me/account?confirm=true", "{}") }
}
