package com.ai4trade.signals;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Register the custom HMS bridge plugins BEFORE super.onCreate so the
        // WebView can call them. These are thin wrappers over the HMS SDKs that
        // the TypeScript layer talks to (src/lib/hms/*).
        registerPlugin(HmsIapPlugin.class);
        registerPlugin(HmsAnalyticsPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
