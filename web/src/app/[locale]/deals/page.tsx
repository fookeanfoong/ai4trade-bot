import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { Ticket } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { OutboundLink } from '@/components/outbound-link';
import { CopyCode } from '@/components/deals/copy-code';
import { providersWithDeals, cheapestGpt4o } from '@/lib/selectors';
import { regionLabel } from '@/lib/display';
import { formatPrice } from '@/lib/utils';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'deals' });
  return { title: t('title'), description: t('subtitle'), alternates: { canonical: `/${locale}/deals` } };
}

export default async function DealsPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'deals' });
  const deals = providersWithDeals();

  return (
    <div className="container py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('subtitle')}</p>
      </header>

      {deals.length === 0 ? (
        <p className="py-16 text-center text-muted-foreground">{t('noDeals')}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {deals.map((p) => {
            const gpt = cheapestGpt4o(p.id);
            return (
              <Card key={p.id} className="flex flex-col">
                <CardContent className="flex flex-1 flex-col gap-3 p-5">
                  <div className="flex items-center gap-3">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={p.logo} alt="" width={40} height={40} className="h-10 w-10 rounded-lg" />
                    <div>
                      <Link href={`/providers/${p.slug}`} className="font-semibold hover:text-primary">
                        {p.name}
                      </Link>
                      <div className="text-xs text-muted-foreground">
                        {p.regions.slice(0, 3).map((r) => regionLabel[r]).join(' · ')}
                      </div>
                    </div>
                    {p.sponsored && <Badge variant="sponsored" className="ml-auto">Sponsored</Badge>}
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    <Ticket className="h-4 w-4 text-primary" />
                    <span className="text-muted-foreground">{t('code')}:</span>
                    <CopyCode code={p.discount_code!} />
                  </div>

                  {gpt && (
                    <p className="text-xs text-muted-foreground">
                      GPT-4o <span className="font-semibold text-primary">{formatPrice(gpt.output_price_per_1m)}</span> /1M · -{gpt.discount_percent}%
                    </p>
                  )}

                  <div className="mt-auto pt-1">
                    <OutboundLink provider={p} sourcePage="/deals" size="sm" className="w-full">
                      {t('useAt')}
                    </OutboundLink>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
