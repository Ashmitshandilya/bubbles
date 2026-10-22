package `in`.heybubbles.app

import `in`.heybubbles.app.data.ApiError
import `in`.heybubbles.app.data.Pending
import `in`.heybubbles.app.data.QueueRules
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

class OfflineQueueTest {
    @Test fun queueSurvivesAnEncodeDecodeRoundTripInOrder() {
        val items = listOf(Pending("a", "sleep", """{"hours":7}""", 1L), Pending("b", "mood", """{"mood":6}""", 2L))
        assertEquals(items, QueueRules.decode(QueueRules.encode(items)))
    }

    @Test fun aDamagedStoreIsAnEmptyQueueNotACrash() {
        assertTrue(QueueRules.decode(null).isEmpty())
        assertTrue(QueueRules.decode("").isEmpty())
        assertTrue(QueueRules.decode("{not json").isEmpty())
    }

    @Test fun onlyRequestsThatNeverReachedTheServerAreQueued() {
        assertTrue(QueueRules.neverReachedServer(UnknownHostException("api")))
        assertTrue(QueueRules.neverReachedServer(ConnectException("refused")))
        assertTrue(QueueRules.neverReachedServer(SocketTimeoutException("failed to connect to /1.2.3.4 (port 443) after 20000ms")))
        // The server may have saved these: queueing them could log the entry twice.
        assertFalse(QueueRules.neverReachedServer(SocketTimeoutException("timeout")))
        assertFalse(QueueRules.neverReachedServer(IOException("unexpected end of stream")))
        assertFalse(QueueRules.neverReachedServer(ApiError(500, "x")))
    }

    @Test fun permanentRefusalsAreDroppedButSignInAndRateLimitsAreRetried() {
        assertTrue(QueueRules.isPermanentRefusal(ApiError(422, "bad")))
        assertTrue(QueueRules.isPermanentRefusal(ApiError(403, "no")))
        assertFalse(QueueRules.isPermanentRefusal(ApiError(401, "sign in")))
        assertFalse(QueueRules.isPermanentRefusal(ApiError(429, "slow")))
        assertFalse(QueueRules.isPermanentRefusal(ApiError(503, "down")))
        assertFalse(QueueRules.isPermanentRefusal(IOException("x")))
    }
}
