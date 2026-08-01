/**
 * Placeholder data. Screens render this until the aicompareapi.com endpoints
 * are wired / reachable, and it doubles as the offline demo dataset.
 *
 * All copy here is compliance-checked: no banned words, educational framing.
 */
import type { Candle, Guide, NewsArticle, Signal } from './types';

export const SAMPLE_SIGNALS: Signal[] = [
  {
    id: 'sig-nvda',
    symbol: 'NVDA',
    companyName: 'NVIDIA Corporation',
    entryLow: 172.4,
    entryHigh: 174.1,
    stopLoss: 168.0,
    target: 184.5,
    bias: 'bullish',
    confidence: 'high',
    rationale:
      'Potential setup: price holding above the rising 20-day average with expanding volume into the open.',
    date: '2026-07-21',
  },
  {
    id: 'sig-aapl',
    symbol: 'AAPL',
    companyName: 'Apple Inc.',
    entryLow: 214.0,
    entryHigh: 215.5,
    stopLoss: 210.2,
    target: 223.0,
    bias: 'bullish',
    confidence: 'medium',
    rationale:
      'Analysis: consolidation near prior resistance; a hold above range highs would mark a potential continuation setup.',
    date: '2026-07-21',
  },
  {
    id: 'sig-tsla',
    symbol: 'TSLA',
    companyName: 'Tesla, Inc.',
    entryLow: 244.0,
    entryHigh: 246.0,
    stopLoss: 251.5,
    target: 232.0,
    bias: 'bearish',
    confidence: 'medium',
    rationale:
      'Analysis: rejection at the declining 50-day average; loss of the intraday range low would illustrate a potential downside setup.',
    date: '2026-07-21',
  },
  {
    id: 'sig-amd',
    symbol: 'AMD',
    companyName: 'Advanced Micro Devices',
    entryLow: 168.5,
    entryHigh: 170.0,
    stopLoss: 164.0,
    target: 179.0,
    bias: 'bullish',
    confidence: 'low',
    rationale:
      'Watchlist: early base-building on lighter volume; monitoring for a potential setup on a volume expansion.',
    date: '2026-07-21',
  },
];

export const SAMPLE_NEWS: NewsArticle[] = [
  {
    id: 'n1',
    headline: 'Chipmakers rally as data-center demand outlook is raised',
    source: 'Reuters',
    url: 'https://www.reuters.com/',
    datetime: 1_753_084_800,
    tickers: ['NVDA', 'AMD'],
    sentiment: 'bullish',
    category: 'earnings',
    summary: 'Sector-wide strength following updated capital-spending commentary.',
  },
  {
    id: 'n2',
    headline: 'Fed minutes signal patience on rate path',
    source: 'Bloomberg',
    url: 'https://www.bloomberg.com/',
    datetime: 1_753_070_400,
    tickers: ['SPY', 'QQQ'],
    sentiment: 'neutral',
    category: 'macro',
    summary: 'Policymakers reiterate a data-dependent stance.',
  },
  {
    id: 'n3',
    headline: 'Supply-route disruption weighs on energy names',
    source: 'AP',
    url: 'https://apnews.com/',
    datetime: 1_753_056_000,
    tickers: ['XOM', 'CVX'],
    sentiment: 'bearish',
    category: 'geopolitical',
    summary: 'Regional tensions add a risk premium to crude.',
  },
];

/** A synthetic candlestick series used by the Learn guides' interactive charts. */
function series(base: number, n = 40): Candle[] {
  const out: Candle[] = [];
  let close = base;
  for (let i = 0; i < n; i++) {
    // Deterministic pseudo-wiggle (no Math.random — reproducible builds).
    const drift = Math.sin(i / 3) * 2 + Math.cos(i / 7) * 1.2;
    const open = close;
    close = Math.max(1, open + drift);
    const high = Math.max(open, close) + Math.abs(Math.sin(i)) * 1.5;
    const low = Math.min(open, close) - Math.abs(Math.cos(i)) * 1.5;
    const day = String((i % 28) + 1).padStart(2, '0');
    const month = String(Math.floor(i / 28) + 1).padStart(2, '0');
    out.push({
      time: `2026-${month}-${day}`,
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
    });
  }
  return out;
}

export const SAMPLE_GUIDES: Guide[] = [
  {
    id: 'kline',
    title: 'Reading K-Line (Candlestick) Charts',
    level: 'beginner',
    summary: 'What each candle body and wick tells you, from the basics to advanced reading.',
    sections: [
      {
        heading: 'Anatomy of a candle',
        body: 'Each candle summarises open, high, low and close for a period. The body spans open-to-close; the wicks mark the extremes. A hollow/green body closes above its open; a filled/red body closes below.',
        chart: { caption: 'Sample daily candles', candles: series(100) },
      },
      {
        heading: 'Reading momentum',
        body: 'Long bodies with small wicks show conviction; long wicks show rejection of a price area. Sequences of candles form the patterns covered later in this guide.',
      },
    ],
  },
  {
    id: 'support-resistance',
    title: 'Support & Resistance Basics',
    level: 'beginner',
    summary: 'How prior turning points become reference levels.',
    sections: [
      {
        heading: 'Levels as reference zones',
        body: 'Support is a zone where declines have paused before; resistance is where advances have paused. Treat them as zones, not exact lines.',
        chart: {
          caption: 'Illustrative support / resistance zones',
          candles: series(80),
          levels: [
            { price: 78, label: 'Support zone' },
            { price: 92, label: 'Resistance zone' },
          ],
        },
      },
    ],
  },
  {
    id: 'position-sizing',
    title: 'Position Sizing & Risk Management',
    level: 'intermediate',
    summary: 'Sizing an illustrative position from a fixed fraction of capital.',
    sections: [
      {
        heading: 'Risk per setup',
        body: 'A common educational model risks a small fixed fraction of capital (e.g. 2%) to the stop distance. Shares = (capital × risk%) ÷ (entry − stop). This app uses that model to illustrate size from your stated capital.',
      },
    ],
  },
  {
    id: 'volume-momentum',
    title: 'Volume & Momentum',
    level: 'intermediate',
    summary: 'Using participation to contextualise price moves.',
    sections: [
      {
        heading: 'Confirmation',
        body: 'Moves on expanding volume carry more information than moves on light volume. Momentum studies (e.g. rate-of-change) summarise the speed of a move.',
        chart: { caption: 'Momentum illustration', candles: series(120) },
      },
    ],
  },
  {
    id: 'chart-patterns',
    title: 'Common Chart Patterns',
    level: 'advanced',
    summary: 'Head & shoulders, flags, triangles, double tops/bottoms.',
    sections: [
      {
        heading: 'Continuation vs reversal',
        body: 'Flags and triangles typically illustrate continuation; head & shoulders and double tops/bottoms illustrate potential reversals. Each is a visual summary of shifting supply and demand — for education, not a signal to act.',
        chart: { caption: 'Pattern illustration', candles: series(90) },
      },
    ],
  },
];
