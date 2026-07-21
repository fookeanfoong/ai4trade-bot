/**
 * Learn / Guides.
 *
 * REQUIREMENTS:
 *  - Guides: K-Line charts, Support & Resistance, Position Sizing, Volume &
 *    Momentum, Common Chart Patterns.
 *  - Interactive candlestick illustrations (lightweight-charts via CandleChart).
 *  - Progress tracking per guide, stored locally (Preferences).
 *  - All guides cached offline.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CandleChart from '@/components/CandleChart';
import { Button, Card, Screen, Spinner } from '@/components/ui';
import * as api from '@/lib/api';
import * as offline from '@/lib/offline';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';
import { SAMPLE_GUIDES } from '@/lib/fixtures';
import type { Guide } from '@/lib/types';

type ProgressMap = Record<string, number>; // guideId -> 0..100

export default function Learn() {
  const { t } = useTranslation();
  const [guides, setGuides] = useState<Guide[] | null>(null);
  const [progress, setProgress] = useState<ProgressMap>({});
  const [active, setActive] = useState<Guide | null>(null);

  useEffect(() => {
    (async () => {
      setProgress(await storage.getJSON<ProgressMap>(KEYS.guideProgress, {}));
      try {
        const data = await api.getGuides();
        setGuides(data);
        await offline.cacheGuides(data);
      } catch {
        const cached = await offline.readGuides();
        setGuides(cached ?? SAMPLE_GUIDES);
      }
    })();
  }, []);

  async function setGuideProgress(guideId: string, pct: number) {
    const next = { ...progress, [guideId]: pct };
    setProgress(next);
    await storage.setJSON(KEYS.guideProgress, next);
  }

  if (active) {
    return (
      <GuideDetail
        guide={active}
        progress={progress[active.id] ?? 0}
        onBack={() => setActive(null)}
        onProgress={(pct) => void setGuideProgress(active.id, pct)}
      />
    );
  }

  return (
    <Screen title={t('guides.title')}>
      <div className="space-y-3 px-4 py-4">
        {guides === null && <Spinner label={t('common.loading')} />}
        {guides?.map((g) => {
          const pct = progress[g.id] ?? 0;
          return (
            <button key={g.id} onClick={() => setActive(g)} className="block w-full text-left">
              <Card>
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-text">{g.title}</h2>
                  <span className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted">
                    {t(`guides.level_${g.level}`)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted">{g.summary}</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border">
                  <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
                </div>
                <p className="mt-1 text-[11px] text-muted">
                  {pct >= 100 ? t('guides.completed') : t('guides.progress', { pct })}
                </p>
              </Card>
            </button>
          );
        })}
      </div>
    </Screen>
  );
}

function GuideDetail({
  guide,
  progress,
  onBack,
  onProgress,
}: {
  guide: Guide;
  progress: number;
  onBack: () => void;
  onProgress: (pct: number) => void;
}) {
  const { t } = useTranslation();

  // Mark progress as the user scrolls through; simple heuristic: reaching the
  // bottom marks complete.
  function onScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    const reached = (el.scrollTop + el.clientHeight) / el.scrollHeight;
    const pct = Math.min(100, Math.round(reached * 100));
    if (pct > progress) onProgress(pct);
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="pt-safe sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur">
        <button onClick={onBack} className="text-muted" aria-label={t('common.back')}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <h1 className="text-base font-bold">{guide.title}</h1>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4" onScroll={onScroll}>
        {guide.sections.map((section, i) => (
          <section key={i} className="mb-6">
            <h2 className="text-sm font-semibold text-text">{section.heading}</h2>
            <p className="mt-1 text-sm leading-relaxed text-muted">{section.body}</p>
            {section.chart && <CandleChart series={section.chart} />}
          </section>
        ))}
        <Button onClick={() => onProgress(100)} disabled={progress >= 100}>
          {progress >= 100 ? t('guides.completed') : t('guides.markComplete')}
        </Button>
      </div>
    </div>
  );
}
