/**
 * Orchestrates the onboarding sequence and blocks app usage until legal
 * acceptance is recorded.
 *
 * Sequence:
 *   1. Welcome + value prop
 *   2. Age confirmation (18+ gate)
 *   3. Create account / sign in   (needed to record acceptance & capital)
 *   4. Capital size input
 *   5. Risk Disclosure & Legal Acceptance (3 checkboxes, backend POST)
 *   6. Notification permission (optional)
 *
 * On completion, sets the onboarding-complete flag and calls onComplete so the
 * router advances to the main app.
 */
import { useState } from 'react';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';
import { useApp } from '@/context/AppContext';
import Welcome from './Welcome';
import AgeConfirm from './AgeConfirm';
import CreateAccount from './CreateAccount';
import CapitalInput from './CapitalInput';
import RiskDisclosure from './RiskDisclosure';
import NotificationPermission from './NotificationPermission';

type Step = 'welcome' | 'age' | 'account' | 'capital' | 'risk' | 'notif';

export default function OnboardingFlow({ onComplete }: { onComplete: () => void }) {
  const { capitalUsd, setCapital, isAuthenticated } = useApp();
  const [step, setStep] = useState<Step>('welcome');
  const [dob, setDob] = useState('');
  // `today` captured once so the age calculation is stable across renders.
  const [today] = useState(() => new Date());

  async function finish() {
    await storage.setBool(KEYS.onboardingComplete, true);
    onComplete();
  }

  switch (step) {
    case 'welcome':
      return <Welcome onNext={() => setStep('age')} />;

    case 'age':
      return (
        <AgeConfirm
          today={today}
          onBack={() => setStep('welcome')}
          onNext={(value) => {
            setDob(value);
            // If already signed in (e.g. returning to finish onboarding), skip
            // the account step.
            setStep(isAuthenticated ? 'capital' : 'account');
          }}
        />
      );

    case 'account':
      return (
        <CreateAccount
          dob={dob}
          onBack={() => setStep('age')}
          onNext={() => setStep('capital')}
        />
      );

    case 'capital':
      return (
        <CapitalInput
          initial={capitalUsd}
          onBack={() => setStep(isAuthenticated ? 'age' : 'account')}
          onNext={async (value) => {
            await setCapital(value);
            setStep('risk');
          }}
        />
      );

    case 'risk':
      return (
        <RiskDisclosure onBack={() => setStep('capital')} onAccepted={() => setStep('notif')} />
      );

    case 'notif':
      return <NotificationPermission onDone={() => void finish()} />;
  }
}
