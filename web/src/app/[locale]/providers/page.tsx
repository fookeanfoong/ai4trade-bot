import type { Metadata } from 'next';
import { hreflangAlternates } from '@/lib/site';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { providers } from '@/lib/data/providers';
import { ProvidersExplorer } from '@/components/providers/providers-explorer';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'providers' });
  return {
    title: t('title'),
    alternates: { canonical: `/${locale}/providers`, languages: hreflangAlternates('/providers') },
  };
}

export default async function ProvidersPage({
  params: { locale },
}: {
  params: { locale: string };
}) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'providers' });

  return (
    <div className="container py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('subtitle', { count: providers.length })}</p>
      </header>
      <ProvidersExplorer providers={providers} />
    </div>
  );
}
