package `in`.heybubbles.app.data

import `in`.heybubbles.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
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
@Serializable private data class ChatBody(val message: String, val message_id: String, val conversation_id: String? = null)
@Serializable private data class ConsentBody(val granted: Boolean, val source: String = "app")

/** One client for the existing FastAPI. The server owns safety, consent and memory; this only carries requests. */
class Api(private val session: Session) {
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true; encodeDefaults = true }
    private val http = OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(90, TimeUnit.SECONDS).build()
    private val jsonType = "application/json".toMediaType()

    private class Raw(val code: Int, val body: String)

    suspend fun signIn(email: String, password: String) = withContext(Dispatchers.IO) {
        if (BuildConfig.SUPABASE_URL.isBlank()) throw ApiError(500, "This build has no sign-in server set up.")
        val res = authCall("password", json.encodeToString(Credentials.serializer(), Credentials(email.trim(), password)))
        if (res.code == 400 || res.code == 401) throw ApiError(401, "That email and password don't match.")
        keep(res)
    }

    /** Debug builds only: the local preview server accepts the token "preview". */
    fun useDemo() {
        check(BuildConfig.DEBUG)
        session.save("preview", null)
    }

    fun signOut() = session.clear()

    private fun authCall(grant: String, body: String): Raw {
        val req = Request.Builder().url("${BuildConfig.SUPABASE_URL}/auth/v1/token?grant_type=$grant")
            .header("apikey", BuildConfig.SUPABASE_KEY).post(body.toRequestBody(jsonType)).build()
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

    suspend fun chat(message: String, messageId: String, conversationId: String?): ChatReply =
        json.decodeFromString(send("POST", "/chat", json.encodeToString(ChatBody.serializer(), ChatBody(message, messageId, conversationId))))

    suspend fun latestChat(): LatestChat = json.decodeFromString(get("/chat/latest?limit=100"))
    suspend fun daily(): DailyResponse = json.decodeFromString(send("POST", "/companion/daily", "{}"))
    suspend fun setConsent(purpose: String, granted: Boolean) {
        send("PUT", "/consents/$purpose", json.encodeToString(ConsentBody.serializer(), ConsentBody(granted)))
    }
}
