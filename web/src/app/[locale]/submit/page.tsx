import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { SubmitForm } from '@/components/submit/submit-form';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'submit' });
  return { title: t('title'), description: t('subtitle'), alternates: { canonical: `/${locale}/submit` } };
}

export default async function SubmitPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'submit' });
  return (
    <div className="container py-10">
      <header className="mb-8 text-center">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mx-auto mt-2 max-w-xl text-muted-foreground">{t('subtitle')}</p>
      </header>
      <SubmitForm />
    </div>
  );
}
