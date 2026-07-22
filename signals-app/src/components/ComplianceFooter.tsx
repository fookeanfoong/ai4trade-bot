/**
 * Persistent compliance footer — fixed above the tab bar on every Signals
 * (and other main) view. Shows the short disclaimer plus a "Learn more" link
 * that opens the Risk Disclosure in the in-app browser.
 *
 * REQUIREMENT: must be visible on every Signals view.
 */
import { useTranslation } from 'react-i18next';
import { openLegal } from '@/lib/browser';

export default function ComplianceFooter() {
  const { t } = useTranslation();
  return (
    <div className="border-t border-border bg-surface px-4 py-2 text-center">
      <p className="text-[11px] leading-tight text-muted">
        {t('compliance.disclaimerShort')}{' '}
        <button
          type="button"
          onClick={() => void openLegal('riskDisclosure')}
          className="underline decoration-dotted underline-offset-2 hover:text-text"
        >
          {t('common.learnMore')}
        </button>
      </p>
    </div>
  );
}
