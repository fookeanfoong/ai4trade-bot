'use client';

import { useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { ExternalLink, X } from 'lucide-react';
import type { Provider } from '@/lib/types';
import { buildAffiliateUrl, cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface Props {
  provider: Provider;
  sourcePage: string;
  className?: string;
  variant?: 'default' | 'outline' | 'secondary' | 'ghost';
  size?: 'default' | 'sm' | 'lg';
  children?: React.ReactNode;
}

// 所有"访问官网/前往购买"按钮都走这里:
// 1) 弹窗提示即将离开本站 + 联盟披露
// 2) 埋点 /api/track/outbound(fire-and-forget)
// 3) 跳转到带 UTM 的 affiliate_url(新标签页,noopener)
export function OutboundLink({
  provider,
  sourcePage,
  className,
  variant = 'default',
  size = 'default',
  children,
}: Props) {
  const t = useTranslations('outbound');
  const [open, setOpen] = useState(false);

  const target = buildAffiliateUrl(provider);

  const go = useCallback(() => {
    // 埋点:不阻塞跳转
    try {
      const payload = JSON.stringify({
        provider_id: provider.id,
        provider_slug: provider.slug,
        source_page: sourcePage,
      });
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/track/outbound', new Blob([payload], { type: 'application/json' }));
      } else {
        fetch('/api/track/outbound', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
          keepalive: true,
        }).catch(() => {});
      }
    } catch {
      /* 埋点失败不影响用户跳转 */
    }
    window.open(target, '_blank', 'noopener,noreferrer');
    setOpen(false);
  }, [provider.id, provider.slug, sourcePage, target]);

  return (
    <>
      <Button
        variant={variant}
        size={size}
        className={className}
        onClick={() => setOpen(true)}
        data-provider={provider.slug}
      >
        {children ?? <span>{t('continue')}</span>}
        <ExternalLink className="h-3.5 w-3.5" />
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setOpen(false)}
        >
          <div
            className="relative w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
              onClick={() => setOpen(false)}
              aria-label="close"
            >
              <X className="h-4 w-4" />
            </button>
            <h3 className="text-lg font-semibold">{t('title')}</h3>
            <p className="mt-3 text-sm text-muted-foreground">
              {t('body', { name: provider.name })}
            </p>
            <p className="mt-3 rounded-md bg-muted/60 p-3 text-xs text-muted-foreground">
              {t('disclosure')}
            </p>
            <div className="mt-5 flex gap-3">
              <Button variant="outline" className="flex-1" onClick={() => setOpen(false)}>
                {t('cancel')}
              </Button>
              <Button className={cn('flex-1')} onClick={go}>
                {t('continue')}
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
