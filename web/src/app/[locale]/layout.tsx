import type { Metadata, Viewport } from 'next';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, getTranslations, setRequestLocale } from 'next-intl/server';
import { notFound } from 'next/navigation';
import { headers } from 'next/headers';
import { routing, htmlLang } from '@/i18n/routing';
import { inter } from '@/app/fonts';
import { ThemeProvider } from '@/components/theme-provider';
import { Header } from '@/components/layout/header';
import { Footer } from '@/components/layout/footer';
import { CookieConsent } from '@/components/cookie-consent';
import { Analytics } from '@/components/analytics';
import { cn } from '@/lib/utils';
import '@/app/globals.css';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aggreapi.com';

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#0b1220' },
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
  ],
};

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'meta' });

  return {
    metadataBase: new URL(SITE_URL),
    title: {
      default: t('homeTitle'),
      template: `%s · ${t('siteName')}`,
    },
    description: t('description'),
    applicationName: t('siteName'),
    alternates: {
      canonical: `/${locale}`,
      languages: {
        // hreflang:中文用 zh-CN(不用 zh-Hans);x-default 指向英文
        'zh-CN': '/zh',
        'zh-TW': '/zh-TW',
        en: '/en',
        ja: '/ja',
        de: '/de',
        'x-default': '/en',
      },
    },
    openGraph: {
      type: 'website',
      siteName: t('siteName'),
      title: t('homeTitle'),
      description: t('description'),
      locale: htmlLang[locale],
      // 微信卡片:300x300 方图 + 标题 + 描述
      images: [{ url: '/og-default.svg', width: 300, height: 300, alt: t('siteName') }],
    },
    twitter: {
      card: 'summary',
      title: t('homeTitle'),
      description: t('description'),
      images: ['/og-default.svg'],
    },
    other: {
      // 双搜索引擎站点验证预留位(上线时填入各平台给的值)
      'baidu-site-verification': process.env.NEXT_PUBLIC_BAIDU_VERIFY || 'reserved',
      '360-site-verification': process.env.NEXT_PUBLIC_360_VERIFY || 'reserved',
      'sogou_site_verification': process.env.NEXT_PUBLIC_SOGOU_VERIFY || 'reserved',
      // 微信分享卡片图(itemprop 让微信抓取更稳)
      'itemprop:image': '/og-default.svg',
      // 百度移动适配 / 转码优化
      'applicable-device': 'pc,mobile',
      'format-detection': 'telephone=no',
    },
  };
}

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  if (!routing.locales.includes(locale as any)) notFound();
  setRequestLocale(locale);

  const messages = await getMessages();

  // 微信内置浏览器检测:命中则加 is-wechat 类,用 CSS 禁用重特效(毛玻璃/动画)
  const ua = headers().get('user-agent') || '';
  const isWeChat = /MicroMessenger/i.test(ua);

  return (
    <html
      lang={htmlLang[locale] || locale}
      suppressHydrationWarning
      className={cn(inter.variable, isWeChat && 'is-wechat')}
    >
      <body className="min-h-screen font-sans antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
          <NextIntlClientProvider messages={messages}>
            <div className="flex min-h-screen flex-col">
              <Header />
              <main className="flex-1">{children}</main>
              <Footer />
            </div>
            <CookieConsent />
            <Analytics />
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
