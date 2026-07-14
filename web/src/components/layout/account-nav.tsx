'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { User, LayoutDashboard } from 'lucide-react';
import { Link } from '@/i18n/routing';
import { useUserStore } from '@/store/user-store';

export function AccountNav() {
  const t = useTranslations('account');
  const [mounted, setMounted] = useState(false);
  const user = useUserStore((s) => s.user);
  useEffect(() => setMounted(true), []);

  if (mounted && user) {
    return (
      <Link
        href="/dashboard"
        className="inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm hover:bg-muted"
        title={user.name}
      >
        <LayoutDashboard className="h-4 w-4" />
        <span className="hidden sm:inline">{t('dashboard')}</span>
      </Link>
    );
  }

  return (
    <Link
      href="/auth"
      className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-2.5 text-sm hover:bg-muted"
    >
      <User className="h-4 w-4" />
      <span className="hidden sm:inline">{t('login')}</span>
    </Link>
  );
}
