# 墨衡 · 企业软件选型（HarmonyOS 原生）

回答 5 个问题，从收录的 32 款主流企业软件里筛出符合自己规模、预算与合规要求的候选，并做横向对比。
**匹配度不是排行榜**：不推销、不接商务合作、不做综合榜单。

- 技术栈：HarmonyOS 原生（ArkTS + ArkUI，Stage 模型，DevEco Studio 工程）。
- 完全离线：无账号、无后端、无网络请求、无任何敏感权限。数据随包发布。
- 目标设备：手机 / 平板 / 折叠屏（`phone`、`tablet`、`2in1`）。

---

## 关于原型 index.html

任务描述提到「附带的 `index.html` 交互原型」，但该文件并未随仓库或任务附带（已在仓库内确认缺失）。
因此本实现以任务文档 **§2 数据模型 / §3 匹配算法 / §4 页面交互** 为唯一真源：

- 32 款产品的数据（`products.json`）依据公开资料自行整理，字段与 §2 的 `Product` 接口一致；
- 匹配算法严格按 §3 实现，并在 `tools/verify.mjs` 中独立重实现同一套规则、锁定具体输入下的排序与分数，作为回归基准；
- 问卷题目与文案按 §4、§6 编写。

若后续拿到原始 `index.html`，只需把它的 `PRODUCTS` 数组迁入 `products.json`（逐条补 `id`/`updatedAt`），
`QUESTIONS` 对照 `model/Questions.ets`，并用 `tools/verify.mjs` 复核分数即可。

---

## 目录结构

```
harmonyos-moheng/
├── AppScope/
│   ├── app.json5                     # bundleName / 版本 / 应用图标与名称（墨衡）
│   └── resources/base/               # 应用级图标(app_icon.png) 与 app_name
├── entry/
│   ├── src/main/
│   │   ├── ets/
│   │   │   ├── entryability/EntryAbility.ets   # 冷启动预加载数据
│   │   │   ├── model/                # 领域层（无 UI）
│   │   │   │   ├── Types.ets         # 接口与枚举
│   │   │   │   ├── Meta.ets          # 展示文案映射 + scaleSummary
│   │   │   │   ├── Questions.ets     # 5 题问卷常量
│   │   │   │   ├── DataStore.ets     # 读取 rawfile，派生统计
│   │   │   │   ├── Matcher.ets       # 匹配算法（§3 唯一真源）+ 收敛条计算
│   │   │   │   ├── Session.ets       # 页面间共享作答/结果/对比选择
│   │   │   │   ├── AppState.ets      # 减弱动效 / 隐私确认
│   │   │   │   └── Legal.ets         # 免责声明 + 隐私政策文案
│   │   │   ├── components/PoolBar.ets            # 候选池收敛条
│   │   │   ├── common/Theme.ets                  # 视觉常量
│   │   │   └── pages/
│   │   │       ├── Index.ets         # 首屏（含首次启动隐私弹窗）
│   │   │       ├── Survey.ets        # 问卷（含底部收敛条）
│   │   │       ├── Results.ets       # 结果列表（常驻免责声明）
│   │   │       ├── Compare.ets       # 横向对比（常驻免责声明）
│   │   │       └── About.ets         # 关于/隐私/减弱动效开关
│   │   ├── resources/
│   │   │   ├── base/element/color.json           # 浅色主题色板
│   │   │   ├── dark/element/color.json           # 深色主题色板（系统自动切换）
│   │   │   ├── base/profile/main_pages.json
│   │   │   ├── base/media/                        # 应用/启动/分层图标
│   │   │   └── rawfile/products.json              # ★ 产品数据（32 条，外置）
│   │   └── module.json5              # 权限清单为空
│   ├── build-profile.json5 / hvigorfile.ts / oh-package.json5
├── tools/
│   ├── make_icons.py                 # 生成“墨衡”印章图标（三处图标同源）
│   └── verify.mjs                    # 算法/数据/合规校验（回归基准）
├── build-profile.json5 / hvigorfile.ts / oh-package.json5
```

## 构建与运行

需要 DevEco Studio（HarmonyOS SDK API 12 / 5.0.0）。

1. DevEco Studio → Open，选择 `harmonyos-moheng/` 目录。
2. 等待 `hvigor` sync 完成（会自动创建 `oh_modules`）。
3. 连接真机或启动模拟器，Run `entry`。
4. 发布：配置发布证书签名、执行华为官方加固后生成 `.app`/HAP 上传应用市场。

> 图标已随包提交（`tools/make_icons.py` 生成）。提交图标、桌面图标、最近任务列表图标使用同一张源图，保证三者一致。

## 回归校验（无需 DevEco）

```
node tools/verify.mjs
```

覆盖：数据合法性（32 条、id 唯一、枚举合法、desc 40–60 字、8 场景全覆盖）、
三条硬性排除规则各自可触发、具体输入下的排序与分数锁定、绝对化用语扫描。全绿即通过。

---

## 匹配算法（满分 100）

先硬性排除，再对存活项加权打分（详见 `model/Matcher.ets`）：

| 维度 | 满分 | 要点 |
|---|---|---|
| 场景 | 35 | `35 × min(1, 命中数 / min(选择数, 2))`；未答 25 |
| 规模 | 25 | 命中 25 / 相邻 12 / 否则 2；未答 18 |
| 部署 | 15 | 明确要求且满足 15；都行 11 |
| 合规 | 10 | 明确满足 10；有海外但产品在境内 5；无要求 8 |
| 预算 | 15 | ≤预算 15；超 1 档 7；超 2 档 1；未答 10 |

排序：分数降序，同分按产品名 `localeCompare('zh-Hans-CN')` 稳定排序。
理由标签正向在前、提示在后，最多 4 个且提示不省略。

## 合规要点（对应任务 §7）

- 权限清单为空：`module.json5` 不含任何 `requestPermissions`。
- 全程离线：无网络代码、无第三方统计/广告 SDK、无对外跳转导流。
- 无第三方 logo：产品仅以纯文字名称呈现。
- 免责声明在结果页、对比页常驻可见（`Legal.DISCLAIMER`）。
- 隐私政策首次启动弹窗告知、可在「关于」页随时复查；明确写明「不收集任何个人信息」。
- 无绝对化用语：`tools/verify.mjs` 会扫描 ets 与 products.json。
- 应用名「墨衡」为自造名，避免泛词与侵权风险；软著名称需与上架名一致。

## 已知平台说明

- **等宽数字**：数字统一使用等宽字体族以获得对齐的「台账感」。如需严格 `tabular-nums`，
  可在工程内 `registerFont` 一款带 tnum 的等宽字体并替换 `common/Theme.ets` 的 `NUM_FF`。
- **减弱动效**：通过媒体查询 `(prefers-reduced-motion: reduce)` 跟随系统（`AppState.bindSystemMotion`），
  同时在「关于」页提供手动开关；平台不支持该媒体特性时手动开关仍可用。
- 本环境无 DevEco/模拟器，UI 未经真机编译验证；算法、数据与合规已通过 `tools/verify.mjs` 校验。
