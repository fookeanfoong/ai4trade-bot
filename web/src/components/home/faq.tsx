'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface FaqItem {
  q: string;
  a: string;
}

export function Faq({ items }: { items: FaqItem[] }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="mx-auto max-w-3xl divide-y divide-border rounded-xl border border-border">
      {items.map((it, i) => (
        <div key={i}>
          <button
            className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
            onClick={() => setOpen(open === i ? null : i)}
            aria-expanded={open === i}
          >
            <span className="font-medium">{it.q}</span>
            <ChevronDown className={cn('h-4 w-4 shrink-0 transition-transform', open === i && 'rotate-180')} />
          </button>
          {open === i && <p className="px-5 pb-4 text-sm text-muted-foreground">{it.a}</p>}
        </div>
      ))}
    </div>
  );
}
