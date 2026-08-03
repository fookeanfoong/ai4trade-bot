/**
 * 签名交互：候选池收敛条。固定在问卷底部。
 * 一行 32 个细竖条，位置固定不重排；存活项按分数映射条高 5–34px，
 * 被排除项降到 2px、透明度 0.16 并变灰。高度变化 500ms 缓动，收敛过程可见。
 *
 * 采用 @Observed / @ObjectLink：父组件就地修改同一批 BarModel 实例的字段，
 * 每根竖条随之原地过渡，而不是重建（重建会丢失动画）。
 */
import { AppState } from '../model/AppState';
import { NUM_FF } from '../common/Theme';

@Observed
export class BarModel {
  id: string;
  alive: boolean;
  height: number; // px
  opacity: number;

  constructor(id: string, alive: boolean, height: number, opacity: number) {
    this.id = id;
    this.alive = alive;
    this.height = height;
    this.opacity = opacity;
  }
}

@Component
struct Bar {
  @ObjectLink model: BarModel;

  build() {
    Column()
      .width(4)
      .height(this.model.height)
      .backgroundColor(this.model.alive ? $r('app.color.zhu') : $r('app.color.ink_faint'))
      .opacity(this.model.opacity)
      .borderRadius(1)
      .animation({ duration: AppState.dur(500), curve: Curve.EaseInOut })
  }
}

@Component
export struct PoolBar {
  @Link bars: BarModel[];
  @Prop alive: number;
  private total: number = 32;

  build() {
    Column() {
      Row() {
        Text('候选池')
          .fontSize(11)
          .fontColor($r('app.color.ink_faint'))
          .letterSpacing(1)
        Blank()
        Row() {
          Text(`${this.alive}`)
            .fontFamily(NUM_FF)
            .fontSize(13)
            .fontColor($r('app.color.zhu'))
            .fontWeight(FontWeight.Medium)
          Text(` / ${this.total}`)
            .fontFamily(NUM_FF)
            .fontSize(13)
            .fontColor($r('app.color.ink_faint'))
        }
      }
      .width('100%')
      .margin({ bottom: 8 })

      Row() {
        ForEach(this.bars, (b: BarModel) => {
          Bar({ model: b })
        }, (b: BarModel) => b.id)
      }
      .width('100%')
      .height(34)
      .justifyContent(FlexAlign.SpaceBetween)
      .alignItems(VerticalAlign.Bottom)
    }
    .width('100%')
  }
}
