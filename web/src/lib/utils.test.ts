import { describe, it, expect } from 'vitest';
import { buildAffiliateUrl, formatPrice, BRAND } from '@/lib/utils';
import type { Provider } from '@/lib/types';

const base: Provider = {
  id: 'p_x',
  slug: 'demo-x',
  name: 'Demo',
  logo: '/logos/x.svg',
  website: 'https://demo.example',
  affiliate_url: 'https://demo.example',
  regions: ['CN'],
  payment_methods: ['alipay'],
  founded_date: '2024-01-01',
  trust_score: 80,
  uptime_30d: 99,
  avg_latency_ms: 400,
  supports_invoice: false,
  supports_dpa: false,
  is_marketplace_seller: false,
  commission_rate: null,
};

describe('buildAffiliateUrl', () => {
  it('appends ref + UTM with provider slug as campaign', () => {
    const url = new URL(buildAffiliateUrl(base));
    expect(url.searchParams.get('ref')).toBe(BRAND);
    expect(url.searchParams.get('utm_source')).toBe(BRAND);
    expect(url.searchParams.get('utm_medium')).toBe('aggregator');
    expect(url.searchParams.get('utm_campaign')).toBe('demo-x');
  });

  it('uses & when the affiliate_url already has a query string', () => {
    const url = buildAffiliateUrl({ ...base, affiliate_url: 'https://demo.example/?a=1' });
    expect(url).toContain('?a=1&ref=');
    expect((url.match(/\?/g) || []).length).toBe(1);
  });

  it('falls back to website when affiliate_url is empty', () => {
    const url = buildAffiliateUrl({ ...base, affiliate_url: '' });
    expect(url).toContain('https://demo.example');
    expect(url).toContain('utm_campaign=demo-x');
  });
});

describe('formatPrice', () => {
  it('formats to 2 decimals with $', () => {
    expect(formatPrice(7)).toBe('$7.00');
    expect(formatPrice(1.234)).toBe('$1.23');
  });
});
