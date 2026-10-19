package `in`.heybubbles.app

import android.app.Application
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Repo
import `in`.heybubbles.app.data.Session

class BubblesApp : Application() {
    lateinit var session: Session
        private set
    lateinit var api: Api
        private set
    lateinit var repo: Repo
        private set

    override fun onCreate() {
        super.onCreate()
        session = Session(this)
        api = Api(session)
        repo = Repo(api, `in`.heybubbles.app.data.OfflineQueue(this))
        `in`.heybubbles.app.push.Push.ensureChannel(this)
    }
}
