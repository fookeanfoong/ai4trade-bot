import type { Model } from '@/lib/types';

// 一期 mock:20 个真实模型报价,分布在各中转站。
// official_price_per_1m = 官方公开的输出价(USD/1M tokens)作为基准参考;
// input/output 为中转站折后价;discount_percent 为相对官方的折扣(5%-25%)。
// 官方价为 2026 年公开近似值,仅供对比演示,请以各家实时价格为准。

const UPDATED = '2026-07-14T00:00:00Z';

function d(official: number, discount: number): number {
  return Math.round(official * (1 - discount / 100) * 100) / 100;
}

export const models: Model[] = [
  // GPT-4o (官方 in 2.5 / out 10)
  { provider_id: 'p_openrouter', model_name: 'GPT-4o', model_family: 'GPT', input_price_per_1m: d(2.5, 8), output_price_per_1m: d(10, 8), official_price_per_1m: 10, discount_percent: 8, context_length: 128000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_aihubmix', model_name: 'GPT-4o', model_family: 'GPT', input_price_per_1m: d(2.5, 18), output_price_per_1m: d(10, 18), official_price_per_1m: 10, discount_percent: 18, context_length: 128000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_deepbricks', model_name: 'GPT-4o', model_family: 'GPT', input_price_per_1m: d(2.5, 24), output_price_per_1m: d(10, 24), official_price_per_1m: 10, discount_percent: 24, context_length: 128000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_api2d', model_name: 'GPT-4o', model_family: 'GPT', input_price_per_1m: d(2.5, 12), output_price_per_1m: d(10, 12), official_price_per_1m: 10, discount_percent: 12, context_length: 128000, status: 'available', updated_at: UPDATED },

  // GPT-4o mini (官方 in 0.15 / out 0.6)
  { provider_id: 'p_ohmygpt', model_name: 'GPT-4o mini', model_family: 'GPT', input_price_per_1m: d(0.15, 15), output_price_per_1m: d(0.6, 15), official_price_per_1m: 0.6, discount_percent: 15, context_length: 128000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_laozhang', model_name: 'GPT-4o mini', model_family: 'GPT', input_price_per_1m: d(0.15, 22), output_price_per_1m: d(0.6, 22), official_price_per_1m: 0.6, discount_percent: 22, context_length: 128000, status: 'available', updated_at: UPDATED },

  // Claude Sonnet 4.5 (官方 in 3 / out 15)
  { provider_id: 'p_openrouter', model_name: 'Claude Sonnet 4.5', model_family: 'Claude', input_price_per_1m: d(3, 6), output_price_per_1m: d(15, 6), official_price_per_1m: 15, discount_percent: 6, context_length: 200000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_aihubmix', model_name: 'Claude Sonnet 4.5', model_family: 'Claude', input_price_per_1m: d(3, 16), output_price_per_1m: d(15, 16), official_price_per_1m: 15, discount_percent: 16, context_length: 200000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_closeai', model_name: 'Claude Sonnet 4.5', model_family: 'Claude', input_price_per_1m: d(3, 20), output_price_per_1m: d(15, 20), official_price_per_1m: 15, discount_percent: 20, context_length: 200000, status: 'degraded', updated_at: UPDATED },

  // Claude Opus 4.1 (官方 in 15 / out 75)
  { provider_id: 'p_ohmygpt', model_name: 'Claude Opus 4.1', model_family: 'Claude', input_price_per_1m: d(15, 10), output_price_per_1m: d(75, 10), official_price_per_1m: 75, discount_percent: 10, context_length: 200000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_poloai', model_name: 'Claude Opus 4.1', model_family: 'Claude', input_price_per_1m: d(15, 14), output_price_per_1m: d(75, 14), official_price_per_1m: 75, discount_percent: 14, context_length: 200000, status: 'available', updated_at: UPDATED },

  // Gemini 2.5 Pro (官方 in 1.25 / out 10)
  { provider_id: 'p_openrouter', model_name: 'Gemini 2.5 Pro', model_family: 'Gemini', input_price_per_1m: d(1.25, 7), output_price_per_1m: d(10, 7), official_price_per_1m: 10, discount_percent: 7, context_length: 1000000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_aigcbest', model_name: 'Gemini 2.5 Pro', model_family: 'Gemini', input_price_per_1m: d(1.25, 21), output_price_per_1m: d(10, 21), official_price_per_1m: 10, discount_percent: 21, context_length: 1000000, status: 'available', updated_at: UPDATED },

  // Gemini 2.5 Flash (官方 in 0.3 / out 2.5)
  { provider_id: 'p_api2d', model_name: 'Gemini 2.5 Flash', model_family: 'Gemini', input_price_per_1m: d(0.3, 13), output_price_per_1m: d(2.5, 13), official_price_per_1m: 2.5, discount_percent: 13, context_length: 1000000, status: 'available', updated_at: UPDATED },

  // DeepSeek V3 (官方 in 0.27 / out 1.1)
  { provider_id: 'p_aihubmix', model_name: 'DeepSeek V3', model_family: 'DeepSeek', input_price_per_1m: d(0.27, 9), output_price_per_1m: d(1.1, 9), official_price_per_1m: 1.1, discount_percent: 9, context_length: 64000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_deepbricks', model_name: 'DeepSeek V3', model_family: 'DeepSeek', input_price_per_1m: d(0.27, 25), output_price_per_1m: d(1.1, 25), official_price_per_1m: 1.1, discount_percent: 25, context_length: 64000, status: 'available', updated_at: UPDATED },

  // DeepSeek R1 (官方 in 0.55 / out 2.19)
  { provider_id: 'p_laozhang', model_name: 'DeepSeek R1', model_family: 'DeepSeek', input_price_per_1m: d(0.55, 19), output_price_per_1m: d(2.19, 19), official_price_per_1m: 2.19, discount_percent: 19, context_length: 64000, status: 'available', updated_at: UPDATED },

  // Grok 4 (官方 in 3 / out 15)
  { provider_id: 'p_gptapius', model_name: 'Grok 4', model_family: 'Grok', input_price_per_1m: d(3, 11), output_price_per_1m: d(15, 11), official_price_per_1m: 15, discount_percent: 11, context_length: 256000, status: 'available', updated_at: UPDATED },
  { provider_id: 'p_openrouter', model_name: 'Grok 4', model_family: 'Grok', input_price_per_1m: d(3, 5), output_price_per_1m: d(15, 5), official_price_per_1m: 15, discount_percent: 5, context_length: 256000, status: 'available', updated_at: UPDATED },

  // Qwen 2.5 Max (官方 out 6 参考)
  { provider_id: 'p_aigcbest', model_name: 'Qwen 2.5 Max', model_family: 'Qwen', input_price_per_1m: d(1.6, 17), output_price_per_1m: d(6, 17), official_price_per_1m: 6, discount_percent: 17, context_length: 131072, status: 'available', updated_at: UPDATED },
];

export function getModelsByProvider(providerId: string): Model[] {
  return models.filter((m) => m.provider_id === providerId);
}
