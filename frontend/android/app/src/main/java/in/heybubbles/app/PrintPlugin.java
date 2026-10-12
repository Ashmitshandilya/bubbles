package in.heybubbles.app;

import android.content.Context;
import android.print.PrintManager;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * window.print() does nothing in an Android WebView. NativeBridge routes it here, which opens the system print
 * dialog for the current page (it also offers "Save as PDF"), so care summaries and reports work in the app.
 */
@CapacitorPlugin(name = "BubblesPrint")
public class PrintPlugin extends Plugin {

    @PluginMethod
    public void print(PluginCall call) {
        String title = call.getString("title", "Bubbles");
        getActivity().runOnUiThread(() -> {
            PrintManager printManager = (PrintManager) getActivity().getSystemService(Context.PRINT_SERVICE);
            if (printManager == null) {
                call.reject("Printing is not available on this device.");
                return;
            }
            printManager.print(title, getBridge().getWebView().createPrintDocumentAdapter(title), null);
            call.resolve();
        });
    }
}
