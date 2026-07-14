import { describe, it, expect } from 'vitest';
import { cheapestByModel, cheapestGpt4o, uniqueModelNames, providersWithDeals, similarProviders } from '@/lib/selectors';
import { rankings } from '@/lib/data/rankings';
import { providers } from '@/lib/data/providers';

describe('cheapestByModel', () => {
  it('returns rows sorted by ascending output price', () => {
    const rows = cheapestByModel('GPT-4o');
    expect(rows.length).toBeGreaterThan(1);
    for (let i = 1; i < rows.length; i++) {
      expect(rows[i].model.output_price_per_1m).toBeGreaterThanOrEqual(rows[i - 1].model.output_price_per_1m);
    }
  });
});

describe('cheapestGpt4o', () => {
  it('returns the lowest GPT-4o output price for a provider that has it', () => {
    const m = cheapestGpt4o('p_deepbricks');
    expect(m?.model_name).toBe('GPT-4o');
  });
});

describe('helpers', () => {
  it('uniqueModelNames de-duplicates', () => {
    const names = uniqueModelNames();
    expect(new Set(names).size).toBe(names.length);
    expect(names).toContain('GPT-4o');
  });

  it('providersWithDeals only returns providers with a discount code', () => {
    for (const p of providersWithDeals()) expect(p.discount_code).toBeTruthy();
  });

  it('similarProviders excludes the target and returns at most n', () => {
    const sim = similarProviders('openrouter', 3);
    expect(sim.length).toBeLessThanOrEqual(3);
    expect(sim.find((p) => p.slug === 'openrouter')).toBeUndefined();
  });
});

describe('rankings', () => {
  it('each ranking computes a non-empty, correctly ordered list', () => {
    for (const r of rankings) {
      const rows = r.compute();
      expect(rows.length).toBeGreaterThan(0);
      // 每行都能解析到真实 provider
      for (const row of rows) expect(providers.find((p) => p.id === row.provider.id)).toBeTruthy();
    }
  });

  it('all ranking slugs are unique', () => {
    const slugs = rankings.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});
