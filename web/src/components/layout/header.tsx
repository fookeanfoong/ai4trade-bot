import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/routing';
import { ThemeToggle } from '@/components/theme-toggle';
import { LocaleSwitcher } from '@/components/locale-switcher';
import { MobileNav } from '@/components/layout/mobile-nav';
import { AccountNav } from '@/components/layout/account-nav';

export function Header() {
  const t = useTranslations('nav');
  const links = [
    { href: '/', label: t('home') },
    { href: '/providers', label: t('providers') },
    { href: '/compare', label: t('compare') },
    { href: '/models', label: t('models') },
    { href: '/deals', label: t('deals') },
    { href: '/rankings', label: t('rankings') },
    { href: '/blog', label: t('blog') },
  ] as const;

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur">
      <div className="container flex h-14 items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 font-bold">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground text-sm">
              A
            </span>
            <span className="hidden sm:inline">AggreAPI</span>
          </Link>
          <nav className="hidden items-center gap-1 lg:flex">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-1">
          <LocaleSwitcher />
          <ThemeToggle />
          <AccountNav />
          <MobileNav links={links} />
        </div>
      </div>
    </header>
  );
}
