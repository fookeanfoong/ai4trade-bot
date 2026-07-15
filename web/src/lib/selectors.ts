import { providers } from '@/lib/data/providers';
import { models } from '@/lib/data/models';
import type { Provider, Model } from '@/lib/types';

// 某中转站某模型的报价(取输出价作为主排序参考)
export function providerModelPrice(providerId: string, modelName: string): Model | undefined {
  return models.find((m) => m.provider_id === providerId && m.model_name === modelName);
}

export interface RankedProvider {
  provider: Provider;
  model: Model;
}

// 按指定模型的输出折后价升序排列的中转站(用于「本周最便宜」)
export function cheapestByModel(modelName: string): RankedProvider[] {
  return models
    .filter((m) => m.model_name === modelName)
    .map((m) => ({ provider: providers.find((p) => p.id === m.provider_id)!, model: m }))
    .filter((x) => x.provider)
    .sort((a, b) => a.model.output_price_per_1m - b.model.output_price_per_1m);
}

// 中转站能拿到的最低 GPT-4o 输出价(卡片上展示卖点)
export function cheapestGpt4o(providerId: string): Model | undefined {
  return models
    .filter((m) => m.provider_id === providerId && m.model_name === 'GPT-4o')
    .sort((a, b) => a.output_price_per_1m - b.output_price_per_1m)[0];
}

export const editorPicks = () => providers.filter((p) => p.editor_pick);
export const newArrivals = () => providers.filter((p) => p.new_arrival);

export function maxDiscount(): number {
  return Math.max(...models.map((m) => m.discount_percent));
}

// 全部模型名(按出现顺序去重),用于 /models 榜单
export function uniqueModelNames(): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const m of models) {
    if (!seen.has(m.model_name)) {
      seen.add(m.model_name);
      out.push(m.model_name);
    }
  }
  return out;
}

// 模型名 → URL slug(用于 /models/[slug] 程序化 SEO 比价页)。
// "GPT-4o" → "gpt-4o";"Claude Sonnet 4.5" → "claude-sonnet-4-5"。
export function modelSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export interface ModelSummary {
  name: string;
  slug: string;
  family: string;
  official: number; // 官方基准输出价
  providerCount: number;
  cheapestOutput: number; // 最低折后输出价
  maxDiscount: number; // 最高折扣 %
}

// 全部模型摘要(去重,含 slug / 收录家数 / 最低价 / 最高折扣),用于 /models 与 sitemap。
export function modelSummaries(): ModelSummary[] {
  const names = uniqueModelNames();
  return names.map((name) => {
    const rows = cheapestByModel(name); // 已按输出价升序
    const first = models.find((m) => m.model_name === name)!;
    const discounts = rows.map((r) => r.model.discount_percent);
    return {
      name,
      slug: modelSlug(name),
      family: first.model_family,
      official: first.official_price_per_1m,
      providerCount: rows.length,
      cheapestOutput: rows[0]?.model.output_price_per_1m ?? 0,
      maxDiscount: discounts.length ? Math.max(...discounts) : 0,
    };
  });
}

// slug → 模型名(找不到返回 undefined),用于 /models/[slug] 反查。
export function modelNameBySlug(slug: string): string | undefined {
  return uniqueModelNames().find((name) => modelSlug(name) === slug);
}

// 有优惠码的中转站,用于 /deals
export function providersWithDeals(): Provider[] {
  return providers.filter((p) => !!p.discount_code);
}

// 相似中转站推荐:按共同地区数排序,取前 N
export function similarProviders(slug: string, n = 3): Provider[] {
  const self = providers.find((p) => p.slug === slug);
  if (!self) return [];
  return providers
    .filter((p) => p.slug !== slug)
    .map((p) => ({
      p,
      score: p.regions.filter((r) => self.regions.includes(r)).length,
    }))
    .sort((a, b) => b.score - a.score || b.p.trust_score - a.p.trust_score)
    .slice(0, n)
    .map((x) => x.p);
}
