'use client';

import { useMemo, useState, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { X, Share2, Check } from 'lucide-react';
import { useRouter, Link } from '@/i18n/routing';
import type { Provider } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { OutboundLink } from '@/components/outbound-link';
import { paymentShort, regionLabel } from '@/lib/display';
import { formatPrice, cn } from '@/lib/utils';

type PriceMap = Record<string, Record<string, { price: number; discount: number }>>;

export function CompareBuilder({
  providers,
  priceMap,
  modelNames,
}: {
  providers: Provider[];
  priceMap: PriceMap;
  modelNames: string[];
}) {
  const t = useTranslations('compare');
  const detail = useTranslations('detail');
  const router = useRouter();
  const params = useSearchParams();
  const [copied, setCopied] = useState(false);

  const selectedSlugs = useMemo(() => {
    const raw = params.get('ids') || '';
    return raw.split(',').map((s) => s.trim()).filter(Boolean).slice(0, 4);
  }, [params]);

  const selected = selectedSlugs
    .map((s) => providers.find((p) => p.slug === s))
    .filter((p): p is Provider => !!p);

  const setSelection = useCallback(
    (slugs: string[]) => {
      const ids = slugs.slice(0, 4).join(',');
      router.replace(ids ? { pathname: '/compare', query: { ids } } : { pathname: '/compare' });
    },
    [router]
  );

  const toggle = (slug: string) => {
    if (selectedSlugs.includes(slug)) setSelection(selectedSlugs.filter((s) => s !== slug));
    else if (selectedSlugs.length < 4) setSelection([...selectedSlugs, slug]);
  };

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  // 只显示至少有一家选中提供报价的模型行
  const activeModels = modelNames.filter((m) => selected.some((p) => priceMap[p.id]?.[m]));

  return (
    <div>
      {/* 选择器 */}
      <div className="mb-6 rounded-xl border border-border p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium">{t('pick')}</p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{selectedSlugs.length}/4 · {t('max')}</span>
            {selectedSlugs.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setSelection([])}>
                {t('clear')}
              </Button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {providers.map((p) => {
            const on = selectedSlugs.includes(p.slug);
            const disabled = !on && selectedSlugs.length >= 4;
            return (
              <button
                key={p.id}
                onClick={() => toggle(p.slug)}
                disabled={disabled}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
                  on ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted',
                  disabled && 'cursor-not-allowed opacity-40'
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.logo} alt="" width={18} height={18} className="h-[18px] w-[18px] rounded" />
                {p.name}
                {on && <Check className="h-3.5 w-3.5" />}
              </button>
            );
          })}
        </div>
      </div>

      {selected.length < 2 ? (
        <p className="py-12 text-center text-muted-foreground">{t('needTwo')}</p>
      ) : (
        <>
          <div className="mb-3 flex justify-end">
            <Button variant="outline" size="sm" onClick={share}>
              {copied ? <Check className="h-3.5 w-3.5" /> : <Share2 className="h-3.5 w-3.5" />}
              {copied ? t('shareCopied') : t('share')}
            </Button>
          </div>

          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-muted/95 px-4 py-3 text-left text-xs font-medium text-muted-foreground backdrop-blur">
                    {t('attribute')}
                  </th>
                  {selected.map((p) => (
                    <th key={p.id} className="min-w-[160px] px-4 py-3 text-left">
                      <div className="flex items-center gap-2">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={p.logo} alt="" width={28} height={28} className="h-7 w-7 rounded-md" />
                        <Link href={`/providers/${p.slug}`} className="font-semibold hover:text-primary">
                          {p.name}
                        </Link>
                        <button onClick={() => toggle(p.slug)} className="text-muted-foreground hover:text-destructive" aria-label={t('remove')}>
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <Row label={detail('founded')} cells={selected.map((p) => p.founded_date)} />
                <Row label="Trust" cells={selected.map((p) => String(p.trust_score))} highlightMax />
                <Row label={detail('status')} cells={selected.map((p) => `${p.uptime_30d}%`)} />
                <Row label="Latency" cells={selected.map((p) => `${p.avg_latency_ms}ms`)} />
                <Row label={detail('invoice')} cells={selected.map((p) => (p.supports_invoice ? detail('yes') : detail('no')))} />
                <Row label={detail('dpa')} cells={selected.map((p) => (p.supports_dpa ? detail('yes') : detail('no')))} />
                <Row label={detail('payments')} cells={selected.map((p) => p.payment_methods.map((m) => paymentShort[m]).join(' '))} />
                <Row label={detail('regions')} cells={selected.map((p) => p.regions.map((r) => regionLabel[r]).join(' '))} />

                <tr>
                  <td colSpan={selected.length + 1} className="bg-muted/40 px-4 py-2 text-xs font-semibold text-muted-foreground">
                    {detail('outputCol')}
                  </td>
                </tr>
                {activeModels.map((m) => {
                  const prices = selected.map((p) => priceMap[p.id]?.[m]?.price ?? null);
                  const min = Math.min(...prices.filter((v): v is number => v !== null));
                  return (
                    <tr key={m} className="border-t border-border hover:bg-primary/5">
                      <td className="sticky left-0 z-10 bg-background px-4 py-2.5 font-medium">{m}</td>
                      {selected.map((p, i) => {
                        const cell = priceMap[p.id]?.[m];
                        return (
                          <td key={p.id} className="px-4 py-2.5">
                            {cell ? (
                              <span className={cn('font-semibold', prices[i] === min ? 'text-primary' : 'text-foreground')}>
                                {formatPrice(cell.price)}
                                <span className="ml-1 text-xs font-normal text-muted-foreground">-{cell.discount}%</span>
                                {prices[i] === min && <Badge variant="success" className="ml-1">★</Badge>}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}

                <tr className="border-t border-border">
                  <td className="sticky left-0 z-10 bg-background px-4 py-3" />
                  {selected.map((p) => (
                    <td key={p.id} className="px-4 py-3">
                      <OutboundLink provider={p} sourcePage="/compare" size="sm" className="w-full" />
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, cells, highlightMax }: { label: string; cells: string[]; highlightMax?: boolean }) {
  const maxVal = highlightMax ? Math.max(...cells.map((c) => parseFloat(c) || -Infinity)) : null;
  return (
    <tr className="border-t border-border hover:bg-primary/5">
      <td className="sticky left-0 z-10 bg-background px-4 py-2.5 text-xs font-medium text-muted-foreground">{label}</td>
      {cells.map((c, i) => (
        <td key={i} className={cn('px-4 py-2.5', highlightMax && parseFloat(c) === maxVal && 'font-semibold text-primary')}>
          {c}
        </td>
      ))}
    </tr>
  );
}
