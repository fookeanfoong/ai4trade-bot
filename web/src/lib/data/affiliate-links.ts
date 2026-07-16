// 集中管理所有中转站的 affiliate / 推广链接 —— 联盟返佣的唯一改动入口。
//
// 未来只改这一个文件,全站所有「前往中转站」按钮的目标 URL 就会跟着变
// (providers.ts 按 slug 从这里读取,跳转埋点会再自动附加 UTM 参数)。
//
// ⚠️ 目前全部为占位(= 各家官网,没带你的推广代码,点了成交也拿不到返佣)。
// 注册各家自助推广后,把值换成带推广代码的链接即可,例如:
//   aihubmix: 'https://aihubmix.com/register?aff=你的邀请码',
//   openrouter: 'https://openrouter.ai/?ref=你的码',
// 换完这一处,全站生效。

export const affiliateLinks: Record<string, string> = {
  openrouter: 'https://openrouter.ai', // TODO: 换成真实推广链接
  aihubmix: 'https://aihubmix.com', // TODO: 换成真实推广链接
  closeai: 'https://www.closeai-asia.com', // TODO: 换成真实推广链接
  deepbricks: 'https://deepbricks.ai', // TODO: 换成真实推广链接
  api2d: 'https://api2d.com', // TODO: 换成真实推广链接
  ohmygpt: 'https://www.ohmygpt.com', // TODO: 换成真实推广链接
  'gptapi-us': 'https://gptapi.us', // TODO: 换成真实推广链接
  'laozhang-ai': 'https://laozhang.ai', // TODO: 换成真实推广链接
  aigcbest: 'https://api.aigcbest.top', // TODO: 换成真实推广链接
  poloai: 'https://poloai.top', // TODO: 换成真实推广链接
};

// 按 slug 取 affiliate 链接;未配置时返回 undefined(providers 会回退到官网)。
export function getAffiliateUrl(slug: string): string | undefined {
  return affiliateLinks[slug];
}
