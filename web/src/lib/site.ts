import { routing, htmlLang } from '@/i18n/routing';

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://aicompareapi.com';

// 联系方式与社群 —— About / Contact / Footer 的唯一改动入口。
// ⚠️ 以下为占位,请替换成你的真实信息(email 先用你自己的域名当默认值)。
// 社群(twitter/discord/wechat)留空的项不会显示,填了才出现——避免误链到他人账号。
export const CONTACT = {
  email: 'hello@aicompareapi.com', // TODO: 换成你的真实联系 email
  business: 'business@aicompareapi.com', // TODO: 商务合作 email(可与上面相同)
  twitter: '', // TODO: 你的 X/Twitter handle(不含 @),例如 'aggreapi'
  discord: '', // TODO: Discord 邀请链接(预留)
  wechat: '', // TODO: 微信群说明或二维码页链接(预留)
};

export function twitterUrl(handle: string): string {
  return `https://x.com/${handle.replace(/^@/, '')}`;
}

// 深度研究报告(Deep-Dive Report)商品设置 —— 定价与结帐的唯一改动入口。
// ⚠️ 占位:上线前替换。checkoutUrl 建议用 Lemon Squeezy 托管结帐链接(对亚洲卖家友善,
// 只需贴一个链接、无需接后端);留空时页面按钮显示「即将开放」,不会假装能买。
export const REPORT = {
  priceOriginal: 99, // 原价(划掉)
  price: 49, // 早鸟价
  currency: 'US$',
  earlyBirdTotal: 100, // 早鸟名额
  earlyBirdLeft: 43, // TODO: 先写死,未来动态化
  checkoutUrl: 'https://aicompareapi1.lemonsqueezy.com/checkout/buy/4bf8a28e-f162-42a5-8ef8-5bcd1c6260b2', // Lemon Squeezy 托管结帐
};

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
