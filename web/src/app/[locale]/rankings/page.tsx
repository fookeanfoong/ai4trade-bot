import type { Metadata } from 'next';
import { hreflangAlternates } from '@/lib/site';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { Trophy, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { rankings, rankingText } from '@/lib/data/rankings';
import { cn } from '@/lib/utils';

const MEDAL = ['text-gold', 'text-silver', 'text-bronze'];

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'rankings' });
  return { title: t('title'), description: t('subtitle'), alternates: { canonical: `/${locale}/rankings`, languages: hreflangAlternates('/rankings') } };
}

export default async function RankingsPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'rankings' });

  return (
    <div className="container py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('subtitle')}</p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {rankings.map((r) => {
          const top = r.compute().slice(0, 3);
          return (
            <Card key={r.slug} className="transition-colors hover:border-primary/50">
              <CardContent className="p-5">
                <Link href={`/rankings/${r.slug}`} className="group flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold group-hover:text-primary">{rankingText(r, 'title', locale)}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{rankingText(r, 'description', locale)}</p>
                  </div>
                  <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-muted-foreground group-hover:text-primary" />
                </Link>
                <ol className="mt-4 space-y-1.5">
                  {top.map((row, i) => (
                    <li key={row.provider.id} className="flex items-center gap-2 text-sm">
                      <Trophy className={cn('h-4 w-4', MEDAL[i])} />
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={row.provider.logo} alt="" width={20} height={20} className="h-5 w-5 rounded" />
                      <span className="font-medium">{row.provider.name}</span>
                      <span className="ml-auto text-xs text-muted-foreground">{row.display}</span>
                    </li>
                  ))}
                </ol>
                <Link href={`/rankings/${r.slug}`} className="mt-3 inline-block text-sm text-primary hover:underline">
                  {t('viewRanking')} →
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
