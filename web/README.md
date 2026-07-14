# AggreAPI — AI API 中转站比价平台

面向亚洲与欧洲市场的 AI API 中转站聚合比价平台。**不自己卖 API**,而是收录市面主流中转站,统一对比价格、速度与稳定性,帮开发者找到最便宜、最快、最稳的那一家。变现:一期联盟返佣 + 精选广告位;二期升级托管交易(数据结构与 URL 已预留)。

## 技术栈

Next.js 14 (App Router) · TypeScript · Tailwind · shadcn 风格组件 · next-intl(简中/繁中/英/日/德)· next-themes(深色默认)· Zustand/Recharts(已装,二期用)。数据先用 JSON mock(`src/lib/data`),结构对齐未来数据库表。

## 本地开发

```bash
cd web
npm install
npm run dev      # http://localhost:3000 → 自动跳转 /zh
npm run build    # 生产构建
npm run start    # 运行生产构建
node scripts/gen-logos.mjs   # 重新生成本地占位 logo
```

复制 `.env.example` 为 `.env.local` 按需填写(站点域名、搜索引擎验证、自托管分析、Turnstile、国内 CDN 前缀)。

## 第 1 阶段已交付

- 脚手架 + i18n(5 语言,`/zh` 前缀,中文 `lang="zh-CN"`)+ 深/浅色 + GDPR Cookie 分类同意弹窗
- 首页(Hero+搜索 → 数据条 → 本周最便宜 Top5 → 编辑精选 → 新上架 → 三步 → 评价 → FAQ)
- `/providers` 总览(筛选/排序/卡片·表格切换)
- `/providers/[slug]` 详情(概览/价格/状态/评价/优惠码 + 相似推荐 + 举报 + 截图分享卡 + 复制文字版对比)
- Footer 法律链接 + 显眼 Affiliate Disclosure + 备案预留位 + AI 提示
- 跳转追踪组件(离站弹窗 + UTM)+ `POST /api/track/outbound` 埋点
- Mock:10 家真实中转站 + 20 个真实模型报价
- 法律页 `/legal/{terms,privacy,cookies,disclaimer,affiliate-disclosure}`
- `robots.txt`(明确 allow 百度/搜狗/360/头条)+ `sitemap.xml`(全 locale)

### 国内可访问性(已验证)

- 无 Google Fonts/Analytics/reCAPTCHA/GTM、无 Twitter/FB/Gravatar/Disqus 等被墙资源
- 字体走 `next/font` 构建期自托管(运行时零 Google 请求),中文用系统黑体栈,图标/logo 本地打包
- 预留 `<meta>` baidu/360/sogou 验证位、`og:image` 300×300 + `itemprop:image`(微信卡片)
- 微信内置浏览器 UA 检测 → 禁用毛玻璃/动画重特效
- 分析预留 Plausible/Umami 自托管 + 百度统计位;验证码用 Cloudflare Turnstile;`NEXT_PUBLIC_ASSET_PREFIX` 预留国内 CDN 切换

## 数据模型(为二期预留)

见 `src/lib/types.ts`:Provider 含 `is_marketplace_seller`/`commission_rate` 二期字段;Listing 结构已留;URL 预留 `/providers/[slug]/shop`、`/listings/[id]`、`/checkout`、`/orders` 不改老路由。

## 部署

Cloudflare Pages 或 Vercel,项目根目录设为 `web/`。主域名 `.com`,`hreflang="zh-CN"` 预留指向未来中国镜像。

> mock 数据中的价格、信任分、延迟等为演示占位值,非各中转站官方承诺;上线时替换 `affiliate_url` 与真实价格即可。
