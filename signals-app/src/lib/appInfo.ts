/**
 * App version/build helpers. Uses the Capacitor App plugin on native; falls
 * back to the Vite-injected package version on web.
 */
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';

const FALLBACK_VERSION = '1.0.0';

export async function getAppVersion(): Promise<string> {
  if (Capacitor.getPlatform() === 'web') return FALLBACK_VERSION;
  try {
    const info = await App.getInfo();
    return info.version;
  } catch {
    return FALLBACK_VERSION;
  }
}

export async function getAppBuild(): Promise<string> {
  if (Capacitor.getPlatform() === 'web') return 'dev';
  try {
    const info = await App.getInfo();
    return info.build;
  } catch {
    return 'dev';
  }
}

/** Compute age in whole years from an ISO date-of-birth (yyyy-mm-dd). */
export function ageFromDob(dob: string, today: Date): number {
  const birth = new Date(dob + 'T00:00:00');
  if (Number.isNaN(birth.getTime())) return NaN;
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}
