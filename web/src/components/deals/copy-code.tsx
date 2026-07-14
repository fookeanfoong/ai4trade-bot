'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Copy, Check } from 'lucide-react';

export function CopyCode({ code }: { code: string }) {
  const t = useTranslations('deals');
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(code);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          /* ignore */
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-primary/60 bg-primary/5 px-2.5 py-1 font-mono text-sm hover:bg-primary/10"
    >
      {code}
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5 text-muted-foreground" />}
      <span className="sr-only">{copied ? t('copied') : t('copy')}</span>
    </button>
  );
}
