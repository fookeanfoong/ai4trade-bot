import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 订阅收集。一期落地到服务端日志(方便先跑起来);
// 未来接入 Resend Audiences / 邮件列表服务时替换即可(结构保持不变)。
// 可选环境变量:RESEND_API_KEY + RESEND_AUDIENCE_ID —— 两者都配置时写入 Resend 受众。
export async function POST(req: NextRequest) {
  let body: { email?: string; source?: string } = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const email = (body.email ?? '').trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return NextResponse.json({ ok: false, error: 'invalid email' }, { status: 400 });
  }

  console.log('[newsletter]', JSON.stringify({ event: 'subscribe', email, source: body.source ?? null, ts: new Date().toISOString() }));

  const apiKey = process.env.RESEND_API_KEY;
  const audienceId = process.env.RESEND_AUDIENCE_ID;
  if (apiKey && audienceId) {
    try {
      const res = await fetch(`https://api.resend.com/audiences/${audienceId}/contacts`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, unsubscribed: false }),
      });
      if (!res.ok) {
        console.error('[newsletter] resend audience failed', res.status);
        // 不阻断用户:仍返回成功(已记录日志),避免因下游失败影响体验
      }
    } catch (e) {
      console.error('[newsletter] resend error', e);
    }
  }

  return NextResponse.json({ ok: true });
}
