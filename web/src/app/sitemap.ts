import type { MetadataRoute } from 'next';
import { routing } from '@/i18n/routing';
import { providers } from '@/lib/data/providers';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aggreapi.com';

// 标准 sitemap.xml,兼容百度/Google 提交格式。每个 locale × 页面独立 URL。
export default function sitemap(): MetadataRoute.Sitemap {
  const staticPaths = ['', '/providers'];
  const entries: MetadataRoute.Sitemap = [];

  for (const locale of routing.locales) {
    for (const p of staticPaths) {
      entries.push({
        url: `${SITE_URL}/${locale}${p}`,
        lastModified: new Date('2026-07-14'),
        changeFrequency: 'daily',
        priority: p === '' ? 1 : 0.8,
      });
    }
    for (const prov of providers) {
      entries.push({
        url: `${SITE_URL}/${locale}/providers/${prov.slug}`,
        lastModified: new Date('2026-07-14'),
        changeFrequency: 'daily',
        priority: 0.7,
      });
    }
  }

  return entries;
}
