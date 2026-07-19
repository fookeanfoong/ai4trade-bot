// ============================================================================
// AI4Trade Signals — PWA 配置
// 你只需要改这个文件里的东西（价格 / Stripe 支付链接 / 品牌名），其余不用动。
// ============================================================================

window.APP_CONFIG = {
  // —— 品牌 ——
  brand: 'AI4Trade Signals',
  tagline: '每个交易日前，机器人替你挑几只值得关注的票',

  // —— 定价（美元）——
  // 首次购买自动 95 折（-5%）。价格只用于「展示」；真正扣款金额由 Stripe 决定，
  // 所以下面的「首购链接」必须在 Stripe 后台建成打完折的链接（见 README）。
  pricing: {
    monthly: 20,
    yearly: 240,
    firstBuyDiscount: 0.05, // 首次购买 -5%
  },

  // —— 免费试用 ——
  // 用户第一次看信号的那个「交易日」可以全程免费；此后必须订阅才能看。
  trialTradingDays: 1,

  // —— Stripe 支付链接（Payment Links，无需自建后端）——
  // 在 Stripe 后台建 4 条 Payment Link，把成功回跳地址(Success URL)设为：
  //   https://你的域名/?paid=monthly    （月付）
  //   https://你的域名/?paid=yearly     （年付）
  // 首购折扣那两条，价格建成打完 5% 折的即可。建法见 pwa/README.md。
  paymentLinks: {
    monthly:      'REPLACE_WITH_STRIPE_MONTHLY_LINK',
    yearly:       'REPLACE_WITH_STRIPE_YEARLY_LINK',
    monthlyFirst: 'REPLACE_WITH_STRIPE_MONTHLY_5OFF_LINK',
    yearlyFirst:  'REPLACE_WITH_STRIPE_YEARLY_5OFF_LINK',
  },

  // —— 信号数据源 ——
  // 机器人每天开盘前把当日信号写进这个文件（build_feed.py 从 signals.json 生成）。
  feedUrl: './data/signals.json',

  // —— 风控展示参数（只影响「建议仓位」的算法，不是下单）——
  risk: {
    maxDeployPct: 1.0,   // 最多建议投入本金的比例（1.0 = 100%）
    perNameCapPct: 0.25, // 单只票最多占本金的比例
    maxNames: 4,         // 一天最多建议几只
  },
};
