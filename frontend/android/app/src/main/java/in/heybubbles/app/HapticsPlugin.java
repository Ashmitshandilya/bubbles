package in.heybubbles.app;

import android.view.HapticFeedbackConstants;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * A light tick on navigation and main-button taps (NativeBridge calls it). It is the system's own key feedback on the
 * web view, so it needs no VIBRATE permission and stays silent when the person turned touch feedback off.
 */
@CapacitorPlugin(name = "BubblesHaptics")
public class HapticsPlugin extends Plugin {

    @PluginMethod
    public void tick(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            getBridge().getWebView().performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
            call.resolve();
        });
    }
}
