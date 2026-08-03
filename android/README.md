# AI4Trade Signals — Android 打包（华为 AppGallery 上线用）

把线上 PWA（`https://aicompareapi.com/`）包成一个**原生 Android 壳**（WebView），
用来上架 **华为应用市场（AppGallery）**。

> 为什么用 WebView 壳而不是 TWA？华为手机没有谷歌服务框架（GMS）/Chrome，
> TWA 在华为上不可靠。WebView 壳在任何安卓机（含华为）都稳。App 只是个外壳，
> 内容和更新仍然全部走你已经部署好的网页，改网页即改 App，无需重新发版。

## 目录结构

```
android/
  app/src/main/
    java/com/ai4trade/signals/MainActivity.java   WebView 壳逻辑（返回键/离线重试/外链跳转）
    res/                                          图标、启动图、主题、文案
    AndroidManifest.xml
  app/build.gradle        版本号 / 签名 / 依赖（applicationId = com.ai4trade.signals）
  build.gradle, settings.gradle, gradle/          Gradle 工程
  keystore.properties.example                     签名配置模板（复制成 keystore.properties）
  store/icon-512.png                              商店用 512×512 图标
  HUAWEI_UPLOAD.md        ← 一步步上架华为的完整手册（先看这个）
```

## 三种拿到安装包的方式

1. **GitHub Actions（推荐，无需本地装 Android SDK）**
   仓库根已带 `.github/workflows/android-huawei.yml`。配好签名 Secret 后，
   打一个 `android-v*` 的 tag（或在 Actions 页手动 `Run workflow`）即可产出
   已签名的 `.aab` + `.apk`，在 workflow 的 Artifacts 里下载。

2. **本地命令行**（需装 Android SDK）
   ```bash
   cd android
   cp keystore.properties.example keystore.properties   # 填好你的签名密码
   ./gradlew bundleRelease assembleRelease
   # 产物：app/build/outputs/bundle/release/app-release.aab
   #       app/build/outputs/apk/release/app-release.apk
   ```

3. **Android Studio**：`File → Open` 选 `android/` 目录，等 Gradle 同步完，
   `Build → Generate Signed Bundle / APK`。

改版本号：编辑 `app/build.gradle` 里的 `versionCode`（每次上传要 +1）和 `versionName`。

**上架步骤看 [`HUAWEI_UPLOAD.md`](./HUAWEI_UPLOAD.md)。**
