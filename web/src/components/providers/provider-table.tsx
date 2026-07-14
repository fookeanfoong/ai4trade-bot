import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/routing';
import type { Provider } from '@/lib/types';
import { OutboundLink } from '@/components/outbound-link';
import { Badge } from '@/components/ui/badge';
import { paymentShort, regionLabel } from '@/lib/display';
import { cheapestGpt4o } from '@/lib/selectors';
import { formatPrice } from '@/lib/utils';

// 数据表格:斑马纹 + hover 高亮 + 粘性表头(样式见 globals .data-table)
export function ProviderTable({ providers, sourcePage }: { providers: Provider[]; sourcePage: string }) {
  const t = useTranslations('providers');
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="data-table w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="px-3 py-2.5 font-medium">{t('colName')}</th>
            <th className="px-3 py-2.5 font-medium">{t('cheapestGpt4o')}</th>
            <th className="px-3 py-2.5 font-medium">{t('colTrust')}</th>
            <th className="hidden px-3 py-2.5 font-medium md:table-cell">{t('colUptime')}</th>
            <th className="hidden px-3 py-2.5 font-medium md:table-cell">{t('colLatency')}</th>
            <th className="hidden px-3 py-2.5 font-medium lg:table-cell">{t('colPayment')}</th>
            <th className="px-3 py-2.5 text-right font-medium">{t('colAction')}</th>
          </tr>
        </thead>
        <tbody>
          {providers.map((p) => {
            const gpt = cheapestGpt4o(p.id);
            return (
              <tr key={p.id} className="border-t border-border">
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={p.logo} alt="" width={26} height={26} className="h-6 w-6 rounded-md" />
                    <Link href={`/providers/${p.slug}`} className="font-medium hover:text-primary">
                      {p.name}
                    </Link>
                    {p.sponsored && <Badge variant="sponsored">Sponsored</Badge>}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  {gpt ? (
                    <span className="font-semibold text-primary">{formatPrice(gpt.output_price_per_1m)}</span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-3 py-2.5">{p.trust_score}</td>
                <td className="hidden px-3 py-2.5 md:table-cell">{p.uptime_30d}%</td>
                <td className="hidden px-3 py-2.5 md:table-cell">{p.avg_latency_ms}ms</td>
                <td className="hidden px-3 py-2.5 lg:table-cell">
                  <div className="flex flex-wrap gap-1">
                    {p.payment_methods.slice(0, 3).map((m) => (
                      <span key={m} className="rounded bg-secondary px-1.5 py-0.5 text-xs">
                        {paymentShort[m]}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-right">
                  <OutboundLink provider={p} sourcePage={sourcePage} size="sm" variant="outline">
                    {t('visit')}
                  </OutboundLink>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
