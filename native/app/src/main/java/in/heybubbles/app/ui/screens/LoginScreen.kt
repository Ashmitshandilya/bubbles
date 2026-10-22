package `in`.heybubbles.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import `in`.heybubbles.app.BuildConfig
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.AuthRules
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.CheckRow
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.Mascot
import `in`.heybubbles.app.ui.theme.Bubbles

enum class AuthMode(val tab: String, val action: String) {
    SignIn("Sign in", "Sign in"), SignUp("Create account", "Create my account"), Reset("Forgot password", "Send me a link")
}

@Composable
fun LoginScreen(api: Api) {
    var mode by remember { mutableStateOf(AuthMode.SignIn) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var acknowledged by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var canResend by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    val links = LocalUriHandler.current

    fun switchTo(next: AuthMode) { mode = next; error = null; info = null; canResend = false }

    fun submit() {
        if (busy) return
        error = null; info = null
        when (mode) {
            AuthMode.SignIn -> if (email.isBlank() || password.isBlank()) return
            AuthMode.SignUp -> AuthRules.signUpProblem(name, email, password, acknowledged)?.let { error = it; return }
            AuthMode.Reset -> if (!AuthRules.looksLikeEmail(email)) { error = "That email doesn't look right."; return }
        }
        busy = true
        scope.launch {
            try {
                when (mode) {
                    AuthMode.SignIn -> api.signIn(email, password)
                    AuthMode.SignUp -> if (!api.signUp(name, email, password)) {
                        info = "Account created! Open the link we emailed you to confirm it (it opens in your browser), then come back here and sign in. Check spam if you can't see it."
                        canResend = true
                    }
                    AuthMode.Reset -> {
                        api.sendPasswordLink(email)
                        info = "If an account exists for that email, we've sent a link. It opens in your browser: set your password there, then come back here and sign in."
                    }
                }
            } catch (e: Exception) { error = e.friendly() }
            busy = false
        }
    }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 28.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(24.dp))
        // The brand character, not a placeholder shape.
        Mascot(120.dp, title = "Bubbles the unicorn")
        Spacer(Modifier.height(20.dp))
        Eyebrow("Welcome")
        Text(if (mode == AuthMode.SignUp) "Nice to meet you!" else "Hey, I'm Bubbles", style = MaterialTheme.typography.headlineLarge, textAlign = TextAlign.Center)
        Text(
            when (mode) {
                AuthMode.SignUp -> "Create your Bubbles and start with one message."
                AuthMode.Reset -> "Enter your email and I'll send a link to set a new password."
                else -> "Tell me how you are in your own words. I'll remember, connect the dots and help you prepare for care."
            },
            Modifier.padding(top = 8.dp, bottom = 20.dp), style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
        )
        if (mode != AuthMode.Reset) {
            Row(Modifier.fillMaxWidth().padding(bottom = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(AuthMode.SignIn, AuthMode.SignUp).forEach { m ->
                    val on = mode == m
                    Box(
                        Modifier.weight(1f).heightIn(min = 48.dp)
                            .background(if (on) MaterialTheme.colorScheme.primaryContainer else Color.Transparent, RoundedCornerShape(24.dp))
                            .selectable(selected = on, role = Role.Tab, onClick = { switchTo(m) }),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(m.tab, style = MaterialTheme.typography.titleSmall, color = if (on) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        if (mode == AuthMode.SignUp) {
            OutlinedTextField(
                name, { name = it.take(80) }, Modifier.fillMaxWidth(), label = { Text("What should Bubbles call you?") }, singleLine = true,
                shape = MaterialTheme.shapes.medium,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words, imeAction = ImeAction.Next),
                keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Down) }),
            )
            Spacer(Modifier.height(12.dp))
        }
        OutlinedTextField(
            email, { email = it }, Modifier.fillMaxWidth(), label = { Text("Email") }, singleLine = true,
            shape = MaterialTheme.shapes.medium,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = if (mode == AuthMode.Reset) ImeAction.Go else ImeAction.Next),
            keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Down) }, onGo = { focus.clearFocus(); submit() }),
        )
        if (mode != AuthMode.Reset) {
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                password, { password = it }, Modifier.fillMaxWidth(), label = { Text("Password") }, singleLine = true,
                supportingText = if (mode == AuthMode.SignUp) ({ Text("At least ${AuthRules.MIN_PASSWORD} characters.") }) else null,
                shape = MaterialTheme.shapes.medium, visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { focus.clearFocus(); submit() }),
            )
        }
        if (mode == AuthMode.SignUp) {
            Spacer(Modifier.height(8.dp))
            CheckRow("I have read the Terms and the Privacy notice. This is not a consent: your privacy choices come later and are all off until you turn them on.", acknowledged) { acknowledged = it }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                LinkText("Read the Terms") { links.openUri("https://heybubbles.in/terms") }
                LinkText("Read the Privacy notice") { links.openUri("https://heybubbles.in/privacy") }
            }
        }
        error?.let {
            Text(it, Modifier.padding(top = 12.dp).semantics { liveRegion = LiveRegionMode.Polite; contentDescription = "Error: $it" }, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
        info?.let {
            Text(it, Modifier.padding(top = 12.dp).semantics { liveRegion = LiveRegionMode.Polite }, color = MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(20.dp))
        Box(
            Modifier.fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp))
                .clickable(enabled = !busy, role = Role.Button, onClickLabel = mode.action) { submit() },
            contentAlignment = Alignment.Center,
        ) {
            if (busy) CircularProgressIndicator(Modifier.size(24.dp), color = Bubbles.White, strokeWidth = 2.5.dp)
            else Text(mode.action, style = MaterialTheme.typography.titleMedium, color = Bubbles.White)
        }
        if (canResend) {
            LinkText("Send the confirmation email again") {
                scope.launch {
                    try { api.resendConfirmation(email); info = "If that address has an unconfirmed account, we sent the email again. It can take a minute." }
                    catch (e: Exception) { error = e.friendly() }
                }
            }
        }
        when (mode) {
            AuthMode.SignIn -> LinkText("Forgot or never set a password?") { switchTo(AuthMode.Reset) }
            AuthMode.Reset -> LinkText("Back to sign in") { switchTo(AuthMode.SignIn) }
            AuthMode.SignUp -> Unit
        }
        if (BuildConfig.DEMO) {
            Text(
                "Use demo data (test build)",
                Modifier.padding(top = 16.dp).clickable(role = Role.Button) { api.useDemo() }.padding(8.dp),
                style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary,
            )
        }
        Spacer(Modifier.height(24.dp))
    }
}

/** A quiet text link: 48dp tall so it is easy to hit, announced as a button. */
@Composable
private fun LinkText(text: String, onClick: () -> Unit) {
    Text(
        text, Modifier.heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onClick).padding(vertical = 14.dp),
        style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary,
    )
}
