/**
 * Subscription / Paywall.
 *
 * REQUIREMENTS:
 *  - Free trial banner: "3 US trading days free — no card required".
 *  - Three tiles: Monthly $20 (sub_monthly), 6 Months $108 (sub_6month,
 *    "Save 10%"), Yearly $208 (sub_yearly, "Best Value — Save 13%").
 *  - "Restore purchases" button.
 *  - Compliance micro-copy below buttons (auto-renew + Terms link -> in-app
 *    browser).
 *  - Link to AppGallery subscription management.
 *  - Purchases via HMS IAP (native only); web shows an availability note.
 */
import { useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Button, Card } from '@/components/ui';
import { openLegal, openAppGallerySubscriptions } from '@/lib/browser';
import { PRODUCTS, purchase, restorePurchases, type ProductId } from '@/lib/hms/iap';
import { useApp } from '@/context/AppContext';
import { useNavigate } from 'react-router-dom';

export default function Paywall() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { entitlement, refreshEntitlement } = useApp();
  const [busy, setBusy] = useState<ProductId | 'restore' | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function buy(productId: ProductId) {
    setMessage(null);
    setBusy(productId);
    try {
      await purchase(productId);
      await refreshEntitlement();
      navigate('/signals');
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function restore() {
    setMessage(null);
    setBusy('restore');
    try {
      await restorePurchases();
      await refreshEntitlement();
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const currentTier = entitlement?.status === 'active' ? entitlement.tier : null;

  return (
    <div className="flex min-h-full flex-col px-4 py-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{t('paywall.title')}</h1>
        <button onClick={() => navigate(-1)} className="text-sm text-muted">
          {t('common.close')}
        </button>
      </div>

      <div className="mt-4 rounded-card border border-accent/40 bg-accent/10 px-3 py-2 text-center text-sm text-accent">
        {t('paywall.trialBanner')}
      </div>

      <div className="mt-4 space-y-3">
        {PRODUCTS.map((p) => {
          const isCurrent = currentTier === p.productId;
          return (
            <Card key={p.productId} className={isCurrent ? 'border-accent' : ''}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{p.title}</span>
                    {p.badge && (
                      <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent">
                        {p.badge}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 font-mono text-lg">{p.priceLabel}</div>
                  <div className="text-[11px] text-muted">/ {p.period}</div>
                </div>
                <div className="w-28">
                  <Button
                    onClick={() => void buy(p.productId)}
                    disabled={busy !== null || isCurrent}
                  >
                    {isCurrent ? t('paywall.current') : t('paywall.subscribe')}
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="mt-4 space-y-2">
        <Button variant="ghost" onClick={() => void restore()} disabled={busy !== null}>
          {t('paywall.restore')}
        </Button>
        <button
          onClick={() => void openAppGallerySubscriptions()}
          className="w-full py-2 text-center text-xs text-accent underline"
        >
          {t('paywall.manage')}
        </button>
      </div>

      {message && <p className="mt-3 text-center text-xs text-muted">{message}</p>}

      {/* Compliance micro-copy below the purchase buttons. Terms link opens the
          in-app browser. */}
      <p className="mt-5 text-center text-[11px] leading-relaxed text-muted">
        <Trans
          i18nKey="compliance.paywallTerms"
          components={{
            1: (
              <button
                type="button"
                onClick={() => void openLegal('terms')}
                className="text-accent underline"
              />
            ),
          }}
          defaults="Subscriptions auto-renew until cancelled in AppGallery. See the <1>Terms of Service</1> for full subscription terms and refund policy."
        >
          Subscriptions auto-renew until cancelled in AppGallery. See the{' '}
          <button
            type="button"
            onClick={() => void openLegal('terms')}
            className="text-accent underline"
          >
            Terms of Service
          </button>{' '}
          for full subscription terms and refund policy.
        </Trans>
      </p>
    </div>
  );
}
