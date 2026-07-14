# 数据库(二期)

一期用 `src/lib/data/*` 的 JSON mock;二期接入 Postgres 时,本目录的 `schema.prisma`
与 mock 字段一一对应,迁移零改动。**一期不需要连数据库,此目录仅为二期准备。**

## 表结构

- `Provider` / `Model` / `Review` —— 对应一期 mock,含二期字段 `isMarketplaceSeller` / `commissionRate`
- `Listing` —— 二期托管商品(status 默认 `external_only`)
- `User` / `Favorite` / `PriceAlert` —— 用户中心(替换一期的本地 Zustand mock)
- `OutboundClick` —— 跳转埋点(替换 `/api/track/outbound` 的 console 落地)
- `Submission` —— 商家自荐(替换 `/api/submit`)

## 二期启用步骤

```bash
cd web
npm i @prisma/client        # 运行时客户端
npm i -D tsx                # 跑 seed 用

# 设置连接串(免费档:Neon / Supabase Postgres)
export DATABASE_URL="postgresql://..."

npm run db:generate         # 生成 Prisma Client
npm run db:migrate          # 创建表
npm run db:seed             # 灌入一期数据,验证映射

# 之后把 src/lib/data/*.ts 的读取改为 Prisma 查询,页面无需改动
```

`npm run db:validate` 可随时校验 schema 语法(无需连库)。
