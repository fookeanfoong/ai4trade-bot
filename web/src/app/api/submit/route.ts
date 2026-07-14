import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 商家自荐提交。一期落地到服务端日志;二期接入审核队列 / 数据库,
// 并升级为正式入驻申请(平台代收款、抽佣)。
export async function POST(req: NextRequest) {
  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  if (!body.name || !body.website || !body.contact) {
    return NextResponse.json({ ok: false, error: 'name, website and contact are required' }, { status: 400 });
  }

  const record = {
    event: 'provider_submission',
    name: body.name,
    website: body.website,
    contact: body.contact,
    regions: body.regions ?? [],
    payments: body.payments ?? [],
    description: body.description ?? '',
    ts: new Date().toISOString(),
  };

  console.log('[submit]', JSON.stringify(record));
  return NextResponse.json({ ok: true });
}
