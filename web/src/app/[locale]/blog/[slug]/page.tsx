import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { MDXRemote } from 'next-mdx-remote/rsc';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/routing';
import { CalendarDays, Clock } from 'lucide-react';
import { posts, getPost } from '@/lib/data/blog';
import { getProvider } from '@/lib/data/providers';
import { routing } from '@/i18n/routing';
import { ProviderCard } from '@/components/providers/provider-card';
import { NewsletterCta } from '@/components/newsletter/newsletter-cta';
import { AdSlot } from '@/components/ads/ad-slot';
import { Badge } from '@/components/ui/badge';
import { JsonLd } from '@/components/json-ld';
import { breadcrumbLd } from '@/lib/jsonld';
import { hreflangAlternates } from '@/lib/site';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aicompareapi.com';

export function generateStaticParams() {
  return routing.locales.flatMap((locale) => posts.map((p) => ({ locale, slug: p.slug })));
}

export async function generateMetadata({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}): Promise<Metadata> {
  const post = getPost(slug);
  if (!post) return {};
  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: `/${locale}/blog/${slug}`, languages: hreflangAlternates(`/blog/${slug}`) },
    openGraph: {
      type: 'article',
      title: post.title,
      description: post.excerpt,
      publishedTime: post.date,
      tags: post.tags,
      images: [{ url: '/og-default.svg', width: 300, height: 300 }],
    },
  };
}

export default async function BlogPostPage({
  params: { locale, slug },
}: {
  params: { locale: string; slug: string };
}) {
  setRequestLocale(locale);
  const post = getPost(slug);
  if (!post) notFound();

  const t = await getTranslations({ locale, namespace: 'blog' });
  const related = post.related.map((s) => getProvider(s)).filter((p) => !!p);

  // AdSense —— 仅部落格,且仅在配置了 env 时启用(否则外观零变化)。
  const adsEnabled = !!process.env.NEXT_PUBLIC_ADSENSE_CLIENT;
  const inArticleSlot = process.env.NEXT_PUBLIC_ADSENSE_SLOT_INARTICLE;
  const sidebarSlot = process.env.NEXT_PUBLIC_ADSENSE_SLOT_SIDEBAR;
  const blocks = post.content.split('\n\n');
  const splitAd = adsEnabled && !!inArticleSlot && blocks.length > 4; // 文章第 3 段后插入
  const head = splitAd ? blocks.slice(0, 3).join('\n\n') : post.content;
  const tail = splitAd ? blocks.slice(3).join('\n\n') : '';

  // Article + BreadcrumbList 结构化数据(SEO)
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: post.title,
    description: post.excerpt,
    datePublished: post.date,
    inLanguage: post.locale === 'zh' ? 'zh-CN' : 'en',
    keywords: post.tags.join(', '),
    mainEntityOfPage: `${SITE_URL}/${locale}/blog/${slug}`,
  };

  const main = (
    <>
      <JsonLd
        data={[
          jsonLd,
          breadcrumbLd([
            { name: t('backToBlog'), path: `/${locale}/blog` },
            { name: post.title, path: `/${locale}/blog/${slug}` },
          ]),
        ]}
      />

      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/blog" className="hover:text-foreground">
          {t('backToBlog')}
        </Link>
        {' / '}
        <span className="text-foreground">{post.title}</span>
      </nav>

      <article>
        <header className="mb-6">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {post.tags.map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </div>
          <h1 className="text-3xl font-bold leading-tight tracking-tight">{post.title}</h1>
          <div className="mt-3 flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <CalendarDays className="h-4 w-4" />
              {t('publishedOn')} {post.date}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              {post.minRead} {t('minRead')}
            </span>
          </div>
        </header>

        <div className="prose prose-neutral max-w-none dark:prose-invert prose-a:text-primary prose-headings:scroll-mt-20">
          <MDXRemote source={head} />
        </div>

        {/* 文章内广告位:第 3 段之后(仅配置 AdSense 后出现) */}
        {splitAd && <AdSlot slot={inArticleSlot} format="fluid" layout="in-article" className="my-8" />}
        {splitAd && tail && (
          <div className="prose prose-neutral max-w-none dark:prose-invert prose-a:text-primary prose-headings:scroll-mt-20">
            <MDXRemote source={tail} />
          </div>
        )}
      </article>

      <NewsletterCta source={`blog/${slug}`} />

      {related.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 text-xl font-semibold">{t('relatedTitle')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {related.map((p) => (
              <ProviderCard key={p!.id} provider={p!} sourcePage={`/blog/${slug}`} />
            ))}
          </div>
          <Link href="/providers" className="mt-4 inline-block text-sm text-primary hover:underline">
            {t('browseProviders')}
          </Link>
        </section>
      )}
    </>
  );

  // 未配置 AdSense:保持原单栏阅读版式,零变化。
  if (!adsEnabled) {
    return <div className="container max-w-3xl py-8">{main}</div>;
  }

  // 配置后:主栏 + 侧栏广告位(仅大屏,阅读区仍限宽保证可读性)。
  return (
    <div className="container py-8">
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 max-w-3xl">{main}</div>
        {sidebarSlot && (
          <aside className="hidden lg:block">
            <div className="sticky top-20">
              <AdSlot slot={sidebarSlot} format="auto" />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
