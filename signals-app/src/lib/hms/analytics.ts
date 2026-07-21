/**
 * HMS Analytics Kit bridge (optional).
 *
 * Wraps a thin native bridge ('HmsAnalytics') if present; no-ops on web and
 * when the plugin is absent, so analytics is fully optional and never blocks.
 */
import { Capacitor, registerPlugin } from '@capacitor/core';

interface HmsAnalyticsPlugin {
  logEvent(options: { name: string; params?: Record<string, unknown> }): Promise<void>;
  setEnabled(options: { enabled: boolean }): Promise<void>;
}

const HmsAnalytics = registerPlugin<HmsAnalyticsPlugin>('HmsAnalytics');

function available(): boolean {
  return Capacitor.getPlatform() !== 'web' && Capacitor.isPluginAvailable('HmsAnalytics');
}

export async function logEvent(name: string, params?: Record<string, unknown>): Promise<void> {
  if (!available()) return;
  try {
    await HmsAnalytics.logEvent({ name, params });
  } catch {
    /* analytics is best-effort */
  }
}

export async function setAnalyticsEnabled(enabled: boolean): Promise<void> {
  if (!available()) return;
  try {
    await HmsAnalytics.setEnabled({ enabled });
  } catch {
    /* ignore */
  }
}
