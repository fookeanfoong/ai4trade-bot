'use client';

import { Globe } from 'lucide-react';
import { useLocale } from 'next-intl';
import { useState, useRef, useEffect } from 'react';
import { usePathname, useRouter } from '@/i18n/routing';
import { routing } from '@/i18n/routing';
import { cn } from '@/lib/utils';

const LABELS: Record<string, string> = {
  zh: '简体中文',
  'zh-TW': '繁體中文',
  en: 'English',
  ja: '日本語',
  de: 'Deutsch',
};

export function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex h-10 items-center gap-1.5 rounded-md px-2 text-sm hover:bg-muted"
        aria-label="switch language"
      >
        <Globe className="h-4 w-4" />
        <span className="hidden sm:inline">{LABELS[locale]}</span>
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-1 w-40 rounded-md border border-border bg-card p-1 shadow-lg">
          {routing.locales.map((l) => (
            <button
              key={l}
              onClick={() => {
                router.replace(pathname, { locale: l });
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center rounded px-2 py-1.5 text-sm hover:bg-muted',
                l === locale && 'text-primary font-medium'
              )}
            >
              {LABELS[l]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
