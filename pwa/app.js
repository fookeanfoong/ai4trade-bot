// ============================================================================
// AI4Trade Signals — 前端逻辑(纯客户端 MVP,无后端)
// 数据源: config.js + data/signals.json;状态存 localStorage。
// ⚠️ 试用/订阅状态存在浏览器本地,懂技术的人可绕过。正式放量前请接后端校验
//    (见 README 的「上线加固」)。作为最小可行产品验证需求,这样足够。
// ============================================================================
const CFG = window.APP_CONFIG;
const KEY = 'a4t_state_v1';
const $ = (sel, el = document) => el.querySelector(sel);
const fmt$ = (n) => '$' + (Math.round(n * 100) / 100).toLocaleString('en-US');
const pct = (n) => (n * 100).toFixed(1) + '%';

// —— 状态 ——
function loadState() {
  try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; }
}
function saveState(s) { localStorage.setItem(KEY, JSON.stringify(s)); }
let state = loadState();

// —— 纽约时间 / 交易日 ——
function ny() {
  const now = new Date();
  const dateStr = now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' }); // YYYY-MM-DD
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(now);
  const get = (t) => parts.find((p) => p.type === t)?.value;
  const wd = get('weekday');
  const minutes = parseInt(get('hour')) * 60 + parseInt(get('minute'));
  const isWeekday = !['Sat', 'Sun'].includes(wd);
  const isOpen = isWeekday && minutes >= 570 && minutes < 960; // 9:30–16:00 ET
  return { dateStr, wd, minutes, isWeekday, isOpen };
}

// —— 订阅 / 试用 ——
function isSubscribed() {
  return !!(state.sub && state.sub.plan);
}
// 首个使用日免费;之后必须订阅。
function accessAllowed() {
  if (isSubscribed()) return true;
  const today = ny().dateStr;
  if (!state.trialDate) return true;          // 还没开始试用
  return state.trialDate === today;           // 仍在首个使用日
}
function startTrialIfNeeded() {
  if (!state.trialDate && !isSubscribed()) {
    state.trialDate = ny().dateStr;
    saveState(state);
  }
}

// —— 支付回跳: ?paid=monthly|yearly ——
function handlePaymentReturn() {
  const p = new URLSearchParams(location.search).get('paid');
  if (p === 'monthly' || p === 'yearly') {
    state.sub = { plan: p, since: ny().dateStr };
    state.everBought = true; // 首购折扣仅一次
    saveState(state);
    history.replaceState({}, '', location.pathname);
    toast('订阅成功,已解锁 🎉');
  }
}
function priceFor(plan, firstBuy) {
  const base = CFG.pricing[plan];
  return firstBuy ? Math.round(base * (1 - CFG.pricing.firstBuyDiscount) * 100) / 100 : base;
}
function payLink(plan) {
  const firstBuy = !state.everBought;
  const key = plan + (firstBuy ? 'First' : '');
  return CFG.paymentLinks[key] || CFG.paymentLinks[plan];
}

// —— 仓位建议算法 ——
function computePlan(signals) {
  const cap = Number(state.capital) || 0;
  const target = Number(state.dailyTarget) || 0;
  const tradable = signals
    .filter((s) => s.tradable)
    .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
    .slice(0, CFG.risk.maxNames);

  if (!tradable.length || cap <= 0) return { tradable: [], items: [], cap, target };

  const avgT1 = tradable.reduce((a, s) => a + (s.t1_pct || 0), 0) / tradable.length || 0.03;
  const neededCap = target > 0 && avgT1 > 0 ? target / avgT1 : cap;
  const maxDeploy = cap * CFG.risk.maxDeployPct;
  const deploy = Math.min(neededCap, maxDeploy);
  const tooAggressive = neededCap > maxDeploy + 1e-6;

  const capPer = cap * CFG.risk.perNameCapPct;
  const totalW = tradable.reduce((a, s) => a + (s.confidence || 0.6), 0);
  let capped = false;
  const items = tradable.map((s) => {
    let alloc = deploy * ((s.confidence || 0.6) / totalW);
    if (alloc > capPer) { alloc = capPer; capped = true; }
    const shares = s.ref_price ? alloc / s.ref_price : null; // 允许零股/碎股
    return {
      sig: s, alloc,
      shares,
      potential: alloc * (s.t1_pct || 0),
      risk: alloc * (s.stop_pct || 0),
    };
  });
  const totalDeploy = items.reduce((a, i) => a + i.alloc, 0);
  const totalPotential = items.reduce((a, i) => a + i.potential, 0);
  const totalRisk = items.reduce((a, i) => a + i.risk, 0);
  return { tradable, items, cap, target, deploy: totalDeploy, totalPotential, totalRisk, tooAggressive, capped };
}

