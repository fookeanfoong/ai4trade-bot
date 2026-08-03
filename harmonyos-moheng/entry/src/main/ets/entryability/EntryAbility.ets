import UIAbility from '@ohos.app.ability.UIAbility';
import window from '@ohos.window';
import hilog from '@ohos.hilog';
import { AppState } from '../model/AppState';
import { DataStore } from '../model/DataStore';

export default class EntryAbility extends UIAbility {
  onCreate(): void {
    AppState.init();
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    // 冷启动即同步加载随包发布的产品数据，全程无网络请求。
    try {
      DataStore.load(this.context);
    } catch (e) {
      hilog.error(0x0000, 'moheng', 'load products failed: %{public}s', JSON.stringify(e));
    }
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(0x0000, 'moheng', 'loadContent failed: %{public}s', JSON.stringify(err));
      }
    });
  }

  onDestroy(): void {
  }

  onWindowStageDestroy(): void {
  }

  onForeground(): void {
  }

  onBackground(): void {
  }
}
