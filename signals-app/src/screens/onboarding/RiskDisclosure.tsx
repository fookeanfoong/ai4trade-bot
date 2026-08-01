/**
 * ============================================================================
 * Risk Disclosure & Legal Acceptance — CANNOT BE SKIPPED.
 * ============================================================================
 *
 * REQUIREMENTS (all enforced here):
 *  - Full-screen scrollable summary of key risks.
 *  - Three SEPARATE checkboxes the user MUST tick to proceed:
 *      1. Accept Terms of Service     (link -> in-app browser)
 *      2. Accept Privacy Policy       (link -> in-app browser)
 *      3. Read/understood Risk Disclosure + confirm 18+  (link -> in-app browser)
 *  - "Continue" disabled until all three are ticked.
 *  - On continue: POST /user/acceptance so the timestamp is stored on the
 *    backend against the user account (server stamps timestamp + ip).
 *  - Each link opens in the in-app browser (@capacitor/browser), NOT the system
 *    browser.
 */
import { useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Button, Checkbox } from '@/components/ui';
import { openLegal } from '@/lib/browser';
import * as api from '@/lib/api';
import { getAppVersion } from '@/lib/appInfo';
import { useApp } from '@/context/AppContext';
import type { LegalDocKey } from '@/lib/compliance';

/** Inline link that opens a legal doc in the in-app browser.
 *  `children` is optional because <Trans> injects the label text at runtime. */
function LegalLink({ doc, children }: { doc: LegalDocKey; children?: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={() => void openLegal(doc)}
      className="text-accent underline decoration-dotted underline-offset-2"
    >
      {children}
    </button>
  );
}

export default function RiskDisclosure({
  onAccepted,
  onBack,
}: {
  onAccepted: () => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const { refreshAcceptance } = useApp();
  const [terms, setTerms] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [risk, setRisk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allAccepted = terms && privacy && risk;

  async function handleContinue() {
    if (!allAccepted) return;
    setError(null);
    setBusy(true);
    try {
      const appVersion = await getAppVersion();
      // Records terms/privacy/risk versions + app version; backend stamps the
      // timestamp and ip against the user account.
      await api.recordAcceptance(appVersion);
      await refreshAcceptance();
      onAccepted();
    } catch {
      setError(t('onboarding.acceptanceError'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-border px-6 py-4">
        <h1 className="text-xl font-bold">{t('onboarding.riskTitle')}</h1>
        <p className="mt-1 text-sm text-muted">{t('onboarding.riskIntro')}</p>
      </header>

      {/* Scrollable risk summary */}
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
        <RiskBlock heading={t('onboarding.riskH1')} body={t('onboarding.riskP1')} />
        <RiskBlock heading={t('onboarding.riskH2')} body={t('onboarding.riskP2')} />
        <RiskBlock heading={t('onboarding.riskH3')} body={t('onboarding.riskP3')} />
        <RiskBlock heading={t('onboarding.riskH4')} body={t('onboarding.riskP4')} />
      </div>

      {/* Sticky acceptance panel */}
      <div className="space-y-4 border-t border-border bg-surface px-6 py-5">
        <Checkbox id="accept-terms" checked={terms} onChange={setTerms}>
          <Trans
            i18nKey="onboarding.acceptTerms"
            components={{ 1: <LegalLink doc="terms" /> }}
            defaults="I have read and accept the <1>Terms of Service</1>"
          >
            I have read and accept the <LegalLink doc="terms">Terms of Service</LegalLink>
          </Trans>
        </Checkbox>

        <Checkbox id="accept-privacy" checked={privacy} onChange={setPrivacy}>
          <Trans
            i18nKey="onboarding.acceptPrivacy"
            components={{ 1: <LegalLink doc="privacy" /> }}
            defaults="I have read and accept the <1>Privacy Policy</1>"
          >
            I have read and accept the <LegalLink doc="privacy">Privacy Policy</LegalLink>
          </Trans>
        </Checkbox>

        <Checkbox id="accept-risk" checked={risk} onChange={setRisk}>
          <Trans
            i18nKey="onboarding.acceptRisk"
            components={{ 1: <LegalLink doc="riskDisclosure" /> }}
            defaults="I have read and understood the <1>Risk Disclosure</1> and confirm I am 18 years or older"
          >
            I have read and understood the{' '}
            <LegalLink doc="riskDisclosure">Risk Disclosure</LegalLink> and confirm I am 18 years or
            older
          </Trans>
        </Checkbox>

        {error && <p className="text-sm text-bear">{error}</p>}

        <div className="flex gap-3 pt-1">
          <Button variant="ghost" onClick={onBack} className="flex-1">
            {t('common.back')}
          </Button>
          <Button onClick={() => void handleContinue()} disabled={!allAccepted || busy} className="flex-1">
            {busy ? t('common.loading') : t('common.continue')}
          </Button>
        </div>
      </div>
    </div>
  );
}

function RiskBlock({ heading, body }: { heading: string; body: string }) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-text">{heading}</h2>
      <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
    </section>
  );
}
