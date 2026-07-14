'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { ShieldCheck } from 'lucide-react';
import { useRouter } from '@/i18n/routing';
import { useUserStore } from '@/store/user-store';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export function AuthForm() {
  const t = useTranslations('auth');
  const router = useRouter();
  const login = useUserStore((s) => s.login);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setError(t('invalidEmail'));
      return;
    }
    login(email, name || undefined);
    router.push('/dashboard');
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-bold tracking-tight">{t('loginTitle')}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t('loginSubtitle')}</p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">{t('email')}</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
        </div>
        {mode === 'register' && (
          <div>
            <label className="mb-1 block text-sm font-medium">{t('name')}</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="dev" />
          </div>
        )}
        <div>
          <label className="mb-1 block text-sm font-medium">{t('password')}</label>
          <Input type="password" placeholder="••••••••" required />
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {/* Cloudflare Turnstile 占位(替代 reCAPTCHA,国内可访问)。上线时接入真实 widget。 */}
        <div className="flex items-center gap-2 rounded-md border border-dashed border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <span>Cloudflare Turnstile · {t('turnstileNote')}</span>
        </div>

        <Button type="submit" className="w-full">
          {mode === 'login' ? t('loginBtn') : t('registerBtn')}
        </Button>
      </form>

      <button
        onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
        className="mt-4 w-full text-center text-sm text-primary hover:underline"
      >
        {mode === 'login' ? t('toRegister') : t('toLogin')}
      </button>

      <p className="mt-6 text-center text-xs text-muted-foreground">{t('mockNote')}</p>
    </div>
  );
}
