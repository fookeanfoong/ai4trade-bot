# 发布文案 — Product Hunt + Reddit

⚠️ 时机:**等自动信号跑出几周正记录再正式发布**。现在先备好文案。
⚠️ 合规:全程「simulated / educational / not advice / no guaranteed returns」。
把 `[LINK]` 换成 `https://ai4trade-bot.vercel.app`。

---

## 一、Product Hunt

**Name:** AI4Trade Signals

**Tagline(≤60 字符,选一个):**
- Pre-market stock signals, sized to your capital
- A few tickers a day, with exact buy/stop/target prices
- Your honest pre-market watchlist — wins and losses shown

**Description:**
> AI4Trade Signals surfaces a few tickers before each US trading day, each with an
> exact buy price, stop-loss and two targets — and sizes every position to your own
> capital. It's a simulated bot (educational, not investment advice, no guaranteed
> returns), and it shows its full track record, wins and losses included. First
> trading day free.

**Topics:** Fintech, Investing, Productivity, Web App

**First comment(Maker intro,发布时贴在评论区):**
> Hi PH 👋 I built this because every "signal" account I followed only ever showed
> their winners. So I made the opposite: a tool that gives a short daily watchlist
> with exact price levels, sizes it to your capital, and logs *every* result —
> green or red — publicly.
>
> Important: it's a simulated bot for education/research, not investment advice, and
> it can't promise profits (trading loses money too). The honesty is the point.
>
> It runs on GitHub Actions, installs as a PWA, and the first trading day is free.
> Would love feedback on the sizing logic and the transparency page. [LINK]

**Gallery(准备 4–5 张图):** 落地页、今日信号页(价位)、透明战绩页、订阅页、og.png。

---

## 二、Reddit

Reddit 对硬广极度反感。**别去 r/stocks 发广告(会被删+拉黑)。** 走「建造故事」路线,
发到对 indie/技术友好的版,自然带出产品。

### 版块选择
- ✅ **r/SideProject, r/indiehackers, r/webdev, r/reactjs, r/selfhosted** — 讲「我怎么做的」
- ⚠️ **r/algotrading** — 可发,但必须硬核+诚实(贴真实战绩含亏损,别吹),否则被喷
- ❌ **r/stocks, r/wallstreetbets** — 别发广告帖,会被当推销删除

### 建造故事帖(发 r/SideProject / r/indiehackers)

**标题:**
> I built a pre-market stock-signal app that runs on GitHub Actions — and publicly
> shows its losses

**正文:**
> I kept seeing "signal" accounts that only post winners, so I built the opposite as
> a side project.
>
> **What it does:** before each US trading day, a script picks a few tickers with
> exact buy / stop / target prices and sizes them to your capital. You place trades
> in your own broker.
>
> **Stack:** it's a static PWA (installable, offline) + a Python signal generator
> that runs on GitHub Actions every morning, commits the day's signals, and the site
> auto-redeploys. No backend for the app itself; Stripe Payment Links for billing.
>
> **The honest part:** it's a *simulated* bot, it's educational (not investment
> advice), and it can't promise returns — so I show the full record, losses included.
> Early runs were actually net-negative, which taught me to add trend/regime filters
> and stop revenge-entering losers.
>
> Happy to answer anything about the GitHub-Actions-as-cron setup, the PWA→install
> flow, or the position-sizing math. [LINK]
>
> (Not investment advice. Trading involves risk of loss.)

**跟帖策略:** 认真回每条评论,尤其技术问题。别只顾发链接。被问到才多聊产品。

### r/algotrading 版(只有战绩转正后再发)
> 标题:Backtesting/forward-testing a simple trend+regime signal generator — sharing
> the real (unflattering) results
> 正文:贴真实战绩曲线(含亏损)、讲你的过滤规则(SMA 趋势、SPY regime、no-chase、
> bad-data 过滤)、诚实说还没证明能盈利、求反馈。**这个版只吃干货和诚实,不吃营销。**

---

## 三、发布顺序建议

1. 先把 X 连载跑 2–4 周,攒真实战绩 + 一点粉丝。
2. 战绩曲线转正 → Product Hunt 发布(周二/周三 PST 半夜发效果好)。
3. 同日发 r/SideProject 建造故事帖 + X 宣布。
4. r/algotrading 单独发,纯干货。
