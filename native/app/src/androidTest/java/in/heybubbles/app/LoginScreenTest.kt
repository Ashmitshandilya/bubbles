package `in`.heybubbles.app

import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Session
import `in`.heybubbles.app.ui.screens.LoginScreen
import `in`.heybubbles.app.ui.theme.BubblesTheme
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/** The first screen a person sees: sign in, create an account, and the plain-language checks before anything is sent. */
class LoginScreenTest {
    @get:Rule val rule = createComposeRule()

    @Before fun show() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val api = Api(Session(context))
        rule.setContent { BubblesTheme(dark = false) { LoginScreen(api) } }
    }

    @Test fun opensOnSignInWithTheTwoTabs() {
        rule.onAllNodesWithText("Sign in").assertCountEquals(2)   // the tab and the button
        rule.onAllNodesWithText("Sign in")[0].assertIsSelected()
        rule.onNodeWithText("Create account").assertIsDisplayed()
        rule.onNodeWithText("Forgot or never set a password?").assertIsDisplayed()
    }

    @Test fun createAccountShowsTheNameBoxAndTheTermsTick() {
        rule.onNodeWithText("Create account").performClick()
        rule.onNodeWithText("Create account").assertIsSelected()
        rule.onNodeWithText("What should Bubbles call you?").assertIsDisplayed()
        rule.onNodeWithText("At least 6 characters.").assertIsDisplayed()
        rule.onNodeWithText("Read the Terms").assertIsDisplayed()
    }

    @Test fun anEmptyFormNamesWhatIsMissingInsteadOfSendingAnything() {
        rule.onNodeWithText("Create account").performClick()
        rule.onNodeWithText("Create my account").performClick()
        rule.onNodeWithText("Tell Bubbles what to call you.").assertIsDisplayed()
    }

    @Test fun tabsAndLinksAreAtLeast48dpTall() {
        rule.onAllNodesWithText("Sign in")[0].assertHeightIsAtLeast(48.dp)
        rule.onNodeWithText("Create account").assertHeightIsAtLeast(48.dp)
        rule.onNodeWithText("Forgot or never set a password?").assertHeightIsAtLeast(48.dp)
    }
}
