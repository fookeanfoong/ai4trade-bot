import router from '@ohos.router';
import { QUESTIONS, Question, QOption } from '../model/Questions';
import { Answers, SceneKey, Scale, DeployNeed, RegionNeed, Level } from '../model/Types';
import { Session } from '../model/Session';
import { poolBar, aliveCount, match, PoolBarItem } from '../model/Matcher';
import { DataStore } from '../model/DataStore';
import { PoolBar, BarModel } from '../components/PoolBar';
import { MAX_W, PAD, RADIUS, NUM_FF, FS_H2, FS_BODY, FS_SMALL, FS_TINY } from '../common/Theme';

@Entry
@Component
struct Survey {
  @State index: number = 0;
  @State answers: Answers = Session.getAnswers();
  @State bars: BarModel[] = [];
  @State alive: number = 0;

  aboutToAppear(): void {
    // 按产品顺序创建 32 个稳定的竖条实例，位置固定不重排；后续只就地改字段
    this.bars = DataStore.all().map((p) => new BarModel(p.id, true, 5, 1));
    this.recompute();
  }

  private copy(a: Answers): Answers {
    return {
      scenes: a.scenes.slice(),
      scale: a.scale,
      deploy: a.deploy,
      region: a.region,
      budget: a.budget
    };
  }

  private recompute(): void {
    const products = DataStore.all();
    const items: PoolBarItem[] = poolBar(products, this.answers);
    // 就地更新每根竖条（@Observed 触发原地过渡），顺序与 products 一致
    for (let i = 0; i < items.length && i < this.bars.length; i++) {
      this.bars[i].alive = items[i].alive;
      this.bars[i].height = items[i].height;
      this.bars[i].opacity = items[i].opacity;
    }
    this.alive = aliveCount(products, this.answers);
  }

  private current(): Question {
    return QUESTIONS[this.index];
  }

  private isSelected(q: Question, value: string): boolean {
    switch (q.key) {
      case 'scenes':
        return this.answers.scenes.indexOf(value as SceneKey) >= 0;
      case 'scale':
        return this.answers.scale === (parseInt(value) as Scale);
      case 'deploy':
        return this.answers.deploy === (value as DeployNeed);
      case 'region':
        return this.answers.region === (value as RegionNeed);
      case 'budget':
        return this.answers.budget === (parseInt(value) as Level);
      default:
        return false;
    }
  }

  private select(q: Question, value: string): void {
    const next = this.copy(this.answers);
    if (q.key === 'scenes') {
      const k = value as SceneKey;
      const i = next.scenes.indexOf(k);
      if (i >= 0) {
        next.scenes.splice(i, 1);
      } else {
        next.scenes.push(k);
      }
    } else if (q.key === 'scale') {
      next.scale = parseInt(value) as Scale;
    } else if (q.key === 'deploy') {
      next.deploy = value as DeployNeed;
    } else if (q.key === 'region') {
      next.region = value as RegionNeed;
    } else if (q.key === 'budget') {
      next.budget = parseInt(value) as Level;
    }
    this.answers = next;
    Session.setAnswers(next);
    this.recompute();
  }

  private answered(): boolean {
    const q = this.current();
    switch (q.key) {
      case 'scenes':
        return this.answers.scenes.length > 0;
      case 'scale':
        return this.answers.scale !== null;
      case 'deploy':
        return this.answers.deploy !== null;
      case 'region':
        return this.answers.region !== null;
      case 'budget':
        return this.answers.budget !== null;
      default:
        return false;
    }
  }

  private goNext(): void {
    if (!this.answered()) {
      return;
    }
    if (this.index < QUESTIONS.length - 1) {
      this.index += 1;
    } else {
      // 最后一题：计算匹配并进入结果页
      const result = match(DataStore.all(), this.answers);
      Session.setResult(result);
      router.pushUrl({ url: 'pages/Results' });
    }
  }

  private goPrev(): void {
    if (this.index > 0) {
      this.index -= 1;
    }
  }

