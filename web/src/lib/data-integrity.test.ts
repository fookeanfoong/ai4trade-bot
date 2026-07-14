import { describe, it, expect } from 'vitest';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { providers } from '@/lib/data/providers';
import { models } from '@/lib/data/models';
import { reviews } from '@/lib/data/reviews';
import { posts } from '@/lib/data/blog';

const PUBLIC = resolve(__dirname, '../../public');

describe('data integrity', () => {
  it('provider slugs and ids are unique', () => {
    expect(new Set(providers.map((p) => p.slug)).size).toBe(providers.length);
    expect(new Set(providers.map((p) => p.id)).size).toBe(providers.length);
  });

  it('every provider logo file exists locally (no blocked CDN)', () => {
    for (const p of providers) {
      expect(p.logo.startsWith('/logos/'), `${p.name} logo must be local`).toBe(true);
      expect(existsSync(resolve(PUBLIC, p.logo.replace(/^\//, ''))), `missing ${p.logo}`).toBe(true);
    }
  });

  it('phase-2 fields keep their phase-1 defaults', () => {
    for (const p of providers) {
      expect(p.is_marketplace_seller).toBe(false);
      expect(p.commission_rate).toBeNull();
    }
  });

  it('every model references an existing provider', () => {
    const ids = new Set(providers.map((p) => p.id));
    for (const m of models) expect(ids.has(m.provider_id), `unknown provider_id ${m.provider_id}`).toBe(true);
  });

  it('model prices and discounts are sane', () => {
    for (const m of models) {
      expect(m.output_price_per_1m).toBeGreaterThan(0);
      expect(m.output_price_per_1m).toBeLessThanOrEqual(m.official_price_per_1m);
      expect(m.discount_percent).toBeGreaterThanOrEqual(0);
      expect(m.discount_percent).toBeLessThanOrEqual(100);
    }
  });

  it('every review references an existing provider', () => {
    const ids = new Set(providers.map((p) => p.id));
    for (const r of reviews) expect(ids.has(r.provider_id)).toBe(true);
  });

  it('blog: 5 posts, at least 3 in Chinese, unique slugs, valid related providers', () => {
    expect(posts.length).toBe(5);
    expect(posts.filter((p) => p.locale === 'zh').length).toBeGreaterThanOrEqual(3);
    expect(new Set(posts.map((p) => p.slug)).size).toBe(posts.length);
    const slugs = new Set(providers.map((p) => p.slug));
    for (const post of posts) for (const rel of post.related) expect(slugs.has(rel), `unknown related ${rel}`).toBe(true);
  });
});
