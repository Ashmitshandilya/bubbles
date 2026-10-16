package in.heybubbles.app;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.firebase.FirebaseApp;
import com.google.firebase.crashlytics.FirebaseCrashlytics;

/**
 * Firebase on this phone (docs/FIREBASE.md): whether this build has a Firebase project (google-services.json was present when
 * it was built), and the crash-report switch in Settings, This device.
 *
 * Crash reports are off until the person turns them on (firebase_crashlytics_collection_enabled=false in AndroidManifest.xml);
 * Crashlytics keeps the choice across launches. Reports written while they were off are deleted, never sent later. No user id,
 * no custom keys and no web (JavaScript) errors are ever passed to Crashlytics, so a report can't carry what someone typed.
 */
@CapacitorPlugin(name = "BubblesFirebase")
public class BubblesFirebasePlugin extends Plugin {

    private boolean configured() {
        return !FirebaseApp.getApps(getContext()).isEmpty();
    }

    @Override
    public void load() {
        if (configured() && !FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled()) {
            FirebaseCrashlytics.getInstance().deleteUnsentReports();
        }
    }

    @PluginMethod
    public void status(PluginCall call) {
        boolean ready = configured();
        JSObject result = new JSObject();
        result.put("configured", ready);
        result.put("crashReports", ready && FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled());
        call.resolve(result);
    }

    @PluginMethod
    public void setCrashReports(PluginCall call) {
        if (!configured()) {
            call.reject("Firebase is not set up in this build.");
            return;
        }
        boolean enabled = Boolean.TRUE.equals(call.getBoolean("enabled", false));
        FirebaseCrashlytics crashlytics = FirebaseCrashlytics.getInstance();
        // Anything stored before this choice was made was never agreed to: drop it either way.
        crashlytics.deleteUnsentReports();
        crashlytics.setCrashlyticsCollectionEnabled(enabled);
        JSObject result = new JSObject();
        result.put("crashReports", enabled);
        call.resolve(result);
    }
}