  @Builder
  OptionRow(q: Question, opt: QOption) {
    Row() {
      // 前导指示：单选圆点，多选方块
      Stack() {
        if (this.isSelected(q, opt.value)) {
          Column()
            .width(12)
            .height(12)
            .backgroundColor($r('app.color.zhu'))
            .borderRadius(q.multi ? 1 : 6)
        }
      }
      .width(20)
      .height(20)
      .borderWidth(1.5)
      .borderColor(this.isSelected(q, opt.value) ? $r('app.color.zhu') : $r('app.color.ink_faint'))
      .borderRadius(q.multi ? 2 : 10)
      .alignContent(Alignment.Center)

      Column() {
        Text(opt.label)
          .fontSize(FS_BODY)
          .fontColor($r('app.color.ink'))
          .fontWeight(this.isSelected(q, opt.value) ? FontWeight.Medium : FontWeight.Normal)
        if (opt.hint !== undefined) {
          Text(opt.hint)
            .fontSize(FS_TINY)
            .fontColor($r('app.color.ink_faint'))
            .margin({ top: 2 })
        }
      }
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 12 })
      .layoutWeight(1)
    }
    .width('100%')
    .padding({ top: 14, bottom: 14, left: 14, right: 14 })
    .backgroundColor(this.isSelected(q, opt.value) ? $r('app.color.zhu_dim') : $r('app.color.paper_2'))
    .borderWidth(1)
    .borderColor(this.isSelected(q, opt.value) ? $r('app.color.zhu') : $r('app.color.rule'))
    .borderRadius(RADIUS)
    .margin({ bottom: 10 })
    .onClick(() => this.select(q, opt.value))
  }

  build() {
    Column() {
      // 顶部：进度与题目
      Scroll() {
        Column() {
          Row() {
            Text(`第 ${this.index + 1}`)
              .fontFamily(NUM_FF)
              .fontSize(FS_SMALL)
              .fontColor($r('app.color.zhu'))
              .fontWeight(FontWeight.Medium)
            Text(` / ${QUESTIONS.length} 题`)
              .fontFamily(NUM_FF)
              .fontSize(FS_SMALL)
              .fontColor($r('app.color.ink_faint'))
            Blank()
            if (this.current().multi) {
              Text('可多选')
                .fontSize(FS_TINY)
                .fontColor($r('app.color.ink_faint'))
            }
          }
          .width('100%')

          Text(this.current().title)
            .fontSize(FS_H2)
            .fontWeight(FontWeight.Bold)
            .fontColor($r('app.color.ink'))
            .margin({ top: 12 })
            .width('100%')

          Text(this.current().hint)
            .fontSize(FS_SMALL)
            .fontColor($r('app.color.ink_soft'))
            .lineHeight(20)
            .margin({ top: 8, bottom: 20 })
            .width('100%')

          ForEach(this.current().options, (opt: QOption) => {
            this.OptionRow(this.current(), opt);
          }, (opt: QOption) => this.current().key + '_' + opt.value + '_' + (this.isSelected(this.current(), opt.value) ? '1' : '0'))
        }
        .constraintSize({ maxWidth: MAX_W })
        .width('100%')
        .padding({ left: PAD, right: PAD, top: 24, bottom: 24 })
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .layoutWeight(1)
      .align(Alignment.Top)

      // 底部：收敛条 + 导航
      Column() {
        Column() {
          PoolBar({ bars: $bars, alive: this.alive })
        }
        .constraintSize({ maxWidth: MAX_W })
        .width('100%')
        .padding({ left: PAD, right: PAD, top: 14, bottom: 6 })

        Row() {
          if (this.index > 0) {
            Button('上一题')
              .fontSize(15)
              .fontColor($r('app.color.ink'))
              .backgroundColor($r('app.color.paper_2'))
              .borderWidth(1)
              .borderColor($r('app.color.rule'))
              .borderRadius(RADIUS)
              .height(48)
              .layoutWeight(1)
              .onClick(() => this.goPrev())
            Blank().width(12)
          }
          Button(this.index === QUESTIONS.length - 1 ? '查看结果' : '下一题')
            .fontSize(15)
            .fontWeight(FontWeight.Medium)
            .fontColor($r('app.color.paper_2'))
            .backgroundColor(this.answered() ? $r('app.color.zhu') : $r('app.color.ink_faint'))
            .borderRadius(RADIUS)
            .height(48)
            .layoutWeight(this.index > 0 ? 2 : 1)
            .enabled(this.answered())
            .onClick(() => this.goNext())
        }
        .constraintSize({ maxWidth: MAX_W })
        .width('100%')
        .padding({ left: PAD, right: PAD, top: 8, bottom: 20 })
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
