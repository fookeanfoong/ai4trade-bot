'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Ticket, Activity } from 'lucide-react';
import type { Provider, Model, Review } from '@/lib/types';
import { PricingTable } from '@/components/provider/pricing-table';
import { StarRating } from '@/components/star-rating';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { regionLabel, paymentLabel } from '@/lib/display';
import { cn } from '@/lib/utils';

type Tab = 'overview' | 'pricing' | 'status' | 'reviews' | 'coupons';

export function ProviderTabs({
  provider,
  models,
  reviews,
}: {
  provider: Provider;
  models: Model[];
  reviews: Review[];
}) {
  const t = useTranslations('detail');
  const [tab, setTab] = useState<Tab>('overview');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: t('overview') },
    { key: 'pricing', label: t('pricing') },
    { key: 'status', label: t('status') },
    { key: 'reviews', label: `${t('reviews')} (${reviews.length})` },
    { key: 'coupons', label: t('coupons') },
  ];

  return (
    <div>
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={cn(
              'whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              tab === tb.key
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid gap-4 sm:grid-cols-2">
          <InfoRow label={t('founded')} value={provider.founded_date} />
          <InfoRow label={t('regions')} value={provider.regions.map((r) => regionLabel[r]).join(' · ')} />
          <InfoRow label={t('payments')} value={provider.payment_methods.map((m) => paymentLabel[m]).join(' · ')} />
          <InfoRow label={t('invoice')} value={provider.supports_invoice ? t('yes') : t('no')} />
          <InfoRow label={t('dpa')} value={provider.supports_dpa ? t('yes') : t('no')} />
          <InfoRow label="Trust / Uptime / Latency" value={`${provider.trust_score} · ${provider.uptime_30d}% · ${provider.avg_latency_ms}ms`} />
        </div>
      )}

      {tab === 'pricing' && <PricingTable models={models} />}

      {tab === 'status' && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <StatCard label={t('status')} value={`${provider.uptime_30d}%`} sub="30d uptime" />
            <StatCard label="Latency" value={`${provider.avg_latency_ms}ms`} sub="avg" />
            <StatCard label="Trust" value={String(provider.trust_score)} sub="/100" />
          </div>
          <div className="rounded-lg border border-border">
            {models.map((m, i) => (
              <div key={i} className={cn('flex items-center justify-between px-4 py-2.5', i > 0 && 'border-t border-border')}>
                <span className="flex items-center gap-2 text-sm">
                  <Activity className="h-3.5 w-3.5 text-muted-foreground" />
                  {m.model_name}
                </span>
                <Badge variant={m.status === 'available' ? 'success' : m.status === 'degraded' ? 'warning' : 'danger'}>
                  {m.status === 'available' ? t('statusAvailable') : m.status === 'degraded' ? t('statusDegraded') : t('statusOffline')}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'reviews' && (
        <div className="space-y-3">
          {reviews.length === 0 && <p className="text-muted-foreground">{t('communityReview')}: —</p>}
          {reviews.map((r) => (
            <Card key={r.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StarRating value={r.rating} />
                    <span className="text-sm font-medium">@{r.author}</span>
                    <Badge variant={r.verified_purchase ? 'success' : 'outline'}>
                      {r.verified_purchase ? t('verifiedPurchase') : t('communityReview')}
                    </Badge>
                  </div>
                  <span className="text-xs text-muted-foreground">{regionLabel[r.region]} · {r.use_case}</span>
                </div>
                <p className="mt-2 text-sm">{r.content}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tab === 'coupons' && (
        <div>
          {provider.discount_code ? (
            <div className="flex items-center gap-3 rounded-lg border border-dashed border-primary/50 bg-primary/5 p-4">
              <Ticket className="h-5 w-5 text-primary" />
              <code className="rounded bg-background px-2 py-1 text-sm font-semibold">{provider.discount_code}</code>
              <span className="text-sm text-muted-foreground">{provider.name}</span>
            </div>
          ) : (
            <p className="text-muted-foreground">{t('noCoupon')}</p>
          )}
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium">{value}</div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4 text-center">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold text-primary">{value}</div>
      <div className="text-xs text-muted-foreground">{sub}</div>
    </div>
  );
}
