/**
 * Age gate (18+). Collects a date of birth and validates client-side.
 * REQUIREMENT: reject below 18 with a clear message. The DOB is carried into
 * signup, where the backend re-validates the age gate server-side.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Checkbox, TextInput } from '@/components/ui';
import { MIN_AGE } from '@/lib/compliance';
import { ageFromDob } from '@/lib/appInfo';

export default function AgeConfirm({
  today,
  onNext,
  onBack,
}: {
  today: Date;
  onNext: (dob: string) => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const [dob, setDob] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [touched, setTouched] = useState(false);

  const age = useMemo(() => (dob ? ageFromDob(dob, today) : NaN), [dob, today]);
  const isOldEnough = !Number.isNaN(age) && age >= MIN_AGE;
  const showError = touched && dob !== '' && !isOldEnough;
  const canContinue = isOldEnough && confirmed;

  // Max selectable DOB = today (avoid future dates); ISO yyyy-mm-dd.
  const maxDate = today.toISOString().slice(0, 10);

  return (
    <div className="flex min-h-full flex-col justify-between px-6 py-8">
      <div>
        <h1 className="text-xl font-bold">{t('onboarding.ageTitle')}</h1>
        <p className="mt-2 text-sm text-muted">{t('onboarding.ageBody')}</p>

        <div className="mt-6 space-y-4">
          <TextInput
            label={t('onboarding.ageDobLabel')}
            type="date"
            value={dob}
            max={maxDate}
            onChange={(e) => {
              setDob(e.target.value);
              setTouched(true);
            }}
            error={showError ? t('onboarding.ageTooYoung') : undefined}
          />
          <Checkbox id="age-confirm" checked={confirmed} onChange={setConfirmed}>
            {t('onboarding.ageConfirmLabel')}
          </Checkbox>
        </div>
      </div>

      <div className="flex gap-3">
        <Button variant="ghost" onClick={onBack} className="flex-1">
          {t('common.back')}
        </Button>
        <Button onClick={() => onNext(dob)} disabled={!canContinue} className="flex-1">
          {t('common.continue')}
        </Button>
      </div>
    </div>
  );
}
