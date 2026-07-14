import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { DashboardClient } from '@/components/dashboard/dashboard-client';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'dashboard' });
  return { title: t('title'), robots: { index: false }, alternates: { canonical: `/${locale}/dashboard` } };
}

export default async function DashboardPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  return (
    <div className="container py-8">
      <DashboardClient />
    </div>
  );
}
