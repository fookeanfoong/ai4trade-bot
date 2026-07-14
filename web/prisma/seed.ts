// 二期数据库种子脚本(模板)。把一期的 JSON mock 灌入 Postgres,
// 证明 mock → DB 的字段映射零改动。运行前需:
//   1) npm i @prisma/client && npm i -D tsx
//   2) 设置 DATABASE_URL
//   3) npx prisma migrate dev
//   4) npx tsx prisma/seed.ts
import { PrismaClient } from '@prisma/client';
import { providers } from '../src/lib/data/providers';
import { models } from '../src/lib/data/models';
import { reviews } from '../src/lib/data/reviews';

const prisma = new PrismaClient();

async function main() {
  for (const p of providers) {
    await prisma.provider.upsert({
      where: { slug: p.slug },
      update: {},
      create: {
        slug: p.slug,
        name: p.name,
        logo: p.logo,
        website: p.website,
        affiliateUrl: p.affiliate_url,
        regions: p.regions,
        paymentMethods: p.payment_methods,
        foundedDate: new Date(p.founded_date),
        trustScore: p.trust_score,
        uptime30d: p.uptime_30d,
        avgLatencyMs: p.avg_latency_ms,
        supportsInvoice: p.supports_invoice,
        supportsDpa: p.supports_dpa,
        isMarketplaceSeller: p.is_marketplace_seller,
        commissionRate: p.commission_rate,
        sponsored: p.sponsored ?? false,
        editorPick: p.editor_pick ?? false,
        newArrival: p.new_arrival ?? false,
        discountCode: p.discount_code ?? null,
      },
    });
  }

  const bySlug = new Map(providers.map((p) => [p.id, p.slug]));

  for (const m of models) {
    const slug = bySlug.get(m.provider_id);
    if (!slug) continue;
    const provider = await prisma.provider.findUnique({ where: { slug } });
    if (!provider) continue;
    await prisma.model.upsert({
      where: { providerId_modelName: { providerId: provider.id, modelName: m.model_name } },
      update: {},
      create: {
        providerId: provider.id,
        modelName: m.model_name,
        modelFamily: m.model_family,
        inputPricePer1m: m.input_price_per_1m,
        outputPricePer1m: m.output_price_per_1m,
        officialPricePer1m: m.official_price_per_1m,
        discountPercent: m.discount_percent,
        contextLength: m.context_length,
        status: m.status,
      },
    });
  }

  for (const r of reviews) {
    const slug = bySlug.get(r.provider_id);
    if (!slug) continue;
    const provider = await prisma.provider.findUnique({ where: { slug } });
    if (!provider) continue;
    await prisma.review.create({
      data: {
        providerId: provider.id,
        rating: r.rating,
        content: r.content,
        verifiedPurchase: r.verified_purchase,
        region: r.region,
        useCase: r.use_case,
        author: r.author,
        createdAt: new Date(r.created_at),
      },
    });
  }

  console.log('Seed complete.');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
