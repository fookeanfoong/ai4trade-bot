'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Heart, Bell } from 'lucide-react';
import { useUserStore } from '@/store/user-store';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// 收藏 + 降价提醒按钮。未登录也可用(存本地),登录后在用户中心统一管理。
export function FavoriteButton({ slug, withAlert = true }: { slug: string; withAlert?: boolean }) {
  const t = useTranslations('account');
  const [mounted, setMounted] = useState(false);
  const favorites = useUserStore((s) => s.favorites);
  const alerts = useUserStore((s) => s.alerts);
  const toggleFavorite = useUserStore((s) => s.toggleFavorite);
  const toggleAlert = useUserStore((s) => s.toggleAlert);

  useEffect(() => setMounted(true), []);
  const faved = mounted && favorites.includes(slug);
  const alerted = mounted && alerts.includes(slug);

  return (
    <div className="flex gap-2">
      <Button
        variant={faved ? 'default' : 'outline'}
        size="sm"
        onClick={() => toggleFavorite(slug)}
        aria-pressed={faved}
      >
        <Heart className={cn('h-3.5 w-3.5', faved && 'fill-current')} />
        {faved ? t('favorited') : t('favorite')}
      </Button>
      {withAlert && (
        <Button
          variant={alerted ? 'default' : 'outline'}
          size="sm"
          onClick={() => toggleAlert(slug)}
          aria-pressed={alerted}
        >
          <Bell className={cn('h-3.5 w-3.5', alerted && 'fill-current')} />
          {t('priceAlert')}
        </Button>
      )}
    </div>
  );
}
