import router from '@ohos.router';
import { Scored } from '../model/Types';
import { Session } from '../model/Session';
import { DISCLAIMER } from '../model/Legal';
import { sceneSummary, scaleSummary, DEPLOY_LABEL, REGION_LABEL, PRICE_LABEL, EFFORT_LABEL } from '../model/Meta';
import { MAX_W, PAD, RADIUS, NUM_FF, FS_BODY, FS_SMALL, FS_TINY } from '../common/Theme';

interface CmpRow {
  key: string;
  label: string;
  height: number;
}

const ROWS: CmpRow[] = [
  { key: 'name', label: '产品名', height: 46 },
  { key: 'score', label: '匹配度', height: 44 },
  { key: 'vendor', label: '厂商', height: 40 },
  { key: 'scenes', label: '覆盖场景', height: 60 },
  { key: 'scales', label: '适合规模', height: 44 },
  { key: 'deploy', label: '部署方式', height: 40 },
  { key: 'region', label: '数据合规', height: 40 },
  { key: 'price', label: '价格档位', height: 40 },
  { key: 'effort', label: '上手难度', height: 40 },
  { key: 'desc', label: '核心特点', height: 108 }
];

const COL_W: number = 138;
const LABEL_W: number = 84;

@Entry
@Component
struct Compare {
  @State picked: Scored[] = Session.pickedScored();

  private valueFor(s: Scored, key: string): string {
    switch (key) {
      case 'name':
        return s.product.name;
      case 'score':
        return `${s.score}`;
      case 'vendor':
        return s.product.vendor;
      case 'scenes':
        return sceneSummary(s.product.scenes);
      case 'scales':
        return scaleSummary(s.product.scales);
      case 'deploy':
        return DEPLOY_LABEL[s.product.deploy];
      case 'region':
        return REGION_LABEL[s.product.region];
      case 'price':
        return PRICE_LABEL[s.product.price];
      case 'effort':
        return EFFORT_LABEL[s.product.effort];
      case 'desc':
        return s.product.desc;
      default:
        return '';
    }
  }

  @Builder
  Cell(text: string, height: number, key: string, isHead: boolean) {
    Column() {
      Text(text)
        .fontFamily(key === 'score' ? NUM_FF : 'HarmonyOS Sans')
        .fontSize(key === 'name' ? FS_BODY : (key === 'desc' ? FS_TINY : FS_SMALL))
        .fontWeight(isHead || key === 'name' ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(key === 'score' ? $r('app.color.zhu') : $r('app.color.ink'))
        .lineHeight(key === 'desc' ? 17 : 20)
        .maxLines(key === 'desc' ? 6 : 3)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .width('100%')
    }
    .width('100%')
    .height(height)
    .padding({ left: 10, right: 10, top: 8, bottom: 8 })
    .justifyContent(FlexAlign.Start)
    .alignItems(HorizontalAlign.Start)
    .borderWidth({ bottom: 1 })
    .borderColor($r('app.color.rule'))
  }

  @Builder
  LabelCell(text: string, height: number) {
    Column() {
      Text(text)
        .fontSize(FS_TINY)
        .fontColor($r('app.color.ink_faint'))
        .width('100%')
    }
    .width(LABEL_W)
    .height(height)
    .padding({ left: PAD, right: 8, top: 8, bottom: 8 })
    .justifyContent(FlexAlign.Start)
    .alignItems(HorizontalAlign.Start)
    .borderWidth({ bottom: 1 })
    .borderColor($r('app.color.rule'))
  }

  @Builder
  ProductColumn(s: Scored) {
    Column() {
      ForEach(ROWS, (r: CmpRow) => {
        this.Cell(this.valueFor(s, r.key), r.height, r.key, r.key === 'name');
      }, (r: CmpRow) => r.key)
    }
    .width(COL_W)
    .borderWidth({ left: 1 })
    .borderColor($r('app.color.rule'))
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
        Text('横向对比')
          .fontSize(FS_BODY)
          .fontWeight(FontWeight.Medium)
          .fontColor($r('app.color.ink'))
        Blank()
        Text(`${this.picked.length} 个`)
          .fontFamily(NUM_FF)
          .fontSize(FS_SMALL)
          .fontColor($r('app.color.ink_faint'))
      }
      .width('100%')
      .constraintSize({ maxWidth: MAX_W })
      .padding({ left: PAD, right: PAD, top: 14, bottom: 14 })

      Divider().color($r('app.color.rule'))

      // 表格：左侧标签列固定，右侧产品列横向滚动
      Scroll() {
        Row() {
          // 标签列
          Column() {
            ForEach(ROWS, (r: CmpRow) => {
              this.LabelCell(r.label, r.height);
            }, (r: CmpRow) => 'l_' + r.key)
          }
          .width(LABEL_W)

          // 产品列，横向滚动
          Scroll() {
            Row() {
              ForEach(this.picked, (s: Scored) => {
                this.ProductColumn(s);
              }, (s: Scored) => s.product.id)
            }
          }
          .scrollable(ScrollDirection.Horizontal)
          .layoutWeight(1)
          .align(Alignment.TopStart)
        }
        .alignItems(VerticalAlign.Top)
        .width('100%')
      }
      .layoutWeight(1)
      .width('100%')
      .align(Alignment.Top)

      // 常驻免责声明
      Column() {
        Text(DISCLAIMER)
          .fontSize(FS_TINY)
          .fontColor($r('app.color.ink_faint'))
          .lineHeight(17)
          .width('100%')
      }
      .width('100%')
      .constraintSize({ maxWidth: MAX_W })
      .padding({ left: PAD, right: PAD, top: 12, bottom: 20 })
      .borderWidth({ top: 1 })
      .borderColor($r('app.color.rule'))
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.paper'))
    .alignItems(HorizontalAlign.Center)
  }
}
