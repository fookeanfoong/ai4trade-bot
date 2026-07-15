import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { Trophy, Info, ArrowRight } from 'lucide-react';
import { routing } from '@/i18n/routing';
import { OutboundLink } from '@/components/outbound-link';
import { Badge } from '@/components/ui/badge';
import { JsonLd } from '@/components/json-ld';
import { itemListLd, breadcrumbLd, faqPageLd } from '@/lib/jsonld';
import { hreflangAlternates, abs } from '@/lib/site';
import { regionLabel } from '@/lib/display';
import {
  cheapestByModel,
  modelNameBySlug,
  modelSummaries,
  modelSlug,
} from '@/lib/selectors';
import { formatPrice, cn } from '@/lib/utils';
import type { ModelStatus } from '@/lib/types';

const MEDAL = ['text-gold', 'text-silver', 'text-bronze'];
const STATUS_KEY: Record<ModelStatus, string> = {
  available: 'statusAvailable',
  degraded: 'statusDegraded',
  offline: 'statusOffline',
};
const STATUS_CLASS: Record<ModelStatus, string> = {
  available: 'text-green-500',
  degraded: 'text-amber-500',
  offline: 'text-muted-foreground',
};

function ctxLabel(tokens: number): string {
  if (tokens >= 1_000_000) return `${tokens / 1_000_000}M`;
  if (tokens >= 1000) return `${Math.round(tokens / 1000)}K`;
  return String(tokens);
}

export function generateStaticParams() {
  return routing.locales.flatMap((locale) =>
    modelSummaries().map((m) => ({ locale, slug: m.slug }))
  );
}

export async function generateMetadata({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}): Promise<Metadata> {
  const name = modelNameBySlug(slug);
  if (!name) return {};
  const t = await getTranslations({ locale, namespace: 'modelDetail' });
  const rows = cheapestByModel(name);
  const summary = modelSummaries().find((m) => m.slug === slug)!;
  const vars = {
    model: name,
    count: summary.providerCount,
    cheapest: formatPrice(summary.cheapestOutput),
    official: formatPrice(summary.official),
    discount: summary.maxDiscount,
  };
  return {
    title: t('metaTitle', vars),
    description: t('metaDescription', vars),
    alternates: {
      canonical: `/${locale}/models/${slug}`,
      languages: hreflangAlternates(`/models/${slug}`),
    },
    openGraph: {
      title: t('metaTitle', vars),
      description: t('metaDescription', vars),
      images: [{ url: '/og-default.svg', width: 300, height: 300 }],
    },
  };
}

