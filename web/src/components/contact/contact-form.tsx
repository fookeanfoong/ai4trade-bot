'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { CheckCircle2, Send } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

type Status = 'idle' | 'sending' | 'done' | 'error';

export function ContactForm() {
  const t = useTranslations('contact');
  const [status, setStatus] = useState<Status>('idle');
  const [form, setForm] = useState({ name: '', email: '', message: '' });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('sending');
    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error('bad status');
      setStatus('done');
    } catch {
      setStatus('error');
    }
  }

  if (status === 'done') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-green-500/40 bg-green-500/10 p-5">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-green-500" />
        <p className="text-sm">{t('success')}</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium">{t('fieldName')}</span>
          <Input
            required
            value={form.name}
            placeholder={t('namePlaceholder')}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium">{t('fieldEmail')}</span>
          <Input
            required
            type="email"
            value={form.email}
            placeholder={t('emailPlaceholder')}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>
      </div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium">{t('fieldMessage')}</span>
        <textarea
          required
          rows={5}
          value={form.message}
          placeholder={t('messagePlaceholder')}
          onChange={(e) => setForm({ ...form, message: e.target.value })}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </label>

      {status === 'error' && <p className="text-sm text-destructive">{t('error')}</p>}

      <Button type="submit" disabled={status === 'sending'}>
        {status === 'sending' ? t('sending') : t('submit')}
        <Send className="h-3.5 w-3.5" />
      </Button>
    </form>
  );
}
