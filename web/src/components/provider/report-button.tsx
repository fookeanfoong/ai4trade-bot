'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Flag, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

// 举报入口(一期为占位交互;二期接入工单/审核队列)
export function ReportButton({ providerName }: { providerName: string }) {
  const t = useTranslations('detail');
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [sent, setSent] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive"
      >
        <Flag className="h-3.5 w-3.5" />
        {t('report')}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="relative w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
              onClick={() => setOpen(false)}
            >
              <X className="h-4 w-4" />
            </button>
            <h3 className="text-lg font-semibold">
              {t('report')} · {providerName}
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">{t('reportHint')}</p>
            {sent ? (
              <p className="mt-4 text-sm text-emerald-500">✓ {t('copied')}</p>
            ) : (
              <>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={4}
                  className="mt-4 w-full rounded-md border border-input bg-background p-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder={t('reportHint')}
                />
                <div className="mt-4 flex justify-end">
                  <Button size="sm" disabled={!reason.trim()} onClick={() => setSent(true)}>
                    {t('report')}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
