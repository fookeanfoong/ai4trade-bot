import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { MatchResult, Scored, ReasonTag } from '../model/Types';
import { Session } from '../model/Session';
import { DISCLAIMER } from '../model/Legal';
import { sceneSummary, scaleSummary, DEPLOY_LABEL, PRICE_LABEL, EFFORT_LABEL } from '../model/Meta';
import { MAX_W, PAD, RADIUS, NUM_FF, FS_H2, FS_BODY, FS_SMALL, FS_TINY } from '../common/Theme';

@Entry
@Component
struct Results {
  @State result: MatchResult | null = Session.getResult();
  @State compareIds: string[] = Session.compare().slice();

  private refreshCompare(): void {
    this.compareIds = Session.compare().slice();
  }

  private toggleCompare(id: string): void {
    if (Session.isPicked(id)) {
      Session.removeCompare(id);
    } else {
      const ok = Session.addCompare(id);
      if (!ok) {
        promptAction.showToast({ message: '最多 3 个', duration: 1200 });
        return;
      }
    }
    this.refreshCompare();
  }

  @Builder
  Tag(t: ReasonTag) {
    Text(t.text)
      .fontSize(FS_TINY)
      .fontColor(t.kind === 'good' ? $r('app.color.jade') : $r('app.color.ink_soft'))
      .backgroundColor(t.kind === 'good' ? $r('app.color.jade_dim') : $r('app.color.hint_bg'))
      .padding({ left: 8, right: 8, top: 3, bottom: 3 })
      .borderRadius(RADIUS)
      .margin({ right: 6, bottom: 6 })
  }

  @Builder
  Meta(label: string, value: string) {
    Column() {
      Text(label)
        .fontSize(FS_TINY)
        .fontColor($r('app.color.ink_faint'))
      Text(value)
        .fontSize(FS_SMALL)
        .fontColor($r('app.color.ink'))
        .margin({ top: 2 })
    }
    .alignItems(HorizontalAlign.Start)
    .layoutWeight(1)
  }

