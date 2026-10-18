package `in`.heybubbles.app

import android.app.Application
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.Session

class BubblesApp : Application() {
    lateinit var session: Session
        private set
    lateinit var api: Api
        private set

    override fun onCreate() {
        super.onCreate()
        session = Session(this)
        api = Api(session)
    }
}
