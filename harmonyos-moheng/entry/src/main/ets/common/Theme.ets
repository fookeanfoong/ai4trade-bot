/**
 * 视觉常量与小工具。颜色统一走资源引用（$r('app.color.*')），
 * 深色模式由系统在 base/dark 之间自动切换。
 */

/** 数字统一使用等宽字体，保证匹配度、序号、计数对齐（台账感的来源） */
export const NUM_FF: string = 'HarmonyOS Sans,monospace';

/** 圆角 2px，接近直角 */
export const RADIUS: number = 2;

/** 内容区最大宽度，折叠屏 / 平板下居中不拉伸 */
export const MAX_W: number = 560;

/** 通用水平留白 */
export const PAD: number = 20;

export const FS_TITLE: number = 26;
export const FS_H2: number = 19;
export const FS_BODY: number = 15;
export const FS_SMALL: number = 13;
export const FS_TINY: number = 11;
