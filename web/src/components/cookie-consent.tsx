'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';

const STORAGE_KEY = 'aggreapi.cookie.consent.v1';

interface Consent {
  necessary: true;
  analytics: boolean;
  marketing: boolean;
}

export function CookieConsent() {
  const t = useTranslations('cookie');
  const [visible, setVisible] = useState(false);
  const [manage, setManage] = useState(false);
  const [analytics, setAnalytics] = useState(true);
  const [marketing, setMarketing] = useState(true);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
    } catch {
      setVisible(true);
    }
  }, []);

  function persist(c: Consent) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...c, ts: Date.now() }));
      // 通知分析组件:同意后即时加载(不刷新页面)
      window.dispatchEvent(new CustomEvent('aggreapi:consent', { detail: c }));
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-[90] border-t border-border bg-card/95 backdrop-blur">
      <div className="container flex flex-col gap-4 py-4 md:flex-row md:items-center md:justify-between">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold">{t('title')}</p>
          <p className="mt-1 text-xs text-muted-foreground">{t('body')}</p>
          {manage && (
            <div className="mt-3 flex flex-wrap gap-4 text-xs">
              <label className="flex items-center gap-1.5 text-muted-foreground">
                <input type="checkbox" checked readOnly className="accent-primary" />
                {t('necessary')}
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={analytics}
                  onChange={(e) => setAnalytics(e.target.checked)}
                  className="accent-primary"
                />
                {t('analytics')}
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={marketing}
                  onChange={(e) => setMarketing(e.target.checked)}
                  className="accent-primary"
                />
                {t('marketing')}
              </label>
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {!manage ? (
            <Button variant="ghost" size="sm" onClick={() => setManage(true)}>
              {t('manage')}
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => persist({ necessary: true, analytics, marketing })}
            >
              {t('save')}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => persist({ necessary: true, analytics: false, marketing: false })}
          >
            {t('rejectAll')}
          </Button>
          <Button size="sm" onClick={() => persist({ necessary: true, analytics: true, marketing: true })}>
            {t('acceptAll')}
          </Button>
        </div>
      </div>
    </div>
  );
}
