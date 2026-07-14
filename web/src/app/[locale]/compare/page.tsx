import { setRequestLocale, getTranslations } from 'next-intl/server';
import { ComingSoon } from '@/components/coming-soon';

export default async function Page({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'nav' });
  return <ComingSoon title={t('compare')} phase="第 2 阶段 · Phase 2" />;
}
