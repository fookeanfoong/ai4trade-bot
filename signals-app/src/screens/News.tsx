/**
 * News Feed.
 *
 * REQUIREMENTS:
 *  - Market-impacting news (backend proxies Finnhub — free tier 60 calls/min).
 *  - Filter chips: All / Earnings / Macro / Geopolitical / My Watchlist.
 *  - Per article: headline, source, timestamp, affected tickers, sentiment tag.
 *  - Tap article -> in-app browser to source.
 *  - Compliance micro-line at top: "News for educational context. Not a
 *    recommendation to trade."
 *  - Offline cache fallback.
 */
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Screen, Spinner } from '@/components/ui';
import { NEWS_DISCLAIMER } from '@/lib/compliance';
import { openInApp } from '@/lib/browser';
import * as api from '@/lib/api';
import * as offline from '@/lib/offline';
import { SAMPLE_NEWS } from '@/lib/fixtures';
import type { NewsArticle, Sentiment } from '@/lib/types';

type Filter = 'all' | 'earnings' | 'macro' | 'geopolitical' | 'watchlist';

const FILTERS: Filter[] = ['all', 'earnings', 'macro', 'geopolitical', 'watchlist'];

function sentimentClass(s: Sentiment): string {
  return s === 'bullish' ? 'text-bull' : s === 'bearish' ? 'text-bear' : 'text-muted';
}

function timeAgo(unixSec: number, now: number): string {
  const mins = Math.max(1, Math.floor((now - unixSec * 1000) / 60000));
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

export default function News() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<Filter>('all');
  const [articles, setArticles] = useState<NewsArticle[] | null>(null);
  const [offlineMode, setOfflineMode] = useState(false);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    (async () => {
      setArticles(null);
      const category = filter === 'watchlist' ? 'all' : filter;
      try {
        const data = await api.getLatestNews(category);
        setArticles(data);
        setOfflineMode(false);
        await offline.cacheNews(filter, data);
      } catch {
        const cached = await offline.readNews(filter);
        if (cached) {
          setArticles(cached);
          setOfflineMode(true);
        } else {
          setArticles(SAMPLE_NEWS);
          setOfflineMode(false);
        }
      }
    })();
  }, [filter]);

  const filtered = useMemo(() => {
    if (!articles) return null;
    if (filter === 'all' || filter === 'watchlist') return articles;
    return articles.filter((a) => a.category === filter);
  }, [articles, filter]);

  return (
    <Screen title={t('news.title')}>
      <p className="px-4 pt-3 text-center text-[11px] text-muted">{NEWS_DISCLAIMER}</p>

      <div className="no-scrollbar flex gap-2 overflow-x-auto px-4 py-3">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`whitespace-nowrap rounded-full border px-3 py-1 text-xs ${
              filter === f
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-muted'
            }`}
          >
            {t(
              `news.filter${f.charAt(0).toUpperCase() + f.slice(1)}` as
                | 'news.filterAll'
                | 'news.filterEarnings'
                | 'news.filterMacro'
                | 'news.filterGeopolitical'
                | 'news.filterWatchlist',
            )}
          </button>
        ))}
      </div>

      {offlineMode && (
        <p className="px-4 text-center text-xs text-muted">{t('common.offline')}</p>
      )}

      <div className="space-y-3 px-4 py-2">
        {filtered === null && <Spinner label={t('common.loading')} />}
        {filtered?.map((a) => (
          <button key={a.id} onClick={() => void openInApp(a.url)} className="block w-full text-left">
            <Card>
              <div className="mb-1 flex items-center justify-between text-[11px] text-muted">
                <span>{a.source}</span>
                <span className="font-mono">{timeAgo(a.datetime, now)}</span>
              </div>
              <p className="text-sm font-medium leading-snug text-text">{a.headline}</p>
              <div className="mt-2 flex items-center justify-between">
                <div className="flex flex-wrap gap-1">
                  {a.tickers.map((tk) => (
                    <span
                      key={tk}
                      className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted"
                    >
                      {tk}
                    </span>
                  ))}
                </div>
                <span className={`text-[11px] font-semibold ${sentimentClass(a.sentiment)}`}>
                  {t(`news.sentiment_${a.sentiment}`)}
                </span>
              </div>
            </Card>
          </button>
        ))}
      </div>
    </Screen>
  );
}
