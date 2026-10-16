package in.heybubbles.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // App-local plugins must be registered before the bridge starts.
        registerPlugin(PrintPlugin.class);
        registerPlugin(HapticsPlugin.class);
        super.onCreate(savedInstanceState);
        createNotificationChannels();
    }

    /**
     * Channels exist from the first launch (Android 8+), so a push that arrives before the web view ever ran still has
     * somewhere to land. Importance is the system default: a normal sound, never a heads-up interruption. Creating a
     * channel that already exists changes nothing, so this is safe on every start.
     */
    private void createNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager == null) return;
        manager.createNotificationChannel(channel(R.string.channel_reminders_id, R.string.channel_reminders_name,
            R.string.channel_reminders_desc, NotificationManager.IMPORTANCE_DEFAULT));
        manager.createNotificationChannel(channel(R.string.channel_checkins_id, R.string.channel_checkins_name,
            R.string.channel_checkins_desc, NotificationManager.IMPORTANCE_LOW));
    }

    private NotificationChannel channel(int id, int name, int description, int importance) {
        NotificationChannel channel = new NotificationChannel(getString(id), getString(name), importance);
        channel.setDescription(getString(description));
        return channel;
    }
}
