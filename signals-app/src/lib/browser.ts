/**
 * In-app browser helper. ALL legal / external links (privacy, terms,
 * risk-disclosure, news sources, AppGallery management) open here via the
 * Capacitor Browser plugin — NEVER via window.open to the system browser.
 *
 * Requirement: legal URLs must open in an in-app browser (@capacitor/browser).
 */
import { Browser } from '@capacitor/browser';
import { LEGAL_URLS, type LegalDocKey } from './compliance';

const IN_APP_TOOLBAR_COLOR = '#0b1220'; // matches app background

/** Open any absolute URL in the in-app browser. */
export async function openInApp(url: string): Promise<void> {
  await Browser.open({ url, toolbarColor: IN_APP_TOOLBAR_COLOR, presentationStyle: 'popover' });
}

/** Open one of the three hosted legal documents in the in-app browser. */
export async function openLegal(doc: LegalDocKey): Promise<void> {
  await openInApp(LEGAL_URLS[doc]);
}

/**
 * Deeplink to AppGallery subscription management. Uses the AppGallery
 * subscriptions URI; falls back to the web management page if the scheme
 * cannot be resolved (e.g. on a non-Huawei device during testing).
 */
export async function openAppGallerySubscriptions(): Promise<void> {
  // Huawei AppGallery subscription-management deeplink.
  const uri = 'appmarket://com.huawei.appmarket?activityName=activityUri|subscribe.manager';
  try {
    await openInApp(uri);
  } catch {
    await openInApp('https://appgallery.huawei.com/');
  }
}

/** Open the support mail client. */
export function openSupportMail(email: string): void {
  const subject = encodeURIComponent('AI4Trade Signals — Support');
  window.location.href = `mailto:${email}?subject=${subject}`;
}
