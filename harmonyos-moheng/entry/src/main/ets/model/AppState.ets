/**
 * 全局设置：减弱动效、隐私政策确认状态。
 * 偏好保存在应用沙箱（AppStorage / PersistentStorage），不涉及任何敏感权限。
 */
import mediaquery from '@ohos.mediaquery';

const KEY_MOTION = 'reduceMotion';    // 手动开关（持久化）
const KEY_SYS_MOTION = 'sysReduceMotion'; // 跟随系统（内存）
const KEY_PRIVACY = 'privacyAccepted';

export class AppState {
  /** 在 Ability 启动时调用一次，登记需要持久化的键 */
  static init(): void {
    PersistentStorage.persistProp(KEY_MOTION, false);
    PersistentStorage.persistProp(KEY_PRIVACY, false);
    if (AppStorage.get<boolean>(KEY_SYS_MOTION) === undefined) {
      AppStorage.setOrCreate(KEY_SYS_MOTION, false);
    }
  }

  /**
   * 跟随系统「减弱动效」。平台支持时通过媒体查询实时更新；
   * 不支持时保持手动开关可用。需在 UI 上下文中调用。
   */
  static bindSystemMotion(): void {
    try {
      const listener = mediaquery.matchMediaSync('(prefers-reduced-motion: reduce)');
      AppStorage.setOrCreate(KEY_SYS_MOTION, listener.matches);
      listener.on('change', (r: mediaquery.MediaQueryResult) => {
        AppStorage.setOrCreate(KEY_SYS_MOTION, r.matches);
      });
    } catch (e) {
      // 平台不支持该媒体特性时忽略，保留“关于”页的手动开关
    }
  }

  /** 有效的减弱动效状态：系统开启 或 用户手动开启 */
  static reduceMotion(): boolean {
    const sys = AppStorage.get<boolean>(KEY_SYS_MOTION) ?? false;
    const manual = AppStorage.get<boolean>(KEY_MOTION) ?? false;
    return sys || manual;
  }

  static manualReduceMotion(): boolean {
    return AppStorage.get<boolean>(KEY_MOTION) ?? false;
  }

  static setManualReduceMotion(v: boolean): void {
    AppStorage.setOrCreate(KEY_MOTION, v);
  }

  /** 动画时长；减弱动效时返回 0，用于关闭所有过渡 */
  static dur(ms: number): number {
    return AppState.reduceMotion() ? 0 : ms;
  }

  // ——— 隐私政策 ———

  static privacyAccepted(): boolean {
    return AppStorage.get<boolean>(KEY_PRIVACY) ?? false;
  }

  static acceptPrivacy(): void {
    AppStorage.setOrCreate(KEY_PRIVACY, true);
  }
}
