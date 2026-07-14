import { providers } from '@/lib/data/providers';
import type { Provider } from '@/lib/types';
import { cheapestGpt4o, providerModelPrice } from '@/lib/selectors';

// SEO 榜单:每个榜单一个独立 URL(/rankings/[slug])。
// compute() 返回排好序的 { provider, value, display },供榜单页与首页引用。

export interface RankingRow {
  provider: Provider;
  value: number;
  display: string;
}

export interface Ranking {
  slug: string;
  compute: () => RankingRow[];
  // 标题/描述/方法多语言(一期 zh/en;其余回退)
  title: Record<'zh' | 'en', string>;
  description: Record<'zh' | 'en', string>;
  methodology: Record<'zh' | 'en', string>;
}

function byModelCheapest(modelName: string): RankingRow[] {
  return providers
    .map((p) => {
      const m = providerModelPrice(p.id, modelName);
      return m ? { provider: p, value: m.output_price_per_1m, display: `$${m.output_price_per_1m.toFixed(2)} /1M · -${m.discount_percent}%` } : null;
    })
    .filter((x): x is RankingRow => x !== null)
    .sort((a, b) => a.value - b.value);
}

export const rankings: Ranking[] = [
  {
    slug: 'cheapest-gpt-4o',
    compute: () =>
      providers
        .map((p) => {
          const m = cheapestGpt4o(p.id);
          return m ? { provider: p, value: m.output_price_per_1m, display: `$${m.output_price_per_1m.toFixed(2)} /1M · -${m.discount_percent}%` } : null;
        })
        .filter((x): x is RankingRow => x !== null)
        .sort((a, b) => a.value - b.value),
    title: { zh: '2026 GPT-4o API 价格排行榜', en: '2026 GPT-4o API Price Ranking' },
    description: {
      zh: '收录各中转站 GPT-4o 的输出折后价,从低到高排序,帮你一眼找到最便宜的 GPT-4o API 渠道。',
      en: 'GPT-4o output prices across resellers, cheapest first — find the lowest-cost GPT-4o API in one glance.',
    },
    methodology: {
      zh: '按各中转站 GPT-4o 输出价(USD / 1M tokens)升序排列,价格越低排名越前。',
      en: 'Sorted ascending by each reseller’s GPT-4o output price (USD / 1M tokens).',
    },
  },
  {
    slug: 'cheapest-claude-sonnet',
    compute: () => byModelCheapest('Claude Sonnet 4.5'),
    title: { zh: 'Claude Sonnet 4.5 最便宜中转站排行', en: 'Cheapest Claude Sonnet 4.5 Resellers' },
    description: {
      zh: '对比各中转站 Claude Sonnet 4.5 的输出折后价,找支付宝可付、价格最低的 Claude API 渠道。',
      en: 'Compare Claude Sonnet 4.5 output prices to find the cheapest Claude API reseller.',
    },
    methodology: {
      zh: '按 Claude Sonnet 4.5 输出价(USD / 1M tokens)升序排列。',
      en: 'Sorted ascending by Claude Sonnet 4.5 output price.',
    },
  },
  {
    slug: 'china-friendly',
    compute: () =>
      providers
        .filter((p) => p.regions.includes('CN') && (p.payment_methods.includes('alipay') || p.payment_methods.includes('wechat')))
        .map((p) => ({ provider: p, value: p.trust_score, display: `信任分 ${p.trust_score} · ${p.uptime_30d}%` }))
        .sort((a, b) => b.value - a.value),
    title: { zh: '国内直连友好中转站排行(支付宝/微信)', en: 'Best China-Friendly Resellers (Alipay/WeChat)' },
    description: {
      zh: '筛选覆盖中国大陆且支持支付宝或微信付款的中转站,按信任分排序,国内开发者首选。',
      en: 'Resellers covering mainland China with Alipay/WeChat, ranked by trust score.',
    },
    methodology: {
      zh: '仅收录覆盖中国大陆且支持支付宝或微信的中转站,按信任分降序排列。',
      en: 'Only resellers covering mainland China with Alipay/WeChat, sorted by trust score descending.',
    },
  },
  {
    slug: 'most-reliable',
    compute: () =>
      [...providers]
        .map((p) => ({ provider: p, value: p.uptime_30d, display: `${p.uptime_30d}% · ${p.avg_latency_ms}ms` }))
        .sort((a, b) => b.value - a.value),
    title: { zh: '最稳定 AI API 中转站排行(30天在线率)', en: 'Most Reliable Resellers (30-day Uptime)' },
    description: {
      zh: '按近 30 天在线率排序,找最稳定、最少宕机的 AI API 中转站,适合生产环境。',
      en: 'Ranked by 30-day uptime — the most stable resellers for production use.',
    },
    methodology: {
      zh: '按近 30 天在线率(uptime_30d)降序排列。',
      en: 'Sorted descending by 30-day uptime.',
    },
  },
  {
    slug: 'fastest',
    compute: () =>
      [...providers]
        .map((p) => ({ provider: p, value: p.avg_latency_ms, display: `${p.avg_latency_ms}ms · ${p.uptime_30d}%` }))
        .sort((a, b) => a.value - b.value),
    title: { zh: '最快 AI API 中转站排行(平均延迟)', en: 'Fastest Resellers (Average Latency)' },
    description: {
      zh: '按平均响应延迟从低到高排序,找响应最快的 AI API 中转站。',
      en: 'Ranked by average latency, lowest first — the fastest-responding resellers.',
    },
    methodology: {
      zh: '按平均延迟(avg_latency_ms)升序排列,数值越低越靠前。',
      en: 'Sorted ascending by average latency.',
    },
  },
];

export function getRanking(slug: string): Ranking | undefined {
  return rankings.find((r) => r.slug === slug);
}

export function rankingText<K extends 'title' | 'description' | 'methodology'>(
  r: Ranking,
  key: K,
  locale: string
): string {
  const l = locale === 'zh' || locale === 'zh-TW' ? 'zh' : 'en';
  return r[key][l];
}
