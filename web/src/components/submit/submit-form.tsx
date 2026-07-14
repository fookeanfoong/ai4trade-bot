'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { CheckCircle2, ShieldCheck } from 'lucide-react';
import { Link } from '@/i18n/routing';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ALL_REGIONS, ALL_PAYMENTS, regionLabel, paymentShort } from '@/lib/display';
import { cn } from '@/lib/utils';

export function SubmitForm() {
  const t = useTranslations('submit');
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [regions, setRegions] = useState<string[]>([]);
  const [payments, setPayments] = useState<string[]>([]);
  const [form, setForm] = useState({ name: '', website: '', contact: '', description: '' });

  function toggle(list: string[], setList: (v: string[]) => void, val: string) {
    setList(list.includes(val) ? list.filter((x) => x !== val) : [...list, val]);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, regions, payments }),
      });
    } catch {
      /* 演示版:即使失败也进入成功态 */
    }
    setSubmitting(false);
    setDone(true);
  }

  if (done) {
    return (
      <div className="mx-auto max-w-md py-10 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
        <h2 className="mt-4 text-xl font-semibold">{t('successTitle')}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t('successBody')}</p>
        <div className="mt-6 flex justify-center gap-3">
          <Button variant="outline" onClick={() => { setDone(false); setForm({ name: '', website: '', contact: '', description: '' }); setRegions([]); setPayments([]); }}>
            {t('again')}
          </Button>
          <Link href="/providers" className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            OK
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-xl space-y-4">
      <Field label={t('fieldName')} required>
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </Field>
      <Field label={t('fieldWebsite')} required>
        <Input type="url" placeholder="https://" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} required />
      </Field>
      <Field label={t('fieldContact')} required>
        <Input type="email" value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} required />
      </Field>

      <Field label={t('fieldRegions')}>
        <div className="flex flex-wrap gap-1.5">
          {ALL_REGIONS.map((r) => (
            <Chip key={r} on={regions.includes(r)} onClick={() => toggle(regions, setRegions, r)}>
              {regionLabel[r]}
            </Chip>
          ))}
        </div>
      </Field>

      <Field label={t('fieldPayments')}>
        <div className="flex flex-wrap gap-1.5">
          {ALL_PAYMENTS.map((p) => (
            <Chip key={p} on={payments.includes(p)} onClick={() => toggle(payments, setPayments, p)}>
              {paymentShort[p]}
            </Chip>
          ))}
        </div>
      </Field>

      <Field label={t('fieldDesc')}>
        <textarea
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          rows={4}
          placeholder={t('descPlaceholder')}
          className="w-full rounded-md border border-input bg-background p-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </Field>

      <div className="flex items-center gap-2 rounded-md border border-dashed border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        <ShieldCheck className="h-4 w-4 text-primary" />
        Cloudflare Turnstile
      </div>

      <p className="text-xs text-muted-foreground">{t('phase2Note')}</p>

      <Button type="submit" className="w-full" disabled={submitting}>
        {t('submitBtn')}
      </Button>
    </form>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium">
        {label} {required && <span className="text-destructive">*</span>}
      </label>
      {children}
    </div>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-2.5 py-1 text-xs transition-colors',
        on ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'
      )}
    >
      {children}
    </button>
  );
}
