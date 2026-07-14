import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { Trophy, Info } from 'lucide-react';
import { rankings, getRanking, rankingText } from '@/lib/data/rankings';
import { routing } from '@/i18n/routing';
import { OutboundLink } from '@/components/outbound-link';
import { Badge } from '@/components/ui/badge';
import { regionLabel } from '@/lib/display';
import { cn } from '@/lib/utils';

const MEDAL = ['text-gold', 'text-silver', 'text-bronze'];

export function generateStaticParams() {
  return routing.locales.flatMap((locale) => rankings.map((r) => ({ locale, slug: r.slug })));
}

export async function generateMetadata({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}): Promise<Metadata> {
  const r = getRanking(slug);
  if (!r) return {};
  return {
    title: rankingText(r, 'title', locale),
    description: rankingText(r, 'description', locale),
    alternates: { canonical: `/${locale}/rankings/${slug}` },
    openGraph: {
      title: rankingText(r, 'title', locale),
      description: rankingText(r, 'description', locale),
      images: [{ url: '/og-default.svg', width: 300, height: 300 }],
    },
  };
}

export default async function RankingDetailPage({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}) {
  setRequestLocale(locale);
  const r = getRanking(slug);
  if (!r) notFound();

  const t = await getTranslations({ locale, namespace: 'rankings' });
  const rows = r.compute();

  return (
    <div className="container max-w-4xl py-8">
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/rankings" className="hover:text-foreground">{t('backToRankings')}</Link>
        {' / '}
        <span className="text-foreground">{rankingText(r, 'title', locale)}</span>
      </nav>

      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{rankingText(r, 'title', locale)}</h1>
        <p className="mt-2 text-muted-foreground">{rankingText(r, 'description', locale)}</p>
      </header>

      <div className="overflow-hidden rounded-xl border border-border">
        <table className="data-table w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">{t('rank')}</th>
              <th className="px-4 py-2.5 font-medium">Provider</th>
              <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('value')}</th>
              <th className="px-4 py-2.5 text-right font-medium">·</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.provider.id} className="border-t border-border">
                <td className="px-4 py-3">
                  {i < 3 ? (
                    <Trophy className={cn('h-5 w-5', MEDAL[i])} />
                  ) : (
                    <span className="text-muted-foreground">{i + 1}</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Link href={`/providers/${row.provider.slug}`} className="flex items-center gap-2 font-medium hover:text-primary">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={row.provider.logo} alt="" width={26} height={26} className="h-6 w-6 rounded" />
                    {row.provider.name}
                    {row.provider.sponsored && <Badge variant="sponsored">Sponsored</Badge>}
                  </Link>
                  <div className="mt-0.5 text-xs text-muted-foreground sm:hidden">{row.display}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {row.provider.regions.slice(0, 3).map((rg) => regionLabel[rg]).join(' · ')}
                  </div>
                </td>
                <td className="hidden px-4 py-3 font-semibold text-primary sm:table-cell">{row.display}</td>
                <td className="px-4 py-3 text-right">
                  <OutboundLink provider={row.provider} sourcePage={`/rankings/${slug}`} size="sm" variant="outline" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 flex items-start gap-2 rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <span className="font-medium text-foreground">{t('methodology')}:</span> {rankingText(r, 'methodology', locale)}
        </div>
      </div>
    </div>
  );
}
