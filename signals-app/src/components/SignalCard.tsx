/**
 * A single educational signal card: symbol, company, entry range, stop, target,
 * position size from capital, confidence indicator, brief analysis.
 *
 * Green/red are used ONLY for the bias indicator and price direction, never for
 * chrome. Monospace for tickers/prices per the design spec.
 */
import { useTranslation } from 'react-i18next';
import type { Signal } from '@/lib/types';
import { computePositionSize } from '@/lib/position';
import { Card } from './ui';

function money(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ConfidenceDots({ level }: { level: Signal['confidence'] }) {
  const filled = level === 'high' ? 3 : level === 'medium' ? 2 : 1;
  return (
    <span className="inline-flex gap-1" aria-hidden>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${i < filled ? 'bg-text' : 'bg-border'}`}
        />
      ))}
    </span>
  );
}

export default function SignalCard({ signal, capitalUsd }: { signal: Signal; capitalUsd: number }) {
  const { t } = useTranslation();
  const size = computePositionSize(signal, capitalUsd);
  const biasColor = signal.bias === 'bullish' ? 'text-bull' : signal.bias === 'bearish' ? 'text-bear' : 'text-muted';

  return (
    <Card>
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="font-mono text-lg font-bold tracking-tight">{signal.symbol}</div>
          <div className="text-xs text-muted">{signal.companyName}</div>
        </div>
        <div className="text-right">
          <div className={`text-xs font-semibold ${biasColor}`}>
            {t(`signals.bias_${signal.bias}`)}
          </div>
          <div className="mt-1 flex items-center justify-end gap-1 text-[11px] text-muted">
            {t('signals.confidence')} <ConfidenceDots level={signal.confidence} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <Metric label={t('signals.entry')}>
          <span className="font-mono text-sm">
            {money(signal.entryLow)}–{money(signal.entryHigh)}
          </span>
        </Metric>
        <Metric label={t('signals.stop')}>
          <span className="font-mono text-sm text-bear">{money(signal.stopLoss)}</span>
        </Metric>
        <Metric label={t('signals.target')}>
          <span className="font-mono text-sm text-bull">{money(signal.target)}</span>
        </Metric>
      </div>

      <div className="mt-3 flex items-center justify-between rounded-card bg-surface px-3 py-2">
        <span className="text-xs text-muted">{t('signals.size')}</span>
        <span className="font-mono text-sm">
          {t('signals.shares', { count: size.shares })} · ${money(size.dollarAmount)}
        </span>
      </div>

      <div className="mt-3">
        <div className="mb-1 text-[11px] uppercase tracking-wide text-muted">
          {t('signals.rationale')}
        </div>
        <p className="text-sm leading-relaxed text-text">{signal.rationale}</p>
      </div>
    </Card>
  );
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-card border border-border py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}
