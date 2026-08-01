/**
 * ============================================================================
 * COMPLIANCE — single source of truth for AppGallery-required legal strings.
 * ============================================================================
 *
 * Huawei AppGallery Global rejects finance/education apps that read as
 * investment advice. Every user-facing compliance string lives here (or in the
 * i18n locale files, keyed the same way) so future updates touch ONE place.
 *
 * Hard rules enforced across the app:
 *   - Every signal screen shows the educational disclaimer.
 *   - Banned words: buy, sell now, guaranteed, profit, winner, sure win,
 *     recommendation. (See BANNED_WORDS + assertNoBannedWords test helper.)
 *   - Allowed vocabulary: signal, watchlist, analysis, simulation,
 *     potential setup, educational illustration.
 *
 * NOTE: The disclaimer strings are duplicated into the i18n locale files under
 * the `compliance.*` keys for translation. These constants are the canonical
 * English fallbacks and the source for the banned-word lint.
 */

/** The three legal documents hosted on aicompareapi.com. */
export const LEGAL_URLS = {
  terms: 'https://aicompareapi.com/terms',
  privacy: 'https://aicompareapi.com/privacy',
  riskDisclosure: 'https://aicompareapi.com/risk-disclosure',
} as const;

export type LegalDocKey = keyof typeof LEGAL_URLS;

/**
 * Versions of each legal document. Sourced from env so ops can bump a version
 * when a doc changes; the app compares these against the stored acceptance
 * record and re-prompts the user to re-accept when they differ.
 */
export const LEGAL_VERSIONS = {
  terms: import.meta.env.VITE_TERMS_VERSION ?? '2026-01-01',
  privacy: import.meta.env.VITE_PRIVACY_VERSION ?? '2026-01-01',
  riskDisclosure: import.meta.env.VITE_RISK_DISCLOSURE_VERSION ?? '2026-01-01',
} as const;

/** Persistent educational disclaimer shown on every Signals view. */
export const DISCLAIMER_FULL =
  'Educational content only. Not investment advice. Trading carries risk of loss.';

/** Short form used in the fixed footer banner above the tab bar. */
export const DISCLAIMER_SHORT = 'Educational content only. Not investment advice.';

/** News feed compliance micro-line. */
export const NEWS_DISCLAIMER = 'News for educational context. Not a recommendation to trade.';

/** First-time signal-view modal body (shown once per install). */
export const FIRST_SIGNAL_NOTICE =
  'Signals are educational illustrations produced by an automated algorithm. ' +
  'They are not personalised advice. You alone are responsible for any trading decisions.';

/** Paywall micro-copy shown below the purchase buttons. */
export const PAYWALL_SUBSCRIPTION_TERMS =
  'Subscriptions auto-renew until cancelled in AppGallery. See the Terms of Service ' +
  'for full subscription terms and refund policy.';

/** Minimum age required to use the app. */
export const MIN_AGE = 18;

/**
 * Push-notification body prefix. Every notification body MUST start with this.
 * Canonical format: `[Educational] {ticker} setup for {date} — tap to view analysis`.
 */
export const PUSH_PREFIX = '[Educational]';

/**
 * Build a compliant push-notification body. Always prefixed with `[Educational]`.
 * Used by the local-notification path; the backend must apply the same prefix
 * for server-sent HMS pushes (documented in README).
 */
export function buildPushBody(ticker: string, date: string): string {
  return `${PUSH_PREFIX} ${ticker} setup for ${date} — tap to view analysis`;
}

/**
 * Words that must never appear in user-facing copy (AppGallery rejection risk).
 * Enforced by assertNoBannedWords() which the compliance unit test runs over
 * every locale file and these constants.
 */
export const BANNED_WORDS: readonly string[] = [
  'buy',
  'sell now',
  'guaranteed',
  'profit',
  'winner',
  'sure win',
  'recommendation',
];

/** Approved vocabulary — for reference and reviewer documentation. */
export const APPROVED_VOCABULARY: readonly string[] = [
  'signal',
  'watchlist',
  'analysis',
  'simulation',
  'potential setup',
  'educational illustration',
];

/**
 * Returns the list of banned words found in a piece of copy (case-insensitive,
 * word-boundary aware). Empty array means the copy is clean.
 * Exposed for the compliance unit test and dev-time assertions.
 */
export function findBannedWords(text: string): string[] {
  const found: string[] = [];
  const lower = text.toLowerCase();
  for (const word of BANNED_WORDS) {
    // Word-boundary match so "profitability" or "buyer" in a URL don't trip it,
    // but the standalone marketing terms do.
    const re = new RegExp(`\\b${word.replace(/\s+/g, '\\s+')}\\b`, 'i');
    if (re.test(lower)) found.push(word);
  }
  return found;
}
