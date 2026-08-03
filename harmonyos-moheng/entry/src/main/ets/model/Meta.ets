/**
 * 展示用文案映射。集中放置，便于文案一致性与合规扫描。
 * 全部为中立描述，不含绝对化用语。
 */
import { SceneKey, Scale, Deploy, Region, Level, Effort } from './Types';

export const SCENE_NAME: Record<SceneKey, string> = {
  collab: '协作办公',
  crm: '客户与销售',
  hr: '人力人事',
  fin: '财务费控',
  dev: '项目研发',
  svc: '客服营销',
  bi: '数据分析',
  sign: '合同签署'
};

/** 场景枚举的稳定顺序，用于首屏统计与问卷选项 */
export const SCENE_ORDER: SceneKey[] = ['collab', 'crm', 'hr', 'fin', 'dev', 'svc', 'bi', 'sign'];

export const SCALE_LABEL: Record<Scale, string> = {
  1: '20 人以下',
  2: '20–100 人',
  3: '100–500 人',
  4: '500 人以上'
};

/** 用于理由标签“{规模}适配” */
export const SCALE_TAG: Record<Scale, string> = {
  1: '小团队',
  2: '中小团队',
  3: '中型团队',
  4: '大型组织'
};

export const DEPLOY_LABEL: Record<Deploy, string> = {
  saas: '云端 SaaS',
  both: '云端 / 私有化'
};

export const REGION_LABEL: Record<Region, string> = {
  cn: '数据在境内',
  global: '全球部署'
};

export const PRICE_LABEL: Record<Level, string> = {
  1: '免费起步',
  2: '入门投入',
  3: '中等投入',
  4: '重投入'
};

export const EFFORT_LABEL: Record<Effort, string> = {
  1: '开箱即用',
  2: '需简单配置',
  3: '需实施顾问'
};

/** 覆盖场景名，顿号连接 */
export function sceneSummary(scenes: SceneKey[]): string {
  return scenes.map((s) => SCENE_NAME[s]).join('、');
}

/** 适配规模的简述，例如 [1,2,3,4] → “各规模” */
export function scaleSummary(scales: Scale[]): string {
  if (scales.length >= 4) {
    return '各规模';
  }
  const sorted = scales.slice().sort((a, b) => a - b);
  return sorted.map((s) => SCALE_TAG[s]).join('·');
}
