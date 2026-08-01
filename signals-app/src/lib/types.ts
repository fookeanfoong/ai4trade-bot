/** Shared domain types. */

export type Sentiment = 'bullish' | 'bearish' | 'neutral';
export type Confidence = 'low' | 'medium' | 'high';

/** A single educational signal / potential setup for one ticker. */
export interface Signal {
  id: string;
  symbol: string;
  companyName: string;
  /** Suggested entry range [low, high]. */
  entryLow: number;
  entryHigh: number;
  stopLoss: number;
  target: number;
  /** Direction of the setup — drives colour only, never UI chrome. */
  bias: Sentiment;
  confidence: Confidence;
  rationale: string;
  /** Pre-market date this setup is for (ISO yyyy-mm-dd). */
  date: string;
}

/** Position sizing derived from user capital (computed client-side). */
export interface PositionSize {
  shares: number;
  dollarAmount: number;
  riskAmount: number; // capital at risk to the stop
  riskPct: number;
}

export interface NewsArticle {
  id: string;
  headline: string;
  source: string;
  url: string;
  /** Unix seconds. */
  datetime: number;
  tickers: string[];
  sentiment: Sentiment;
  category: 'earnings' | 'macro' | 'geopolitical' | 'general';
  summary?: string;
}

export interface Guide {
  id: string;
  title: string;
  level: 'beginner' | 'intermediate' | 'advanced';
  summary: string;
  /** Ordered sections of markdown-ish content. */
  sections: GuideSection[];
}

export interface GuideSection {
  heading: string;
  body: string;
  /** Optional interactive candlestick illustration for this section. */
  chart?: CandleSeries;
}

export interface Candle {
  time: string; // yyyy-mm-dd
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface CandleSeries {
  caption: string;
  candles: Candle[];
  /** Optional horizontal reference lines (support/resistance illustrations). */
  levels?: { price: number; label: string }[];
}

export type EntitlementStatus = 'trial' | 'active' | 'expired';

export interface Entitlement {
  status: EntitlementStatus;
  tier: string | null;
  expiresAt: string | null;
  trialDaysUsed: number;
}

export interface AcceptanceRecord {
  userId: string;
  termsVersion: string;
  privacyVersion: string;
  riskDisclosureVersion: string;
  /** ISO timestamp recorded by the backend. */
  timestamp: string;
  ip?: string;
  appVersion?: string;
}

export interface AuthUser {
  userId: string;
  email: string;
  joinDate: string;
}
