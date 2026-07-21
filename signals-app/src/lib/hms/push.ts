/**
 * HMS Push Kit bridge.
 *
 * On Huawei devices push is delivered by Push Kit, surfaced through the
 * Capacitor PushNotifications plugin (the native HMS bridge maps Push Kit
 * tokens/messages onto the standard plugin API — see android/ notes in README).
 *
 * COMPLIANCE: every notification body the app displays MUST be prefixed with
 * `[Educational]`. Server-sent bodies are prefixed by the backend; the
 * defensive `ensureEducationalPrefix` here guarantees it for any body that
 * reaches the client, including local notifications.
 */
import { Capacitor } from '@capacitor/core';
import { PushNotifications, type PushNotificationSchema } from '@capacitor/push-notifications';
import { PUSH_PREFIX } from '../compliance';

export type PushToken = string;

/** Force the `[Educational]` prefix onto any notification body. */
export function ensureEducationalPrefix(body: string): string {
  return body.startsWith(PUSH_PREFIX) ? body : `${PUSH_PREFIX} ${body}`;
}

/**
 * Request permission and register for push. Returns the device token, or null
 * if unavailable / denied / running on web.
 */
export async function registerForPush(
  onToken?: (token: PushToken) => void,
  onMessage?: (msg: PushNotificationSchema) => void,
): Promise<PushToken | null> {
  if (Capacitor.getPlatform() === 'web') return null;

  const perm = await PushNotifications.requestPermissions();
  if (perm.receive !== 'granted') return null;

  return new Promise<PushToken | null>((resolve) => {
    let settled = false;

    PushNotifications.addListener('registration', (token) => {
      onToken?.(token.value);
      if (!settled) {
        settled = true;
        resolve(token.value);
      }
    });

    PushNotifications.addListener('registrationError', () => {
      if (!settled) {
        settled = true;
        resolve(null);
      }
    });

    PushNotifications.addListener('pushNotificationReceived', (msg) => {
      // Defensive: guarantee the compliance prefix before anything is shown.
      if (msg.body) msg.body = ensureEducationalPrefix(msg.body);
      onMessage?.(msg);
    });

    PushNotifications.register();
  });
}

export async function removePushListeners(): Promise<void> {
  await PushNotifications.removeAllListeners();
}
