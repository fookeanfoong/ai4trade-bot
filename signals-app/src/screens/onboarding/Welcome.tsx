import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui';
import { DISCLAIMER_FULL } from '@/lib/compliance';

export default function Welcome({ onNext }: { onNext: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-full flex-col justify-between px-6 py-10">
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-card border border-border bg-card">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#e5e7eb" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 17l6-6 4 4 8-8" />
            <path d="M21 7v6h-6" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold">{t('onboarding.welcomeTitle')}</h1>
        <p className="mt-2 text-sm font-medium text-accent">{t('onboarding.welcomeTag')}</p>
        <p className="mt-4 max-w-sm text-sm leading-relaxed text-muted">
          {t('onboarding.welcomeBody')}
        </p>
      </div>
      <div className="space-y-4">
        <p className="text-center text-[11px] leading-tight text-muted">{DISCLAIMER_FULL}</p>
        <Button onClick={onNext}>{t('onboarding.getStarted')}</Button>
      </div>
    </div>
  );
}
