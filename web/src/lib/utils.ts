import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { Provider } from '@/lib/types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const BRAND = 'aggreapi';

// 跳转追踪 —— 联盟返佣的命脉。
// 为 affiliate_url 附加固定 UTM 参数,campaign 用 provider slug 区分。
export function buildAffiliateUrl(provider: Provider): string {
  const base = provider.affiliate_url || provider.website;
  const params = new URLSearchParams({
    ref: BRAND,
    utm_source: BRAND,
    utm_medium: 'aggregator',
    utm_campaign: provider.slug,
  });
  const sep = base.includes('?') ? '&' : '?';
  return `${base}${sep}${params.toString()}`;
}

export function formatPrice(v: number): string {
  return `$${v.toFixed(2)}`;
}

export function formatLatency(ms: number): string {
  return `${ms}ms`;
}
