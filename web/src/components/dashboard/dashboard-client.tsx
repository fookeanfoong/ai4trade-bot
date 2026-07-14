'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Heart, Bell, Star, Trash2, Download, LogOut } from 'lucide-react';
import { Link, useRouter } from '@/i18n/routing';
import { useUserStore } from '@/store/user-store';
import { providers, getProvider } from '@/lib/data/providers';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

type Tab = 'favorites' | 'reviews' | 'alerts' | 'data';

export function DashboardClient() {
  const t = useTranslations('dashboard');
  const acc = useTranslations('account');
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [tab, setTab] = useState<Tab>('favorites');
  const store = useUserStore();

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  if (!store.user) {
    return (
      <div className="py-16 text-center">
        <p className="text-muted-foreground">{t('loginRequired')}</p>
        <Link
          href="/auth"
          className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          {t('goLogin')}
        </Link>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'favorites', label: t('tabFavorites'), icon: <Heart className="h-4 w-4" /> },
    { key: 'reviews', label: t('tabReviews'), icon: <Star className="h-4 w-4" /> },
    { key: 'alerts', label: t('tabAlerts'), icon: <Bell className="h-4 w-4" /> },
    { key: 'data', label: t('tabData'), icon: <Download className="h-4 w-4" /> },
  ];

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('welcome')}, {store.user.name} · {store.user.email}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { store.logout(); router.push('/'); }}>
          <LogOut className="h-3.5 w-3.5" /> {acc('logout')}
        </Button>
      </div>

      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={cn(
              'flex items-center gap-1.5 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium',
              tab === tb.key ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {tb.icon}
            {tb.label}
          </button>
        ))}
      </div>

      {tab === 'favorites' && <ProviderList slugs={store.favorites} empty={t('noFavorites')} browse={t('browse')} onRemove={store.toggleFavorite} />}
      {tab === 'alerts' && <ProviderList slugs={store.alerts} empty={t('noAlerts')} browse={t('browse')} onRemove={store.toggleAlert} removeLabel={t('removeAlert')} />}
      {tab === 'reviews' && <ReviewsTab />}
      {tab === 'data' && <DataTab />}
    </div>
  );
}

function ProviderList({
  slugs,
  empty,
  browse,
  onRemove,
  removeLabel,
}: {
  slugs: string[];
  empty: string;
  browse: string;
  onRemove: (slug: string) => void;
  removeLabel?: string;
}) {
  if (slugs.length === 0) {
    return (
      <div className="py-12 text-center">
        <p className="text-muted-foreground">{empty}</p>
        <Link href="/providers" className="mt-3 inline-block text-sm text-primary hover:underline">
          {browse} →
        </Link>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {slugs.map((slug) => {
        const p = getProvider(slug);
        if (!p) return null;
        return (
          <Card key={slug}>
            <CardContent className="flex items-center gap-3 p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.logo} alt="" width={36} height={36} className="h-9 w-9 rounded-lg" />
              <Link href={`/providers/${p.slug}`} className="font-medium hover:text-primary">
                {p.name}
              </Link>
              <span className="ml-auto text-xs text-muted-foreground">
                Trust {p.trust_score} · {p.uptime_30d}% · {p.avg_latency_ms}ms
              </span>
              <Button variant="ghost" size="sm" onClick={() => onRemove(slug)}>
                <Trash2 className="h-3.5 w-3.5" /> {removeLabel}
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function ReviewsTab() {
  const t = useTranslations('dashboard');
  const store = useUserStore();
  const [slug, setSlug] = useState(providers[0].slug);
  const [rating, setRating] = useState(5);
  const [content, setContent] = useState('');

  function submit() {
    if (!content.trim()) return;
    const p = getProvider(slug)!;
    store.addReview({ providerSlug: slug, providerName: p.name, rating, content: content.trim() });
    setContent('');
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-3 p-5">
          <p className="font-medium">{t('writeReview')}</p>
          <div className="flex flex-wrap gap-3">
            <select
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              aria-label={t('pickProvider')}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <button key={i} onClick={() => setRating(i)} aria-label={`${i} ${t('myRating')}`}>
                  <Star className={cn('h-5 w-5', i <= rating ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/40')} />
                </button>
              ))}
            </div>
          </div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={3}
            placeholder={t('reviewPlaceholder')}
            className="w-full rounded-md border border-input bg-background p-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button size="sm" disabled={!content.trim()} onClick={submit}>
            {t('submitReview')}
          </Button>
        </CardContent>
      </Card>

      {store.reviews.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">{t('noReviews')}</p>
      ) : (
        <div className="space-y-3">
          {store.reviews.map((r) => (
            <Card key={r.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{r.providerName}</span>
                    <span className="flex">
                      {[1, 2, 3, 4, 5].map((i) => (
                        <Star key={i} className={cn('h-3.5 w-3.5', i <= r.rating ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/40')} />
                      ))}
                    </span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => store.removeReview(r.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <p className="mt-2 text-sm">{r.content}</p>
                <p className="mt-1 text-xs text-muted-foreground">{new Date(r.createdAt).toLocaleDateString()}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function DataTab() {
  const t = useTranslations('dashboard');
  const store = useUserStore();

  function exportJson() {
    const data = store.exportData();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'aggreapi-my-data.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-5">
          <p className="font-medium">{t('exportTitle')}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t('exportDesc')}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={exportJson}>
            <Download className="h-3.5 w-3.5" /> {t('exportBtn')}
          </Button>
        </CardContent>
      </Card>
      <Card className="border-destructive/40">
        <CardContent className="p-5">
          <p className="font-medium text-destructive">{t('deleteTitle')}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t('deleteDesc')}</p>
          <Button
            variant="destructive"
            size="sm"
            className="mt-3"
            onClick={() => {
              if (confirm(t('deleteConfirm'))) store.deleteAllData();
            }}
          >
            <Trash2 className="h-3.5 w-3.5" /> {t('deleteBtn')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
