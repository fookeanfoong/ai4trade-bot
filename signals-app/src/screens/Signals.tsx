/**
 * Home / Today's Signals.
 *
 * REQUIREMENTS:
 *  - Card list per ticker (symbol, company, entry range, stop, target, size,
 *    confidence, brief analysis) — see SignalCard.
 *  - Persistent compliance footer on every view (rendered by MainLayout).
 *  - Free-tier: unlocked for the first 3 US trading days after signup, then a
 *    paywall gate on the cards (entitlement.status === 'expired').
 *  - First-time signal view shows the once-per-install educational modal.
 *  - Offline: falls back to the IndexedDB cache; writes through on success.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import SignalCard from '@/components/SignalCard';
import FirstSignalModal from '@/components/FirstSignalModal';
import { Button, Card, Screen, Spinner } from '@/components/ui';
import { DISCLAIMER_FULL } from '@/lib/compliance';
import * as api from '@/lib/api';
import * as offline from '@/lib/offline';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';
import { SAMPLE_SIGNALS } from '@/lib/fixtures';
import { useApp } from '@/context/AppContext';
import type { Signal } from '@/lib/types';

export default function Signals() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { capitalUsd, entitlement } = useApp();
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const [offlineMode, setOfflineMode] = useState(false);
  const [showFirstModal, setShowFirstModal] = useState(false);

  const locked = entitlement?.status === 'expired';
  const trialDaysLeft =
    entitlement?.status === 'trial' ? Math.max(0, 3 - (entitlement.trialDaysUsed ?? 0)) : 0;

  useEffect(() => {
    (async () => {
      // First-time signal-view modal (once per install).
      const seen = await storage.getBool(KEYS.firstSignalSeen);
      if (!seen) setShowFirstModal(true);

      try {
        const data = await api.getTodaySignals();
        setSignals(data);
        setOfflineMode(false);
        await offline.cacheSignals(data);
      } catch {
        const cached = await offline.readSignals();
        if (cached) {
          setSignals(cached);
          setOfflineMode(true);
        } else {
          // No backend and no cache yet — show placeholder fixtures so the
          // screen is demonstrable before the API is wired.
          setSignals(SAMPLE_SIGNALS);
          setOfflineMode(false);
        }
      }
    })();
  }, []);

  async function dismissFirstModal() {
    await storage.setBool(KEYS.firstSignalSeen, true);
    setShowFirstModal(false);
  }

  return (
    <Screen title={t('signals.title')}>
      {trialDaysLeft > 0 && (
        <div className="px-4 pt-3">
          <div className="rounded-card border border-accent/40 bg-accent/10 px-3 py-2 text-center text-xs text-accent">
            {t('signals.trialBadge', { days: trialDaysLeft })}
          </div>
        </div>
      )}

      {offlineMode && (
        <p className="px-4 pt-3 text-center text-xs text-muted">{t('common.offline')}</p>
      )}

      <div className="space-y-3 px-4 py-4">
        {signals === null && <Spinner label={t('common.loading')} />}

        {signals !== null && locked && <PaywallGate onView={() => navigate('/paywall')} />}

        {signals !== null &&
          !locked &&
          (signals.length === 0 ? (
            <Card>
              <p className="text-center text-sm text-muted">{t('signals.empty')}</p>
            </Card>
          ) : (
            signals.map((s) => <SignalCard key={s.id} signal={s} capitalUsd={capitalUsd} />)
          ))}

        {/* Educational disclaimer inline on the signal screen (in addition to
            the persistent footer banner). */}
        {signals !== null && !locked && (
          <p className="px-2 pt-2 text-center text-[11px] leading-tight text-muted">
            {DISCLAIMER_FULL}
          </p>
        )}
      </div>

      {showFirstModal && <FirstSignalModal onDismiss={() => void dismissFirstModal()} />}
    </Screen>
  );
}

function PaywallGate({ onView }: { onView: () => void }) {
  const { t } = useTranslation();
  return (
    <Card className="text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-border">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="4" y="10" width="16" height="10" rx="2" />
          <path d="M8 10V7a4 4 0 0 1 8 0v3" />
        </svg>
      </div>
      <h2 className="text-base font-bold">{t('signals.locked')}</h2>
      <p className="mx-auto mt-1 max-w-xs text-sm text-muted">{t('signals.lockedBody')}</p>
      <div className="mt-4">
        <Button onClick={onView}>{t('signals.viewPlans')}</Button>
      </div>
    </Card>
  );
}
