// ============================================================================
// AI4Trade Signals — 前端逻辑(纯客户端 MVP,无后端)
// 数据源: config.js + data/signals.json;状态存 localStorage;文案走 i18n.js。
// ⚠️ 试用/订阅状态存在浏览器本地,懂技术的人可绕过。正式放量前请接后端校验。
// ============================================================================
const CFG = window.APP_CONFIG;
const T = window.I18N.t;                       // 取词(默认英语)
const SHORT = { en: 'EN', zh: '中', 'zh-TW': '繁', ja: '日', de: 'DE' };
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
  const dateStr = now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(now);
  const get = (k) => parts.find((p) => p.type === k)?.value;
  const wd = get('weekday');
  const minutes = parseInt(get('hour')) * 60 + parseInt(get('minute'));
  const isWeekday = !['Sat', 'Sun'].includes(wd);
  const isOpen = isWeekday && minutes >= 570 && minutes < 960; // 9:30–16:00 ET
  return { dateStr, wd, minutes, isWeekday, isOpen };
}

// —— 订阅 / 试用 ——
function isSubscribed() { return !!(state.sub && state.sub.plan); }
function accessAllowed() {
  if (isSubscribed()) return true;
  const today = ny().dateStr;
  if (!state.trialDate) return true;
  return state.trialDate === today;
}
function startTrialIfNeeded() {
  if (!state.trialDate && !isSubscribed()) { state.trialDate = ny().dateStr; saveState(state); }
}

