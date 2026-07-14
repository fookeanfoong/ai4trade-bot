import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { AuthForm } from '@/components/auth/auth-form';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'auth' });
  // 登录页不需要被搜索引擎收录
  return { title: t('loginTitle'), robots: { index: false }, alternates: { canonical: `/${locale}/auth` } };
}

export default async function AuthPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  return (
    <div className="container py-16">
      <AuthForm />
    </div>
  );
}
