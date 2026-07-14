import type { Metadata } from 'next';
import { hreflangAlternates } from '@/lib/site';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { Trophy } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { OutboundLink } from '@/components/outbound-link';
import { uniqueModelNames, cheapestByModel } from '@/lib/selectors';
import { models as allModels } from '@/lib/data/models';
import { formatPrice, cn } from '@/lib/utils';

const MEDAL = ['text-gold', 'text-silver', 'text-bronze'];

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'models' });
  return { title: t('title'), description: t('subtitle'), alternates: { canonical: `/${locale}/models`, languages: hreflangAlternates('/models') } };
}

export default async function ModelsPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'models' });
  const modelNames = uniqueModelNames();

  return (
    <div className="container py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('subtitle')}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        {modelNames.map((name) => {
          const rows = cheapestByModel(name);
          const official = allModels.find((m) => m.model_name === name)?.official_price_per_1m;
          return (
            <Card key={name}>
              <CardContent className="p-0">
                <div className="flex items-center justify-between border-b border-border px-5 py-3">
                  <div>
                    <h2 className="font-semibold">{name}</h2>
                    <p className="text-xs text-muted-foreground">
                      {t('providerCount', { count: rows.length })}
                      {official ? ` · ${t('official')} ${formatPrice(official)}` : ''}
                    </p>
                  </div>
                  <Badge variant="success">
                    {t('cheapest')} {formatPrice(rows[0].model.output_price_per_1m)}
                  </Badge>
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={row.provider.id} className="border-b border-border/60 last:border-0 hover:bg-primary/5">
                        <td className="w-8 py-2.5 pl-5 text-center">
                          {i < 3 ? (
                            <Trophy className={cn('mx-auto h-4 w-4', MEDAL[i])} />
                          ) : (
                            <span className="text-xs text-muted-foreground">{i + 1}</span>
                          )}
                        </td>
                        <td className="py-2.5">
                          <Link
                            href={`/providers/${row.provider.slug}`}
                            className="flex items-center gap-2 font-medium hover:text-primary"
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={row.provider.logo} alt="" width={22} height={22} className="h-[22px] w-[22px] rounded" />
                            {row.provider.name}
                            {row.provider.sponsored && <Badge variant="sponsored">Sponsored</Badge>}
                          </Link>
                        </td>
                        <td className="py-2.5 text-right">
                          <span className="font-semibold text-primary">{formatPrice(row.model.output_price_per_1m)}</span>
                          <span className="ml-1 text-xs text-muted-foreground">-{row.model.discount_percent}%</span>
                        </td>
                        <td className="py-2.5 pl-3 pr-5 text-right">
                          <OutboundLink provider={row.provider} sourcePage="/models" size="sm" variant="outline" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
