import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { ShieldCheck, Gauge, Timer } from 'lucide-react';
import { providers, getProvider } from '@/lib/data/providers';
import { getModelsByProvider } from '@/lib/data/models';
import { getReviewsByProvider, avgRating } from '@/lib/data/reviews';
import { similarProviders } from '@/lib/selectors';
import { routing } from '@/i18n/routing';
import { OutboundLink } from '@/components/outbound-link';
import { ProviderTabs } from '@/components/provider/provider-tabs';
import { ProviderCard } from '@/components/providers/provider-card';
import { CopyCompare } from '@/components/provider/copy-compare';
import { ReportButton } from '@/components/provider/report-button';
import { FavoriteButton } from '@/components/favorite-button';
import { StarRating } from '@/components/star-rating';
import { Badge } from '@/components/ui/badge';
import { JsonLd } from '@/components/json-ld';
import { providerProductLd, breadcrumbLd } from '@/lib/jsonld';
import { hreflangAlternates } from '@/lib/site';
import { regionLabel } from '@/lib/display';
import { formatPrice } from '@/lib/utils';

export function generateStaticParams() {
  return routing.locales.flatMap((locale) =>
    providers.map((p) => ({ locale, slug: p.slug }))
  );
}

export async function generateMetadata({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}): Promise<Metadata> {
  const provider = getProvider(slug);
  if (!provider) return {};
  const desc = provider.description?.[locale] || provider.description?.en || provider.name;
  return {
    title: `${provider.name} 价格、评价与实时状态`,
    description: desc,
    alternates: { canonical: `/${locale}/providers/${slug}`, languages: hreflangAlternates(`/providers/${slug}`) },
    openGraph: {
      title: `${provider.name} · AggreAPI`,
      description: desc,
      images: [{ url: provider.logo, width: 300, height: 300, alt: provider.name }],
    },
    other: { 'itemprop:image': provider.logo },
  };
}

export default async function ProviderDetailPage({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}) {
  setRequestLocale(locale);
  const provider = getProvider(slug);
  if (!provider) notFound();

  const t = await getTranslations({ locale, namespace: 'detail' });
  const providersT = await getTranslations({ locale, namespace: 'providers' });
  const common = await getTranslations({ locale, namespace: 'common' });

  const models = getModelsByProvider(provider.id);
  const reviews = getReviewsByProvider(provider.id);
  const rating = avgRating(provider.id);
  const similar = similarProviders(slug);
  const desc = provider.description?.[locale] || provider.description?.en || '';

  // 文字版对比(供「复制」按钮 → 小红书/知乎/微信分享)
  const compareText = [
    `【${provider.name}】AI API 中转站`,
    `信任分 ${provider.trust_score}/100 · 30天在线 ${provider.uptime_30d}% · 延迟 ${provider.avg_latency_ms}ms`,
    `覆盖:${provider.regions.map((r) => regionLabel[r]).join('/')}`,
    '——价格(输出价/1M tokens)——',
    ...models.map((m) => `${m.model_name}: ${formatPrice(m.output_price_per_1m)}(-${m.discount_percent}%)`),
    `via AggreAPI 比价`,
  ].join('\n');

  return (
    <div className="container py-8">
      <JsonLd
        data={[
          providerProductLd(provider, models, reviews, rating, locale, `/${locale}/providers/${slug}`),
          breadcrumbLd([
            { name: common('backHome'), path: `/${locale}` },
            { name: providersT('title'), path: `/${locale}/providers` },
            { name: provider.name, path: `/${locale}/providers/${slug}` },
          ]),
        ]}
      />
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/" className="hover:text-foreground">{common('backHome')}</Link>
        {' / '}
        <Link href="/providers" className="hover:text-foreground">{providersT('title')}</Link>
        {' / '}
        <span className="text-foreground">{provider.name}</span>
      </nav>

      {/* 核心分享卡片:logo + 关键指标 + 迷你价格表 + 购买 —— 信息完整,适合截图 */}
      <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-5 sm:p-7">
        {provider.sponsored && (
          <Badge variant="sponsored" className="absolute right-4 top-4">{common('sponsored')}</Badge>
        )}
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={provider.logo} alt={`${provider.name} logo`} width={72} height={72} className="h-16 w-16 rounded-xl sm:h-[72px] sm:w-[72px]" />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{provider.name}</h1>
              {provider.editor_pick && <Badge>{common('editorPick')}</Badge>}
              {provider.new_arrival && <Badge variant="success">{common('new')}</Badge>}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <StarRating value={rating} />
              <span className="text-sm text-muted-foreground">{rating.toFixed(1)} · {reviews.length} {t('reviews')}</span>
            </div>
            {desc && <p className="mt-3 max-w-2xl text-sm text-muted-foreground">{desc}</p>}

            <div className="mt-4 grid grid-cols-3 gap-3 sm:max-w-md">
              <Metric icon={<ShieldCheck className="h-4 w-4" />} label={providersT('trustScore')} value={String(provider.trust_score)} />
              <Metric icon={<Gauge className="h-4 w-4" />} label={providersT('uptime')} value={`${provider.uptime_30d}%`} />
              <Metric icon={<Timer className="h-4 w-4" />} label={providersT('latency')} value={`${provider.avg_latency_ms}ms`} />
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:w-44">
            <OutboundLink provider={provider} sourcePage={`/providers/${slug}`} size="lg" className="w-full">
              {t('buyNow')}
            </OutboundLink>
            <CopyCompare text={compareText} />
            <FavoriteButton slug={provider.slug} />
            <span className="text-center text-[10px] text-muted-foreground">{t('shareCardHint')}</span>
          </div>
        </div>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_300px]">
        <div>
          <ProviderTabs provider={provider} models={models} reviews={reviews} />
          <div className="mt-6">
            <ReportButton providerName={provider.name} />
          </div>
        </div>

        {/* 相似推荐 */}
        <aside>
          <h2 className="mb-4 text-lg font-semibold">{t('similarTitle')}</h2>
          <div className="space-y-4">
            {similar.map((p) => (
              <ProviderCard key={p.id} provider={p} sourcePage={`/providers/${slug}`} />
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/40 p-2.5 text-center">
      <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground">{icon}{label}</div>
      <div className="mt-0.5 font-semibold">{value}</div>
    </div>
  );
}