export default async function ModelDetailPage({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}) {
  setRequestLocale(locale);
  const name = modelNameBySlug(slug);
  if (!name) notFound();

  const t = await getTranslations({ locale, namespace: 'modelDetail' });
  const rows = cheapestByModel(name);
  const summary = modelSummaries().find((m) => m.slug === slug)!;
  const others = modelSummaries().filter((m) => m.slug !== slug);

  const vars = {
    model: name,
    count: summary.providerCount,
    cheapest: formatPrice(summary.cheapestOutput),
    official: formatPrice(summary.official),
    discount: summary.maxDiscount,
  };

  const faqs = [
    { q: t('faqQ1', vars), a: t('faqA1', vars) },
    { q: t('faqQ2', vars), a: t('faqA2', vars) },
    { q: t('faqQ3', vars), a: t('faqA3', vars) },
  ];

  // AggregateOffer 结构化数据:让搜索结果直接展示价格区间与折扣。
  const offerLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: `${name} API`,
    description: t('metaDescription', vars),
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: 'USD',
      lowPrice: rows[0]?.model.output_price_per_1m.toFixed(2),
      highPrice: rows[rows.length - 1]?.model.output_price_per_1m.toFixed(2),
      offerCount: rows.length,
      availability: 'https://schema.org/InStock',
      url: abs(`/${locale}/models/${slug}`),
    },
  };

  return (
    <div className="container max-w-4xl py-8">
      <JsonLd
        data={[
          offerLd,
          itemListLd(
            t('h1', vars),
            rows.map((row) => ({
              name: row.provider.name,
              path: `/${locale}/providers/${row.provider.slug}`,
            }))
          ),
          faqPageLd(faqs),
          breadcrumbLd([
            { name: t('backToModels'), path: `/${locale}/models` },
            { name: t('h1', vars), path: `/${locale}/models/${slug}` },
          ]),
        ]}
      />

      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/models" className="hover:text-foreground">
          {t('backToModels')}
        </Link>
        {' / '}
        <span className="text-foreground">{name}</span>
      </nav>

      <header className="mb-6">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('h1', vars)}</h1>
          <Badge variant="secondary">{summary.family}</Badge>
        </div>
        <p className="mt-2 text-muted-foreground">{t('intro', vars)}</p>
      </header>

      {/* 最便宜卡片:第一屏就把核心卖点(最低价 + 省多少)顶上去 */}
      {rows.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={rows[0].provider.logo}
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 rounded-lg"
            />
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-primary">
                {t('cheapestNow')}
              </div>
              <div className="font-semibold">{rows[0].provider.name}</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-2xl font-bold text-primary">
                {formatPrice(summary.cheapestOutput)}
                <span className="ml-1 text-xs font-normal text-muted-foreground">
                  {t('perM')}
                </span>
              </div>
              <div className="text-xs text-green-500">
                {t('save', { percent: summary.maxDiscount })}
              </div>
            </div>
            <OutboundLink provider={rows[0].provider} sourcePage={`/models/${slug}`} />
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="data-table w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">{t('colRank')}</th>
              <th className="px-4 py-2.5 font-medium">{t('colProvider')}</th>
              <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
                {t('colInput')}
              </th>
              <th className="px-4 py-2.5 text-right font-medium">{t('colOutput')}</th>
              <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
                {t('colStatus')}
              </th>
              <th className="px-4 py-2.5 text-right font-medium">·</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.provider.id} className="border-t border-border">
                <td className="px-4 py-3">
                  {i < 3 ? (
                    <Trophy className={cn('h-5 w-5', MEDAL[i])} />
                  ) : (
                    <span className="text-muted-foreground">{i + 1}</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/providers/${row.provider.slug}`}
                    className="flex items-center gap-2 font-medium hover:text-primary"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={row.provider.logo}
                      alt=""
                      width={26}
                      height={26}
                      className="h-6 w-6 rounded"
                    />
                    {row.provider.name}
                    {row.provider.sponsored && <Badge variant="sponsored">Sponsored</Badge>}
                  </Link>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {row.provider.regions.slice(0, 3).map((rg) => regionLabel[rg]).join(' · ')}
                    {' · '}
                    {ctxLabel(row.model.context_length)}
                  </div>
                  {/* 移动端:把输入价/状态收进这里 */}
                  <div className="mt-0.5 text-xs text-muted-foreground sm:hidden">
                    {t('colInput')} {formatPrice(row.model.input_price_per_1m)}
                    {' · '}
                    <span className={STATUS_CLASS[row.model.status]}>
                      {t(STATUS_KEY[row.model.status])}
                    </span>
                  </div>
                </td>
                <td className="hidden px-4 py-3 text-right text-muted-foreground sm:table-cell">
                  {formatPrice(row.model.input_price_per_1m)}
                </td>
                <td className="px-4 py-3 text-right">
                  <span className="font-semibold text-primary">
                    {formatPrice(row.model.output_price_per_1m)}
                  </span>
                  <div className="text-xs text-green-500">-{row.model.discount_percent}%</div>
                </td>
                <td className="hidden px-4 py-3 text-right sm:table-cell">
                  <span className={cn('text-xs', STATUS_CLASS[row.model.status])}>
                    {t(STATUS_KEY[row.model.status])}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <OutboundLink
                    provider={row.provider}
                    sourcePage={`/models/${slug}`}
                    size="sm"
                    variant="outline"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-lg border border-border bg-muted/30 p-4 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          {t('official')} {formatPrice(summary.official)} {t('perM')} · {t('disclaimer')}
        </span>
      </div>

      {/* FAQ:命中长尾问题词,并喂给 FAQPage 结构化数据 */}
      <section className="mt-10">
        <h2 className="mb-4 text-xl font-bold tracking-tight">{t('faqTitle')}</h2>
        <div className="space-y-3">
          {faqs.map((f) => (
            <details
              key={f.q}
              className="group rounded-lg border border-border bg-card px-4 py-3"
            >
              <summary className="cursor-pointer list-none font-medium marker:content-none">
                {f.q}
              </summary>
              <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* 内链:对比其他模型 —— 让爬虫在模型页之间流转,分散权重 */}
      <section className="mt-10">
        <h2 className="mb-4 text-lg font-semibold">{t('otherModels')}</h2>
        <div className="flex flex-wrap gap-2">
          {others.map((m) => (
            <Link
              key={m.slug}
              href={`/models/${m.slug}`}
              className="rounded-full border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              {m.name}
            </Link>
          ))}
        </div>
        <Link
          href="/providers"
          className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          {t('allProviders')}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
