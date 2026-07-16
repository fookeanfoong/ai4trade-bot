'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Mail, CheckCircle2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

type Status = 'idle' | 'sending' | 'done' | 'error';

// 复用型订阅 CTA(博客文末等处)。POST /api/newsletter,未配置邮件服务时安全降级。
export function NewsletterCta({ source = 'blog' }: { source?: string }) {
  const t = useTranslations('newsletter');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>('idle');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('sending');
    try {
      const res = await fetch('/api/newsletter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, source }),
      });
      if (!res.ok) throw new Error('bad status');
      setStatus('done');
    } catch {
      setStatus('error');
    }
  }

  return (
    <section className="my-10 rounded-2xl border border-primary/30 bg-primary/5 p-6">
      <div className="flex items-center gap-2 text-primary">
        <Mail className="h-5 w-5" />
        <h2 className="text-lg font-bold tracking-tight">{t('title')}</h2>
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">{t('subtitle')}</p>

      {status === 'done' ? (
        <div className="mt-4 flex items-center gap-2 text-sm font-medium text-green-600 dark:text-green-500">
          <CheckCircle2 className="h-5 w-5" />
          {t('success')}
        </div>
      ) : (
        <form onSubmit={submit} className="mt-4 flex flex-col gap-2 sm:flex-row">
          <Input
            required
            type="email"
            value={email}
            placeholder={t('placeholder')}
            onChange={(e) => setEmail(e.target.value)}
            className="sm:max-w-xs"
          />
          <Button type="submit" disabled={status === 'sending'}>
            {status === 'sending' ? t('sending') : t('button')}
          </Button>
        </form>
      )}
      {status === 'error' && <p className="mt-2 text-sm text-destructive">{t('error')}</p>}
    </section>
  );
}
