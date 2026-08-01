/**
 * Thin typed wrapper over @capacitor/preferences for local user prefs and
 * guide progress. Works on web (localStorage-backed) and native identically.
 */
import { Preferences } from '@capacitor/preferences';

/** Keys used across the app. Centralised to avoid typos / collisions. */
export const KEYS = {
  onboardingComplete: 'onboarding_complete',
  authToken: 'auth_token',
  userEmail: 'user_email',
  capitalUsd: 'capital_usd',
  language: 'language',
  firstSignalSeen: 'first_signal_seen',
  guideProgress: 'guide_progress', // JSON map { guideId: 0..100 }
  notifPrefs: 'notif_prefs', // JSON { signals, news, product }
  acceptanceRecord: 'acceptance_record', // last known acceptance (cached)
} as const;

export async function get(key: string): Promise<string | null> {
  const { value } = await Preferences.get({ key });
  return value;
}

export async function set(key: string, value: string): Promise<void> {
  await Preferences.set({ key, value });
}

export async function remove(key: string): Promise<void> {
  await Preferences.remove({ key });
}

export async function getJSON<T>(key: string, fallback: T): Promise<T> {
  const raw = await get(key);
  if (raw == null) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function setJSON(key: string, value: unknown): Promise<void> {
  await set(key, JSON.stringify(value));
}

export async function getBool(key: string): Promise<boolean> {
  return (await get(key)) === 'true';
}

export async function setBool(key: string, value: boolean): Promise<void> {
  await set(key, value ? 'true' : 'false');
}

/** Clear all app-owned keys (used on sign-out / delete account). */
export async function clearAll(): Promise<void> {
  await Preferences.clear();
}
