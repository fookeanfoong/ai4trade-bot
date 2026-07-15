import { NextRequest, NextResponse } from 'next/server';
import { aggregateClicks } from '@/lib/clicks';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 联盟点击统计(内部)。若设置了 ADMIN_TOKEN,需带 ?token= 或 x-admin-token 头;
// 未设置(本地开发)则直接开放。返回结构见 aggregateClicks。
export async function GET(req: NextRequest) {
  const required = process.env.ADMIN_TOKEN;
  if (required) {
    const got =
      req.nextUrl.searchParams.get('token') || req.headers.get('x-admin-token') || '';
    if (got !== required) {
      return NextResponse.json({ ok: false, error: 'unauthorized' }, { status: 401 });
    }
  }
  const stats = aggregateClicks(new Date().toISOString());
  return NextResponse.json({ ok: true, ...stats });
}
