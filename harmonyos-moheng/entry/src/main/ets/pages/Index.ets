import router from '@ohos.router';
import common from '@ohos.app.ability.common';
import { DataStore } from '../model/DataStore';
import { Session } from '../model/Session';
import { AppState } from '../model/AppState';
import { DISCLAIMER, PRIVACY_INTRO, PRIVACY_PARAGRAPHS, PRIVACY_TITLE } from '../model/Legal';
import { MAX_W, PAD, RADIUS, NUM_FF, FS_TITLE, FS_BODY, FS_SMALL, FS_TINY } from '../common/Theme';

@Entry
@Component
struct Index {
  @State productCount: number = 0;
  @State sceneCount: number = 0;
  @State dimensionCount: number = 0;
  @State dataDate: string = '';
  @State showPrivacy: boolean = false;

  aboutToAppear(): void {
    // 兜底加载（正常已在 Ability 预加载）
    if (DataStore.count() === 0) {
      const ctx = getContext(this) as common.UIAbilityContext;
      DataStore.load(ctx);
    }
    AppState.bindSystemMotion();
    this.productCount = DataStore.count();
    this.sceneCount = DataStore.sceneCount();
    this.dimensionCount = DataStore.dimensionCount();
    this.dataDate = DataStore.updatedAt();
    this.showPrivacy = !AppState.privacyAccepted();
  }

  @Builder
  Stat(value: number, label: string) {
    Column() {
      Text(`${value}`)
        .fontFamily(NUM_FF)
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
        .fontColor($r('app.color.ink'))
      Text(label)
        .fontSize(FS_TINY)
        .fontColor($r('app.color.ink_faint'))
        .margin({ top: 4 })
    }
    .layoutWeight(1)
    .alignItems(HorizontalAlign.Center)
  }

  build() {
    Stack() {
      Column() {
        Scroll() {
          Column() {
            // 品牌标记
            Text('墨衡')
              .fontSize(FS_TITLE)
              .fontWeight(FontWeight.Bold)
              .fontColor($r('app.color.ink'))
              .letterSpacing(2)
            Text('企业软件选型 · 匹配度不是排行榜')
              .fontSize(FS_SMALL)
              .fontColor($r('app.color.zhu'))
              .margin({ top: 6 })

            Text('回答 5 个问题，从收录的主流企业软件里，筛出符合你规模、预算和合规要求的候选，并做横向对比。不推销、不接商务合作、不做排行榜。')
              .fontSize(FS_BODY)
              .fontColor($r('app.color.ink_soft'))
              .lineHeight(24)
              .margin({ top: 20 })

            // 三个统计数字
            Row() {
              this.Stat(this.productCount, '收录产品')
              Divider().vertical(true).height(36).color($r('app.color.rule'))
              this.Stat(this.sceneCount, '覆盖场景')
              Divider().vertical(true).height(36).color($r('app.color.rule'))
              this.Stat(this.dimensionCount, '筛选维度')
            }
            .width('100%')
            .padding({ top: 24, bottom: 24 })
            .margin({ top: 24 })
            .borderWidth({ top: 1, bottom: 1 })
            .borderColor($r('app.color.rule'))

            Button('开始筛选')
              .width('100%')
              .height(50)
              .fontSize(16)
              .fontWeight(FontWeight.Medium)
              .fontColor($r('app.color.paper_2'))
              .backgroundColor($r('app.color.zhu'))
              .borderRadius(RADIUS)
              .margin({ top: 28 })
              .onClick(() => {
                Session.reset();
                router.pushUrl({ url: 'pages/Survey' });
              })

            Text('数据整理时间 ' + this.dataDate + ' · 全程离线，不联网、不收集信息')
              .fontSize(FS_TINY)
              .fontColor($r('app.color.ink_faint'))
              .margin({ top: 16 })

            Blank().height(24)

            Text(DISCLAIMER)
              .fontSize(FS_TINY)
              .fontColor($r('app.color.ink_faint'))
              .lineHeight(18)

            Text('关于与隐私政策')
              .fontSize(FS_SMALL)
              .fontColor($r('app.color.jade'))
              .decoration({ type: TextDecorationType.Underline, color: $r('app.color.jade') })
              .margin({ top: 16 })
              .onClick(() => router.pushUrl({ url: 'pages/About' }))
          }
          .constraintSize({ maxWidth: MAX_W })
          .width('100%')
          .padding({ left: PAD, right: PAD, top: 56, bottom: 40 })
          .alignItems(HorizontalAlign.Start)
        }
        .width('100%')
        .layoutWeight(1)
        .align(Alignment.Top)
      }
      .width('100%')
      .height('100%')
      .backgroundColor($r('app.color.paper'))

      // 首次启动隐私政策弹窗
      if (this.showPrivacy) {
        this.PrivacyGate()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  PrivacyGate() {
    Column() {
      Column() {
        Text(PRIVACY_TITLE)
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor($r('app.color.ink'))
        Text(PRIVACY_INTRO)
          .fontSize(FS_SMALL)
          .fontColor($r('app.color.ink_soft'))
          .lineHeight(22)
          .margin({ top: 12 })

        Scroll() {
          Column() {
            ForEach(PRIVACY_PARAGRAPHS, (p: string) => {
              Text('· ' + p)
                .fontSize(FS_SMALL)
                .fontColor($r('app.color.ink_soft'))
                .lineHeight(21)
                .margin({ bottom: 8 })
                .width('100%')
            })
          }
          .width('100%')
        }
        .margin({ top: 12 })
        .constraintSize({ maxHeight: 220 })

        Button('已了解，开始使用')
          .width('100%')
          .height(48)
          .fontSize(15)
          .fontColor($r('app.color.paper_2'))
          .backgroundColor($r('app.color.zhu'))
          .borderRadius(RADIUS)
          .margin({ top: 16 })
          .onClick(() => {
            AppState.acceptPrivacy();
            this.showPrivacy = false;
          })
      }
      .width('100%')
      .constraintSize({ maxWidth: MAX_W - 40 })
      .padding(20)
      .backgroundColor($r('app.color.paper_2'))
      .borderRadius(RADIUS)
      .borderWidth(1)
      .borderColor($r('app.color.rule'))
    }
    .width('100%')
    .height('100%')
    .padding(PAD)
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .backgroundColor('rgba(0,0,0,0.45)')
  }
}