  @Builder
  Card(s: Scored, rank: number) {
    Column() {
      // 顶行：排名 + 名称 / 匹配度
      Row() {
        Text(`${rank}`)
          .fontFamily(NUM_FF)
          .fontSize(FS_SMALL)
          .fontColor($r('app.color.ink_faint'))
          .width(24)
        Column() {
          Text(s.product.name)
            .fontSize(FS_H2)
            .fontWeight(FontWeight.Bold)
            .fontColor($r('app.color.ink'))
          Text(s.product.vendor + ' · ' + sceneSummary(s.product.scenes))
            .fontSize(FS_TINY)
            .fontColor($r('app.color.ink_faint'))
            .margin({ top: 2 })
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
        Column() {
          Text(`${s.score}`)
            .fontFamily(NUM_FF)
            .fontSize(24)
            .fontWeight(FontWeight.Bold)
            .fontColor($r('app.color.zhu'))
          Text('匹配度')
            .fontSize(FS_TINY)
            .fontColor($r('app.color.ink_faint'))
        }
        .alignItems(HorizontalAlign.End)
      }
      .width('100%')

      // 匹配度进度条
      Row() {
        Column()
          .width(`${s.score}%`)
          .height(6)
          .backgroundColor($r('app.color.zhu'))
          .borderRadius(RADIUS)
      }
      .width('100%')
      .height(6)
      .backgroundColor($r('app.color.zhu_dim'))
      .borderRadius(RADIUS)
      .margin({ top: 12 })

      Text(s.product.desc)
        .fontSize(FS_SMALL)
        .fontColor($r('app.color.ink_soft'))
        .lineHeight(21)
        .margin({ top: 12 })
        .width('100%')

      // 理由标签
      if (s.reasons.length > 0) {
        Flex({ wrap: FlexWrap.Wrap }) {
          ForEach(s.reasons, (t: ReasonTag) => {
            this.Tag(t);
          }, (t: ReasonTag) => t.text)
        }
        .width('100%')
        .margin({ top: 12 })
      }

      // 四项元信息
      Row() {
        this.Meta('适合规模', scaleSummary(s.product.scales))
        this.Meta('部署方式', DEPLOY_LABEL[s.product.deploy])
      }
      .width('100%')
      .margin({ top: 14 })

      Row() {
        this.Meta('价格档', PRICE_LABEL[s.product.price])
        this.Meta('上手难度', EFFORT_LABEL[s.product.effort])
      }
      .width('100%')
      .margin({ top: 12 })

      Button(Session.isPicked(s.product.id) ? '已加入对比' : '加入对比')
        .width('100%')
        .height(42)
        .fontSize(FS_SMALL)
        .fontColor(Session.isPicked(s.product.id) ? $r('app.color.paper_2') : $r('app.color.zhu'))
        .backgroundColor(Session.isPicked(s.product.id) ? $r('app.color.zhu') : $r('app.color.paper_2'))
        .borderWidth(1)
        .borderColor($r('app.color.zhu'))
        .borderRadius(RADIUS)
        .margin({ top: 16 })
        .onClick(() => this.toggleCompare(s.product.id))
    }
    .width('100%')
    .padding(16)
    .backgroundColor($r('app.color.paper_2'))
    .borderWidth(1)
    .borderColor($r('app.color.rule'))
    .borderRadius(RADIUS)
    .margin({ bottom: 14 })
  }

  @Builder
  Header() {
    Row() {
      Text('返回')
        .fontSize(FS_SMALL)
        .fontColor($r('app.color.jade'))
        .onClick(() => router.back())
      Blank()
      Text('匹配结果')
        .fontSize(FS_BODY)
        .fontWeight(FontWeight.Medium)
        .fontColor($r('app.color.ink'))
      Blank()
      Text('重新开始')
        .fontSize(FS_SMALL)
        .fontColor($r('app.color.jade'))
        .onClick(() => {
          Session.reset();
          router.clear();
          router.replaceUrl({ url: 'pages/Index' });
        })
    }
    .width('100%')
    .constraintSize({ maxWidth: MAX_W })
    .padding({ left: PAD, right: PAD, top: 14, bottom: 14 })
  }

  @Builder
  EmptyState() {
    Column() {
      Text('没有产品同时满足你的硬性条件。试着放宽部署方式或数据合规要求。')
        .fontSize(FS_BODY)
        .fontColor($r('app.color.ink'))
        .lineHeight(24)
        .textAlign(TextAlign.Center)
      Button('返回修改条件')
        .height(46)
        .fontSize(FS_SMALL)
        .fontColor($r('app.color.paper_2'))
        .backgroundColor($r('app.color.zhu'))
        .borderRadius(RADIUS)
        .margin({ top: 24 })
        .padding({ left: 24, right: 24 })
        .onClick(() => router.back())
    }
    .width('100%')
    .constraintSize({ maxWidth: MAX_W })
    .padding(40)
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
  }

  build() {
    Column() {
      // 顶栏
      Column() {
        this.Header()
      }
      .width('100%')
      .alignItems(HorizontalAlign.Center)
      .borderWidth({ bottom: 1 })
      .borderColor($r('app.color.rule'))
      .backgroundColor($r('app.color.paper'))

      // 列表
      Scroll() {
        Column() {
          if (this.result === null || this.result.ranked.length === 0) {
            this.EmptyState()
          } else {
            ForEach(this.result.ranked, (s: Scored, i: number) => {
              this.Card(s, i + 1);
            }, (s: Scored) => s.product.id + '_' + (this.compareIds.indexOf(s.product.id) >= 0 ? '1' : '0'))

            Text(`已排除 ${this.result.excluded} 个不满足硬性条件的产品`)
              .fontSize(FS_SMALL)
              .fontColor($r('app.color.ink_faint'))
              .textAlign(TextAlign.Center)
              .width('100%')
              .margin({ top: 4, bottom: 8 })
          }
        }
        .constraintSize({ maxWidth: MAX_W })
        .width('100%')
        .padding({ left: PAD, right: PAD, top: 16, bottom: 20 })
      }
      .width('100%')
      .layoutWeight(1)
      .align(Alignment.Top)

      // 底部：常驻免责声明 + 对比入口
      Column() {
        Column() {
          Text(DISCLAIMER)
            .fontSize(FS_TINY)
            .fontColor($r('app.color.ink_faint'))
            .lineHeight(17)
            .width('100%')

          if (this.compareIds.length > 0) {
            Button(this.compareIds.length >= 2
              ? `对比已选 ${this.compareIds.length} 个`
              : `再选 1 个即可对比（已选 ${this.compareIds.length}）`)
              .width('100%')
              .height(48)
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor($r('app.color.paper_2'))
              .backgroundColor(this.compareIds.length >= 2 ? $r('app.color.zhu') : $r('app.color.ink_faint'))
              .borderRadius(RADIUS)
              .margin({ top: 12 })
              .enabled(this.compareIds.length >= 2)
              .onClick(() => router.pushUrl({ url: 'pages/Compare' }))
          }
        }
        .constraintSize({ maxWidth: MAX_W })
        .width('100%')
        .padding({ left: PAD, right: PAD, top: 12, bottom: 20 })
      }
      .width('100%')
      .backgroundColor($r('app.color.paper'))
      .borderWidth({ top: 1 })
      .borderColor($r('app.color.rule'))
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.paper'))
  }
}
