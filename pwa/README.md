# AI4Trade Signals — PWA（手机可安装的交易信号 App）

一个**纯静态**的 PWA：用户在手机上「添加到主屏幕」后像原生 App 一样打开，
每个交易日看机器人挑的几只票 + 按自己本金/目标算出的建议仓位。
**首个交易日免费试用**，之后按 **月付 $20 / 年付 $240**（首购 -5%）订阅。

> ⚠️ **合规红线（务必读）**：全站已按「信号=模拟机器人产出、仅供参考、不构成投资
> 建议、不承诺收益、盈亏自负」来措辞。**不要**改成「保证每天赚 X」这类承诺 ——
> 在多数国家这属于违规投资顾问/虚假宣传，风险在你。「每日目标」只用于算仓位。

> 👉 **想直接照着上线？看 [`SETUP.md`](./SETUP.md)**（部署 / Stripe 收款 / 每日信号 /
> 开讨论区 / 挂到网站，一步步带你做）。

功能一览：今日信号（含建议仓位）、我的计划、**反馈/讨论区**（意见收集 + 更新路线图，
可选接 giscus 公开讨论墙）、账户订阅。

---

## 目录结构

```
pwa/
  index.html            App 外壳
  styles.css            样式
  app.js                全部逻辑（试用/付费/信号/仓位）
  config.js             ← 你要改的：价格、Stripe 链接、品牌
  manifest.webmanifest  PWA 清单
  sw.js                 Service Worker（离线）
  icons/                图标
  data/signals.json     每日信号（由 build_feed.py 从根 signals.json 生成）
  build_feed.py         机器人信号 → PWA 信号源
```

## 本地预览

```bash
cd pwa
python3 -m http.server 8080
# 手机与电脑同一 WiFi，浏览器打开 http://<电脑IP>:8080
```

## 部署（任选其一，都免费）

PWA 必须走 **HTTPS** 才能安装。把 `pwa/` 目录作为站点根发布即可：

- **Vercel / Netlify / Cloudflare Pages**：新建项目，构建命令留空，
  **发布目录设为 `pwa`**（Output Directory = `pwa`），部署完成即得 HTTPS 域名。
- **GitHub Pages**：仓库 Settings → Pages，选分支 + `/pwa` 目录（或用 Actions 发布）。

装到手机：用 Safari/Chrome 打开你的域名 →「分享 / 添加到主屏幕」。

## 配置 Stripe 收款（无需后端）

1. 注册 [Stripe](https://stripe.com) → Dashboard。
2. 建 4 条 **Payment Link**（Products → Payment Links）：

   | 用途 | 价格 | Success URL（成功回跳） |
   |---|---|---|
   | 月付 | $20/月（recurring） | `https://你的域名/?paid=monthly` |
   | 年付 | $240/年（recurring） | `https://你的域名/?paid=yearly` |
   | 月付·首购 | $19/月 | `https://你的域名/?paid=monthly` |
   | 年付·首购 | $228/年 | `https://你的域名/?paid=yearly` |

   （首购 -5%：直接把首购那两条链接的价格建成打完折的数额即可。）
3. 把 4 条链接填进 `config.js` 的 `paymentLinks`。搞定。

## 每天更新信号（关键）

机器人开盘前重写根目录 `signals.json` 后，跑一行把它同步给 PWA：

```bash
python3 pwa/build_feed.py            # 生成 pwa/data/signals.json
```

把这行接进机器人已有的「盘前刷新」流程 / GitHub Actions 收尾，
让 PWA 每个交易日自动拿到当天信号。演示用可加 `--demo` 追加示例票。

## 上线加固（放量前再做，MVP 可先跳过）

当前 MVP 的**试用与订阅状态存在浏览器本地**，技术用户可绕过、且换设备不同步。
正式收费前建议：

1. 加账号登录（邮箱/OAuth）。
2. 用 **Stripe Webhook** 在后端记录「谁订阅了」，前端凭登录态向后端要访问权，
   而不是信 localStorage。
3. 信号接口改成登录后才返回完整内容（未订阅只给摘要）。

这套后端可以直接复用仓库里 `web/` 的 Next.js + Prisma（已有 User 表和 Stripe 可挂的位置）。

## 免责声明

本 App 提供的所有信息由模拟交易机器人自动生成，仅供学习与研究参考，
不构成投资建议，不承诺任何收益，交易风险自负。与任何券商/交易所无隶属关系。
