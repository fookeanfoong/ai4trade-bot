import type { MetadataRoute } from 'next';
import { routing } from '@/i18n/routing';
import { providers } from '@/lib/data/providers';
import { rankings } from '@/lib/data/rankings';
import { posts } from '@/lib/data/blog';
import { LEGAL_DOCS } from '@/lib/data/legal';
import { modelSummaries } from '@/lib/selectors';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aicompareapi.com';
const LM = new Date('2026-07-14');

// 标准 sitemap.xml,兼容百度/Google 提交格式。每个 locale × 页面独立 URL。
// auth / dashboard 为 noindex,不收录。
export default function sitemap(): MetadataRoute.Sitemap {
  const staticPaths = ['', '/providers', '/compare', '/models', '/deals', '/rankings', '/blog', '/submit', '/about', '/contact', '/legal'];
  const entries: MetadataRoute.Sitemap = [];

  for (const locale of routing.locales) {
    for (const p of staticPaths) {
      entries.push({ url: `${SITE_URL}/${locale}${p}`, lastModified: LM, changeFrequency: 'daily', priority: p === '' ? 1 : 0.8 });
    }
    for (const prov of providers) {
      entries.push({ url: `${SITE_URL}/${locale}/providers/${prov.slug}`, lastModified: LM, changeFrequency: 'daily', priority: 0.7 });
    }
    for (const r of rankings) {
      entries.push({ url: `${SITE_URL}/${locale}/rankings/${r.slug}`, lastModified: LM, changeFrequency: 'daily', priority: 0.7 });
    }
    for (const m of modelSummaries()) {
      entries.push({ url: `${SITE_URL}/${locale}/models/${m.slug}`, lastModified: LM, changeFrequency: 'daily', priority: 0.7 });
    }
    for (const post of posts) {
      entries.push({ url: `${SITE_URL}/${locale}/blog/${post.slug}`, lastModified: new Date(post.date), changeFrequency: 'weekly', priority: 0.6 });
    }
    for (const doc of LEGAL_DOCS) {
      entries.push({ url: `${SITE_URL}/${locale}/legal/${doc}`, lastModified: LM, changeFrequency: 'monthly', priority: 0.3 });
    }
  }

  return entries;
}
