import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { ShieldCheck, RefreshCw, Wrench, Users, Database, FlaskConical, ArrowRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { hreflangAlternates, CONTACT, twitterUrl } from '@/lib/site';
import { JsonLd } from '@/components/json-ld';
import { organizationLd, breadcrumbLd } from '@/lib/jsonld';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'about' });
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: { canonical: `/${locale}/about`, languages: hreflangAlternates('/about') },
    openGraph: { title: t('metaTitle'), description: t('metaDescription'), images: [{ url: '/og-default.svg', width: 300, height: 300 }] },
  };
}

export default async function AboutPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'about' });
  const nav = await getTranslations({ locale, namespace: 'nav' });

  const promises = [
    { icon: ShieldCheck, title: t('promise1Title'), body: t('promise1Body') },
    { icon: RefreshCw, title: t('promise2Title'), body: t('promise2Body') },
    { icon: Wrench, title: t('promise3Title'), body: t('promise3Body') },
  ];
  const facts = [
    { icon: Users, title: t('audienceTitle'), body: t('audienceBody') },
    { icon: Database, title: t('sourceTitle'), body: t('sourceBody') },
    { icon: FlaskConical, title: t('methodologyTitle'), body: t('methodologyBody') },
  ];

  return (
    <div className="container max-w-4xl py-10">
      <JsonLd
        data={[
          organizationLd('AggreAPI'),
          breadcrumbLd([{ name: nav('about'), path: `/${locale}/about` }]),
        ]}
      />

      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('h1')}</h1>
      </header>

      {/* 创办人区块(ShipFast 风格,放上半部) */}
      <section className="mb-12 grid gap-6 sm:grid-cols-[auto_1fr] sm:items-start">
        <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/40 text-center text-xs text-muted-foreground">
          {t('photoPlaceholder')}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">{t('founderKicker')}</p>
          <p className="mt-1 text-lg font-semibold">{t('founderName')}</p>
          <p className="text-sm text-muted-foreground">{t('founderRole')}</p>
          <p className="mt-4 leading-relaxed text-muted-foreground">{t('founderStory')}</p>
          {CONTACT.twitter && (
            <a
              href={twitterUrl(CONTACT.twitter)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              {t('twitterCta')}
              <ArrowRight className="h-4 w-4" />
            </a>
          )}
        </div>
      </section>

      {/* 我们的承诺(trust builder) */}
      <section className="mb-12">
        <h2 className="mb-5 text-xl font-bold tracking-tight">{t('promisesTitle')}</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {promises.map((p) => (
            <Card key={p.title}>
              <CardContent className="p-5">
                <p.icon className="h-5 w-5 text-primary" />
                <h3 className="mt-3 font-semibold">{p.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{p.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* 服务对象 / 资料来源 / 方法论 */}
      <section className="mb-12 space-y-6">
        {facts.map((f) => (
          <div key={f.title} className="flex gap-4">
            <f.icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div>
              <h3 className="font-semibold">{f.title}</h3>
              <p className="mt-1 leading-relaxed text-muted-foreground">{f.body}</p>
            </div>
          </div>
        ))}
      </section>

      <Link
        href="/contact"
        className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        {t('contactCta')}
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
