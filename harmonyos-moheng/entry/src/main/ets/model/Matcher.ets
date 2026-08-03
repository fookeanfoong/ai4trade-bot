/**
 * 匹配算法（满分 100）。
 *
 * 先做硬性排除（§3.1），再对存活项加权打分（§3.2），
 * 打分过程中收集理由标签（§3.3）。
 *
 * 算法规则集中在本文件，UI 层不得复制其中任何规则。
 */
import { Answers, Product, Scored, ReasonTag, MatchResult, SceneKey, Scale } from './Types';
import { SCENE_NAME, SCALE_TAG } from './Meta';

/** 两个场景数组是否有交集 */
function intersect(a: SceneKey[], b: SceneKey[]): SceneKey[] {
  const out: SceneKey[] = [];
  for (const s of a) {
    if (b.indexOf(s) >= 0) {
      out.push(s);
    }
  }
  return out;
}

function maxScale(scales: Scale[]): number {
  let m = 0;
  for (const s of scales) {
    if (s > m) {
      m = s;
    }
  }
  return m;
}

/** 硬性排除：任一命中则该产品不进入结果 */
function isExcluded(p: Product, a: Answers): boolean {
  // 场景：用户选了场景，且产品 scenes 与之无交集
  if (a.scenes.length > 0 && intersect(p.scenes, a.scenes).length === 0) {
    return true;
  }
  // 部署：用户选“需要私有化”，且产品 deploy !== 'both'
  if (a.deploy === 'private' && p.deploy !== 'both') {
    return true;
  }
  // 合规：用户选“纯国内业务”，且产品 region !== 'cn'
  if (a.region === 'cn' && p.region !== 'cn') {
    return true;
  }
  return false;
}

/** 场景维度（满分 35） */
function scoreScene(p: Product, a: Answers): number {
  if (a.scenes.length === 0) {
    return 25; // 未答
  }
  const hits = intersect(p.scenes, a.scenes).length;
  const denom = Math.min(a.scenes.length, 2);
  return 35 * Math.min(1, hits / denom);
}

/** 规模维度（满分 25） */
function scoreScale(p: Product, a: Answers): number {
  if (a.scale === null) {
    return 18; // 未答
  }
  const s = a.scale;
  if (p.scales.indexOf(s) >= 0) {
    return 25; // 命中区间
  }
  if (p.scales.indexOf((s - 1) as Scale) >= 0 || p.scales.indexOf((s + 1) as Scale) >= 0) {
    return 12; // 相邻区间
  }
  return 2;
}

/** 部署维度（满分 15） */
function scoreDeploy(p: Product, a: Answers): number {
  // 明确要求（private / saas）且满足 → 15；都行 / 未答 → 11
  if (a.deploy === 'private') {
    return 15; // 存活产品必为 both，已满足
  }
  if (a.deploy === 'saas') {
    return 15; // 所有产品均提供云端，已满足
  }
  return 11; // 'any' 或未答
}

/** 合规维度（满分 10） */
function scoreRegion(p: Product, a: Answers): number {
  if (a.region === null || a.region === 'none') {
    return 8; // 无要求
  }
  if (a.region === 'cn') {
    return 10; // 存活产品必为 cn，明确要求且满足
  }
  // 有海外业务
  if (p.region === 'global') {
    return 10; // 明确要求且满足
  }
  return 5; // 有海外业务但产品数据在境内
}

/** 预算维度（满分 15） */
function scoreBudget(p: Product, a: Answers): number {
  if (a.budget === null) {
    return 10; // 未答
  }
  const b = a.budget;
  if (p.price <= b) {
    return 15;
  }
  if (p.price === b + 1) {
    return 7; // 超 1 档
  }
  return 1; // 超 2 档及以上
}

