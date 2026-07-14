import { useTranslations } from 'next-intl';
import type { Model } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { formatPrice } from '@/lib/utils';

const statusVariant = {
  available: 'success',
  degraded: 'warning',
  offline: 'danger',
} as const;

export function PricingTable({ models }: { models: Model[] }) {
  const t = useTranslations('detail');
  const statusLabel: Record<Model['status'], string> = {
    available: t('statusAvailable'),
    degraded: t('statusDegraded'),
    offline: t('statusOffline'),
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="data-table w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="px-3 py-2.5 font-medium">{t('modelCol')}</th>
            <th className="px-3 py-2.5 font-medium">{t('inputCol')}</th>
            <th className="px-3 py-2.5 font-medium">{t('outputCol')}</th>
            <th className="hidden px-3 py-2.5 font-medium sm:table-cell">{t('officialCol')}</th>
            <th className="px-3 py-2.5 font-medium">{t('discountCol')}</th>
            <th className="hidden px-3 py-2.5 font-medium md:table-cell">{t('contextCol')}</th>
            <th className="px-3 py-2.5 font-medium">{t('statusCol')}</th>
          </tr>
        </thead>
        <tbody>
          {models.map((m, i) => (
            <tr key={`${m.model_name}-${i}`} className="border-t border-border">
              <td className="px-3 py-2.5 font-medium">{m.model_name}</td>
              <td className="px-3 py-2.5">{formatPrice(m.input_price_per_1m)}</td>
              <td className="px-3 py-2.5 font-semibold text-primary">{formatPrice(m.output_price_per_1m)}</td>
              <td className="hidden px-3 py-2.5 text-muted-foreground line-through sm:table-cell">
                {formatPrice(m.official_price_per_1m)}
              </td>
              <td className="px-3 py-2.5">
                <Badge variant="success">-{m.discount_percent}%</Badge>
              </td>
              <td className="hidden px-3 py-2.5 text-muted-foreground md:table-cell">
                {(m.context_length / 1000).toLocaleString()}K
              </td>
              <td className="px-3 py-2.5">
                <Badge variant={statusVariant[m.status]}>{statusLabel[m.status]}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
