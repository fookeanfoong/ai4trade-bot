import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Check, Clock, ShieldCheck, Star, ArrowRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { hreflangAlternates, REPORT } from '@/lib/site';
import { testimonials } from '@/lib/data/testimonials';
import { JsonLd } from '@/components/json-ld';
import { faqPageLd, breadcrumbLd } from '@/lib/jsonld';
import { cn } from '@/lib/utils';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'report' });
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: { canonical: `/${locale}/report`, languages: hreflangAlternates('/report') },
    openGraph: { title: t('metaTitle'), description: t('metaDescription'), images: [{ url: '/og-default.svg', width: 300, height: 300 }] },
  };
}

export default async function ReportPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'report' });
  const nav = await getTranslations({ locale, namespace: 'nav' });

  const includes = [t('include1'), t('include2'), t('include3'), t('include4'), t('include5')];
  const faqs = [
    { q: t('faq1q'), a: t('faq1a') },
    { q: t('faq2q'), a: t('faq2a') },
    { q: t('faq3q'), a: t('faq3a') },
    { q: t('faq4q'), a: t('faq4a') },
  ];
  const soldPct = Math.min(
    100,
    Math.round(((REPORT.earlyBirdTotal - REPORT.earlyBirdLeft) / REPORT.earlyBirdTotal) * 100)
  );

  return (
    <div className="container max-w-4xl py-10">
      <JsonLd
        data={[
          faqPageLd(faqs),
          breadcrumbLd([{ name: nav('report'), path: `/${locale}/report` }]),
        ]}
      />

      {/* Hero */}
      <header className="mb-10 text-center">
        <Badge variant="secondary" className="mb-3">{t('kicker')}</Badge>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('h1')}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">{t('subtitle')}</p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
        {/* 左:内含 + outcome + 见证 */}
        <div className="space-y-8">
          <section>
            <h2 className="mb-4 text-xl font-bold tracking-tight">{t('includesTitle')}</h2>
            <ul className="space-y-3">
              {includes.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <Check className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-border bg-muted/30 p-5">
            <h2 className="flex items-center gap-2 font-semibold">
              <Clock className="h-5 w-5 text-primary" />
              {t('outcomeTitle')}
            </h2>
            <p className="mt-2 leading-relaxed text-muted-foreground">{t('outcomeBody')}</p>
          </section>

          <section>
            <h2 className="mb-4 text-xl font-bold tracking-tight">{t('testimonialsTitle')}</h2>
            <div className="space-y-4">
              {testimonials.map((tm, i) => (
                <Card key={i}>
                  <CardContent className="p-5">
                    <div className="mb-2 flex gap-0.5 text-primary">
                      {Array.from({ length: 5 }).map((_, s) => (
                        <Star key={s} className="h-4 w-4 fill-current" />
                      ))}
                    </div>
                    <p className="text-sm leading-relaxed">{tm.quote}</p>
                    <div className="mt-3 flex items-center gap-2 text-sm">
                      <span className="grid h-8 w-8 place-items-center rounded-full bg-muted text-xs font-semibold">
                        {tm.name.replace(/[[\]]/g, '').slice(0, 1) || '·'}
                      </span>
                      <div>
                        <p className="font-medium">
                          {tm.name} · <span className="text-muted-foreground">{tm.role}</span>
                        </p>
                        <p className="text-xs text-muted-foreground">{tm.tag}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        </div>

        {/* 右:定价区(sticky) */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Card className="border-primary/40">
            <CardContent className="p-6">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{REPORT.currency}{REPORT.price}</span>
                <span className="text-lg text-muted-foreground line-through">
                  {REPORT.currency}{REPORT.priceOriginal}
                </span>
              </div>
              <p className="mt-1 text-xs font-medium uppercase tracking-wide text-primary">
                {t('earlyBirdLabel')}
              </p>

              {/* 稀缺 */}
              <div className="mt-4">
                <p className="text-sm font-medium">{t('scarcity', { total: REPORT.earlyBirdTotal, left: REPORT.earlyBirdLeft })}</p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${soldPct}%` }} />
                </div>
              </div>

              {/* CTA */}
              {REPORT.checkoutUrl ? (
                <a
                  href={REPORT.checkoutUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-5 flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  {t('cta')}
                  <ArrowRight className="h-4 w-4" />
                </a>
              ) : (
                <div
                  className={cn(
                    'mt-5 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border px-4 py-3 text-sm font-medium text-muted-foreground'
                  )}
                >
                  {t('comingSoon')}
                </div>
              )}

              <div className="mt-4 space-y-2 text-xs text-muted-foreground">
                <p className="flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                  {t('faq3a')}
                </p>
                {includes.map((item) => (
                  <p key={item} className="flex items-start gap-1.5">
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                    {item}
                  </p>
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>

      {/* FAQ */}
      <section className="mt-12">
        <h2 className="mb-4 text-xl font-bold tracking-tight">{t('faqTitle')}</h2>
        <div className="space-y-3">
          {faqs.map((f) => (
            <details key={f.q} className="group rounded-lg border border-border bg-card px-4 py-3">
              <summary className="cursor-pointer list-none font-medium marker:content-none">{f.q}</summary>
              <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
