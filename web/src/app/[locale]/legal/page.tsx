import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { FileText, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { LEGAL_DOCS, getLegalDoc } from '@/lib/data/legal';

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'legalIndex' });
  return { title: t('title'), description: t('subtitle'), alternates: { canonical: `/${locale}/legal` } };
}

export default async function LegalIndexPage({ params: { locale } }: { params: { locale: string } }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'legalIndex' });

  return (
    <div className="container max-w-3xl py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">{t('subtitle')}</p>
      </header>

      <div className="grid gap-3">
        {LEGAL_DOCS.map((doc) => {
          const d = getLegalDoc(locale, doc);
          if (!d) return null;
          return (
            <Card key={doc} className="transition-colors hover:border-primary/50">
              <CardContent className="p-0">
                <Link href={`/legal/${doc}`} className="group flex items-center gap-3 p-4">
                  <FileText className="h-5 w-5 text-primary" />
                  <div className="flex-1">
                    <div className="font-medium group-hover:text-primary">{d.title}</div>
                    <div className="line-clamp-1 text-xs text-muted-foreground">{d.body[0]}</div>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary" />
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
