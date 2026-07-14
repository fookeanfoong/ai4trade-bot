'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Search } from 'lucide-react';
import { useRouter } from '@/i18n/routing';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export function HeroSearch() {
  const t = useTranslations('home');
  const router = useRouter();
  const [q, setQ] = useState('');

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // 一期:跳到总览页(后续接入全文检索)
    router.push('/providers');
  }

  return (
    <form onSubmit={submit} className="mx-auto flex w-full max-w-xl gap-2">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('searchPlaceholder')}
          className="h-12 pl-9"
          aria-label="search"
        />
      </div>
      <Button type="submit" size="lg" className="h-12">
        {t('searchButton')}
      </Button>
    </form>
  );
}
