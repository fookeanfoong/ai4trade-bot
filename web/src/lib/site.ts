import { routing, htmlLang } from '@/i18n/routing';

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aggreapi.com';

export function abs(path: string): string {
  return `${SITE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
}

// 生成某页面在各语言下的 hreflang alternates(中文用 zh-CN,不用 zh-Hans;含 x-default)。
// path 不含 locale 前缀,例如 "/providers/openrouter" 或 ""(首页)。
export function hreflangAlternates(path: string): Record<string, string> {
  const languages: Record<string, string> = {};
  for (const loc of routing.locales) {
    languages[htmlLang[loc] || loc] = `/${loc}${path}`;
  }
  languages['x-default'] = `/en${path}`;
  return languages;
}
