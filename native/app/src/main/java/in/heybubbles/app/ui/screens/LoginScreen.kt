package `in`.heybubbles.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import `in`.heybubbles.app.BuildConfig
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.friendly
import `in`.heybubbles.app.ui.components.BubbleGradient
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.theme.Bubbles

@Composable
fun LoginScreen(api: Api) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current

    fun submit() {
        if (busy || email.isBlank() || password.isBlank()) return
        busy = true; error = null
        scope.launch {
            try { api.signIn(email, password) } catch (e: Exception) { error = e.friendly() }
            busy = false
        }
    }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 28.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(24.dp))
        // The brand mark: one big bubble with a highlight, the same shape the chat is made of.
        Box(Modifier.size(88.dp).background(BubbleGradient, CircleShape), contentAlignment = Alignment.TopStart) {
            Box(Modifier.padding(start = 20.dp, top = 16.dp).size(22.dp).background(Bubbles.White.copy(alpha = 0.55f), CircleShape))
        }
        Spacer(Modifier.height(20.dp))
        Eyebrow("Welcome")
        Text("Hey, I'm Bubbles", style = MaterialTheme.typography.headlineLarge, textAlign = TextAlign.Center)
        Text(
            "Tell me how you are in your own words. I'll remember, connect the dots and help you prepare for care.",
            Modifier.padding(top = 8.dp, bottom = 28.dp), style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
        )
        OutlinedTextField(
            email, { email = it }, Modifier.fillMaxWidth(), label = { Text("Email") }, singleLine = true,
            shape = MaterialTheme.shapes.medium,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
            keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Down) }),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            password, { password = it }, Modifier.fillMaxWidth(), label = { Text("Password") }, singleLine = true,
            shape = MaterialTheme.shapes.medium, visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Go),
            keyboardActions = KeyboardActions(onGo = { focus.clearFocus(); submit() }),
        )
        error?.let {
            Text(it, Modifier.padding(top = 12.dp).semantics { contentDescription = "Error: $it" }, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(20.dp))
        Box(
            Modifier.fillMaxWidth().height(56.dp).background(BubbleGradient, RoundedCornerShape(28.dp))
                .clickable(enabled = !busy, role = Role.Button, onClickLabel = "Sign in") { submit() },
            contentAlignment = Alignment.Center,
        ) {
            if (busy) CircularProgressIndicator(Modifier.size(24.dp), color = Bubbles.White, strokeWidth = 2.5.dp)
            else Text("Sign in", style = MaterialTheme.typography.titleMedium, color = Bubbles.White)
        }
        Text(
            "New here? Create your account on heybubbles.in, then sign in.",
            Modifier.padding(top = 20.dp), style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
        )
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
