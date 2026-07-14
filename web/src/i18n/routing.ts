import { defineRouting } from 'next-intl/routing';
import { createNavigation } from 'next-intl/navigation';

// 语言:简中(默认)/ 繁中 / 英 / 日 / 德
// 中文 URL 用 /zh 前缀(localePrefix: 'always'),不用 ?lang= 参数。
export const routing = defineRouting({
  locales: ['zh', 'zh-TW', 'en', 'ja', 'de'],
  defaultLocale: 'zh',
  localePrefix: 'always',
});

export type Locale = (typeof routing.locales)[number];

// 每个 locale 对应的 HTML lang(中文用 zh-CN,不用 zh-Hans)
export const htmlLang: Record<string, string> = {
  zh: 'zh-CN',
  'zh-TW': 'zh-TW',
  en: 'en',
  ja: 'ja',
  de: 'de',
};

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
