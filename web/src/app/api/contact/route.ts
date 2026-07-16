import { NextRequest, NextResponse } from 'next/server';
import { CONTACT } from '@/lib/site';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 联系表单提交 → 用 Resend 寄信给站点联系邮箱。
// 未配置 RESEND_API_KEY 时:安全降级(记录日志并返回成功),表单照常可用,
// 只是不真正寄信——等你在 Vercel 填入 RESEND_API_KEY 后即自动生效。
// 环境变量:
//   RESEND_API_KEY  —— Resend 的 API key
//   CONTACT_FROM    —— 发件人(需为 Resend 已验证域名),默认用 onboarding@resend.dev(仅测试)
//   CONTACT_TO      —— 收件人,默认用 site.ts 里的 CONTACT.email

interface Payload {
  name?: string;
  email?: string;
  message?: string;
}

export async function POST(req: NextRequest) {
  let body: Payload = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const name = (body.name ?? '').trim();
  const email = (body.email ?? '').trim();
  const message = (body.message ?? '').trim();

  if (!name || !email || !message) {
    return NextResponse.json({ ok: false, error: 'name, email and message are required' }, { status: 400 });
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return NextResponse.json({ ok: false, error: 'invalid email' }, { status: 400 });
  }

  const record = { event: 'contact_message', name, email, message, ts: new Date().toISOString() };
  console.log('[contact]', JSON.stringify(record));

  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    // 没配 key:降级为记录日志,表单仍返回成功
    return NextResponse.json({ ok: true, delivered: false });
  }

  const from = process.env.CONTACT_FROM || 'AggreAPI <onboarding@resend.dev>';
  const to = process.env.CONTACT_TO || CONTACT.email;

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from,
        to: [to],
        reply_to: email,
        subject: `[AggreAPI 联系] ${name}`,
        text: `来自:${name} <${email}>\n\n${message}`,
      }),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      console.error('[contact] resend failed', res.status, detail);
      return NextResponse.json({ ok: false, error: 'send failed' }, { status: 502 });
    }
    return NextResponse.json({ ok: true, delivered: true });
  } catch (e) {
    console.error('[contact] resend error', e);
    return NextResponse.json({ ok: false, error: 'send error' }, { status: 502 });
  }
}
