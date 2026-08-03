/**
 * 领域类型定义。
 * 数据字段与 resources/rawfile/products.json 一一对应。
 */

export type SceneKey =
  | 'collab' // 协作办公
  | 'crm'    // 客户与销售
  | 'hr'     // 人力人事
  | 'fin'    // 财务费控
  | 'dev'    // 项目研发
  | 'svc'    // 客服营销
  | 'bi'     // 数据分析
  | 'sign';  // 合同签署

export type Scale = 1 | 2 | 3 | 4;        // 1=20人以下 2=20-100 3=100-500 4=500以上
export type Deploy = 'saas' | 'both';     // both = 支持私有化部署
export type Region = 'cn' | 'global';     // 数据主要合规区域
export type Level = 1 | 2 | 3 | 4;        // 价格档
export type Effort = 1 | 2 | 3;           // 上手难度

export interface Product {
  id: string;
  name: string;
  vendor: string;
  scenes: SceneKey[];
  scales: Scale[];
  deploy: Deploy;
  region: Region;
  price: Level;
  effort: Effort;
  desc: string;
  updatedAt: string;
}

/** rawfile 顶层结构 */
export interface ProductFile {
  schema: number;
  updatedAt: string;
  products: Product[];
}

/** 用户对部署方式的要求 */
export type DeployNeed = 'private' | 'saas' | 'any';
/** 用户对数据合规的要求 */
export type RegionNeed = 'cn' | 'overseas' | 'none';

/**
 * 用户作答。未作答的字段为 null，用于在打分时走"未答"分支。
 * scenes 为空数组表示首题未作答。
 */
export interface Answers {
  scenes: SceneKey[];        // Q1 多选
  scale: Scale | null;       // Q2
  deploy: DeployNeed | null; // Q3
  region: RegionNeed | null; // Q4
  budget: Level | null;      // Q5
}

export function emptyAnswers(): Answers {
  return { scenes: [], scale: null, deploy: null, region: null, budget: null };
}

/** 匹配理由标签，kind 决定颜色 */
export interface ReasonTag {
  text: string;
  kind: 'good' | 'hint'; // good=正向(绿) hint=提示(灰)
}

/** 单个产品的打分结果 */
export interface Scored {
  product: Product;
  score: number;       // 0-100
  reasons: ReasonTag[];
}

/** 一次匹配的完整结果 */
export interface MatchResult {
  ranked: Scored[];    // 存活产品，已按分数降序、同分按名称排序
  excluded: number;    // 被硬性条件排除的产品数量
  total: number;       // 数据集中的产品总数
}
