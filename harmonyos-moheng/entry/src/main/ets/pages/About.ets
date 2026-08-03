import router from '@ohos.router';
import { AppState } from '../model/AppState';
import { DataStore } from '../model/DataStore';
import { DISCLAIMER, PRIVACY_TITLE, PRIVACY_PARAGRAPHS } from '../model/Legal';
import { MAX_W, PAD, RADIUS, FS_H2, FS_BODY, FS_SMALL, FS_TINY } from '../common/Theme';

@Entry
@Component
struct About {
  @State manual: boolean = AppState.manualReduceMotion();

  @Builder
  SectionTitle(t: string) {
    Text(t)
      .fontSize(FS_SMALL)
      .fontWeight(FontWeight.Bold)
      .fontColor($r('app.color.zhu'))
      .letterSpacing(1)
      .margin({ top: 24, bottom: 10 })
      .width('100%')
  }

  build() {
    Column() {
      // 顶栏
      Row() {
        Text('返回')
          .fontSize(FS_SMALL)
          .fontColor($r('app.color.jade'))
          .onClick(() => router.back())
        Blank()
        Text('关于')
          .fontSize(FS_BODY)
          .fontWeight(FontWeight.Medium)
          .fontColor($r('app.color.ink'))
        Blank()
        Text('  ').fontSize(FS_SMALL)
      }
      .width('100%')
      .constraintSize({ maxWidth: MAX_W })
      .padding({ left: PAD, right: PAD, top: 14, bottom: 14 })
      .borderWidth({ bottom: 1 })
      .borderColor($r('app.color.rule'))

      Scroll() {
        Column() {
          Text('墨衡')
            .fontSize(FS_H2)
            .fontWeight(FontWeight.Bold)
            .fontColor($r('app.color.ink'))
          Text('版本 1.0.0 · 数据整理时间 ' + DataStore.updatedAt())
            .fontSize(FS_TINY)
            .fontColor($r('app.color.ink_faint'))
            .margin({ top: 4 })

          Text('墨衡是一个离线的企业软件选型工具。它按固定规则为产品打分，给出的是与你条件的匹配度，不是排行榜，也不接商务合作。')
            .fontSize(FS_BODY)
            .fontColor($r('app.color.ink_soft'))
            .lineHeight(23)
            .margin({ top: 16 })
            .width('100%')

          // 权限说明
          this.SectionTitle('权限')
          Text('本应用不申请任何权限：无网络、无定位、无存储、无设备标识、无通讯录。全程离线运行。')
            .fontSize(FS_SMALL)
            .fontColor($r('app.color.ink_soft'))
            .lineHeight(21)
            .width('100%')

          // 显示设置
          this.SectionTitle('显示')
          Row() {
            Column() {
              Text('减弱动效')
                .fontSize(FS_BODY)
                .fontColor($r('app.color.ink'))
              Text('关闭收敛条等过渡动画。系统开启“减弱动效”时会自动生效。')
                .fontSize(FS_TINY)
                .fontColor($r('app.color.ink_faint'))
                .margin({ top: 2 })
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            Toggle({ type: ToggleType.Switch, isOn: this.manual })
              .selectedColor($r('app.color.zhu'))
              .onChange((on: boolean) => {
                this.manual = on;
                AppState.setManualReduceMotion(on);
              })
          }
          .width('100%')
          .padding({ top: 12, bottom: 12 })

          // 免责声明
          this.SectionTitle('免责声明')
          Text(DISCLAIMER)
            .fontSize(FS_SMALL)
            .fontColor($r('app.color.ink_soft'))
            .lineHeight(21)
            .width('100%')

          // 隐私政策
          this.SectionTitle(PRIVACY_TITLE)
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
          .padding(14)
          .backgroundColor($r('app.color.paper_2'))
          .borderWidth(1)
          .borderColor($r('app.color.rule'))
          .borderRadius(RADIUS)

          Blank().height(32)
        }
        .constraintSize({ maxWidth: MAX_W })
        .width('100%')
        .padding({ left: PAD, right: PAD, top: 20, bottom: 20 })
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .layoutWeight(1)
      .align(Alignment.Top)
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.paper'))
    .alignItems(HorizontalAlign.Center)
  }
}
