// 法律文案。一期重点:免责声明 + 联盟返佣披露(合规强制);
// 服务条款/隐私/Cookie 为基础版,三期 /legal 完整化。

export type LegalDoc = 'terms' | 'privacy' | 'cookies' | 'disclaimer' | 'affiliate-disclosure';

interface Doc {
  title: string;
  body: string[]; // 段落
}

const zh: Record<LegalDoc, Doc> = {
  disclaimer: {
    title: '免责声明',
    body: [
      'AggreAPI(以下称「本站」)是一个 AI API 中转站信息聚合与比价平台。本站不直接销售任何 API、算力或账号,不代收款、不参与任何交易。',
      '本站展示的价格、折扣、延迟、在线率、评价等信息来自第三方公开渠道并定期更新,可能存在滞后或误差。所有数据仅供参考,不构成任何购买、投资或使用建议。请在下单前以对应中转站官网的实时信息为准。',
      '你与任何第三方中转站之间的订单、付款、发票、售后与纠纷,均由你与该第三方自行处理,本站不承担任何责任,也不对任何一方作出背书或担保。',
      '部分内容由 AI 辅助生成。请自行核实关键信息。若你发现价格造假、虚假宣传或跑路行为,欢迎通过详情页「举报」入口反馈。',
    ],
  },
  'affiliate-disclosure': {
    title: '联盟返佣披露',
    body: [
      '根据美国 FTC 及欧盟相关法规,我们在此明确披露:本站包含联盟推广(affiliate)链接。',
      '当你通过本站的「访问官网 / 前往购买」链接前往第三方中转站并完成注册或购买时,本站可能从对方获得一定比例的返佣。',
      '该返佣由第三方支付,不会增加你的任何费用,也不会影响我们对各中转站的客观排序与评分。',
      '标注「Sponsored」的位置为付费推广位,我们会明确标识以区别于自然排序结果。',
    ],
  },
  terms: {
    title: '服务条款',
    body: [
      '欢迎使用 AggreAPI。使用本站即表示你同意本条款。本站按「现状」提供信息聚合与比价服务,不保证信息的绝对准确、完整或实时。',
      '你同意不将本站用于任何违法用途,不对本站进行爬取、攻击或干扰。本站保留随时修改内容与条款的权利。',
      '本条款为一期基础版本,完整条款将于后续阶段发布。',
    ],
  },
  privacy: {
    title: '隐私政策',
    body: [
      '我们尊重并保护你的隐私,遵循数据最小化原则。本站仅收集提供服务与改进体验所必需的信息。',
      '跳转埋点仅记录中转站 ID、时间、来源页与脱敏后的访问信息(不存储完整 IP),用于核对联盟返佣。分析统计使用自托管方案(如 Plausible / Umami),不使用 Google Analytics 等被墙服务。',
      '根据 GDPR,你有权访问、导出或删除你的个人数据(相关功能将在用户中心提供)。完整隐私政策将于后续阶段发布。',
    ],
  },
  cookies: {
    title: 'Cookie 政策',
    body: [
      '本站使用 Cookie 以提供必要功能(如语言、主题偏好)并了解站点使用情况。你可以在 Cookie 弹窗中按类别(必要 / 分析 / 营销)选择是否同意。',
      '必要类 Cookie 始终开启;分析与营销类需你明确同意后才会启用。你可随时通过页面底部重新管理偏好。',
    ],
  },
};

const en: Record<LegalDoc, Doc> = {
  disclaimer: {
    title: 'Disclaimer',
    body: [
      'AggreAPI ("the Site") is an information-aggregation and price-comparison platform for AI API resellers. We do not sell any API, compute or accounts, do not collect payments, and do not take part in any transaction.',
      'Prices, discounts, latency, uptime and reviews are collected from public third-party sources and updated periodically; they may be delayed or inaccurate. All data is for reference only and does not constitute purchase, investment or usage advice. Always confirm on the provider site before buying.',
      'Any order, payment, invoice, support or dispute between you and a third-party reseller is handled solely between you and that third party. We accept no liability and endorse no party.',
      'Some content is AI-assisted. Please verify key details. If you spot fake pricing, false claims or a scam, report it via the "Report" entry on the detail page.',
    ],
  },
  'affiliate-disclosure': {
    title: 'Affiliate Disclosure',
    body: [
      'In accordance with the US FTC and EU regulations, we disclose that this site contains affiliate links.',
      'When you use our "Visit site / Buy now" links to reach a third-party reseller and sign up or purchase, we may earn a commission from them.',
      'This commission is paid by the third party, never increases your cost, and does not affect our objective rankings or scores.',
      'Positions marked "Sponsored" are paid placements and are always clearly labelled to distinguish them from organic results.',
    ],
  },
  terms: {
    title: 'Terms of Service',
    body: [
      'Welcome to AggreAPI. By using the site you agree to these terms. The site provides aggregation and comparison on an "as-is" basis without guaranteeing accuracy, completeness or timeliness.',
      'You agree not to use the site for unlawful purposes or to scrape, attack or disrupt it. We may modify content and terms at any time.',
      'This is a phase-1 baseline; full terms will follow.',
    ],
  },
  privacy: {
    title: 'Privacy Policy',
    body: [
      'We respect your privacy and follow data minimisation. We collect only what is necessary to provide and improve the service.',
      'Outbound tracking records only the provider ID, timestamp, source page and de-identified request info (no full IP) to reconcile affiliate commissions. Analytics use self-hosted tools (Plausible / Umami), never Google Analytics.',
      'Under GDPR you may access, export or delete your data (features provided in the dashboard). A full policy will follow.',
    ],
  },
  cookies: {
    title: 'Cookie Policy',
    body: [
      'We use cookies for essential functionality (language, theme) and to understand usage. You can consent by category (necessary / analytics / marketing) in the banner.',
      'Necessary cookies are always on; analytics and marketing require explicit consent. You can re-manage preferences at any time.',
    ],
  },
};

export function getLegalDoc(locale: string, doc: LegalDoc): Doc | undefined {
  const set = locale === 'zh' || locale === 'zh-TW' ? zh : en;
  return set[doc];
}

export const LEGAL_DOCS: LegalDoc[] = ['terms', 'privacy', 'cookies', 'disclaimer', 'affiliate-disclosure'];
