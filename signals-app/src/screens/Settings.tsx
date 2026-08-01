/**
 * Settings / Account.
 *
 * REQUIREMENTS:
 *  - Account info (email, join date, subscription status).
 *  - Manage subscription (deeplink to AppGallery).
 *  - Capital size (editable).
 *  - Push notification preferences (signal / news / product).
 *  - Language: English / Simplified Chinese / Traditional Chinese.
 *  - Legal section: Privacy Policy, Terms of Service, Risk Disclosure (each
 *    opens the URL in the in-app browser) + "Acceptance recorded on [date]".
 *  - Contact support (mailto).
 *  - App version + build number.
 *  - Sign out / Delete account.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Card, Screen, TextInput } from '@/components/ui';
import { openLegal, openAppGallerySubscriptions, openSupportMail } from '@/lib/browser';
import { getAppBuild, getAppVersion } from '@/lib/appInfo';
import { SUPPORTED_LANGUAGES, setLanguage, type LanguageCode } from '@/i18n';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';
import { useApp, type NotifPrefs } from '@/context/AppContext';
import type { LegalDocKey } from '@/lib/compliance';

const SUPPORT_EMAIL = import.meta.env.VITE_SUPPORT_EMAIL ?? 'support@aicompareapi.com';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h2 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {title}
      </h2>
      <Card className="divide-y divide-border p-0">{children}</Card>
    </section>
  );
}

function Row({
  label,
  value,
  onClick,
  danger,
}: {
  label: string;
  value?: string;
  onClick?: () => void;
  danger?: boolean;
}) {
  const Comp = onClick ? 'button' : 'div';
  return (
    <Comp
      onClick={onClick}
      className={`flex w-full items-center justify-between px-4 py-3 text-left ${
        onClick ? 'active:bg-surface' : ''
      }`}
    >
      <span className={`text-sm ${danger ? 'text-bear' : 'text-text'}`}>{label}</span>
      {value !== undefined && <span className="font-mono text-xs text-muted">{value}</span>}
      {onClick && !value && (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 6l6 6-6 6" />
        </svg>
      )}
    </Comp>
  );
}

export default function Settings({ onSignedOut }: { onSignedOut: () => void }) {
  const { t, i18n } = useTranslation();
  const { user, entitlement, acceptance, capitalUsd, notifPrefs, setCapital, setNotifPrefs, logout, deleteAccount } =
    useApp();
  const [version, setVersion] = useState('');
  const [build, setBuild] = useState('');
  const [capitalDraft, setCapitalDraft] = useState(String(capitalUsd || ''));

  useEffect(() => {
    void getAppVersion().then(setVersion);
    void getAppBuild().then(setBuild);
  }, []);

  useEffect(() => {
    setCapitalDraft(String(capitalUsd || ''));
  }, [capitalUsd]);

  async function changeLanguage(code: LanguageCode) {
    await setLanguage(code);
    await storage.set(KEYS.language, code);
  }

  function toggleNotif(key: keyof NotifPrefs) {
    void setNotifPrefs({ ...notifPrefs, [key]: !notifPrefs[key] });
  }

  const subStatus = entitlement ? t(`settings.status_${entitlement.status}`) : '—';
  const acceptanceDate = acceptance
    ? new Date(acceptance.timestamp).toLocaleDateString()
    : null;

  const legalRows: { key: LegalDocKey; label: string }[] = [
    { key: 'privacy', label: t('settings.privacy') },
    { key: 'terms', label: t('settings.terms') },
    { key: 'riskDisclosure', label: t('settings.risk') },
  ];

  async function handleDelete() {
    if (!window.confirm(t('settings.deleteConfirm'))) return;
    await deleteAccount();
    onSignedOut();
  }

  async function handleSignOut() {
    await logout();
    onSignedOut();
  }

  return (
    <Screen title={t('settings.title')}>
      <div className="px-4 pb-8">
        {/* Account */}
        <Section title={t('settings.accountSection')}>
          <Row label={t('settings.emailLabel')} value={user?.email ?? '—'} />
          {user?.joinDate && (
            <Row
              label={t('settings.joinedLabel')}
              value={new Date(user.joinDate).toLocaleDateString()}
            />
          )}
          <Row label={t('settings.subStatusLabel')} value={subStatus} />
          <Row label={t('settings.manageSub')} onClick={() => void openAppGallerySubscriptions()} />
        </Section>

        {/* Capital */}
        <Section title={t('settings.capitalSection')}>
          <div className="p-4">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <TextInput
                  label={t('onboarding.capitalLabel')}
                  type="number"
                  inputMode="decimal"
                  min={0}
                  value={capitalDraft}
                  onChange={(e) => setCapitalDraft(e.target.value)}
                />
              </div>
              <div className="w-24">
                <Button
                  onClick={() => void setCapital(Number(capitalDraft) || 0)}
                  disabled={!(Number(capitalDraft) > 0)}
                >
                  {t('common.save')}
                </Button>
              </div>
            </div>
          </div>
        </Section>

        {/* Notifications */}
        <Section title={t('settings.notifSection')}>
          <Toggle label={t('settings.notifSignals')} on={notifPrefs.signals} onToggle={() => toggleNotif('signals')} />
          <Toggle label={t('settings.notifNews')} on={notifPrefs.news} onToggle={() => toggleNotif('news')} />
          <Toggle label={t('settings.notifProduct')} on={notifPrefs.product} onToggle={() => toggleNotif('product')} />
        </Section>

        {/* Language */}
        <Section title={t('settings.languageSection')}>
          {SUPPORTED_LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => void changeLanguage(lang.code)}
              className="flex w-full items-center justify-between px-4 py-3 text-left active:bg-surface"
            >
              <span className="text-sm text-text">{lang.label}</span>
              {i18n.language === lang.code && (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              )}
            </button>
          ))}
        </Section>

        {/* Legal */}
        <Section title={t('settings.legalSection')}>
          {legalRows.map((r) => (
            <Row key={r.key} label={r.label} onClick={() => void openLegal(r.key)} />
          ))}
          <div className="px-4 py-3">
            <p className="text-[11px] text-muted">
              {acceptanceDate
                ? t('settings.acceptedOn', { date: acceptanceDate })
                : t('settings.acceptedUnknown')}
            </p>
          </div>
        </Section>

        {/* Support & about */}
        <Section title={t('common.account')}>
          <Row label={t('settings.support')} onClick={() => openSupportMail(SUPPORT_EMAIL)} />
          <Row label={t('settings.version')} value={version ? `${version} (${build})` : '—'} />
        </Section>

        {/* Danger zone */}
        <Section title="">
          <Row label={t('settings.signOut')} onClick={() => void handleSignOut()} />
          <Row label={t('settings.deleteAccount')} onClick={() => void handleDelete()} danger />
        </Section>
      </div>
    </Screen>
  );
}

function Toggle({ label, on, onToggle }: { label: string; on: boolean; onToggle: () => void }) {
  return (
    <button onClick={onToggle} className="flex w-full items-center justify-between px-4 py-3 text-left">
      <span className="text-sm text-text">{label}</span>
      <span
        className={`relative h-6 w-10 rounded-full transition-colors ${on ? 'bg-accent' : 'bg-border'}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
            on ? 'translate-x-[18px]' : 'translate-x-0.5'
          }`}
        />
      </span>
    </button>
  );
}
