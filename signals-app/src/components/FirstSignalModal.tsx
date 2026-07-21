/**
 * First-time signal-view modal (once per install).
 * REQUIREMENT: shown the first time the user opens the Signals view, dismissed
 * with an "I understand" button; the seen flag persists in Preferences.
 */
import { useTranslation } from 'react-i18next';
import { Button } from './ui';

export default function FirstSignalModal({ onDismiss }: { onDismiss: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-card border border-border bg-surface p-5">
        <h2 className="mb-3 text-base font-bold">{t('common.learn')}</h2>
        <p className="mb-5 text-sm leading-relaxed text-text">
          {t('compliance.firstSignalNotice')}
        </p>
        <Button onClick={onDismiss}>{t('common.iUnderstand')}</Button>
      </div>
    </div>
  );
}