// —— 数据 ——
let FEED = null;
async function loadFeed() {
  if (FEED) return FEED;
  const res = await fetch(CFG.feedUrl, { cache: 'no-store' });
  FEED = await res.json();
  return FEED;
}

// ============================================================================
// 视图
// ============================================================================
const view = $('#view');
let currentTab = 'today';

function esc(s) { return String(s ?? '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }

function renderOnboarding() {
  $('#tabbar').hidden = true;
  $('#statusChip').hidden = true;
  view.innerHTML = `
    <div class="hero">
      <div class="logo">📈</div>
      <h1>${esc(CFG.brand)}</h1>
      <p class="muted">${esc(CFG.tagline)}</p>
    </div>
    <div class="card">
      <h2>先告诉我两件事</h2>
      <p class="small muted">用来推算「今天建议投多少、买哪几只」。可随时在「我的计划」里改。</p>
      <label>你可用于交易的本金</label>
      <div class="field-suffix">
        <input id="capital" type="number" inputmode="decimal" min="0" placeholder="例如 1000" value="${state.capital || ''}" />
        <span class="suf">USD</span>
      </div>
      <label>你今天想赚多少(目标,非保证)</label>
      <div class="field-suffix">
        <input id="target" type="number" inputmode="decimal" min="0" placeholder="例如 30" value="${state.dailyTarget || ''}" />
        <span class="suf">USD</span>
      </div>
      <button class="btn primary" id="startBtn">开始 · 首个交易日免费</button>
    </div>
    <div class="disclaimer">
      <b>风险提示</b>:本产品的信号由一个<b>模拟</b>交易机器人根据公开新闻与行情自动生成,
      <b>仅供学习/研究参考,不构成投资建议,也不承诺任何收益</b>。
      股票交易可能导致本金亏损,「今天想赚多少」只是用于计算仓位的目标,不代表你会赚到。
      是否操作、如何操作,请你自行判断并自负盈亏。继续即表示你已理解并同意。
    </div>`;
  $('#startBtn').onclick = () => {
    const c = parseFloat($('#capital').value);
    const t = parseFloat($('#target').value);
    if (!(c > 0)) return toast('请填写有效的本金');
    if (!(t > 0)) return toast('请填写今天的目标金额');
    state.capital = c; state.dailyTarget = t; state.onboarded = true; state.acknowledgedRisk = true;
    saveState(state);
    currentTab = 'today';
    render();
  };
}

function signalCard(item, locked) {
  const s = item.sig;
  const dirCls = s.direction === 'bearish' ? 'bear' : 'bull';
  const dirTxt = s.direction === 'bearish' ? '看跌 ▼' : '看涨 ▲';
  const demo = s.demo ? '<span class="tag demo">示例</span>' : '';
  const recheck = s.preopen_recheck ? '<span class="tag">开盘前需复核</span>' : '';
  const allocBlock = locked ? '' : `
    <div class="alloc">
      <div><div class="small muted">建议投入</div><div class="amt">${fmt$(item.alloc)}</div></div>
      <div class="center"><div class="small muted">若达一档 (+${pct(s.t1_pct)})</div><div class="v up" style="color:var(--up);font-weight:800">${fmt$(item.potential)}</div></div>
      ${item.shares != null ? `<div class="center"><div class="small muted">约</div><div style="font-weight:800">${item.shares >= 1 ? item.shares.toFixed(2) : item.shares.toFixed(3)} 股</div></div>` : ''}
    </div>`;
  return `
    <div class="card sig">
      <div class="head">
        <span class="ticker">${esc(s.ticker)}</span>
        <span class="dir ${dirCls}">${dirTxt}</span>
        ${demo} ${recheck}
      </div>
      <div class="conf-wrap">
        <div class="row spread small muted"><span>信心度</span><span>${Math.round((s.confidence || 0) * 100)}% · ${esc(s.timeframe || '')}</span></div>
        <div class="conf-bar"><div class="conf-fill" style="width:${Math.round((s.confidence || 0) * 100)}%"></div></div>
      </div>
      <div class="metrics">
        <div class="metric"><div class="k">止损</div><div class="v down">-${pct(s.stop_pct)}</div></div>
        <div class="metric"><div class="k">目标一</div><div class="v up">+${pct(s.t1_pct)}</div></div>
        <div class="metric"><div class="k">目标二</div><div class="v up">+${pct(s.t2_pct)}</div></div>
      </div>
      ${allocBlock}
      <div class="reason clamp" onclick="this.classList.toggle('clamp')">${esc(s.reasoning)}</div>
    </div>`;
}

async function renderToday() {
  $('#tabbar').hidden = false;
  const feed = await loadFeed().catch(() => null);
  const t = ny();
  const sub = isSubscribed();
  $('#statusChip').hidden = false;
  $('#statusChip').textContent = sub ? (state.sub.plan === 'yearly' ? '年度会员' : '月度会员')
    : (accessAllowed() ? '免费试用中' : '试用已结束');
  $('#statusChip').onclick = () => { currentTab = 'account'; render(); };

  if (!feed || !feed.signals) {
    view.innerHTML = `<div class="card center muted">暂时无法加载今日信号,稍后再试。</div>`;
    return;
  }

  // 市场/日期状态条
  const marketTxt = t.isOpen ? '🟢 美股开盘中' : (t.isWeekday ? '🌙 盘前/盘后' : '💤 周末休市');
  const validTxt = feed.valid_for ? `信号适用日:${feed.valid_for}` : '';
  const staleWarn = feed.valid_for && feed.valid_for < t.dateStr
    ? `<div class="disclaimer" style="border-color:rgba(239,68,68,.4);background:rgba(239,68,68,.06)"><b style="color:var(--down)">信号可能已过期</b>:当前显示的是 ${esc(feed.valid_for)} 的信号,请等机器人开盘前刷新后再参考。</div>` : '';

  startTrialIfNeeded();
  const allowed = accessAllowed();
  const plan = computePlan(feed.signals);

  // 顶部「今日计划」摘要
  let summary = '';
  if (plan.tradable.length) {
    summary = `
      <div class="card">
        <div class="row spread"><h2>今日计划</h2><span class="small muted">${marketTxt}</span></div>
        <div class="metrics" style="grid-template-columns:repeat(3,1fr)">
          <div class="metric"><div class="k">建议投入</div><div class="v">${allowed ? fmt$(plan.deploy) : '🔒'}</div></div>
          <div class="metric"><div class="k">目标(非保证)</div><div class="v up">${allowed ? '+' + fmt$(plan.totalPotential) : '🔒'}</div></div>
          <div class="metric"><div class="k">最大风险</div><div class="v down">${allowed ? '-' + fmt$(plan.totalRisk) : '🔒'}</div></div>
        </div>
        <div class="small muted">本金 ${fmt$(plan.cap)} · 目标 ${fmt$(plan.target)}/日 ·
        ${plan.tooAggressive ? '<b style="color:var(--gold)">目标偏高,已按你的本金上限压缩仓位</b>' : '仓位已按风控上限分配'}。
        「最大风险」= 全部触及止损时的估算亏损。</div>
      </div>`;
  } else {
    summary = `<div class="card center"><h2>今天没有达标信号</h2><p class="muted small">机器人没找到信心度足够的机会 —— 空仓也是一种决定。明天开盘前再来看。</p></div>`;
  }

  const cards = plan.items.map((it) => signalCard(it, !allowed)).join('');

  let gate = '';
  if (!allowed) {
    gate = `
      <div class="card lock-overlay">
        <div style="font-size:32px">🔒</div>
        <h2>免费试用已结束</h2>
        <p class="muted small">订阅后可继续查看每个交易日的信号与仓位建议。</p>
        <button class="btn gold" onclick="go('account')">查看订阅方案</button>
      </div>`;
  }

  view.innerHTML = `
    ${staleWarn}
    ${summary}
    ${!allowed ? gate : ''}
    <div class="${allowed ? '' : 'locked'}">${cards}</div>
    <div class="disclaimer">${esc(feed.disclaimer || '')}</div>
    <div class="note">数据更新:${esc(feed.updated_at || '—')} · ${esc(validTxt)}</div>`;
}

function renderPlan() {
  $('#tabbar').hidden = false;
  view.innerHTML = `
    <div class="card">
      <h2>我的计划</h2>
      <p class="small muted">改这两个数,今日信号页的「建议投入」会跟着变。</p>
      <label>可用本金</label>
      <div class="field-suffix">
        <input id="capital2" type="number" inputmode="decimal" min="0" value="${state.capital || ''}" />
        <span class="suf">USD</span>
      </div>
      <label>每日目标(非保证)</label>
      <div class="field-suffix">
        <input id="target2" type="number" inputmode="decimal" min="0" value="${state.dailyTarget || ''}" />
        <span class="suf">USD</span>
      </div>
      <button class="btn primary" id="saveBtn">保存</button>
    </div>
    <div class="card">
      <h2>仓位是怎么算的?</h2>
      <ul class="list">
        <li>按「目标 ÷ 平均目标一涨幅」估算需要投入多少,再用你的本金封顶。</li>
        <li>单只票最多占本金 ${Math.round(CFG.risk.perNameCapPct * 100)}%,一天最多 ${CFG.risk.maxNames} 只,分散风险。</li>
        <li>信心度越高的信号分到越多仓位。</li>
        <li>这是「参考仓位」,不是下单指令 —— 最终由你决定。</li>
      </ul>
    </div>`;
  $('#saveBtn').onclick = () => {
    const c = parseFloat($('#capital2').value), t = parseFloat($('#target2').value);
    if (!(c > 0) || !(t > 0)) return toast('请填写有效数值');
    state.capital = c; state.dailyTarget = t; saveState(state);
    toast('已保存'); go('today');
  };
}

function renderAccount() {
  $('#tabbar').hidden = false;
  const sub = isSubscribed();
  const firstBuy = !state.everBought;
  const mPrice = priceFor('monthly', firstBuy);
  const yPrice = priceFor('yearly', firstBuy);
  const saveTag = firstBuy ? `<span class="badge-save">首购 -${Math.round(CFG.pricing.firstBuyDiscount * 100)}%</span>` : '';

  const status = sub ? `
    <div class="card">
      <h2>${state.sub.plan === 'yearly' ? '年度会员' : '月度会员'} ✅</h2>
      <p class="small muted">开通于 ${esc(state.sub.since)}。可随时在 Stripe 邮件收据里管理或取消订阅。</p>
      <button class="btn outline" onclick="signOutSub()">退出/切换账户(清除本机订阅状态)</button>
    </div>` : '';

  const plans = sub ? '' : `
    <div class="card">
      <h2>选择订阅方案 ${saveTag}</h2>
      <p class="small muted">免费试用仅限首个交易日。订阅后每个交易日都能看信号与仓位建议。</p>
      <div class="plans">
        <div class="plan">
          <div class="row spread"><b>月付</b><div class="per">按月续订</div></div>
          <div class="price">${firstBuy ? `<s>${fmt$(CFG.pricing.monthly)}</s>` : ''}${fmt$(mPrice)}<span class="per"> / 月</span></div>
          <button class="btn primary" onclick="subscribe('monthly')">选月付</button>
        </div>
        <div class="plan best">
          <div class="row spread"><b>年付</b><span class="badge-save">省 ${fmt$(CFG.pricing.monthly * 12 - CFG.pricing.yearly)}</span></div>
          <div class="price">${firstBuy ? `<s>${fmt$(CFG.pricing.yearly)}</s>` : ''}${fmt$(yPrice)}<span class="per"> / 年</span></div>
          <div class="per">≈ ${fmt$(yPrice / 12)}/月</div>
          <button class="btn gold" onclick="subscribe('yearly')">选年付(更划算)</button>
        </div>
      </div>
      <p class="note">支付由 Stripe 处理,我们不接触你的卡号。</p>
    </div>`;

  view.innerHTML = `
    ${status}
    ${plans}
    <div class="card">
      <h2>账户</h2>
      <div class="row spread small"><span class="muted">本金</span><span>${fmt$(state.capital || 0)}</span></div>
      <div class="row spread small" style="margin-top:8px"><span class="muted">每日目标</span><span>${fmt$(state.dailyTarget || 0)}</span></div>
      <button class="btn outline" onclick="go('plan')">修改计划</button>
    </div>
    <div class="disclaimer">
      <b>再次提醒</b>:所有信号仅供参考与学习,不构成投资建议,不承诺收益,交易风险自负。
      本产品与你所用的券商、交易所无隶属关系。
    </div>
    <div class="note">${esc(CFG.brand)} · 纯客户端 MVP</div>`;
}

// —— 全局动作(供 onclick 调用)——
window.go = (tab) => { currentTab = tab; render(); };
window.subscribe = (plan) => {
  const link = payLink(plan);
  if (!link || link.startsWith('REPLACE_')) {
    toast('支付链接还没配置(见 config.js)');
    return;
  }
  location.href = link;
};
window.signOutSub = () => {
  if (!confirm('确定清除本机订阅状态?(不会取消 Stripe 上的实际订阅)')) return;
  delete state.sub; saveState(state); toast('已清除'); render();
};

// —— toast ——
let toastTimer;
function toast(msg) {
  let el = $('.toast');
  if (!el) { el = document.createElement('div'); el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
}

// —— 路由 ——
function render() {
  $('#brandName').textContent = CFG.brand;
  if (!state.onboarded) return renderOnboarding();
  document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === currentTab));
  if (currentTab === 'today') return renderToday();
  if (currentTab === 'plan') return renderPlan();
  if (currentTab === 'account') return renderAccount();
}

document.querySelectorAll('.tab').forEach((b) => {
  b.onclick = () => { currentTab = b.dataset.tab; render(); };
});

// —— 启动 ——
handlePaymentReturn();
render();

// —— Service Worker(PWA 离线外壳)——
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js').catch(() => {});
}
