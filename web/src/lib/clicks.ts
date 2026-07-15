import fs from 'node:fs';
import path from 'node:path';
import { providers } from '@/lib/data/providers';

// 联盟跳转点击的服务端存储(一期最小可用版)。
//
// 生产环境(Cloudflare Pages / Vercel 无状态函数)文件系统只读,
// 写入会被 try/catch 吞掉——那时应改用二期的 Postgres(prisma OutboundClick 表,
// 见 prisma/schema.prisma)。本地 `npm run dev` / 长驻 Node(`npm run start`)
// 下走文件,追加到 .data/outbound-clicks.jsonl(已 gitignore)。
//
// 字段与 /api/track/outbound 的 record、以及 prisma OutboundClick 一一对应。

export interface ClickRecord {
  provider_id: string;
  provider_slug: string | null;
  source_page: string | null;
  ts: string; // ISO
  user_agent?: string | null;
  referer?: string | null;
  ip_prefix?: string | null;
}

const DATA_DIR = path.join(process.cwd(), '.data');
const FILE = path.join(DATA_DIR, 'outbound-clicks.jsonl');

// 追加一条点击。任何 IO 失败都不抛出(不能因埋点失败影响主流程)。
export function recordClick(rec: ClickRecord): boolean {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    fs.appendFileSync(FILE, JSON.stringify(rec) + '\n', 'utf8');
    return true;
  } catch {
    // 只读文件系统(serverless):静默降级,交由 console 日志 / 二期 DB 兜底
    return false;
  }
}

// 读取全部点击(最新在前)。文件不存在或损坏行都安全跳过。
export function readClicks(): ClickRecord[] {
  let raw: string;
  try {
    raw = fs.readFileSync(FILE, 'utf8');
  } catch {
    return [];
  }
  const out: ClickRecord[] = [];
  for (const line of raw.split('\n')) {
    const s = line.trim();
    if (!s) continue;
    try {
      out.push(JSON.parse(s) as ClickRecord);
    } catch {
      /* 跳过损坏行 */
    }
  }
  return out.reverse();
}

export interface ProviderClickStat {
  provider_id: string;
  slug: string;
  name: string;
  logo: string;
  clicks: number;
  affiliateUrl: string;
}

export interface ClickStats {
  total: number;
  today: number;
  last7d: number;
  byProvider: ProviderClickStat[];
  bySourcePage: { page: string; clicks: number }[];
  byDay: { day: string; clicks: number }[]; // 最近 14 天
  recent: ClickRecord[]; // 最近 20 条
  isDemo: boolean;
}

// 汇总统计。传入 now(ISO,由调用方在请求期传入以保证可预测)。
export function aggregateClicks(nowIso: string): ClickStats {
  const clicks = readClicks();

  if (clicks.length === 0) {
    return { ...demoStats(nowIso), isDemo: true };
  }

  const now = new Date(nowIso);
  const dayKey = (d: Date) => d.toISOString().slice(0, 10);
  const todayKey = dayKey(now);
  const sevenAgo = new Date(now.getTime() - 7 * 864e5);

  const providerCount = new Map<string, number>();
  const pageCount = new Map<string, number>();
  const dayCount = new Map<string, number>();
  let today = 0;
  let last7d = 0;

  for (const c of clicks) {
    providerCount.set(c.provider_id, (providerCount.get(c.provider_id) ?? 0) + 1);
    const page = c.source_page ?? '(unknown)';
    pageCount.set(page, (pageCount.get(page) ?? 0) + 1);
    const t = new Date(c.ts);
    dayCount.set(dayKey(t), (dayCount.get(dayKey(t)) ?? 0) + 1);
    if (dayKey(t) === todayKey) today++;
    if (t >= sevenAgo) last7d++;
  }

  const byProvider = [...providerCount.entries()]
    .map(([pid, n]) => statForProvider(pid, n))
    .sort((a, b) => b.clicks - a.clicks);

  const bySourcePage = [...pageCount.entries()]
    .map(([page, clicks]) => ({ page, clicks }))
    .sort((a, b) => b.clicks - a.clicks);

  const byDay: { day: string; clicks: number }[] = [];
  for (let i = 13; i >= 0; i--) {
    const d = dayKey(new Date(now.getTime() - i * 864e5));
    byDay.push({ day: d, clicks: dayCount.get(d) ?? 0 });
  }

  return {
    total: clicks.length,
    today,
    last7d,
    byProvider,
    bySourcePage,
    byDay,
    recent: clicks.slice(0, 20),
    isDemo: false,
  };
}

function statForProvider(pid: string, clicks: number): ProviderClickStat {
  const p = providers.find((x) => x.id === pid);
  return {
    provider_id: pid,
    slug: p?.slug ?? pid,
    name: p?.name ?? pid,
    logo: p?.logo ?? '/logos/placeholder.svg',
    affiliateUrl: p?.affiliate_url ?? '',
    clicks,
  };
}

// 无真实数据时的演示预览(明确标注 isDemo:true)。
// 用 provider 的 trust_score 派生确定性的示例点击量,不用随机数,保证 SSR 稳定。
function demoStats(nowIso: string): Omit<ClickStats, 'isDemo'> {
  const now = new Date(nowIso);
  const dayKey = (d: Date) => d.toISOString().slice(0, 10);
  const top = providers.slice(0, 8);
  const byProvider = top
    .map((p, i) => ({
      provider_id: p.id,
      slug: p.slug,
      name: p.name,
      logo: p.logo,
      affiliateUrl: p.affiliate_url ?? '',
      clicks: Math.max(3, Math.round((p.trust_score / 5) - i * 4)),
    }))
    .sort((a, b) => b.clicks - a.clicks);

  const total = byProvider.reduce((s, x) => s + x.clicks, 0);
  const byDay: { day: string; clicks: number }[] = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 864e5);
    byDay.push({ day: dayKey(d), clicks: 4 + ((i * 7) % 11) });
  }
  const pages = ['/models/gpt-4o', '/providers', '/rankings/cheapest-gpt-4o', '/', '/models/claude-sonnet-4-5'];
  const bySourcePage = pages.map((page, i) => ({ page, clicks: Math.max(2, 30 - i * 6) }));

  return {
    total,
    today: byDay[byDay.length - 1].clicks,
    last7d: byDay.slice(-7).reduce((s, x) => s + x.clicks, 0),
    byProvider,
    bySourcePage,
    byDay,
    recent: [],
  };
}
