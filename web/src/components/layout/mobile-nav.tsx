'use client';

import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Link } from '@/i18n/routing';

export function MobileNav({ links }: { links: readonly { href: string; label: string }[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="lg:hidden">
      <button
        className="grid h-10 w-10 place-items-center rounded-md hover:bg-muted"
        aria-label="menu"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>
      {open && (
        <div className="absolute inset-x-0 top-14 border-b border-border bg-background p-2 shadow-lg">
          <nav className="flex flex-col">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-2.5 text-sm hover:bg-muted"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </div>
  );
}
