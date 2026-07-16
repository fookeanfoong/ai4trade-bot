# 部署指南

项目为 Next.js 14(App Router),位于仓库子目录 `web/`。以下两种免费方案二选一。

---

## 方案 A:Vercel(推荐,零配置)

1. 在 Vercel 导入本 GitHub 仓库。
2. **Root Directory 设为 `web`**(关键:项目不在仓库根目录)。
3. Framework 自动识别为 Next.js,Build Command / Output 用默认即可。
4. 在 Project → Settings → Environment Variables 填入下方环境变量。
5. Deploy。

Node 版本:20+。API 路由(`/api/track/outbound`、`/api/submit`)用 Node runtime,Vercel 原生支持,无需改动。

---

## 方案 B:Cloudflare Pages

Cloudflare Pages 跑 Next.js App Router 需要官方适配器 `@cloudflare/next-on-pages`,且动态路由必须用 Edge runtime。

1. 安装适配器并调整构建:
   ```bash
   cd web
   npm i -D @cloudflare/next-on-pages
   ```
2. 将两个 API 路由改为 Edge runtime(它们只用到 Web 标准 API,兼容):
   - `src/app/api/track/outbound/route.ts`:把 `export const runtime = 'nodejs'` 改为 `'edge'`
   - `src/app/api/submit/route.ts`:同上(如未声明则新增 `export const runtime = 'edge'`)
3. Pages 项目设置:
   - **Root directory / build 目录**:`web`
   - Build command:`npx @cloudflare/next-on-pages`
   - Build output directory:`.vercel/output/static`
   - 兼容性标志:开启 `nodejs_compat`
4. 填入下方环境变量并部署。

> 页面大多为静态(SSG),两个 API 走 Edge Functions。改 Edge runtime 后 Vercel 同样可用,可保持一份代码两处部署。

---

## 环境变量

见 `.env.example`。上线时按需填写:

| 变量 | 说明 |
|---|---|
| `NEXT_PUBLIC_SITE_URL` | 站点主域名(.com),用于 canonical / sitemap / hreflang |
| `NEXT_PUBLIC_ASSET_PREFIX` | 未来切国内 CDN 时设置 |
| `NEXT_PUBLIC_BAIDU_VERIFY` / `_360_VERIFY` / `_SOGOU_VERIFY` | 搜索引擎站点验证值 |
| `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` + `NEXT_PUBLIC_PLAUSIBLE_SRC` | 自托管 Plausible |
| `NEXT_PUBLIC_UMAMI_URL` + `NEXT_PUBLIC_UMAMI_ID` | 自托管 Umami |
| `NEXT_PUBLIC_BAIDU_TONGJI_ID` | 百度统计 ID |
| `NEXT_PUBLIC_GA_ID` | Google Analytics 4 Measurement ID(`G-XXXXXXXXXX`);覆盖海外,同意「分析」后加载 |
| `NEXT_PUBLIC_CLARITY_ID` | Microsoft Clarity 项目 ID;点击热图/会话回放 |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Cloudflare Turnstile 站点密钥 |

分析脚本默认不加载:仅当对应变量已配置**且**用户在 Cookie 弹窗同意「分析」后才注入,且不使用任何 Google 服务。

---

## 上线后动作

- 提交 `NEXT_PUBLIC_SITE_URL/sitemap.xml` 到 Google Search Console 与百度站长平台。
- `robots.txt` 已明确 allow 百度/搜狗/360/头条爬虫。
- 各页 canonical + 5 语言 hreflang(`zh-CN` 指向中文站,`x-default` 指向英文)已就绪;上线真实域名后 Lighthouse SEO 亦满分。
- 联盟上线时:替换 `src/lib/data/providers.ts` 里各家的 `affiliate_url`(结构不变),跳转埋点会自动带 UTM。
