import type { Metadata } from 'next';
import { setRequestLocale } from 'next-intl/server';
import { Lock } from 'lucide-react';
import { aggregateClicks } from '@/lib/clicks';
import { ClicksDashboard } from '@/components/admin/clicks-dashboard';

export const dynamic = 'force-dynamic';

export function generateMetadata(): Metadata {
  return { title: '联盟点击后台', robots: { index: false, follow: false } };
}

export default function AdminClicksPage({
  params: { locale },
  searchParams,
}: {
  params: { locale: string };
  searchParams: { token?: string };
}) {
  setRequestLocale(locale);

  // 设置了 ADMIN_TOKEN 时需 ?token= 匹配;未设置(本地开发)直接开放。
  const required = process.env.ADMIN_TOKEN;
  if (required && searchParams.token !== required) {
    return (
      <div className="container flex max-w-md flex-col items-center py-24 text-center">
        <Lock className="h-8 w-8 text-muted-foreground" />
        <h1 className="mt-4 text-lg font-semibold">需要访问令牌</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          在链接后加 <code>?token=你的 ADMIN_TOKEN</code> 访问本页。
        </p>
      </div>
    );
  }

  const stats = aggregateClicks(new Date().toISOString());
  return (
    <div className="container max-w-4xl py-8">
      <ClicksDashboard stats={stats} />
    </div>
  );
}
