/**
 * Sign-in screen for returning users who have completed onboarding but signed
 * out. New-account creation and the age gate + legal acceptance live in the
 * onboarding flow, so "Create an account" restarts onboarding.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, TextInput } from '@/components/ui';
import { DISCLAIMER_FULL } from '@/lib/compliance';
import { useApp } from '@/context/AppContext';
import { ApiError } from '@/lib/api';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';

export default function AuthScreen({ onRestartOnboarding }: { onRestartOnboarding: () => void }) {
  const { t } = useTranslation();
  const { login } = useApp();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canSubmit = /.+@.+\..+/.test(email) && password.length >= 8 && !busy;

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError(t('auth.invalidCredentials'));
      else setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createAccount() {
    // Restart onboarding so signup goes through the age gate + acceptance.
    await storage.setBool(KEYS.onboardingComplete, false);
    onRestartOnboarding();
  }

  return (
    <div className="flex min-h-full flex-col justify-between px-6 py-10">
      <div className="flex-1">
        <h1 className="text-2xl font-bold">{t('auth.loginTitle')}</h1>
        <div className="mt-6 space-y-4">
          <TextInput
            label={t('auth.email')}
            type="email"
            inputMode="email"
            autoCapitalize="none"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextInput
            label={t('auth.password')}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="text-sm text-bear">{error}</p>}
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-center text-[11px] leading-tight text-muted">{DISCLAIMER_FULL}</p>
        <Button onClick={() => void submit()} disabled={!canSubmit}>
          {t('auth.signIn')}
        </Button>
        <Button variant="ghost" onClick={() => void createAccount()}>
          {t('auth.noAccount')}
        </Button>
      </div>
    </div>
  );
}
