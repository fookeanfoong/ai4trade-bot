import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 跳转埋点:记录每次"前往第三方"的点击,方便核对联盟返佣。
// 一期先落地到服务端日志(console),二期接入数据库 / 队列。
// 结构与二期 outbound_click 表保持一致:provider_id、时间、来源页、UA、referer、ip 前缀。

interface OutboundPayload {
  provider_id?: string;
  provider_slug?: string;
  source_page?: string;
}

function clientIpPrefix(req: NextRequest): string {
  const fwd = req.headers.get('x-forwarded-for') || '';
  const ip = fwd.split(',')[0]?.trim() || req.headers.get('x-real-ip') || '';
  // 仅保留网段前缀,避免存储完整 IP(GDPR 数据最小化)
  if (ip.includes('.')) return ip.split('.').slice(0, 2).join('.') + '.x.x';
  if (ip.includes(':')) return ip.split(':').slice(0, 2).join(':') + '::x';
  return 'unknown';
}

export async function POST(req: NextRequest) {
  let body: OutboundPayload = {};
  try {
    body = await req.json();
  } catch {
    // sendBeacon 可能以 text 形式送达,再尝试解析
    try {
      const txt = await req.text();
      body = txt ? JSON.parse(txt) : {};
    } catch {
      body = {};
    }
  }

  if (!body.provider_id) {
    return NextResponse.json({ ok: false, error: 'provider_id required' }, { status: 400 });
  }

  const record = {
    event: 'outbound_click',
    provider_id: body.provider_id,
    provider_slug: body.provider_slug ?? null,
    source_page: body.source_page ?? null,
    ts: new Date().toISOString(),
    user_agent: req.headers.get('user-agent') ?? null,
    referer: req.headers.get('referer') ?? null,
    ip_prefix: clientIpPrefix(req),
  };

  // 一期:结构化日志;二期替换为 DB / analytics sink。
  console.log('[track/outbound]', JSON.stringify(record));

  return NextResponse.json({ ok: true }, { status: 200 });
}

export async function GET() {
  // 健康检查,便于国内可访问性排查
  return NextResponse.json({ ok: true, endpoint: 'track/outbound' });
}
