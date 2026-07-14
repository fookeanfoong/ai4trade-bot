import { setRequestLocale, getTranslations } from 'next-intl/server';
import { ComingSoon } from '@/components/coming-soon';

export default async function Page({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'nav' });
  return <ComingSoon title={t('blog')} phase="第 3 阶段 · Phase 3" />;
}
