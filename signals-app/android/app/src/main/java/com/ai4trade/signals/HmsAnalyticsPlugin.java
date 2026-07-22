package com.ai4trade.signals;

import android.os.Bundle;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import com.huawei.hms.analytics.HiAnalytics;
import com.huawei.hms.analytics.HiAnalyticsInstance;

import java.util.Iterator;

/**
 * HMS Analytics Kit bridge (optional). Implements the contract used by
 * src/lib/hms/analytics.ts: logEvent(name, params?) and setEnabled(enabled).
 */
@CapacitorPlugin(name = "HmsAnalytics")
public class HmsAnalyticsPlugin extends Plugin {

    private HiAnalyticsInstance instance;

    @Override
    public void load() {
        instance = HiAnalytics.getInstance(getContext());
    }

    @PluginMethod
    public void logEvent(final PluginCall call) {
        String name = call.getString("name");
        if (name == null) {
            call.reject("name is required");
            return;
        }
        Bundle bundle = new Bundle();
        JSObject params = call.getObject("params");
        if (params != null) {
            Iterator<String> keys = params.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                Object value = params.opt(key);
                if (value != null) {
                    bundle.putString(key, String.valueOf(value));
                }
            }
        }
        if (instance != null) {
            instance.onEvent(name, bundle);
        }
        call.resolve();
    }

    @PluginMethod
    public void setEnabled(final PluginCall call) {
        boolean enabled = Boolean.TRUE.equals(call.getBoolean("enabled", true));
        if (instance != null) {
            instance.setAnalyticsEnabled(enabled);
        }
        call.resolve();
    }
}
