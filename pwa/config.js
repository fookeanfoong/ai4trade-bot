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

  // —— 反馈 / 讨论区 ——
  feedback: {
    // 收集用户反馈的方式（二选一，优先用 endpoint）：
    //   endpoint 为空时 -> 点「提交」会打开邮件草稿发到下面的 email；
    //   endpoint 填了接口地址 -> POST JSON {message, contact, ts} 到该接口。
    email: 'REPLACE_WITH_YOUR_EMAIL@example.com',
    endpoint: '',
  },
  // 路线图 / 更新日志数据（让用户看到「反馈 → 更新」）。你手动维护这个文件。
  updatesUrl: './data/updates.json',

  // —— 功能开关 ——
  features: {
    // 「透明战绩」页：展示机器人真实历史成绩(python3 pwa/build_track_record.py 生成)。
    // 默认关闭 —— 因为当前真实记录是净亏损。等成绩转正、或你想走「彻底透明」路线时,
    // 把它改成 true 即可显示。数据不会造假,页面永远显示真实数字。
    trackRecord: false,
  },
  trackRecordUrl: './data/track_record.json',
  // 可选：真正的「公开讨论区」（用户能看到彼此的留言）。免费、无需自建后端。
  // 用 giscus（基于 GitHub Discussions）。开启方法见 pwa/SETUP.md，填好下面对象即可：
  //   giscus: { repo:'user/repo', repoId:'...', category:'Announcements', categoryId:'...' }
  discussion: { giscus: null },

  // —— 风控展示参数（只影响「建议仓位」的算法，不是下单）——
  risk: {
    maxDeployPct: 1.0,   // 最多建议投入本金的比例（1.0 = 100%）
    perNameCapPct: 0.25, // 单只票最多占本金的比例
    maxNames: 4,         // 一天最多建议几只
  },
};
