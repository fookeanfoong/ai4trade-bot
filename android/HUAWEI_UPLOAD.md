# 上架华为应用市场（AppGallery）手册

照着做即可。分四块：**① 生成签名 → ② 打出安装包 → ③ 注册华为开发者 & 建应用 →
④ 填资料上传送审**。最后有一节**合规红线**务必读——金融/收费类最容易被这几条卡。

---

## ① 生成签名密钥（只做一次，务必备份）

安装包必须签名。签名密钥丢了就没法给同一个 App 发更新，**一定要备份好**。

```bash
keytool -genkeypair -v \
  -keystore release.jks \
  -alias ai4trade \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass '你的keystore密码' -keypass '你的key密码' \
  -dname "CN=AI4Trade Signals, O=AI4Trade, C=CN"
```

得到 `release.jks`。把它和两个密码存到密码管理器里，别提交进仓库
（`android/.gitignore` 已经挡掉 `*.jks` 和 `keystore.properties`）。

---

## ② 打出安装包（`.aab` + `.apk`）

### 方式 A：GitHub Actions（不用本地装 Android SDK，推荐）

1. 把签名塞进仓库 **Settings → Secrets and variables → Actions → New repository secret**，建 4 个：

   | Secret 名字 | 值 |
   |---|---|
   | `ANDROID_KEYSTORE_BASE64` | `base64 -w0 release.jks` 的输出（整段） |
   | `KEYSTORE_PASSWORD` | 你的 keystore 密码 |
   | `KEY_ALIAS` | `ai4trade` |
   | `KEY_PASSWORD` | 你的 key 密码 |

   生成 base64：
   ```bash
   base64 -w0 release.jks    # macOS 用: base64 -i release.jks | tr -d '\n'
   ```

2. 触发构建：打个 tag 推上去，或到 **Actions → Build Huawei Android app → Run workflow**。
   ```bash
   git tag android-v1.0.0 && git push origin android-v1.0.0
   ```
3. 构建完在该次运行的 **Artifacts** 里下载 `ai4trade-signals-release`，
   里面有 `app-release.aab` 和 `app-release.apk`。

> 没配 Secret 也能跑，但产出的是 **debug 签名**包，只能自测、不能上架。

### 方式 B：本地

```bash
cd android
cp keystore.properties.example keystore.properties   # 填好密码，把 release.jks 放在 android/ 下
./gradlew bundleRelease assembleRelease
```
产物：
- `app/build/outputs/bundle/release/app-release.aab`（华为优先用 AAB）
- `app/build/outputs/apk/release/app-release.apk`（备用/自测直接装这个）

装到手机自测：`adb install app/build/outputs/apk/release/app-release.apk`。

---

## ③ 注册华为开发者 + 创建应用

1. **注册并实名认证**：<https://developer.huawei.com> → 注册 →
   **实名认证**（个人：身份证+人脸；企业：营业执照，1–3 个工作日）。
   收费应用建议走**企业**认证，也便于后面开通交易/结算。
2. 进 **AppGallery Connect（AGC）**：<https://developer.huawei.com/consumer/cn/service/josp/agc/index.html>
3. **我的项目 → 新建项目 → 项目内新建应用**：
   - 应用名称：`AI4Trade Signals`
   - 平台：**Android**
   - 应用分类：**应用**（不是游戏）
   - 默认语言：中文（简体）
   - 包名：**`com.ai4trade.signals`**（必须和 `app/build.gradle` 里的 `applicationId` 一致）

---

## ④ 填资料、上传、送审

在 AGC 里打开这个应用，左侧 **分发 → 应用信息 / 版本信息**，把下面填齐：

**应用信息（商店展示）**
- 应用图标：512×512，用 `android/store/icon-512.png`。
- 应用简介 / 简短介绍 / 完整介绍：突出「盘前参考信号、按本金算仓位、教育用途」，
  **不要**写「保证收益/稳赚」之类（见合规红线）。
- 应用截图：至少 **2–3 张**手机截图（在手机上装好 apk，截今日信号页/计划页/账户页）。
- 分类：建议 **工具** 或 **教育**（**慎选「金融理财」**，见合规红线）。
- 隐私政策网址（必填）：`https://aicompareapi.com/privacy.html`
- 用户协议 / 服务条款：`https://aicompareapi.com/terms.html`
  （这两页本次已生成、随网站一起部署，公网可直接打开。）
- 年龄分级：按华为问卷如实填（含金融信息、无不良内容）。

**版本信息（上传包）**
- 上传 **`app-release.aab`**（或 `.apk`）。
- 华为**应用签名**：首次会让你选「由华为管理签名」或「使用自有签名」。
  简单起见可让**华为托管签名**；若选自有签名，用的就是 ① 里的 `release.jks`。
- 更新说明：`首个版本上线` 之类。
- 保存 → **提交审核**。审核一般 1–3 个工作日；被拒会给具体原因，改完再交即可。

**发更新版本时**：`app/build.gradle` 把 `versionCode` +1、`versionName` 改新号，
重新出包上传新版本即可（其余资料会沿用）。

---

## ⑤ 合规红线（金融 + 收费，务必读）

华为审核对「金融」和「站外收费」最敏感，下面几条最容易被卡：

1. **别用「金融理财」分类去踩资质。** 本 App 定位是**模拟信号 + 教育工具**，不是券商、
   不代客理财、不下单。选 **工具/教育** 分类，全站保持「仅供参考、不构成投资建议、
   不承诺收益、盈亏自负」的措辞。若被划入金融类，华为可能要求**金融/证券相关资质**，
   个人主体通常拿不到——所以定位和文案一定要稳在「教育/信息」。

2. **站外 Stripe 收费有被拒风险。** 华为对「App 内销售数字内容/订阅」原则上要求走
   **华为 IAP（应用内支付）**。当前订阅走的是网页版 Stripe。两种务实做法：
   - **保守**：上架版本先**不在 App 内引导付费**（隐藏/弱化订阅入口，主打免费试用信号），
     先过审、先有量；付费在网页端完成。
   - **合规接入**：要在 App 内正式卖订阅，就接**华为 IAP**（需要企业资质和结算开通）。
   先按第一种过审最省事，跑通了再考虑第二种。

3. **必须有可访问的隐私政策**：已用 `https://aicompareapi.com/privacy.html`，
   确认部署后公网能打开（华为审核会点）。

4. **免责声明要显眼**：App 首页/落地页已有免责声明，保留别删。

5. **权限最小化**：本 App 只申请了 `INTERNET` 和 `ACCESS_NETWORK_STATE`，无敏感权限，
   审核问卷如实勾「无」。

---

## 常见问题

- **审核说「打开是空白/加载失败」**：多半是 `https://aicompareapi.com/` 当时没部署好或被墙。
  先在手机浏览器确认该网址能打开，再重新送审。
- **想改成别的域名**：编辑 `app/src/main/java/com/ai4trade/signals/MainActivity.java`
  里的 `START_URL` 和 `IN_APP_HOSTS`，重新出包。
- **图标/名字要改**：图标在 `res/mipmap-*` 和 `res/drawable-*/ic_launcher_foreground.png`；
  名字在 `res/values/strings.xml` 的 `app_name`。
