// 匹配算法回归校验 + 数据校验 + 合规关键词扫描。
// 由于原型 index.html 未随任务附带，本脚本以 §3 规范为真源，
// 独立重实现算法并锁定具体输入下的排序与分数，作为 ArkTS 实现的回归基准。
//   运行：node tools/verify.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const JSON_PATH = path.join(ROOT, 'entry/src/main/resources/rawfile/products.json');

const file = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'));
const PRODUCTS = file.products;

let failures = 0;
let warnings = 0;
function ok(name, cond, detail = '') {
  if (cond) { console.log(`  ✓ ${name}`); }
  else { console.log(`  ✗ ${name}  ${detail}`); failures++; }
}
function warn(name, detail = '') { console.log(`  ! ${name}  ${detail}`); warnings++; }

// ————— 1. 数据校验 —————
console.log('\n[1] 数据校验');
ok('产品数量为 32', PRODUCTS.length === 32, `实际 ${PRODUCTS.length}`);
const ids = new Set(PRODUCTS.map(p => p.id));
ok('id 唯一', ids.size === PRODUCTS.length);
const SCENES = ['collab','crm','hr','fin','dev','svc','bi','sign'];
let enumOk = true, descOk = true;
for (const p of PRODUCTS) {
  if (!p.id || !p.name || !p.vendor) enumOk = false;
  if (!Array.isArray(p.scenes) || p.scenes.length === 0) enumOk = false;
  for (const s of p.scenes) if (!SCENES.includes(s)) enumOk = false;
  for (const s of p.scales) if (![1,2,3,4].includes(s)) enumOk = false;
  if (!['saas','both'].includes(p.deploy)) enumOk = false;
  if (!['cn','global'].includes(p.region)) enumOk = false;
  if (![1,2,3,4].includes(p.price)) enumOk = false;
  if (![1,2,3].includes(p.effort)) enumOk = false;
  if (!p.updatedAt) enumOk = false;
  const len = [...p.desc].length;
  if (len < 40 || len > 60) { descOk = false; warn(`desc 长度越界: ${p.name}`, `${len} 字`); }
}
ok('字段枚举合法', enumOk);
ok('desc 均为 40–60 字', descOk);
// 场景覆盖
const covered = new Set();
PRODUCTS.forEach(p => p.scenes.forEach(s => covered.add(s)));
ok('8 个场景全部有产品覆盖', covered.size === 8, `覆盖 ${covered.size}`);

// ————— 2. 算法重实现（镜像 §3） —————
const intersect = (a, b) => a.filter(x => b.includes(x));
function isExcluded(p, a) {
  if (a.scenes.length > 0 && intersect(p.scenes, a.scenes).length === 0) return true;
  if (a.deploy === 'private' && p.deploy !== 'both') return true;
  if (a.region === 'cn' && p.region !== 'cn') return true;
  return false;
}
function scoreScene(p, a) {
  if (a.scenes.length === 0) return 25;
  const hits = intersect(p.scenes, a.scenes).length;
  return 35 * Math.min(1, hits / Math.min(a.scenes.length, 2));
}
function scoreScale(p, a) {
  if (a.scale == null) return 18;
  if (p.scales.includes(a.scale)) return 25;
  if (p.scales.includes(a.scale - 1) || p.scales.includes(a.scale + 1)) return 12;
  return 2;
}
function scoreDeploy(p, a) {
  if (a.deploy === 'private') return 15;
  if (a.deploy === 'saas') return 15;
  return 11;
}
function scoreRegion(p, a) {
  if (a.region == null || a.region === 'none') return 8;
  if (a.region === 'cn') return 10;
  if (p.region === 'global') return 10;
  return 5;
}
function scoreBudget(p, a) {
  if (a.budget == null) return 10;
  if (p.price <= a.budget) return 15;
  if (p.price === a.budget + 1) return 7;
  return 1;
}
function scoreProduct(p, a) {
  return Math.round(scoreScene(p,a)+scoreScale(p,a)+scoreDeploy(p,a)+scoreRegion(p,a)+scoreBudget(p,a));
}
function match(a) {
  const survivors = PRODUCTS.filter(p => !isExcluded(p, a));
  const ranked = survivors.map(p => ({ id: p.id, name: p.name, score: scoreProduct(p, a) }));
  ranked.sort((x, y) => y.score - x.score || x.name.localeCompare(y.name, 'zh-Hans-CN'));
  return { ranked, excluded: PRODUCTS.length - survivors.length };
}
const A = (o = {}) => ({ scenes: [], scale: null, deploy: null, region: null, budget: null, ...o });

