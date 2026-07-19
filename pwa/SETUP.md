# 上线手册（照着做，约 30 分钟）

三步让 App 真正跑起来收钱：**① 部署上线 → ② 配 Stripe 收款 → ③ 接每日信号**。
外加两个可选项：**开讨论区**、**挂到你的网站**。

---

## ① 部署上线（拿到 HTTPS 网址）

PWA 必须走 HTTPS 才能「装到手机主屏」。三选一，都免费：

### 方案 A：Vercel（最简单，推荐）
1. 打开 https://vercel.com，用 GitHub 登录。
2. **Add New → Project**，选中本仓库 `ai4trade-bot`。
3. 关键设置：
   - **Root Directory** 点 `Edit` → 选 **`pwa`**
   - Framework Preset：**Other**
   - Build Command：**留空**
   - Output Directory：**留空**（就用 `pwa` 里的静态文件）
4. **Deploy**。完成后得到一个网址，例如 `https://ai4trade-signals.vercel.app`。
   记下它，下面第 ② 步要用。

### 方案 B：Netlify（拖拽即可，不连 GitHub 也行）
1. 打开 https://app.netlify.com/drop
2. 把电脑上的 **`pwa` 整个文件夹**拖进去。
3. 秒得一个 HTTPS 网址。

### 方案 C：Cloudflare Pages
新建 Pages 项目 → 连本仓库 → 构建命令留空、**输出目录填 `pwa`** → 部署。

**验证**：手机浏览器打开你的网址 → 菜单「添加到主屏幕」→ 图标出现在桌面 → 点开像 App 一样全屏。

---

## ② 配 Stripe 收款（无需写后端）

1. 注册 https://stripe.com （国内可用海外主体/Stripe Atlas；测试可先用 Test mode）。
2. 建 4 条 **Payment Link**：Dashboard → **Product catalog** → **Payment Links** → **New**。
   每条都选 **Recurring（订阅）**，并在 **After payment → Redirect** 填「成功回跳地址」：

   | 建哪条 | 价格 / 周期 | 成功回跳地址（Redirect URL） |
   |---|---|---|
   | 月付 | $20 / 月 | `https://你的网址/?paid=monthly` |
   | 年付 | $240 / 年 | `https://你的网址/?paid=yearly` |
   | 月付·首购 | $19 / 月 | `https://你的网址/?paid=monthly` |
   | 年付·首购 | $228 / 年 | `https://你的网址/?paid=yearly` |

   > 首购 -5% 就是把后两条的价格直接建成 $19 / $228。App 会自动对「没买过的人」用首购链接。
3. 复制这 4 条链接，填进 **`pwa/config.js`** 的 `paymentLinks`：
   ```js
   paymentLinks: {
     monthly:      'https://buy.stripe.com/xxxx',
     yearly:       'https://buy.stripe.com/yyyy',
     monthlyFirst: 'https://buy.stripe.com/zzzz',
     yearlyFirst:  'https://buy.stripe.com/wwww',
   },
   ```
4. 改完重新部署（Vercel/Netlify 会自动重建）。用户付款成功后会被 Stripe 送回 App 并自动解锁。

> ⚠️ 这是 MVP：解锁状态存在用户浏览器里，能被技术用户绕过、换设备不同步。
> 先用它验证「有没有人真的付费」。要正式防绕过，见 `pwa/README.md` 的「上线加固」。

---

## ③ 接每日信号（让 App 每天有新内容）

机器人开盘前重写根目录 `signals.json`。加一行把它同步给 App：

```bash
python3 pwa/build_feed.py            # 生成 pwa/data/signals.json
git add pwa/data/signals.json && git commit -m "signals" && git push
```

把这三行接进机器人已有的「盘前刷新」流程或 GitHub Actions 收尾即可自动更新。
部署在 Vercel/Cloudflare 的话，push 后会自动重新发布，用户下次打开就是当天的信号。

（想演示满屏效果：`python3 pwa/build_feed.py --demo` 会额外塞两条示例票。）

---

## 可选一：开「公开讨论区」（用户能看到彼此留言）

App 里已经有**反馈表单 + 更新路线图**（`反馈` 标签页），零配置就能用
（用户提交 → 走你邮箱或接口；你在 `pwa/data/updates.json` 里更新路线图，让大家看到反馈被采纳）。

先在 `pwa/config.js` 把 `feedback.email` 改成你的邮箱即可收反馈。

想要**真正的公开讨论墙**（大家互相可见、能回复），用免费的 **giscus**（基于 GitHub Discussions）：
1. 把某个 GitHub 仓库设为 Public，Settings → 勾选 **Discussions**。
2. 打开 https://giscus.app ，填入你的 `仓库名`，它会生成 `repoId` / `categoryId`。
3. 填进 `pwa/config.js`：
   ```js
   discussion: { giscus: { repo:'你/仓库', repoId:'R_xxx', category:'Announcements', categoryId:'DIC_xxx' } },
   ```
4. 重新部署 → `反馈` 页底部出现真正的讨论区。

---

## 可选二：挂到你的网站（web/ 那个站）

网站页脚已内置一个入口卡片，**默认隐藏**，设了网址才出现：

1. 在网站的部署平台（Vercel）→ Project Settings → **Environment Variables** 加：
   - Name：`NEXT_PUBLIC_PWA_URL`
   - Value：`https://你的PWA网址`
2. 重新部署 → 每个页面底部出现「📈 AI4Trade Signals · 手机版 · 打开 App」卡片（含免责声明，5 种语言自动切换）。

> 提示：你的网站 `web/` 是「AI API 比价站（AggreAPI）」，受众和交易 App 不同。
> 挂上去当引流入口没问题，但要清楚这两拨用户不一定重合。

---

## 可选三：开「透明战绩」页（展示真实历史成绩）

App 内置一个战绩页，用机器人**真实**的已平仓记录算出胜率/累计盈亏/每笔明细，**不美化**。

1. 生成数据：`python3 pwa/build_track_record.py`（读根目录 `state.json`）。
2. 在 `pwa/config.js` 把 `features.trackRecord` 改成 `true`，重新部署。
3. 底部会多出「战绩」标签页。

> ⚠️ **默认关闭**，因为当前真实记录是**净亏损**（0 胜 / 9 负，约 −$4）。
> 如实展示能建立信任、也最合规，但现在还不是卖点。**等成绩转正再开**，
> 或你想走「彻底透明」路线就现在开——数据永远是真的，绝不造假。

---

## 一句话合规提醒

全站文案都是「模拟机器人产出、仅供参考、不构成投资建议、不承诺收益、盈亏自负」。
**不要**改成「保证每天赚 X」这类话术——多数国家会当成违规投顾/虚假宣传，风险在你。
