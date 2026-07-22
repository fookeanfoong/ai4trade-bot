/**
 * Capital size input for position sizing.
 * REQUIREMENT: explain it is stored locally + on the server.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, TextInput } from '@/components/ui';

export default function CapitalInput({
  initial,
  onNext,
  onBack,
}: {
  initial: number;
  onNext: (capital: number) => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState(initial > 0 ? String(initial) : '');
  const capital = Number(value);
  const valid = Number.isFinite(capital) && capital > 0;

  return (
    <div className="flex min-h-full flex-col justify-between px-6 py-8">
      <div>
        <h1 className="text-xl font-bold">{t('onboarding.capitalTitle')}</h1>
        <p className="mt-2 text-sm text-muted">{t('onboarding.capitalBody')}</p>

        <div className="mt-6">
          <TextInput
            label={t('onboarding.capitalLabel')}
            type="number"
            inputMode="decimal"
            min={0}
            placeholder={t('onboarding.capitalHint')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="ghost" onClick={onBack} className="flex-1">
          {t('common.back')}
        </Button>
        <Button onClick={() => onNext(capital)} disabled={!valid} className="flex-1">
          {t('common.continue')}
        </Button>
      </div>
    </div>
  );
}