/** 收集理由标签，正向在前、提示在后，最多 4 个且提示不省略 */
function buildReasons(p: Product, a: Answers): ReasonTag[] {
  const good: ReasonTag[] = [];
  const hint: ReasonTag[] = [];

  // 命中的场景名
  if (a.scenes.length > 0) {
    for (const s of intersect(p.scenes, a.scenes)) {
      good.push({ text: SCENE_NAME[s], kind: 'good' });
    }
  }
  // 规模适配 / 撑不住规模
  if (a.scale !== null) {
    if (p.scales.indexOf(a.scale) >= 0) {
      good.push({ text: `${SCALE_TAG[a.scale]}适配`, kind: 'good' });
    } else if (a.scale > maxScale(p.scales)) {
      hint.push({ text: '可能撑不住规模', kind: 'hint' });
    }
    // 偏重、可能过度：需实施顾问的重产品，用于小体量团队
    if (p.effort === 3 && a.scale <= 2) {
      hint.push({ text: '偏重，可能过度', kind: 'hint' });
    }
  }
  // 支持私有化
  if (a.deploy === 'private' && p.deploy === 'both') {
    good.push({ text: '支持私有化', kind: 'good' });
  }
  // 数据合规
  if (p.region === 'cn' && a.region !== 'overseas') {
    good.push({ text: '数据在境内', kind: 'good' });
  } else if (p.region === 'global' && a.region === 'overseas') {
    good.push({ text: '全球可用', kind: 'good' });
  }
  // 预算
  if (a.budget !== null) {
    if (p.price <= a.budget) {
      good.push({ text: '在预算内', kind: 'good' });
    } else if (p.price === a.budget + 1) {
      hint.push({ text: '略超预算', kind: 'hint' });
    } else {
      hint.push({ text: '明显超预算', kind: 'hint' });
    }
  }

  // 最多 4 个：优先保留全部提示，其余名额给正向
  const cap = 4;
  const room = Math.max(0, cap - hint.length);
  const out: ReasonTag[] = good.slice(0, room).concat(hint);
  return out.slice(0, cap);
}

/** 对单个存活产品打分 */
export function scoreProduct(p: Product, a: Answers): Scored {
  const raw = scoreScene(p, a) + scoreScale(p, a) + scoreDeploy(p, a) + scoreRegion(p, a) + scoreBudget(p, a);
  return { product: p, score: Math.round(raw), reasons: buildReasons(p, a) };
}

/** 完整匹配：排除 → 打分 → 排序 */
export function match(products: Product[], a: Answers): MatchResult {
  const survivors: Product[] = [];
  let excluded = 0;
  for (const p of products) {
    if (isExcluded(p, a)) {
      excluded++;
    } else {
      survivors.push(p);
    }
  }
  const ranked: Scored[] = survivors.map((p) => scoreProduct(p, a));
  // 分数降序，同分按产品名 localeCompare(zh) 稳定排序
  ranked.sort((x, y) => {
    if (y.score !== x.score) {
      return y.score - x.score;
    }
    return x.product.name.localeCompare(y.product.name, 'zh-Hans-CN');
  });
  return { ranked, excluded, total: products.length };
}

/**
 * 收敛条用的每款产品当前状态。
 * 未被排除的产品按分数映射条高 5–34px；被排除的固定 2px 并降透明度。
 */
export interface PoolBarItem {
  id: string;
  alive: boolean;
  height: number;  // px
  opacity: number;
}

const BAR_MIN = 5;
const BAR_MAX = 34;
const BAR_DEAD = 2;

/**
 * 计算收敛条。products 顺序固定（不重排），逐款判断存活并映射条高。
 * 分数区间按存活集合内的 min/max 归一，让收敛过程更可见。
 */
export function poolBar(products: Product[], a: Answers): PoolBarItem[] {
  // 先算存活产品的分数用于归一
  const scores: Map<string, number> = new Map();
  let lo = Number.POSITIVE_INFINITY;
  let hi = Number.NEGATIVE_INFINITY;
  for (const p of products) {
    if (!isExcluded(p, a)) {
      const s = scoreProduct(p, a).score;
      scores.set(p.id, s);
      if (s < lo) {
        lo = s;
      }
      if (s > hi) {
        hi = s;
      }
    }
  }
  const span = hi - lo;
  return products.map((p) => {
    const s = scores.get(p.id);
    if (s === undefined) {
      // 被排除
      return { id: p.id, alive: false, height: BAR_DEAD, opacity: 0.16 } as PoolBarItem;
    }
    const t = span > 0 ? (s - lo) / span : 1;
    const height = Math.round(BAR_MIN + t * (BAR_MAX - BAR_MIN));
    return { id: p.id, alive: true, height, opacity: 1 } as PoolBarItem;
  });
}

/** 存活数量 */
export function aliveCount(products: Product[], a: Answers): number {
  let n = 0;
  for (const p of products) {
    if (!isExcluded(p, a)) {
      n++;
    }
  }
  return n;
}
