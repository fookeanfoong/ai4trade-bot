import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { setRequestLocale } from 'next-intl/server';
import { routing } from '@/i18n/routing';
import { getLegalDoc, LEGAL_DOCS, type LegalDoc } from '@/lib/data/legal';

export function generateStaticParams() {
  return routing.locales.flatMap((locale) =>
    LEGAL_DOCS.map((doc) => ({ locale, doc }))
  );
}

export async function generateMetadata({
  params: { locale, doc },
}: {
  params: { locale: string; doc: string };
}): Promise<Metadata> {
  const d = getLegalDoc(locale, doc as LegalDoc);
  if (!d) return {};
  return { title: d.title, alternates: { canonical: `/${locale}/legal/${doc}` } };
}

export default function LegalPage({
  params: { locale, doc },
}: {
  params: { locale: string; doc: string };
}) {
  setRequestLocale(locale);
  if (!LEGAL_DOCS.includes(doc as LegalDoc)) notFound();
  const d = getLegalDoc(locale, doc as LegalDoc);
  if (!d) notFound();

  return (
    <div className="container max-w-3xl py-12">
      <h1 className="text-3xl font-bold tracking-tight">{d.title}</h1>
      <div className="mt-6 space-y-4 leading-relaxed text-muted-foreground">
        {d.body.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      <p className="mt-10 text-xs text-muted-foreground">最后更新 / Last updated: 2026-07-14</p>
    </div>
  );
}
