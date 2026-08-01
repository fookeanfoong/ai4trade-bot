/**
 * Account creation step. Needed so legal acceptance and capital can be recorded
 * against the user account on the backend. Uses the DOB collected on the age
 * gate; the backend re-validates 18+ on signup. An existing user can switch to
 * sign-in instead.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, TextInput } from '@/components/ui';
import { useApp } from '@/context/AppContext';
import { ApiError } from '@/lib/api';

export default function CreateAccount({
  dob,
  onNext,
  onBack,
}: {
  dob: string;
  onNext: () => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const { signup, login } = useApp();
  const [mode, setMode] = useState<'signup' | 'login'>('signup');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canSubmit = /.+@.+\..+/.test(email) && password.length >= 8 && !busy;

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      if (mode === 'signup') {
        await signup(email, password, dob);
      } else {
        await login(email, password);
      }
      onNext();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(t('auth.emailInUse'));
      } else if (err instanceof ApiError && err.status === 401) {
        setError(t('auth.invalidCredentials'));
      } else {
        setError((err as Error).message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col justify-between px-6 py-8">
      <div>
        <h1 className="text-xl font-bold">
          {mode === 'signup' ? t('auth.signupTitle') : t('auth.loginTitle')}
        </h1>

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
          <button
            type="button"
            className="text-sm text-accent underline"
            onClick={() => {
              setMode(mode === 'signup' ? 'login' : 'signup');
              setError(null);
            }}
          >
            {mode === 'signup' ? t('auth.haveAccount') : t('auth.noAccount')}
          </button>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="ghost" onClick={onBack} className="flex-1">
          {t('common.back')}
        </Button>
        <Button onClick={() => void submit()} disabled={!canSubmit} className="flex-1">
          {mode === 'signup' ? t('auth.signUp') : t('auth.signIn')}
        </Button>
      </div>
    </div>
  );
}
