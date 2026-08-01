/**
 * App shell + routing gates.
 *
 * Gate order (each blocks the next until satisfied):
 *   1. Boot / hydrate.
 *   2. Onboarding not complete            -> OnboardingFlow.
 *   3. Not authenticated (signed out)     -> AuthScreen.
 *   4. Legal docs updated since accepting -> re-acceptance (RiskDisclosure).
 *   5. Otherwise                          -> main app (tabbed).
 */
import { useEffect, useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Spinner } from '@/components/ui';
import MainLayout from '@/components/MainLayout';
import OnboardingFlow from '@/screens/onboarding/OnboardingFlow';
import RiskDisclosure from '@/screens/onboarding/RiskDisclosure';
import AuthScreen from '@/screens/auth/AuthScreen';
import Signals from '@/screens/Signals';
import News from '@/screens/News';
import Learn from '@/screens/Learn';
import Settings from '@/screens/Settings';
import Paywall from '@/screens/Paywall';
import { useApp } from '@/context/AppContext';
import { setLanguage, type LanguageCode } from '@/i18n';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';

export default function App() {
  const { ready, isAuthenticated, hasCurrentAcceptance, logout } = useApp();
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);
  const [langLoaded, setLangLoaded] = useState(false);

  // Hydrate persisted language + onboarding flag on boot.
  useEffect(() => {
    (async () => {
      const lang = await storage.get(KEYS.language);
      if (lang) await setLanguage(lang as LanguageCode);
      setLangLoaded(true);
      setOnboardingComplete(await storage.getBool(KEYS.onboardingComplete));
    })();
  }, []);

  if (!ready || !langLoaded || onboardingComplete === null) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  // Gate 2: onboarding (creates account, records acceptance, sets capital).
  if (!onboardingComplete) {
    return <OnboardingFlow onComplete={() => setOnboardingComplete(true)} />;
  }

  // Gate 3: signed out -> login.
  if (!isAuthenticated) {
    return <AuthScreen onRestartOnboarding={() => setOnboardingComplete(false)} />;
  }

  // Gate 4: legal docs changed since last acceptance -> re-accept.
  if (!hasCurrentAcceptance) {
    return (
      <RiskDisclosure
        onAccepted={() => {
          /* AppContext.refreshAcceptance already ran; state updates re-render */
        }}
        onBack={() => void logout()}
      />
    );
  }

  // Gate 5: main app.
  return (
    <HashRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/signals" element={<Signals />} />
          <Route path="/news" element={<News />} />
          <Route path="/learn" element={<Learn />} />
          <Route
            path="/account"
            element={<Settings onSignedOut={() => setOnboardingComplete(true)} />}
          />
        </Route>
        <Route path="/paywall" element={<Paywall />} />
        <Route path="*" element={<Navigate to="/signals" replace />} />
      </Routes>
    </HashRouter>
  );
}
