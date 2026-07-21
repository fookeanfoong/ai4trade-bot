package com.ai4trade.signals;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.text.TextUtils;

import androidx.core.app.NotificationCompat;

import com.huawei.hms.push.HmsMessageService;
import com.huawei.hms.push.RemoteMessage;

/**
 * HMS Push Kit messaging service.
 *
 * Receives Push Kit tokens and messages on Huawei devices and displays a
 * notification.
 *
 * COMPLIANCE (non-negotiable): every notification body MUST be prefixed with
 * "[Educational]". The canonical server format is:
 *   "[Educational] {ticker} setup for {date} — tap to view analysis"
 * This service enforces the prefix defensively even if a payload arrives
 * without it, so a mis-configured backend can never surface a non-compliant
 * notification body.
 */
public class HmsMessagingService extends HmsMessageService {

    private static final String CHANNEL_ID = "ai4trade_signals";
    private static final String EDUCATIONAL_PREFIX = "[Educational]";

    @Override
    public void onNewToken(String token) {
        super.onNewToken(token);
        // The token is registered with the backend so it can target this device.
        // Forward it to the backend via your registration endpoint. The token is
        // also surfaced to JS through the Capacitor PushNotifications
        // 'registration' event when the app is in the foreground.
        if (!TextUtils.isEmpty(token)) {
            TokenStore.saveToken(getApplicationContext(), token);
        }
    }

    @Override
    public void onMessageReceived(RemoteMessage message) {
        super.onMessageReceived(message);

        String title = getString(R.string.app_name);
        String body = null;

        RemoteMessage.Notification notification = message.getNotification();
        if (notification != null) {
            if (!TextUtils.isEmpty(notification.getTitle())) {
                title = notification.getTitle();
            }
            body = notification.getBody();
        }
        // Fall back to the data payload's "body" field for data messages.
        if (TextUtils.isEmpty(body) && message.getDataOfMap() != null) {
            body = message.getDataOfMap().get("body");
        }
        if (TextUtils.isEmpty(body)) {
            return;
        }

        showNotification(title, ensureEducationalPrefix(body));
    }

    /** Force the compliance prefix onto any notification body. */
    static String ensureEducationalPrefix(String body) {
        if (body == null) {
            return EDUCATIONAL_PREFIX;
        }
        return body.startsWith(EDUCATIONAL_PREFIX) ? body : EDUCATIONAL_PREFIX + " " + body;
    }

    private void showNotification(String title, String body) {
        NotificationManager manager =
            (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "AI4Trade Signals", NotificationManager.IMPORTANCE_DEFAULT);
            manager.createNotificationChannel(channel);
        }

        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
            ? PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            : PendingIntent.FLAG_UPDATE_CURRENT;
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, intent, flags);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent);

        manager.notify((int) System.currentTimeMillis(), builder.build());
    }
}
