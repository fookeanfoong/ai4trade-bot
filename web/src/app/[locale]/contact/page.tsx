import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Mail, Briefcase, Users } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { ContactForm } from '@/components/contact/contact-form';
import { hreflangAlternates, CONTACT, twitterUrl } from '@/lib/site';
import { JsonLd } from '@/components/json-ld';
import { breadcrumbLd } from '@/lib/jsonld';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'contact' });
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: { canonical: `/${locale}/contact`, languages: hreflangAlternates('/contact') },
    openGraph: { title: t('metaTitle'), description: t('metaDescription'), images: [{ url: '/og-default.svg', width: 300, height: 300 }] },
  };
}

export default async function ContactPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'contact' });
  const nav = await getTranslations({ locale, namespace: 'nav' });

  const hasSocial = Boolean(CONTACT.twitter || CONTACT.discord || CONTACT.wechat);

  return (
    <div className="container max-w-3xl py-10">
      <JsonLd data={breadcrumbLd([{ name: nav('contact'), path: `/${locale}/contact` }])} />

      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('h1')}</h1>
        <p className="mt-2 text-muted-foreground">{t('intro')}</p>
      </header>

      <div className="mb-8 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardContent className="p-5">
            <Mail className="h-5 w-5 text-primary" />
            <h2 className="mt-3 font-semibold">{t('emailTitle')}</h2>
            <p className="text-sm text-muted-foreground">{t('emailDesc')}</p>
            <a href={`mailto:${CONTACT.email}`} className="mt-2 inline-block text-sm font-medium text-primary hover:underline">
              {CONTACT.email}
            </a>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <Briefcase className="h-5 w-5 text-primary" />
            <h2 className="mt-3 font-semibold">{t('businessTitle')}</h2>
            <p className="text-sm text-muted-foreground">{t('businessDesc')}</p>
            <a href={`mailto:${CONTACT.business}`} className="mt-2 inline-block text-sm font-medium text-primary hover:underline">
              {CONTACT.business}
            </a>
          </CardContent>
        </Card>
      </div>

      {/* 社群:填了才显示,否则显示"即将开放" */}
      <Card className="mb-8">
        <CardContent className="p-5">
          <Users className="h-5 w-5 text-primary" />
          <h2 className="mt-3 font-semibold">{t('socialTitle')}</h2>
          <p className="text-sm text-muted-foreground">{t('socialDesc')}</p>
          {hasSocial ? (
            <div className="mt-3 flex flex-wrap gap-3 text-sm font-medium text-primary">
              {CONTACT.twitter && (
                <a href={twitterUrl(CONTACT.twitter)} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  X / Twitter
                </a>
              )}
              {CONTACT.discord && (
                <a href={CONTACT.discord} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  Discord
                </a>
              )}
              {CONTACT.wechat && (
                <a href={CONTACT.wechat} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  WeChat
                </a>
              )}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">{t('socialEmpty')}</p>
          )}
        </CardContent>
      </Card>

      <section>
        <h2 className="mb-4 text-xl font-bold tracking-tight">{t('formTitle')}</h2>
        <ContactForm />
      </section>
    </div>
  );
}
