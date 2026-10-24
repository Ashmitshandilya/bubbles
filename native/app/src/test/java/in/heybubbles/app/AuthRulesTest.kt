package `in`.heybubbles.app

import `in`.heybubbles.app.data.AuthRules
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthRulesTest {
    @Test fun aGoodFormHasNoProblem() {
        assertNull(AuthRules.signUpProblem("Asha", "asha@example.com", "secret1", true))
    }

    @Test fun eachMissingPartIsNamedInOrder() {
        assertEquals("Tell Bubbles what to call you.", AuthRules.signUpProblem(" ", "a@b.co", "secret1", true))
        assertEquals("That email doesn't look right.", AuthRules.signUpProblem("A", "not-an-email", "secret1", true))
        assertEquals("Use at least 6 characters for your password.", AuthRules.signUpProblem("A", "a@b.co", "12345", true))
        assertEquals("Please tick that you have read the Terms and the Privacy notice.", AuthRules.signUpProblem("A", "a@b.co", "secret1", false))
    }

    @Test fun emailCheckIgnoresSpacesAroundTheAddress() {
        assertTrue(AuthRules.looksLikeEmail("  a@b.co "))
        assertFalse(AuthRules.looksLikeEmail("a b@c.co"))
    }

    @Test fun linksOpenOnTheRealSiteAndTheNoticeVersionMatchesTheServer() {
        assertEquals("https://heybubbles.in/callback?next=password", AuthRules.RESET_URL)
        assertEquals("2026-11b", AuthRules.NOTICE_VERSION)   // backend/consent.py POLICY_VERSION
    }
}