// —— 支付回跳: ?paid=monthly|yearly ——
function handlePaymentReturn() {
  const p = new URLSearchParams(location.search).get('paid');
  if (p === 'monthly' || p === 'yearly') {
    state.sub = { plan: p, since: ny().dateStr };
    state.everBought = true;
    saveState(state);
    history.replaceState({}, '', location.pathname);
    toast(T('pay_ok'));
  }
}
function priceFor(plan, firstBuy) {
  const base = CFG.pricing[plan];
  return firstBuy ? Math.round(base * (1 - CFG.pricing.firstBuyDiscount) * 100) / 100 : base;
}
// 首购折扣是否启用:需要 firstBuyDiscount>0 且用户还没买过。
function firstBuyActive() {
  return CFG.pricing.firstBuyDiscount > 0 && !state.everBought;
}
function payLink(plan) {
  const key = plan + (firstBuyActive() ? 'First' : '');
  return CFG.paymentLinks[key] || CFG.paymentLinks[plan]; // 打折链接为空时回退原价链接
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
    const shares = s.ref_price ? alloc / s.ref_price : null;
    return { sig: s, alloc, shares, potential: alloc * (s.t1_pct || 0), risk: alloc * (s.stop_pct || 0) };
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
      <p class="muted">${esc(T('tagline'))}</p>
    </div>
    <div class="card">
      <h2>${T('ob_title')}</h2>
      <p class="small muted">${T('ob_sub')}</p>
      <label>${T('ob_capital')}</label>
      <div class="field-suffix">
        <input id="capital" type="number" inputmode="decimal" min="0" placeholder="${T('ob_ph_capital')}" value="${state.capital || ''}" />
        <span class="suf">${T('usd')}</span>
      </div>
      <label>${T('ob_target')}</label>
      <div class="field-suffix">
        <input id="target" type="number" inputmode="decimal" min="0" placeholder="${T('ob_ph_target')}" value="${state.dailyTarget || ''}" />
        <span class="suf">${T('usd')}</span>
      </div>
      <button class="btn primary" id="startBtn">${T('ob_start')}</button>
    </div>
    <div class="disclaimer"><b>${T('risk_b')}</b>: ${T('risk_body')}</div>`;
  $('#startBtn').onclick = () => {
    const c = parseFloat($('#capital').value);
    const t = parseFloat($('#target').value);
    if (!(c > 0)) return toast(T('ob_err_capital'));
    if (!(t > 0)) return toast(T('ob_err_target'));
    state.capital = c; state.dailyTarget = t; state.onboarded = true; state.acknowledgedRisk = true;
    saveState(state);
    currentTab = 'today';
    render();
  };
}

// 信号分析文案:支持字符串,或 {en, zh, ...} 多语言对象(按当前语言取,回退英→中→任意)。
function reasoningText(s) {
  const r = s.reasoning;
  if (!r) return '';
  if (typeof r === 'string') return r;
  const lang = window.I18N.getLang();
  return r[lang] || r.en || r.zh || Object.values(r)[0] || '';
}

// 由方向 + 参考价 + 百分比，算出具体的买入/止损/目标价位。
function priceLevels(s) {
  const ref = s.ref_price;
  if (!ref) return null;
  const long = s.direction !== 'bearish';
  const mv = (p) => long ? ref * (1 + p) : ref * (1 - p);
  return { long, entry: ref, stop: long ? ref * (1 - s.stop_pct) : ref * (1 + s.stop_pct), t1: mv(s.t1_pct), t2: mv(s.t2_pct) };
}

function signalCard(item, locked) {
  const s = item.sig;
  const long = s.direction !== 'bearish';
  const dirCls = long ? 'bull' : 'bear';
  const dirTxt = long ? T('dir_long') : T('dir_short');
  const demo = s.demo ? `<span class="tag demo">${T('demo')}</span>` : '';
  const recheck = s.preopen_recheck ? `<span class="tag">${T('recheck')}</span>` : '';
  const entryWhen = s.entry_mode === 'market' ? T('entry_market') : (s.entry_mode ? esc(s.entry_mode) : T('entry_now'));

  const lv = priceLevels(s);
  const levelsBlock = lv ? `
    <div class="levels">
      <div class="lv"><span class="lab">${long ? T('lv_entry_long') : T('lv_entry_short')}</span>
        <span class="px" style="color:var(--accent)">${fmt$(lv.entry)}</span><span class="pc muted">${entryWhen}</span></div>
      <div class="lv"><span class="lab">${T('lv_stop')}</span>
        <span class="px" style="color:var(--down)">${fmt$(lv.stop)}</span><span class="pc down">${long ? '-' : '+'}${pct(s.stop_pct)}</span></div>
      <div class="lv"><span class="lab">${T('lv_t1')}</span>
        <span class="px" style="color:var(--up)">${fmt$(lv.t1)}</span><span class="pc up">${long ? '+' : '-'}${pct(s.t1_pct)}</span></div>
      <div class="lv"><span class="lab">${T('lv_t2')}</span>
        <span class="px" style="color:var(--up)">${fmt$(lv.t2)}</span><span class="pc up">${long ? '+' : '-'}${pct(s.t2_pct)}</span></div>
    </div>` : `
    <div class="metrics">
      <div class="metric"><div class="k">${T('m_stop')}</div><div class="v down">${long ? '-' : '+'}${pct(s.stop_pct)}</div></div>
      <div class="metric"><div class="k">${T('m_t1')}</div><div class="v up">${long ? '+' : '-'}${pct(s.t1_pct)}</div></div>
      <div class="metric"><div class="k">${T('m_t2')}</div><div class="v up">${long ? '+' : '-'}${pct(s.t2_pct)}</div></div>
    </div>`;

  const allocBlock = locked ? '' : `
    <div class="alloc">
      <div><div class="small muted">${T('a_deploy')}</div><div class="amt">${fmt$(item.alloc)}</div></div>
      ${item.shares != null ? `<div class="center"><div class="small muted">${T('a_shares')}</div><div style="font-weight:800">${item.shares >= 1 ? item.shares.toFixed(2) : item.shares.toFixed(3)} ${T('a_shares_unit')}</div></div>` : ''}
      <div class="center"><div class="small muted">${T('a_profit')}</div><div class="v up" style="color:var(--up);font-weight:800">${fmt$(item.potential)}</div></div>
    </div>`;

  return `
    <div class="card sig">
      <div class="head">
        <span class="ticker">${esc(s.ticker)}</span>
        <span class="dir ${dirCls}">${dirTxt}</span>
        ${demo} ${recheck}
      </div>
      <div class="conf-wrap">
        <div class="row spread small muted"><span>${T('confidence')}</span><span>${Math.round((s.confidence || 0) * 100)}% · ${T('hold', { tf: esc(s.timeframe || '') })}</span></div>
        <div class="conf-bar"><div class="conf-fill" style="width:${Math.round((s.confidence || 0) * 100)}%"></div></div>
      </div>
      ${levelsBlock}
      ${allocBlock}
      ${reasoningText(s) ? `<div class="reason clamp" onclick="this.classList.toggle('clamp')">${esc(reasoningText(s))}</div>` : ''}
    </div>`;
}

async function renderToday() {
  $('#tabbar').hidden = false;
  const feed = await loadFeed().catch(() => null);
  const t = ny();
  const sub = isSubscribed();
  $('#statusChip').hidden = false;
  $('#statusChip').textContent = sub ? (state.sub.plan === 'yearly' ? T('st_yearly') : T('st_monthly'))
    : (accessAllowed() ? T('st_trial') : T('st_trial_ended'));
  $('#statusChip').onclick = () => { currentTab = 'account'; render(); };

  if (!feed || !feed.signals) {
    view.innerHTML = `<div class="card center muted">${T('rec_none')}</div>`;
    return;
  }

  const marketTxt = t.isOpen ? T('mkt_open') : (t.isWeekday ? T('mkt_prepost') : T('mkt_closed'));
  const staleWarn = feed.valid_for && feed.valid_for < t.dateStr
    ? `<div class="disclaimer" style="border-color:rgba(239,68,68,.4);background:rgba(239,68,68,.06)"><b style="color:var(--down)">${T('stale_b')}</b>: ${T('stale_body', { date: esc(feed.valid_for) })}</div>` : '';

  startTrialIfNeeded();
  const allowed = accessAllowed();
  const plan = computePlan(feed.signals);

  let summary = '';
  if (plan.tradable.length) {
    summary = `
      <div class="card">
        <div class="row spread"><h2>${T('plan_title')}</h2><span class="small muted">${marketTxt}</span></div>
        <div class="metrics" style="grid-template-columns:repeat(3,1fr)">
          <div class="metric"><div class="k">${T('deploy')}</div><div class="v">${allowed ? fmt$(plan.deploy) : '🔒'}</div></div>
          <div class="metric"><div class="k">${T('target_ng')}</div><div class="v up">${allowed ? '+' + fmt$(plan.totalPotential) : '🔒'}</div></div>
          <div class="metric"><div class="k">${T('max_risk')}</div><div class="v down">${allowed ? '-' + fmt$(plan.totalRisk) : '🔒'}</div></div>
        </div>
        <div class="small muted">${T('plan_note', { cap: fmt$(plan.cap), target: fmt$(plan.target), sizing: plan.tooAggressive ? T('sizing_aggr') : T('sizing_ok') })}</div>
      </div>`;
  } else {
    summary = `<div class="card center"><h2>${T('no_sig_title')}</h2><p class="muted small">${T('no_sig_body')}</p></div>`;
  }

  const cards = plan.items.map((it) => signalCard(it, !allowed)).join('');

  let gate = '';
  if (!allowed) {
    gate = `
      <div class="card lock-overlay">
        <div style="font-size:32px">🔒</div>
        <h2>${T('gate_title')}</h2>
        <p class="muted small">${T('gate_body')}</p>
        <button class="btn gold" onclick="go('account')">${T('gate_cta')}</button>
      </div>`;
  }

  const validTail = feed.valid_for ? ` · ${T('valid_for', { date: esc(feed.valid_for) })}` : '';
  view.innerHTML = `
    ${staleWarn}
    ${summary}
    ${!allowed ? gate : ''}
    <div class="${allowed ? '' : 'locked'}">${cards}</div>
    <div class="disclaimer">${T('acc_disc')}</div>
    <div class="note">${T('feed_updated', { date: esc(feed.updated_at || '—') })}${validTail}</div>`;
}

function renderPlan() {
  $('#tabbar').hidden = false;
  view.innerHTML = `
    <div class="card">
      <h2>${T('plan_h')}</h2>
      <p class="small muted">${T('plan_h_sub')}</p>
      <label>${T('plan_capital')}</label>
      <div class="field-suffix">
        <input id="capital2" type="number" inputmode="decimal" min="0" value="${state.capital || ''}" />
        <span class="suf">${T('usd')}</span>
      </div>
      <label>${T('plan_target')}</label>
      <div class="field-suffix">
        <input id="target2" type="number" inputmode="decimal" min="0" value="${state.dailyTarget || ''}" />
        <span class="suf">${T('usd')}</span>
      </div>
      <button class="btn primary" id="saveBtn">${T('save')}</button>
    </div>
    <div class="card">
      <h2>${T('how_h')}</h2>
      <ul class="list">
        <li>${T('how_1')}</li>
        <li>${T('how_2', { pct: Math.round(CFG.risk.perNameCapPct * 100), n: CFG.risk.maxNames })}</li>
        <li>${T('how_3')}</li>
        <li>${T('how_4')}</li>
      </ul>
    </div>`;
  $('#saveBtn').onclick = () => {
    const c = parseFloat($('#capital2').value), t = parseFloat($('#target2').value);
    if (!(c > 0) || !(t > 0)) return toast(T('err_values'));
    state.capital = c; state.dailyTarget = t; saveState(state);
    toast(T('saved')); go('today');
  };
}

function renderAccount() {
  $('#tabbar').hidden = false;
  const sub = isSubscribed();
  const firstBuy = firstBuyActive();
  const mPrice = priceFor('monthly', firstBuy);
  const yPrice = priceFor('yearly', firstBuy);
  const saveTag = firstBuy ? `<span class="badge-save">${T('first_buy', { pct: Math.round(CFG.pricing.firstBuyDiscount * 100) })}</span>` : '';

  const status = sub ? `
    <div class="card">
      <h2>${state.sub.plan === 'yearly' ? T('st_yearly') : T('st_monthly')} ✅</h2>
      <p class="small muted">${T('acc_since', { date: esc(state.sub.since) })}</p>
      <button class="btn outline" onclick="signOutSub()">${T('acc_signout')}</button>
    </div>` : '';

  const plans = sub ? '' : `
    <div class="card">
      <h2>${T('plans_h')} ${saveTag}</h2>
      <p class="small muted">${T('plans_sub')}</p>
      <div class="plans">
        <div class="plan">
          <div class="row spread"><b>${T('p_monthly')}</b><div class="per">${T('p_monthly_sub')}</div></div>
          <div class="price">${firstBuy ? `<s>${fmt$(CFG.pricing.monthly)}</s>` : ''}${fmt$(mPrice)}<span class="per"> ${T('per_mo')}</span></div>
          <button class="btn primary" onclick="subscribe('monthly')">${T('choose_mo')}</button>
        </div>
        <div class="plan best">
          <div class="row spread"><b>${T('p_yearly')}</b>${CFG.pricing.monthly * 12 - CFG.pricing.yearly > 0 ? `<span class="badge-save">${T('save_amt', { amt: fmt$(CFG.pricing.monthly * 12 - CFG.pricing.yearly) })}</span>` : ''}</div>
          <div class="price">${firstBuy ? `<s>${fmt$(CFG.pricing.yearly)}</s>` : ''}${fmt$(yPrice)}<span class="per"> ${T('per_yr')}</span></div>
          <div class="per">${T('approx_mo', { amt: fmt$(yPrice / 12) })}</div>
          <button class="btn gold" onclick="subscribe('yearly')">${T('choose_yr')}</button>
        </div>
      </div>
      <p class="note">${T('stripe_note')}</p>
    </div>`;

  view.innerHTML = `
    ${status}
    ${plans}
    <div class="card">
      <h2>${T('acc_h')}</h2>
      <div class="row spread small"><span class="muted">${T('acc_capital')}</span><span>${fmt$(state.capital || 0)}</span></div>
      <div class="row spread small" style="margin-top:8px"><span class="muted">${T('acc_target')}</span><span>${fmt$(state.dailyTarget || 0)}</span></div>
      <button class="btn outline" onclick="go('plan')">${T('acc_edit')}</button>
    </div>
    <div class="disclaimer"><b>${T('acc_disc_b')}</b>: ${T('acc_disc')}</div>
    <div class="note">${T('acc_footer', { brand: esc(CFG.brand) })}</div>`;
}

// —— 透明战绩 ——
function sparkline(curve) {
  if (!curve || curve.length < 2) return '';
  const vals = curve.map((p) => p.cum);
  const min = Math.min(0, ...vals), max = Math.max(0, ...vals);
  const W = 300, H = 70, n = curve.length;
  const x = (i) => (i / (n - 1)) * W;
  const y = (v) => H - ((v - min) / (max - min || 1)) * H;
  const pts = curve.map((p, i) => `${x(i).toFixed(1)},${y(p.cum).toFixed(1)}`).join(' ');
  const zeroY = y(0).toFixed(1);
  const last = vals[vals.length - 1];
  const stroke = last >= 0 ? 'var(--up)' : 'var(--down)';
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" style="margin-top:8px">
    <line x1="0" y1="${zeroY}" x2="${W}" y2="${zeroY}" stroke="var(--line)" stroke-width="1" stroke-dasharray="4 4"/>
    <polyline points="${pts}" fill="none" stroke="${stroke}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

async function renderRecord() {
  $('#tabbar').hidden = false;
  view.innerHTML = `<div class="card center muted">${T('rec_loading')}</div>`;
  const data = await fetch(CFG.trackRecordUrl, { cache: 'no-store' }).then((r) => r.json()).catch(() => null);
  if (!data || !data.summary) { view.innerHTML = `<div class="card center muted">${T('rec_none')}</div>`; return; }
  const s = data.summary;
  const netCls = s.net_pnl >= 0 ? 'up' : 'down';
  const rows = (data.trades || []).map((tr) => {
    const cls = tr.pnl_usd > 0 ? 'up' : (tr.pnl_usd < 0 ? 'down' : 'muted');
    const sign = tr.pnl_usd > 0 ? '+' : '';
    return `<div class="row spread" style="padding:10px 0;border-bottom:1px solid var(--line)">
      <div><b>${esc(tr.ticker)}</b> <span class="small muted">· ${esc(tr.reason)}</span><div class="small muted">${esc(tr.date)}</div></div>
      <div class="center"><div style="font-weight:800;color:var(--${cls})">${sign}${fmt$(tr.pnl_usd)}</div><div class="small muted">${sign}${tr.pnl_pct}%</div></div>
    </div>`;
  }).join('');

  view.innerHTML = `
    <div class="card">
      <div class="row spread"><h2>${T('rec_h')}</h2><span class="tag">${T('rec_tag')}</span></div>
      <div class="metrics" style="grid-template-columns:repeat(2,1fr)">
        <div class="metric"><div class="k">${T('rec_net')}</div><div class="v ${netCls}">${s.net_pnl >= 0 ? '+' : ''}${fmt$(s.net_pnl)}</div></div>
        <div class="metric"><div class="k">${T('rec_wr')}</div><div class="v">${s.win_rate}%</div></div>
        <div class="metric"><div class="k">${T('rec_trades')}</div><div class="v">${s.trades}</div></div>
        <div class="metric"><div class="k">${T('rec_days')}</div><div class="v">${s.days}</div></div>
      </div>
      ${sparkline(data.curve)}
      <div class="small muted" style="margin-top:6px">${T('rec_summary', { first: esc(s.first_date || ''), last: esc(s.last_date || ''), w: s.wins, l: s.losses, b: s.breakeven })}</div>
    </div>
    <div class="card">
      <h2>${T('rec_detail_h')}</h2>
      ${rows || `<span class="muted small">${T('roadmap_empty')}</span>`}
    </div>
    <div class="disclaimer"><b>${T('rec_disc_b')}</b>: ${T('rec_disc')}</div>
    <div class="note">${T('feed_updated', { date: esc(data.updated_at || '—') })}</div>`;
}

// —— 反馈 / 讨论区 ——
const STATUS_KEY = { planned: 's_planned', doing: 's_doing', done: 's_done' };
const STATUS_DOT = { planned: 'var(--muted)', doing: 'var(--accent)', done: 'var(--up)' };

async function renderFeedback() {
  $('#tabbar').hidden = false;
  const mine = state.feedbacks || [];
  const mineHtml = mine.length ? mine.map((f) => `
    <div class="card" style="padding:12px">
      <div class="row spread small muted"><span>${esc(f.ts)}</span><span style="color:var(--up)">${T('received')}</span></div>
      <div style="margin-top:6px;font-size:14px;white-space:pre-wrap">${esc(f.message)}</div>
    </div>`).join('') : `<p class="small muted">${T('myfb_empty')}</p>`;

  const giscus = CFG.discussion && CFG.discussion.giscus
    ? `<div class="card"><h2>${T('discuss_h')}</h2><div id="giscus"></div></div>` : '';

  view.innerHTML = `
    <div class="card">
      <h2>${T('fb_h')}</h2>
      <p class="small muted">${T('fb_sub')}</p>
      <label>${T('fb_label')}</label>
      <textarea id="fbMsg" rows="4" style="width:100%;background:var(--bg-2);border:1px solid var(--line);color:var(--text);border-radius:12px;padding:14px;font-size:15px;font-family:inherit" placeholder="${T('fb_ph')}"></textarea>
      <label>${T('fb_email')}</label>
      <div class="field-suffix"><input id="fbContact" type="text" inputmode="email" placeholder="you@example.com" value="${esc(state.fbContact || '')}" /></div>
      <button class="btn primary" id="fbSend">${T('fb_send')}</button>
      <p class="note">${T('fb_note')}</p>
    </div>
    ${giscus}
    <div class="card">
      <h2>${T('roadmap_h')}</h2>
      <p class="small muted">${T('roadmap_sub')}</p>
      <div id="roadmap" class="small muted" style="margin-top:8px">${T('roadmap_loading')}</div>
    </div>
    <div class="card">
      <h2>${T('myfb_h')}</h2>
      ${mineHtml}
    </div>`;

  $('#fbSend').onclick = submitFeedback;

  fetch(CFG.updatesUrl, { cache: 'no-store' }).then((r) => r.json()).then((data) => {
    const el = $('#roadmap');
    if (!el) return;
    el.innerHTML = (data.items || []).map((it) => `
      <div class="row" style="align-items:flex-start;gap:10px;margin:10px 0">
        <span style="width:9px;height:9px;border-radius:50%;background:${STATUS_DOT[it.status] || 'var(--muted)'};margin-top:5px;flex:0 0 auto"></span>
        <div>
          <div style="color:var(--text);font-weight:600">${esc(it.title)}
            ${it.from_feedback ? `<span class="tag" style="margin-left:6px">${T('from_feedback')}</span>` : ''}</div>
          <div class="small muted">${T(STATUS_KEY[it.status] || 'roadmap_empty')}${it.date ? ' · ' + esc(it.date) : ''}</div>
        </div>
      </div>`).join('') || `<span class="muted">${T('roadmap_empty')}</span>`;
  }).catch(() => { const el = $('#roadmap'); if (el) el.textContent = T('roadmap_fail'); });

  if (CFG.discussion && CFG.discussion.giscus) injectGiscus(CFG.discussion.giscus);
}

function submitFeedback() {
  const msg = ($('#fbMsg').value || '').trim();
  const contact = ($('#fbContact').value || '').trim();
  if (msg.length < 3) return toast(T('fb_short'));
  state.fbContact = contact;
  state.feedbacks = state.feedbacks || [];
  const rec = { message: msg, ts: ny().dateStr + ' ' + new Date().toTimeString().slice(0, 5) };
  state.feedbacks.unshift(rec);
  saveState(state);

  const ep = CFG.feedback && CFG.feedback.endpoint;
  const payload = { message: msg, contact, ts: rec.ts, plan: state.sub?.plan || 'trial' };
  if (ep && !ep.startsWith('REPLACE_')) {
    fetch(ep, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).catch(() => {});
    toast(T('fb_thanks'));
    render();
  } else {
    const to = (CFG.feedback && CFG.feedback.email) || '';
    const subject = encodeURIComponent('[AI4Trade feedback]');
    const body = encodeURIComponent(msg + (contact ? '\n\n' + contact : ''));
    toast(T('fb_thanks_mail'));
    render();
    if (to && !to.startsWith('REPLACE_')) location.href = `mailto:${to}?subject=${subject}&body=${body}`;
  }
}

function injectGiscus(g) {
  const box = $('#giscus');
  if (!box || box.dataset.loaded) return;
  box.dataset.loaded = '1';
  const s = document.createElement('script');
  s.src = 'https://giscus.app/client.js';
  s.async = true; s.crossOrigin = 'anonymous';
  const langMap = { en: 'en', zh: 'zh-CN', 'zh-TW': 'zh-TW', ja: 'ja', de: 'de' };
  const attrs = {
    'data-repo': g.repo, 'data-repo-id': g.repoId,
    'data-category': g.category || 'Announcements', 'data-category-id': g.categoryId,
    'data-mapping': 'pathname', 'data-strict': '0', 'data-reactions-enabled': '1',
    'data-emit-metadata': '0', 'data-input-position': 'top', 'data-theme': 'dark_dimmed',
    'data-lang': langMap[window.I18N.getLang()] || 'en',
  };
  Object.entries(attrs).forEach(([k, v]) => v != null && s.setAttribute(k, v));
  box.appendChild(s);
}

// —— 语言切换 ——
function openLangMenu() {
  if ($('#langMenu')) { $('#langMenu').remove(); return; }
  const cur = window.I18N.getLang();
  const menu = document.createElement('div');
  menu.id = 'langMenu';
  menu.className = 'lang-menu';
  menu.innerHTML = `<div class="lang-title">${T('lang_title')}</div>` +
    window.I18N.LANGS.map((l) => `<button class="lang-item${l.code === cur ? ' active' : ''}" data-code="${l.code}">${l.label}${l.code === cur ? ' ✓' : ''}</button>`).join('');
  document.body.appendChild(menu);
  menu.querySelectorAll('.lang-item').forEach((b) => {
    b.onclick = () => { window.I18N.setLang(b.dataset.code); menu.remove(); applyLang(); render(); };
  });
  setTimeout(() => {
    const close = (e) => { if (!menu.contains(e.target) && e.target.id !== 'langBtn') { menu.remove(); document.removeEventListener('click', close); } };
    document.addEventListener('click', close);
  }, 0);
}
// 更新语言相关的静态元素(html lang、语言按钮、tab 标签)
function applyLang() {
  const lang = window.I18N.getLang();
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
  const lb = $('#langBtn'); if (lb) lb.textContent = '🌐 ' + (SHORT[lang] || lang);
  document.querySelectorAll('.tab').forEach((b) => { b.textContent = T('tab_' + b.dataset.tab); });
}

// —— 全局动作(供 onclick 调用)——
window.go = (tab) => { currentTab = tab; render(); };
window.subscribe = (plan) => {
  const link = payLink(plan);
  if (!link || link.startsWith('REPLACE_')) { toast(T('pay_missing')); return; }
  location.href = link;
};
window.signOutSub = () => {
  if (!confirm(T('signout_confirm'))) return;
  delete state.sub; saveState(state); toast(T('signout_done')); render();
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
  applyLang();
  if (!state.onboarded) return renderOnboarding();
  document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === currentTab));
  if (currentTab === 'today') return renderToday();
  if (currentTab === 'record') return renderRecord();
  if (currentTab === 'plan') return renderPlan();
  if (currentTab === 'feedback') return renderFeedback();
  if (currentTab === 'account') return renderAccount();
}

document.querySelectorAll('.tab').forEach((b) => {
  b.onclick = () => { currentTab = b.dataset.tab; render(); };
});
$('#langBtn').onclick = openLangMenu;

// —— 按功能开关显示/隐藏 tab ——
document.querySelectorAll('.tab[data-feature]').forEach((b) => {
  const on = CFG.features && CFG.features[b.dataset.feature];
  b.hidden = !on;
});
function tabEnabled(tab) {
  const b = document.querySelector(`.tab[data-tab="${tab}"]`);
  return b && !b.hidden;
}

// —— 「添加到主屏幕」安装提示 ——
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; showInstallBar(); });
function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}
function showInstallBar() {
  if (isStandalone() || state.installDismissed || $('#installBar')) return;
  const bar = document.createElement('div');
  bar.id = 'installBar';
  bar.className = 'install-bar';
  bar.innerHTML = `<span>${T('install_text')}</span>
    <span><button id="installYes">${T('install_yes')}</button><button id="installNo" class="x">✕</button></span>`;
  document.body.appendChild(bar);
  $('#installYes').onclick = async () => {
    if (deferredPrompt) { deferredPrompt.prompt(); await deferredPrompt.userChoice.catch(() => {}); deferredPrompt = null; }
    bar.remove();
  };
  $('#installNo').onclick = () => { state.installDismissed = true; saveState(state); bar.remove(); };
}
function maybeIosHint() {
  const isIos = /iPhone|iPad|iPod/.test(navigator.userAgent);
  if (isIos && !isStandalone() && !state.iosHintShown && state.onboarded) {
    state.iosHintShown = true; saveState(state);
    toast(T('ios_hint'));
  }
}

// —— 启动 ——
handlePaymentReturn();
if (currentTab === 'record' && !tabEnabled('record')) currentTab = 'today';
render();
maybeIosHint();

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js').catch(() => {});
}
