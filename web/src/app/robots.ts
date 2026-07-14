import type { MetadataRoute } from 'next';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aggreapi.com';

// 明确 allow 国内主流搜索引擎爬虫,保障百度/360/搜狗/头条收录。
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: '*', allow: '/', disallow: ['/api/', '/dashboard'] },
      { userAgent: 'Baiduspider', allow: '/' },
      { userAgent: 'Sogou web spider', allow: '/' },
      { userAgent: 'Sogou inst spider', allow: '/' },
      { userAgent: '360Spider', allow: '/' },
      { userAgent: 'HaosouSpider', allow: '/' },
      { userAgent: 'Bytespider', allow: '/' },
      { userAgent: 'Googlebot', allow: '/' },
      { userAgent: 'Bingbot', allow: '/' },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
