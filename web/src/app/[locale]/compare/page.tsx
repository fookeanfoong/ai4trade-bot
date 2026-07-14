import type { Metadata } from 'next';
import { Suspense } from 'react';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { providers } from '@/lib/data/providers';
import { models } from '@/lib/data/models';
import { uniqueModelNames } from '@/lib/selectors';
import { CompareBuilder } from '@/components/compare/compare-builder';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'compare' });
  return { title: t('title'), description: t('subtitle'), alternates: { canonical: `/${locale}/compare` } };
}

// 价格映射:provider_id -> modelName -> { 最低输出价, 折扣 }
function buildPriceMap() {
  const map: Record<string, Record<string, { price: number; discount: number }>> = {};
  for (const m of models) {
    const cur = map[m.provider_id]?.[m.model_name];
    if (!cur || m.output_price_per_1m < cur.price) {
      map[m.provider_id] = map[m.provider_id] || {};
      map[m.provider_id][m.model_name] = { price: m.output_price_per_1m, discount: m.discount_percent };
    }
  }
  return map;
}

export default async function ComparePage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'compare' });

  return (
    <div className="container py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('subtitle')}</p>
      </header>
      <Suspense fallback={null}>
        <CompareBuilder providers={providers} priceMap={buildPriceMap()} modelNames={uniqueModelNames()} />
      </Suspense>
    </div>
  );
}
