import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/routing';
import { Gauge, Timer, ShieldCheck } from 'lucide-react';
import type { Provider } from '@/lib/types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { OutboundLink } from '@/components/outbound-link';
import { StarRating } from '@/components/star-rating';
import { paymentShort, regionLabel } from '@/lib/display';
import { cheapestGpt4o } from '@/lib/selectors';
import { avgRating } from '@/lib/data/reviews';
import { formatPrice } from '@/lib/utils';

export function ProviderCard({ provider, sourcePage }: { provider: Provider; sourcePage: string }) {
  const t = useTranslations('providers');
  const common = useTranslations('common');
  const gpt = cheapestGpt4o(provider.id);
  const rating = avgRating(provider.id);

  return (
    <Card className="group relative flex flex-col overflow-hidden transition-colors hover:border-primary/50">
      {provider.sponsored && (
        <Badge variant="sponsored" className="absolute right-3 top-3">
          {common('sponsored')}
        </Badge>
      )}
      <CardContent className="flex flex-1 flex-col gap-4 p-5">
        <div className="flex items-start gap-3">
          {/* 本地打包 SVG,统一圆角方形 */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={provider.logo}
            alt={`${provider.name} logo`}
            width={44}
            height={44}
            className="h-11 w-11 rounded-lg"
            loading="lazy"
          />
          <div className="min-w-0">
            <Link href={`/providers/${provider.slug}`} className="font-semibold hover:text-primary">
              {provider.name}
            </Link>
            <div className="mt-1 flex items-center gap-2">
              <StarRating value={rating} />
              <span className="text-xs text-muted-foreground">{rating.toFixed(1)}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {provider.editor_pick && <Badge>{common('editorPick')}</Badge>}
          {provider.new_arrival && <Badge variant="success">{common('new')}</Badge>}
          {provider.regions.slice(0, 3).map((r) => (
            <Badge key={r} variant="outline">
              {regionLabel[r]}
            </Badge>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-2 rounded-lg bg-muted/40 p-3 text-center text-xs">
          <div>
            <div className="flex items-center justify-center gap-1 text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" /> {t('trustScore')}
            </div>
            <div className="mt-0.5 font-semibold text-foreground">{provider.trust_score}</div>
          </div>
          <div>
            <div className="flex items-center justify-center gap-1 text-muted-foreground">
              <Gauge className="h-3.5 w-3.5" /> {t('uptime')}
            </div>
            <div className="mt-0.5 font-semibold text-foreground">{provider.uptime_30d}%</div>
          </div>
          <div>
            <div className="flex items-center justify-center gap-1 text-muted-foreground">
              <Timer className="h-3.5 w-3.5" /> {t('latency')}
            </div>
            <div className="mt-0.5 font-semibold text-foreground">{provider.avg_latency_ms}ms</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-1 text-xs text-muted-foreground">
          {provider.payment_methods.slice(0, 4).map((m) => (
            <span key={m} className="rounded bg-secondary px-1.5 py-0.5">
              {paymentShort[m]}
            </span>
          ))}
        </div>

        {gpt && (
          <p className="text-sm">
            <span className="text-muted-foreground">{t('cheapestGpt4o')}: </span>
            <span className="font-semibold text-primary">{formatPrice(gpt.output_price_per_1m)}</span>
            <span className="text-muted-foreground"> /1M · -{gpt.discount_percent}%</span>
          </p>
        )}

        <div className="mt-auto flex gap-2 pt-1">
          <Link
            href={`/providers/${provider.slug}`}
            className="inline-flex h-9 flex-1 items-center justify-center rounded-md border border-border text-sm hover:bg-muted"
          >
            {t('detail')}
          </Link>
          <OutboundLink provider={provider} sourcePage={sourcePage} size="sm" className="h-9 flex-1">
            {t('visit')}
          </OutboundLink>
        </div>
      </CardContent>
    </Card>
  );
}
