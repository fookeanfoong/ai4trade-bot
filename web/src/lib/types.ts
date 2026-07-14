// 数据模型 —— 为二期(托管交易)升级预留字段。
// 一期用 JSON mock,结构与未来数据库表保持一致,迁移时零改动。

export type Region = 'CN' | 'HK' | 'TW' | 'JP' | 'KR' | 'SG' | 'EU' | 'US' | 'Global';

export type PaymentMethod =
  | 'alipay'
  | 'wechat'
  | 'unionpay'
  | 'card'
  | 'paypal'
  | 'usdt'
  | 'wise'
  | 'sepa';

export interface Provider {
  id: string;
  slug: string;
  name: string;
  logo: string; // 本地路径 /logos/xxx.svg,不从被墙 CDN 拉
  website: string;
  affiliate_url: string;
  regions: Region[];
  payment_methods: PaymentMethod[];
  founded_date: string; // ISO
  trust_score: number; // 0-100
  uptime_30d: number; // 百分比
  avg_latency_ms: number;
  supports_invoice: boolean;
  supports_dpa: boolean;
  // —— 二期字段(一期恒为默认值)——
  is_marketplace_seller: boolean; // false
  commission_rate: number | null; // null
  // —— 展示辅助 ——
  sponsored?: boolean; // 精选/置顶位需标注 Sponsored
  editor_pick?: boolean;
  new_arrival?: boolean;
  description?: Partial<Record<string, string>>; // 按 locale 的简介
  discount_code?: string;
}

export type ModelStatus = 'available' | 'degraded' | 'offline';

export interface Model {
  provider_id: string;
  model_name: string;
  model_family: string;
  input_price_per_1m: number; // USD / 1M tokens
  output_price_per_1m: number;
  official_price_per_1m: number; // 官方基准(input+output 综合参考价)
  discount_percent: number; // 相对官方的折扣
  context_length: number;
  status: ModelStatus;
  updated_at: string; // ISO
}

// 二期托管商品:一期结构留好,type/status 固定
export interface Listing {
  id: string;
  provider_id: string;
  type: 'credit' | 'subscription' | 'topup';
  price: number;
  stock: number;
  status: 'external_only';
}

export interface Review {
  id: string;
  provider_id: string;
  rating: number; // 1-5
  content: string;
  verified_purchase: boolean;
  created_at: string; // ISO
  region: Region;
  use_case: string;
  author: string;
}
