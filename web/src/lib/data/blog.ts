// 博客文章(MDX,SEO 重点)。一期 5 篇示例,中文 3 篇 + 英文 2 篇。
// content 为 MDX 字符串,由 next-mdx-remote 渲染。related 关联中转站 slug。

export interface BlogPost {
  slug: string;
  locale: 'zh' | 'en';
  title: string;
  excerpt: string;
  date: string; // ISO
  tags: string[];
  minRead: number;
  related: string[]; // provider slugs
  content: string; // MDX
}

export const posts: BlogPost[] = [
  {
    slug: 'chatgpt-api-china-2026',
    locale: 'zh',
    title: 'ChatGPT API 国内怎么用?2026 年最新中转站盘点',
    excerpt:
      '国内直接访问 OpenAI 官方 API 有诸多不便。本文盘点 2026 年主流 ChatGPT / GPT-4o API 中转站,对比线路、付款方式与价格。',
    date: '2026-06-10',
    tags: ['ChatGPT', 'GPT-4o', '国内直连'],
    minRead: 6,
    related: ['aihubmix', 'api2d', 'openrouter'],
    content: `国内开发者想调用 ChatGPT / GPT-4o API,直接连官方常会遇到网络与支付两道门槛。中转站(API 网关)通过在海外部署节点并支持人民币付款,解决了这两个问题。

## 中转站是什么

中转站帮你代理转发请求到 OpenAI 官方,同时提供:

- **国内直连线路**:不用自己搭梯子
- **人民币付款**:支付宝 / 微信 / 银联充值
- **兼容官方 SDK**:多数只需替换 \`base_url\`

## 怎么挑

选中转站主要看四点:价格(折扣力度)、稳定性(在线率)、速度(延迟)、以及付款是否方便。可以直接用我们的[中转站总览](/zh/providers)按这些维度筛选排序。

## 2026 主流选择

多家中转站都支持 GPT-4o 且提供直连线路,价格通常比官方低 5%–25%。你可以在 [GPT-4o 价格排行榜](/zh/rankings/cheapest-gpt-4o)一眼看到最便宜的渠道。

> 提示:下单前请务必核对对方官网的实时价格与线路说明。本平台仅做信息聚合与比价,不参与交易。

想快速上手,建议先在总览页勾选 2–3 家做[并排对比](/zh/compare),再决定充值哪家。`,
  },
  {
    slug: 'claude-api-alipay-china',
    locale: 'zh',
    title: 'Claude API 国内直连,支付宝付款的中转站有哪些',
    excerpt:
      'Anthropic Claude 官方不支持国内支付。本文整理支持支付宝付款、可直连的 Claude(Sonnet 4.5 / Opus)API 中转站。',
    date: '2026-06-18',
    tags: ['Claude', 'Sonnet 4.5', '支付宝'],
    minRead: 5,
    related: ['aihubmix', 'ohmygpt', 'closeai'],
    content: `Claude 的代码与长文能力很强,但 Anthropic 官方在国内既难访问也难付款。好在多家中转站已支持 **Claude Sonnet 4.5 / Opus**,并接入支付宝、微信。

## 关注三点

1. **是否覆盖中国大陆线路**:详情页的「覆盖地区」会标注 CN
2. **是否支持支付宝/微信**:避免海外信用卡的麻烦
3. **Claude 折后价**:不同中转站折扣差异可达 15%+

## 找最便宜的 Claude

我们维护了一个 [Claude Sonnet 4.5 最便宜中转站排行](/zh/rankings/cheapest-claude-sonnet),按输出折后价升序排列,支持支付宝的会在详情页标注。

## 稳定性同样重要

生产环境别只看价格。[最稳定中转站排行](/zh/rankings/most-reliable)按 30 天在线率排序,适合对可用性敏感的团队。

> 本平台不销售 API,也不为任何卖家背书。请自行核实线路与售后政策。`,
  },
  {
    slug: 'openai-api-cheap-channels',
    locale: 'zh',
    title: 'OpenAI API 便宜购买渠道对比,附真实测速',
    excerpt:
      '同样是 GPT-4o,不同中转站价格与速度差很多。本文用统一口径对比价格与平均延迟,帮你省钱又不牺牲体验。',
    date: '2026-06-28',
    tags: ['OpenAI', '价格对比', '测速'],
    minRead: 7,
    related: ['deepbricks', 'aihubmix', 'openrouter'],
    content: `买 OpenAI API,便宜和快往往难两全。本文用统一口径把主流中转站的 **GPT-4o 折后价** 与 **平均延迟** 摆在一起。

## 价格维度

折扣力度是最直观的差异。预算敏感型可以直接看折扣最大的几家,详见 [GPT-4o 价格排行榜](/zh/rankings/cheapest-gpt-4o)。

## 速度维度

延迟直接影响交互体验。我们按平均延迟做了 [最快中转站排行](/zh/rankings/fastest)。一般来说:

- **低价档**:折扣大,延迟略高,适合批量任务
- **均衡档**:价格与速度折中,适合日常开发
- **稳定档**:延迟低、在线率高,适合生产

## 怎么权衡

没有绝对最优,只有最适合你的场景。建议在[总览页](/zh/providers)按「价格最低」和「延迟最低」分别排一次,取交集里评分高的那家。

> 测速数据为演示占位值,实际请以你所在网络环境为准。`,
  },
  {
    slug: 'openrouter-vs-aihubmix',
    locale: 'en',
    title: 'OpenRouter vs AiHubMix: Which Fits Asian Users Better?',
    excerpt:
      'Two popular AI API gateways compared on routing, payments, pricing and mainland-China access for developers across Asia.',
    date: '2026-07-02',
    tags: ['OpenRouter', 'AiHubMix', 'comparison'],
    minRead: 6,
    related: ['openrouter', 'aihubmix'],
    content: `Both **OpenRouter** and **AiHubMix** aggregate many models behind one API key, but they target slightly different users.

## OpenRouter

A global gateway with automatic routing and failover across hundreds of models. Payments are card / PayPal / USDT. Great if you're outside mainland China and want breadth and reliability.

## AiHubMix

Built with Chinese developers in mind: Alipay / WeChat payments and stable mainland routes, covering OpenAI, Claude and Gemini.

## Which one

- **Outside mainland China, want max model coverage** → OpenRouter
- **In mainland China, want Alipay + direct routes** → AiHubMix

Compare them side by side on our [compare page](/en/compare?ids=openrouter,aihubmix), or check the [China-friendly ranking](/en/rankings/china-friendly).

> We only aggregate and compare — verify live pricing and routes on each provider's site before buying.`,
  },
  {
    slug: 'gpt-4o-api-price-ranking-2026',
    locale: 'en',
    title: '2026 GPT-4o API Price Ranking',
    excerpt:
      'The cheapest GPT-4o API channels in 2026, ranked by discounted output price, with notes on payments and reliability.',
    date: '2026-07-08',
    tags: ['GPT-4o', 'pricing', 'ranking'],
    minRead: 4,
    related: ['deepbricks', 'aihubmix', 'api2d'],
    content: `GPT-4o remains a workhorse model in 2026. Reseller prices typically sit **5–25% below** the official rate.

## The ranking

Our live [GPT-4o price ranking](/en/rankings/cheapest-gpt-4o) sorts resellers by discounted output price (USD / 1M tokens), cheapest first.

## Don't buy on price alone

- Check **uptime** for production — see [most reliable](/en/rankings/most-reliable)
- Check **latency** for interactive apps — see [fastest](/en/rankings/fastest)
- Check **payment methods** if you need Alipay / WeChat

## Next step

Shortlist 2–4 resellers and [compare them side by side](/en/compare) before topping up.

> Prices shown are demonstration data; always confirm on the provider site.`,
  },
  {
    slug: 'deepseek-api-china-guide',
    locale: 'zh',
    title: 'DeepSeek API 中转站怎么选?V3 与 R1 价格对比',
    excerpt:
      'DeepSeek V3 与 R1 性价比极高,是国产模型首选。本文对比各中转站的 DeepSeek 报价与线路,教你挑最划算的一家。',
    date: '2026-07-05',
    tags: ['DeepSeek', 'V3', 'R1'],
    minRead: 5,
    related: ['deepbricks', 'aihubmix', 'laozhang-ai'],
    content: `DeepSeek V3 与 R1 以极低价格提供强推理与代码能力,是国内团队的高性价比之选。多数中转站都已接入。

## V3 还是 R1

- **DeepSeek V3**:通用对话与代码,价格最低,适合高频调用
- **DeepSeek R1**:强推理(带思维链),价格略高,适合复杂任务

## 怎么比价

各中转站的 DeepSeek 折扣差异不小。可以在 [模型价格榜](/zh/models) 直接看每个模型在各家的报价排序,一眼挑最便宜。

## 别忽略线路与付款

国内调用还要看是否直连、是否支持支付宝。详情页的「覆盖地区」和「付款方式」都有标注,或直接看 [国内直连友好排行](/zh/rankings/china-friendly)。

> 价格为演示数据,请以各家官网实时报价为准。`,
  },
  {
    slug: 'cut-llm-api-bill-2026',
    locale: 'en',
    title: '5 Ways to Cut Your LLM API Bill in 2026',
    excerpt:
      'Practical tactics to reduce AI API spend — from picking the right reseller discount to matching the model to the task.',
    date: '2026-07-11',
    tags: ['cost', 'optimization', 'pricing'],
    minRead: 5,
    related: ['deepbricks', 'openrouter', 'aihubmix'],
    content: `AI API costs add up fast. Five tactics that actually move the needle:

## 1. Use a reseller discount

Resellers routinely price **5–25% below** official rates. Start from the [GPT-4o price ranking](/en/rankings/cheapest-gpt-4o).

## 2. Match the model to the task

Don't run GPT-4o where GPT-4o mini or DeepSeek V3 would do. Compare per-model prices on the [models page](/en/models).

## 3. Cap output tokens

Output tokens are the expensive half. Set sensible \`max_tokens\`.

## 4. Cache and batch

Reuse results and batch low-priority jobs on cheaper, higher-latency providers — see [fastest vs. cheapest](/en/rankings/fastest).

## 5. Watch reliability, not just price

Retries from an unstable provider cost money too. Check the [most reliable ranking](/en/rankings/most-reliable).

> Shortlist and [compare providers side by side](/en/compare) before you commit.`,
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return posts.find((p) => p.slug === slug);
}

// 当前语言优先,其余文章附在后面(小站点内容互通,利于 SEO 内链)
export function postsForLocale(locale: string): BlogPost[] {
  const primary = locale === 'zh' || locale === 'zh-TW' ? 'zh' : 'en';
  return [...posts].sort((a, b) => {
    if (a.locale !== b.locale) return a.locale === primary ? -1 : 1;
    return a.date < b.date ? 1 : -1;
  });
}
