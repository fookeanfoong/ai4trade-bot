package com.ai4trade.signals;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Small persistence helper for the HMS Push Kit token so it survives until the
 * app foregrounds and can forward it to the backend registration endpoint.
 */
final class TokenStore {

    private static final String PREFS = "ai4trade_push";
    private static final String KEY_TOKEN = "hms_push_token";

    private TokenStore() {}

    static void saveToken(Context context, String token) {
        prefs(context).edit().putString(KEY_TOKEN, token).apply();
    }

    static String getToken(Context context) {
        return prefs(context).getString(KEY_TOKEN, null);
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
