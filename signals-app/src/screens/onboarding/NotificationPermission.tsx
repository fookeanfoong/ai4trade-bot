/**
 * Notification permission request (optional to accept).
 * Requesting registers with HMS Push Kit via the push bridge.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui';
import { registerForPush } from '@/lib/hms/push';

export default function NotificationPermission({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);

  async function enable() {
    setBusy(true);
    try {
      await registerForPush();
    } catch {
      /* permission denied / unavailable — proceed regardless */
    } finally {
      setBusy(false);
      onDone();
    }
  }

  return (
    <div className="flex min-h-full flex-col justify-between px-6 py-10">
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-card border border-border bg-card">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#e5e7eb" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
            <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
          </svg>
        </div>
        <h1 className="text-xl font-bold">{t('onboarding.notifTitle')}</h1>
        <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">
          {t('onboarding.notifBody')}
        </p>
      </div>
      <div className="space-y-3">
        <Button onClick={() => void enable()} disabled={busy}>
          {t('onboarding.notifEnable')}
        </Button>
        <Button variant="ghost" onClick={onDone} disabled={busy}>
          {t('onboarding.notifSkip')}
        </Button>
      </div>
    </div>
  );
}
