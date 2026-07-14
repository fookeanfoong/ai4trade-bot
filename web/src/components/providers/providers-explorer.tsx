'use client';

import { useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';
import { LayoutGrid, Table as TableIcon } from 'lucide-react';
import type { Provider, Region, PaymentMethod } from '@/lib/types';
import { ProviderCard } from '@/components/providers/provider-card';
import { ProviderTable } from '@/components/providers/provider-table';
import { ALL_REGIONS, ALL_PAYMENTS, regionLabel, paymentShort } from '@/lib/display';
import { cheapestGpt4o } from '@/lib/selectors';
import { cn } from '@/lib/utils';

type Sort = 'trust' | 'price' | 'latency' | 'uptime';

export function ProvidersExplorer({ providers }: { providers: Provider[] }) {
  const t = useTranslations('providers');
  const [sort, setSort] = useState<Sort>('trust');
  const [region, setRegion] = useState<Region | 'all'>('all');
  const [payment, setPayment] = useState<PaymentMethod | 'all'>('all');
  const [view, setView] = useState<'card' | 'table'>('card');

  const filtered = useMemo(() => {
    let list = providers.filter((p) => {
      if (region !== 'all' && !p.regions.includes(region)) return false;
      if (payment !== 'all' && !p.payment_methods.includes(payment)) return false;
      return true;
    });
    list = [...list].sort((a, b) => {
      switch (sort) {
        case 'price': {
          const pa = cheapestGpt4o(a.id)?.output_price_per_1m ?? Infinity;
          const pb = cheapestGpt4o(b.id)?.output_price_per_1m ?? Infinity;
          return pa - pb;
        }
        case 'latency':
          return a.avg_latency_ms - b.avg_latency_ms;
        case 'uptime':
          return b.uptime_30d - a.uptime_30d;
        default:
          // 置顶 Sponsored,再按信任分
          return Number(b.sponsored) - Number(a.sponsored) || b.trust_score - a.trust_score;
      }
    });
    return list;
  }, [providers, sort, region, payment]);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Select label={t('sortBy')} value={sort} onChange={(v) => setSort(v as Sort)}
          options={[
            { value: 'trust', label: t('sortTrust') },
            { value: 'price', label: t('sortPrice') },
            { value: 'latency', label: t('sortLatency') },
            { value: 'uptime', label: t('sortUptime') },
          ]}
        />
        <Select label={t('filterRegion')} value={region} onChange={(v) => setRegion(v as Region | 'all')}
          options={[{ value: 'all', label: t('filterAll') }, ...ALL_REGIONS.map((r) => ({ value: r, label: regionLabel[r] }))]}
        />
        <Select label={t('filterPayment')} value={payment} onChange={(v) => setPayment(v as PaymentMethod | 'all')}
          options={[{ value: 'all', label: t('filterAll') }, ...ALL_PAYMENTS.map((m) => ({ value: m, label: paymentShort[m] }))]}
        />
        <div className="ml-auto inline-flex rounded-md border border-border p-0.5">
          <button
            onClick={() => setView('card')}
            className={cn('flex h-8 items-center gap-1 rounded px-2 text-sm', view === 'card' && 'bg-muted')}
            aria-label={t('viewCard')}
          >
            <LayoutGrid className="h-4 w-4" /> {t('viewCard')}
          </button>
          <button
            onClick={() => setView('table')}
            className={cn('flex h-8 items-center gap-1 rounded px-2 text-sm', view === 'table' && 'bg-muted')}
            aria-label={t('viewTable')}
          >
            <TableIcon className="h-4 w-4" /> {t('viewTable')}
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="py-16 text-center text-muted-foreground">{t('empty')}</p>
      ) : view === 'card' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <ProviderCard key={p.id} provider={p} sourcePage="/providers" />
          ))}
        </div>
      ) : (
        <ProviderTable providers={filtered} sourcePage="/providers" />
      )}
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
