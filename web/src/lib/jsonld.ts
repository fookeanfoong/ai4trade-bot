import type { Provider, Model, Review } from '@/lib/types';
import { SITE_URL, abs } from '@/lib/site';

// 结构化数据(JSON-LD)构造器:Product / Review / AggregateRating /
// FAQPage / BreadcrumbList / ItemList / WebSite / Organization。

export function breadcrumbLd(items: { name: string; path: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: abs(it.path),
    })),
  };
}

export function faqPageLd(items: { q: string; a: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((it) => ({
      '@type': 'Question',
      name: it.q,
      acceptedAnswer: { '@type': 'Answer', text: it.a },
    })),
  };
}

// 中转站作为 Product:offers 用各模型折后价,aggregateRating + review 用站内评价。
export function providerProductLd(
  provider: Provider,
  models: Model[],
  reviews: Review[],
  rating: number,
  locale: string,
  path: string
) {
  const ld: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: provider.name,
    url: abs(path),
    image: abs(provider.logo),
    description: provider.description?.[locale] || provider.description?.en || provider.name,
    brand: { '@type': 'Brand', name: provider.name },
  };

  if (models.length > 0) {
    const prices = models.map((m) => m.output_price_per_1m);
    ld.offers = {
      '@type': 'AggregateOffer',
      priceCurrency: 'USD',
      lowPrice: Math.min(...prices).toFixed(2),
      highPrice: Math.max(...prices).toFixed(2),
      offerCount: models.length,
      availability: 'https://schema.org/InStock',
    };
  }

  if (reviews.length > 0) {
    ld.aggregateRating = {
      '@type': 'AggregateRating',
      ratingValue: rating.toFixed(1),
      reviewCount: reviews.length,
      bestRating: '5',
      worstRating: '1',
    };
    ld.review = reviews.slice(0, 5).map((r) => ({
      '@type': 'Review',
      reviewRating: { '@type': 'Rating', ratingValue: String(r.rating), bestRating: '5' },
      author: { '@type': 'Person', name: r.author },
      datePublished: r.created_at.slice(0, 10),
      reviewBody: r.content,
    }));
  }

  return ld;
}

export function itemListLd(name: string, items: { name: string; path: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      url: abs(it.path),
    })),
  };
}

export function webSiteLd(locale: string, siteName: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: siteName,
    url: SITE_URL,
    inLanguage: locale === 'zh' ? 'zh-CN' : locale,
    potentialAction: {
      '@type': 'SearchAction',
      target: { '@type': 'EntryPoint', urlTemplate: `${SITE_URL}/${locale}/providers?q={query}` },
      'query-input': 'required name=query',
    },
  };
}

export function organizationLd(siteName: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: siteName,
    url: SITE_URL,
    logo: abs('/og-default.svg'),
  };
}
