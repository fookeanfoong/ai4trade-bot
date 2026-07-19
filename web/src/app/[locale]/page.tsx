import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { Trophy } from 'lucide-react';
import { HeroSearch } from '@/components/home/hero-search';
import { Faq } from '@/components/home/faq';
import { ProviderCard } from '@/components/providers/provider-card';
import { OutboundLink } from '@/components/outbound-link';
import { StarRating } from '@/components/star-rating';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { providers } from '@/lib/data/providers';
import { models } from '@/lib/data/models';
import { reviews } from '@/lib/data/reviews';
import { getFaq } from '@/lib/data/faq';
import { cheapestByModel, editorPicks, newArrivals, maxDiscount } from '@/lib/selectors';
import { formatPrice, cn } from '@/lib/utils';
import { regionLabel } from '@/lib/display';
import { JsonLd } from '@/components/json-ld';
import { PwaHero } from '@/components/pwa-promo';
import { webSiteLd, organizationLd, faqPageLd } from '@/lib/jsonld';
import { hreflangAlternates } from '@/lib/site';

export async function generateMetadata({ params: { locale } }: { params: { locale: string } }) {
  return { alternates: { canonical: `/${locale}`, languages: hreflangAlternates('') } };
}

const MEDAL = ['text-gold', 'text-silver', 'text-bronze'];

export default async function HomePage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'home' });
  const meta = await getTranslations({ locale, namespace: 'meta' });
  const cheap = cheapestByModel('GPT-4o').slice(0, 5);
  const faqItems = getFaq(locale);

  return (
    <div>
      <JsonLd
        data={[
          webSiteLd(locale, meta('siteName')),
          organizationLd(meta('siteName')),
          faqPageLd(faqItems.map((f) => ({ q: f.q, a: f.a }))),
        ]}
      />
      {/* AI4Trade Signals App 醒目入口(顶部横幅) */}
      <PwaHero />

      {/* Hero + 搜索 */}
      <section className="relative overflow-hidden border-b border-border">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_0%,hsl(var(--primary)/0.15),transparent)]" />
        <div className="container relative py-16 text-center sm:py-24">
          <Badge className="mb-4">GPT-4o · Claude · Gemini · DeepSeek · Grok</Badge>
          <h1 className="mx-auto max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
            {t('heroTitle')}
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-muted-foreground sm:text-lg">{t('heroSubtitle')}</p>
          <div className="mt-8">
            <HeroSearch />
          </div>
        </div>
      </section>

      {/* 数据条 */}
      <section className="border-b border-border bg-card/40">
        <div className="container grid grid-cols-2 gap-px py-0 sm:grid-cols-4">
          <Stat value={String(providers.length)} label={t('statProviders')} />
          <Stat value={String(models.length)} label={t('statModels')} />
          <Stat value="2026-07-14" label={t('statUpdated')} />
          <Stat value={`-${maxDiscount()}%`} label={t('statSaved')} accent />
        </div>
      </section>

      {/* 本周最便宜 Top 5 —— 适合截图分享的核心卡片 */}
      <Section title={t('cheapestTitle')} subtitle={t('cheapestSubtitle')}>
        <Card className="mx-auto max-w-3xl overflow-hidden">
          <CardContent className="p-0">
            {cheap.map((row, i) => (
              <div
                key={row.provider.id}
                className={cn(
                  'flex items-center gap-3 px-4 py-3 sm:px-5',
                  i > 0 && 'border-t border-border'
                )}
              >
                <div className={cn('flex w-7 justify-center', i < 3 ? MEDAL[i] : 'text-muted-foreground')}>
                  {i < 3 ? <Trophy className="h-5 w-5" /> : <span className="text-sm">{i + 1}</span>}
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={row.provider.logo} alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
                <div className="min-w-0 flex-1">
                  <Link href={`/providers/${row.provider.slug}`} className="font-medium hover:text-primary">
                    {row.provider.name}
                  </Link>
                  <div className="text-xs text-muted-foreground">
                    {row.provider.regions.slice(0, 3).map((r) => regionLabel[r]).join(' · ')}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-primary">{formatPrice(row.model.output_price_per_1m)}</div>
                  <div className="text-xs text-muted-foreground">/1M · -{row.model.discount_percent}%</div>
                </div>
                <OutboundLink provider={row.provider} sourcePage="/" size="sm" variant="outline" />
              </div>
            ))}
          </CardContent>
        </Card>
      </Section>

      {/* 编辑精选 */}
      <Section title={t('editorTitle')} subtitle={t('editorSubtitle')}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {editorPicks().map((p) => (
            <ProviderCard key={p.id} provider={p} sourcePage="/" />
          ))}
        </div>
      </Section>

      {/* 新上架 */}
      <Section title={t('newTitle')} subtitle={t('newSubtitle')}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {newArrivals().map((p) => (
            <ProviderCard key={p.id} provider={p} sourcePage="/" />
          ))}
        </div>
      </Section>

      {/* 三步说明 */}
      <Section title={t('howTitle')}>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { t: t('howStep1Title'), d: t('howStep1Desc') },
            { t: t('howStep2Title'), d: t('howStep2Desc') },
            { t: t('howStep3Title'), d: t('howStep3Desc') },
          ].map((s) => (
            <Card key={s.t}>
              <CardContent className="p-6">
                <p className="text-lg font-semibold text-primary">{s.t}</p>
                <p className="mt-2 text-sm text-muted-foreground">{s.d}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      {/* 评价 */}
      <Section title={t('reviewsTitle')}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {reviews.slice(0, 6).map((r) => {
            const prov = providers.find((p) => p.id === r.provider_id);
            return (
              <Card key={r.id}>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <StarRating value={r.rating} />
                    <span className="text-xs text-muted-foreground">{regionLabel[r.region]}</span>
                  </div>
                  <p className="mt-3 text-sm">{r.content}</p>
                  <p className="mt-3 text-xs text-muted-foreground">
                    @{r.author} · {prov?.name} · {r.use_case}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </Section>

      {/* FAQ */}
      <Section title={t('faqTitle')}>
        <Faq items={getFaq(locale)} />
      </Section>
    </div>
  );
}

function Stat({ value, label, accent }: { value: string; label: string; accent?: boolean }) {
  return (
    <div className="bg-background px-4 py-6 text-center">
      <div className={cn('text-2xl font-bold sm:text-3xl', accent && 'text-primary')}>{value}</div>
      <div className="mt-1 text-xs text-muted-foreground sm:text-sm">{label}</div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="container py-12">
      <div className="mb-6">
        <h2 className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}
