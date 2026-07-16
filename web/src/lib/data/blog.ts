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
  {
    slug: 'openai-api-alternatives-2026',
    locale: 'en',
    title: 'Top 10 OpenAI API Alternatives in 2026 (Cheaper & Faster)',
    excerpt:
      'The best OpenAI API alternatives in 2026 — aggregators that resell GPT-4o cheaper, plus rival models like Claude and DeepSeek. Compared on price, speed and payment.',
    date: '2026-07-05',
    tags: ['OpenAI', 'alternatives', 'GPT-4o', 'aggregator'],
    minRead: 8,
    related: ['openrouter', 'aihubmix', 'deepbricks'],
    content: `If the official OpenAI API is too expensive, hard to pay for, or blocked in your region, you have more options in 2026 than ever. "Alternative" can mean two different things, and it's worth separating them:

- **Cheaper access to the same models** — API aggregators and proxy providers that resell GPT-4o, GPT-4o mini and others at a discount, often with local payment.
- **Rival models** — Claude, Gemini, DeepSeek and others that may be cheaper or better for your task.

This guide covers both, then ranks the ten aggregators most worth knowing.

## Why use an aggregator instead of OpenAI directly

An [AI API aggregator](/en/providers) proxies your request to the upstream provider while adding three things developers actually want:

- **Lower prices** — typically 5–25% below official, thanks to volume pricing.
- **Local payment** — Alipay, WeChat, UnionPay or USDT instead of a foreign card.
- **One key, many models** — call GPT-4o, Claude and Gemini through a single endpoint.

Most are drop-in: you change the base URL and keep the official SDK. For the trade-offs, read [AI API pricing explained](/en/blog/ai-api-pricing-explained).

## Rival models worth a look

Before you optimise the price of GPT-4o, ask whether you even need it:

- **DeepSeek V3 / R1** — remarkably cheap for strong reasoning; great for high-volume, cost-sensitive work.
- **Claude Sonnet 4.5** — often preferred for coding and long-context tasks.
- **Gemini 2.5 Flash** — very cheap with a huge context window for summarisation.

You can price all of these across providers on our [model comparison](/en/models) pages.

## The 10 aggregators worth knowing

Ranked roughly by breadth, reliability and value. Verify live pricing on each site before buying — we only aggregate and compare.

### 1. OpenRouter
A global gateway with automatic routing and failover across hundreds of models. Card / PayPal / USDT. The default pick outside mainland China.

### 2. AiHubMix
Built for Chinese developers: Alipay / WeChat, stable mainland routes, and broad coverage of OpenAI, Claude and Gemini.

### 3. API2D
A veteran with SDK-compatible "forward keys", solid docs and invoices — popular with teams.

### 4. OhMyGPT
Many payment options and global nodes, balancing mainland and overseas users.

### 5. DeepBricks
Aggressive pricing for budget-conscious solo developers — one of the cheapest for GPT-4o.

### 6. laozhang.ai
Low-cost mainland access with an active community and frequent new-user credits.

### 7. GPTAPI.us
US-region routes with transparent pricing, aimed at teams needing a stable overseas exit.

### 8. CloseAI
An early mainland reseller supporting RMB top-ups and invoices across OpenAI models.

### 9. AiGCBest
Aggregates many models plus image endpoints — handy if you build AIGC apps.

### 10. Poloai
An emerging provider with EU/Asia nodes and SEPA support for cross-border teams.

## How to choose

Don't pick from a list — pick from your constraints:

- **Cheapest GPT-4o today?** Check the [cheapest-GPT-4o ranking](/en/rankings/cheapest-gpt-4o).
- **In mainland China?** Filter for Alipay and direct routes; see [Claude API in China](/en/blog/claude-api-china-no-vpn).
- **Care about uptime?** A cheap-but-flaky provider costs you in retries — weigh the [most reliable ranking](/en/rankings/most-reliable).

Shortlist two or three and [compare them side by side](/en/compare). If you'd rather not vet fifteen providers yourself, our [Deep-Dive Report](/en/report) does the due diligence for you.

> We aggregate and compare only, and never take payment for a higher ranking. Always confirm live pricing and routes on each provider's own site.`,
  },
  {
    slug: 'openrouter-vs-aihubmix-vs-302ai',
    locale: 'en',
    title: 'OpenRouter vs AiHubMix vs 302.AI: Which AI API Aggregator Wins?',
    excerpt:
      'A hands-on comparison of three popular AI API aggregators — OpenRouter, AiHubMix and 302.AI — on models, routing, payment, pricing and China access.',
    date: '2026-07-08',
    tags: ['OpenRouter', 'AiHubMix', '302.AI', 'comparison'],
    minRead: 7,
    related: ['openrouter', 'aihubmix', 'api2d'],
    content: `"Which aggregator should I use?" is the wrong question until you say where you are and what you're building. Here's how three of the most talked-about options — OpenRouter, AiHubMix and 302.AI — actually differ.

## At a glance

- **OpenRouter** — the global default. Widest model catalogue, automatic routing and failover, card / PayPal / USDT.
- **AiHubMix** — the China-first choice. Alipay / WeChat, stable mainland routes, strong OpenAI + Claude + Gemini coverage.
- **302.AI** — a pay-as-you-go platform bundling many models plus apps and tools, popular with builders who want more than a raw API.

## Model coverage & routing

OpenRouter's edge is breadth: hundreds of models behind one key, with fallback if a provider degrades. That failover matters in production — if one upstream wobbles, your request still completes.

AiHubMix and 302.AI both cover the models most people actually use (GPT-4o, Claude Sonnet 4.5, Gemini, DeepSeek). If your app only needs the top handful, breadth is not a deciding factor.

## Payment — often the real decider

This is where mainland-China developers usually split off:

- **OpenRouter** expects a card, PayPal or USDT — awkward inside China.
- **AiHubMix** takes Alipay and WeChat, which is why many Chinese teams pick it. See [Claude API in China](/en/blog/claude-api-china-no-vpn).
- **302.AI** supports flexible top-ups aimed at both Chinese and international users.

## Pricing

All three discount below official rates, but the exact number moves weekly, so compare live rather than trusting a blog table. Price GPT-4o across every provider on the [cheapest-GPT-4o ranking](/en/rankings/cheapest-gpt-4o), and read [how to cut API costs](/en/blog/cut-openai-api-costs-aggregators) for tactics that beat any single provider choice.

## Reliability & support

For production, uptime beats a marginal price win — a few percent of failed requests wipes out the saving in retries. OpenRouter's failover helps here; for others, check the [most reliable ranking](/en/rankings/most-reliable) and whether they offer invoices and a real support channel.

## The verdict

- **Outside mainland China, want breadth + failover** → OpenRouter.
- **In mainland China, want Alipay + direct routes** → AiHubMix.
- **Want a bundled platform with extra tools** → 302.AI.

There's no universal winner — there's a winner for your region, payment method and reliability needs. [Compare them side by side](/en/compare) with your own numbers, or let our [Deep-Dive Report](/en/report) rank them on hidden fees and outage history.

> We compare independently and never sell ranking positions. Confirm live pricing on each provider's site before you commit.`,
  },
  {
    slug: 'cut-openai-api-costs-aggregators',
    locale: 'en',
    title: 'How to Cut Your OpenAI API Costs by 30% Using Aggregators',
    excerpt:
      'Practical tactics to cut your OpenAI API bill by 30% or more — pick the right aggregator, right model and right token strategy, without hurting quality.',
    date: '2026-07-11',
    tags: ['cost', 'OpenAI', 'optimization', 'aggregator'],
    minRead: 7,
    related: ['deepbricks', 'aihubmix', 'api2d'],
    content: `A 30% cut on your AI bill rarely comes from one trick. It comes from stacking a few — the provider you buy from, the model you call, and how many tokens you send. Here's the order that gives the biggest wins first.

## 1. Buy the same model for less

The fastest saving needs zero code change: buy GPT-4o through a discounted [aggregator](/en/providers) instead of OpenAI directly. Discounts of 5–25% are common. Because most aggregators are drop-in (swap the base URL, keep the SDK), this is a same-day change. Find the current cheapest on the [cheapest-GPT-4o ranking](/en/rankings/cheapest-gpt-4o).

## 2. Right-size the model

Most requests don't need your most expensive model. Route by difficulty:

- **Cheap model for the easy 80%** — classification, extraction, short replies. GPT-4o mini or DeepSeek V3 cost a fraction of GPT-4o.
- **Premium model only for the hard 20%** — complex reasoning, long code.

Splitting traffic this way often saves more than any provider discount. Compare per-model prices on the [model pages](/en/models).

## 3. Cut tokens, not quality

You pay per token in **and** out. To understand which half is costing you, read [AI API pricing explained](/en/blog/ai-api-pricing-explained). Then:

- **Trim prompts** — remove restated instructions and dead context.
- **Cap output** — set a sensible max-tokens; unbounded completions quietly inflate bills.
- **Summarise history** — in chat apps, compress old turns instead of resending them verbatim.

## 4. Cache and batch

- **Cache** repeated or identical requests instead of paying twice.
- **Batch** low-priority jobs (nightly reports, backfills) on a cheaper, higher-latency provider — trade speed you don't need for money you keep. See [fastest vs. cheapest](/en/rankings/fastest).

## 5. Don't let unreliability eat the savings

Every failed request you retry is paid twice. A provider that's 10% cheaper but frequently degraded can cost more than a stable one. Weigh the [most reliable ranking](/en/rankings/most-reliable) before chasing the lowest sticker price.

## Putting it together

Stack these and 30% is conservative: a discounted provider (−15%), right-sizing models (−20% to −40% on the affected traffic), and token hygiene (−10% to −20%) compound. Start with step 1 today, then work down.

If you'd rather not benchmark providers yourself, our [Deep-Dive Report](/en/report) compares real costs, hidden fees and reliability across fifteen of them.

> We only aggregate and compare — always verify live pricing on each provider's site.`,
  },
  {
    slug: 'claude-api-china-no-vpn',
    locale: 'en',
    title: 'Claude API in China: How to Access It Without a VPN',
    excerpt:
      'Anthropic does not serve mainland China directly. Here is how developers call the Claude API from China without a VPN — using aggregators with Alipay and direct routes.',
    date: '2026-07-13',
    tags: ['Claude', 'China', 'Anthropic', 'Alipay'],
    minRead: 6,
    related: ['aihubmix', 'ohmygpt', 'closeai'],
    content: `Anthropic doesn't officially serve mainland China, and it won't take a domestic card. That leaves developers two problems: **access** and **payment**. A VPN only patches the first, poorly — it's slow, unstable in production, and does nothing about billing. The practical answer is an aggregator.

## Why a VPN is the wrong tool for production

A VPN might get you to the Anthropic console once, but for a running service it's a liability: latency spikes, dropped connections, and you still can't pay with Alipay. Routing API traffic through a personal VPN is not something you want under a production SLA.

## How aggregators solve both problems

An [AI API aggregator](/en/providers) deploys nodes outside mainland China and proxies your request to Anthropic, while billing you locally. You get:

- **A direct route** — no VPN on your side; the provider handles the exit.
- **Local payment** — Alipay, WeChat or UnionPay top-ups.
- **SDK compatibility** — usually just change the base URL and keep the official Anthropic or OpenAI-style client.

Several providers already serve **Claude Sonnet 4.5 and Opus** this way with mainland payment.

## Choosing a provider for Claude in China

Weigh four things:

- **Payment** — does it take Alipay / WeChat? (Most China-focused ones do.)
- **Routes & latency** — stable mainland routing matters more than a headline discount.
- **Price** — compare Claude output prices on the [model pages](/en/models).
- **Trust** — top-up balances make exit-scam risk real; favour providers with invoices and a track record.

That last point matters: read [how AI API pricing works](/en/blog/ai-api-pricing-explained) so a "cheap" quote with hidden fees doesn't surprise you, and see the wider list in [OpenAI API alternatives](/en/blog/openai-api-alternatives-2026).

## A safe way to start

- Top up **small** first and test real latency before committing budget.
- Keep your own [side-by-side comparison](/en/compare) of two or three providers.
- Prefer providers that support **invoices** if you're expensing it.

For a vetted shortlist of who's cheap, stable and unlikely to disappear, our [Deep-Dive Report](/en/report) covers the due diligence.

> We aggregate and compare only. Verify live pricing, routes and terms on each provider's own site before buying, and never send more balance than you're willing to lose to an unproven provider.`,
  },
  {
    slug: 'ai-api-pricing-explained',
    locale: 'en',
    title: 'AI API Pricing Explained: Input Tokens, Output Tokens & Hidden Fees',
    excerpt:
      'A plain-English guide to AI API pricing — what input and output tokens cost, why output is pricier, and the hidden fees that make a "cheap" provider expensive.',
    date: '2026-07-14',
    tags: ['pricing', 'tokens', 'billing', 'guide'],
    minRead: 7,
    related: ['openrouter', 'aihubmix'],
    content: `AI API bills confuse people because the sticker price is only half the story. Once you understand tokens and the fees that hide around them, comparing providers gets a lot easier.

## What is a token

A token is a chunk of text — very roughly **¾ of a word** in English. Both what you send and what you get back are counted in tokens, and you pay for both. Prices are usually quoted per **1 million tokens**.

## Input vs output tokens

- **Input tokens** — everything you send: system prompt, chat history, the user's message, any context.
- **Output tokens** — everything the model generates back.

**Output almost always costs more than input** — often 3–5×. For GPT-4o, for example, output is priced well above input. This has a practical consequence: a long prompt is cheaper than a long answer. If you can cap or shorten completions, you save more than by trimming input.

Because the ratio differs by model, comparing only one number is misleading. Our [model pages](/en/models) show input and output separately so you compare like for like.

## Why an aggregator can be cheaper

An [aggregator](/en/providers) buys upstream capacity in volume and resells it at a discount, so you pay 5–25% less for the *same* model. Some also let you mix providers behind one key. See the full landscape in [OpenAI API alternatives](/en/blog/openai-api-alternatives-2026).

## The hidden fees that catch people out

This is where a "cheap" provider quietly becomes expensive:

- **Billing multipliers** — some panels apply a per-model rate multiplier on top of the base price. Two providers can quote the same headline number and bill differently.
- **Minimum top-ups & breakage** — high minimums force you to prepay more than you'll use; unused balance is pure profit for them if you never spend it.
- **FX spread** — pay in local currency, and the exchange rate they set can add a few percent.
- **Silent downgrades** — the worst offenders route a premium-model request to a cheaper or quantised model. You pay for Opus and get something smaller.
- **Invoice / support gaps** — no invoice or no one to reach when balance goes missing is a cost too.

## How to compare honestly

1. Compare **input and output separately**, per 1M tokens — see the [model rankings](/en/models).
2. Estimate your real input:output ratio and weight accordingly.
3. Factor **reliability** — retries from a flaky provider are paid twice; check the [most reliable ranking](/en/rankings/most-reliable).
4. Watch for the hidden fees above, and start with a **small top-up** to verify actual billing.

Then put your shortlist [side by side](/en/compare), and use [cost-cutting tactics](/en/blog/cut-openai-api-costs-aggregators) to go further. If you'd rather skip the vetting, our [Deep-Dive Report](/en/report) breaks down hidden fees and refund policies across fifteen providers.

> We aggregate and compare independently, and never take payment for ranking. Always confirm live pricing on each provider's own site.`,
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