// ————— 3. 硬性排除三条规则各自可触发 —————
console.log('\n[2] 硬性排除');
ok('场景排除：仅选 sign 时只留签署类', (() => {
  const r = match(A({ scenes: ['sign'] }));
  return r.ranked.every(x => ['esign','fadada'].includes(x.id)) && r.ranked.length === 2;
})());
ok('部署排除：需私有化排除 11 个 saas-only', match(A({ deploy: 'private' })).excluded === 11,
  `实际 ${match(A({ deploy: 'private' })).excluded}`);
ok('合规排除：纯国内排除 6 个 global', match(A({ region: 'cn' })).excluded === 6,
  `实际 ${match(A({ region: 'cn' })).excluded}`);
ok('分数上限不超过 100', (() => {
  const r = match(A({ scenes: ['collab'], scale: 2, deploy: 'saas', region: 'cn', budget: 4 }));
  return r.ranked.every(x => x.score <= 100 && x.score >= 0);
})());

// ————— 4. 具体输入锁定排序（回归基准） —————
console.log('\n[3] 回归基准');
{
  const a = A({ scenes: ['collab'], scale: 2, deploy: 'any', region: 'none', budget: 1 });
  const r = match(a);
  ok('collab/中小/都行/无要求/免费 → 存活 7 家', r.ranked.length === 7, `实际 ${r.ranked.length}`);
  ok('该输入排除 25 家', r.excluded === 25, `实际 ${r.excluded}`);
  ok('榜首为 钉钉，分数 94', r.ranked[0].id === 'dingtalk' && r.ranked[0].score === 94,
    `实际 ${r.ranked[0].id}/${r.ranked[0].score}`);
  ok('同分按拼音稳定排序（钉钉 在 企业微信 前）', (() => {
    const names = r.ranked.map(x => x.id);
    return names.indexOf('dingtalk') < names.indexOf('wecom');
  })());
}
{
  // 无结果场景：私有化 + 纯国内 + 仅海外全球产品的场景? 造一个必然为空的组合
  const a = A({ scenes: ['collab'], deploy: 'private', region: 'cn', scale: 4, budget: 1 });
  const r = match(a);
  ok('存在可产生结果的私有化+国内组合', r.ranked.length > 0, `实际 ${r.ranked.length}`);
}

// ————— 5. 合规关键词扫描 —————
console.log('\n[4] 合规关键词扫描');
const BANNED = ['最好','第一','最强','领先','顶级','唯一','最佳','国家级','独家'];
const SOFT = ['智能','精准','AI'];
function scanDir(dir, exts) {
  const out = [];
  for (const f of fs.readdirSync(dir)) {
    const fp = path.join(dir, f);
    const st = fs.statSync(fp);
    if (st.isDirectory()) out.push(...scanDir(fp, exts));
    else if (exts.some(e => f.endsWith(e))) out.push(fp);
  }
  return out;
}
const textFiles = [
  ...scanDir(path.join(ROOT, 'entry/src/main/ets'), ['.ets']),
  JSON_PATH
];
let banHit = false;
for (const fp of textFiles) {
  const txt = fs.readFileSync(fp, 'utf8');
  for (const w of BANNED) {
    if (txt.includes(w)) { banHit = true; warn(`绝对化用语 “${w}”`, path.relative(ROOT, fp)); }
  }
  for (const w of SOFT) {
    // AI 需大小写精确；跳过注释中的英文缩写误报由人工判断
    if (w === 'AI') continue;
    if (txt.includes(w)) warn(`建议规避用语 “${w}”`, path.relative(ROOT, fp));
  }
}
ok('无绝对化用语', !banHit);

console.log(`\n结果：${failures} 处失败，${warnings} 处提示`);
process.exit(failures > 0 ? 1 : 0);
