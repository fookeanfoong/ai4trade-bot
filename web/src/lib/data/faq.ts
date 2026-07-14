import type { FaqItem } from '@/components/home/faq';

// FAQ 内容(用于首页与未来 FAQPage 结构化数据)。
// 一期提供中/英文;其余语言回退到英文,繁中回退到简中。
const zh: FaqItem[] = [
  {
    q: '什么是 AI API 中转站?',
    a: '中转站是第三方服务,帮你代理访问 OpenAI、Anthropic、Google 等官方 API,通常支持人民币/支付宝付款、国内直连,并按用量收费。本站只做比价与信息聚合,不直接销售 API。',
  },
  {
    q: '你们的价格准确吗?',
    a: '价格来自各中转站公开信息并定期更新,但可能存在滞后。下单前请以对方官网实时价格为准。一期数据为演示用途。',
  },
  {
    q: '通过你们的链接购买会更贵吗?',
    a: '不会。我们的联盟返佣由中转站支付,不会增加你的价格,也不影响客观排序。标注「Sponsored」的为付费推广位。',
  },
  {
    q: '国内不用梯子能访问这些中转站吗?',
    a: '多数收录的中转站提供国内直连线路,并支持支付宝/微信。具体可访问性请以各家实际线路为准,我们在详情页标注了覆盖地区。',
  },
  {
    q: '交易出问题找谁?',
    a: '本平台仅提供信息聚合与比价,不参与交易。订单、付款、发票与售后均由对应中转站负责,纠纷需与对方处理。详见免责声明。',
  },
];

const en: FaqItem[] = [
  {
    q: 'What is an AI API reseller?',
    a: 'A reseller is a third-party service that proxies access to official APIs from OpenAI, Anthropic, Google and others — often with local payment options and pay-as-you-go pricing. We only compare and aggregate information; we do not sell API access.',
  },
  {
    q: 'Is your pricing accurate?',
    a: 'Prices are collected from public sources and updated regularly, but may lag. Always confirm the live price on the provider site before buying. Phase-1 data is for demonstration.',
  },
  {
    q: 'Does buying via your links cost more?',
    a: 'No. Affiliate commissions are paid by the reseller and never increase your price or affect our objective rankings. Positions marked "Sponsored" are paid placements.',
  },
  {
    q: 'Can I reach these resellers from mainland China without a VPN?',
    a: 'Most listed resellers offer direct mainland routes and Alipay/WeChat payments. Actual reachability depends on each provider; we label supported regions on the detail page.',
  },
  {
    q: 'Who do I contact if a transaction goes wrong?',
    a: 'We only aggregate and compare. Orders, payments, invoices and support are handled by the reseller. Disputes must be resolved with them — see our disclaimer.',
  },
];

export function getFaq(locale: string): FaqItem[] {
  if (locale === 'zh' || locale === 'zh-TW') return zh;
  return en;
}
