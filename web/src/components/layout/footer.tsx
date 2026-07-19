import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/routing';
import { PwaPromo } from '@/components/pwa-promo';

export function Footer() {
  const t = useTranslations('footer');
  const nav = useTranslations('nav');
  const year = 2026;

  return (
    <footer className="mt-16 border-t border-border bg-card/40">
      <div className="container py-10">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div>
            <p className="mb-3 text-sm font-semibold">{t('product')}</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/providers" className="hover:text-foreground">{nav('providers')}</Link></li>
              <li><Link href="/compare" className="hover:text-foreground">{nav('compare')}</Link></li>
              <li><Link href="/models" className="hover:text-foreground">{nav('models')}</Link></li>
              <li><Link href="/rankings" className="hover:text-foreground">{nav('rankings')}</Link></li>
            </ul>
          </div>
          <div>
            <p className="mb-3 text-sm font-semibold">{t('resources')}</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/report" className="hover:text-foreground">{nav('report')}</Link></li>
              <li><Link href="/blog" className="hover:text-foreground">{nav('blog')}</Link></li>
              <li><Link href="/deals" className="hover:text-foreground">{nav('deals')}</Link></li>
              <li><Link href="/submit" className="hover:text-foreground">{nav('submit')}</Link></li>
            </ul>
          </div>
          <div>
            <p className="mb-3 text-sm font-semibold">{t('legal')}</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/legal/terms" className="hover:text-foreground">{t('terms')}</Link></li>
              <li><Link href="/legal/privacy" className="hover:text-foreground">{t('privacy')}</Link></li>
              <li><Link href="/legal/cookies" className="hover:text-foreground">{t('cookies')}</Link></li>
              <li><Link href="/legal/disclaimer" className="hover:text-foreground">{t('disclaimer')}</Link></li>
              <li><Link href="/legal/affiliate-disclosure" className="hover:text-foreground">{t('affiliateDisclosure')}</Link></li>
            </ul>
          </div>
          <div>
            <p className="mb-3 text-sm font-semibold">{t('about')}</p>
            <ul className="mb-3 space-y-2 text-sm text-muted-foreground">
              <li><Link href="/about" className="hover:text-foreground">{nav('about')}</Link></li>
              <li><Link href="/contact" className="hover:text-foreground">{nav('contact')}</Link></li>
            </ul>
            {/* 亚洲合规:ICP / 公安 / 生成式 AI 备案预留位 */}
            <ul className="space-y-2 text-xs text-muted-foreground">
              <li>{t('icpPlaceholder')}</li>
              <li>{t('psbPlaceholder')}</li>
              <li>{t('genAiPlaceholder')}</li>
            </ul>
          </div>
        </div>

        {/* AI4Trade Signals PWA 入口(仅在设置 NEXT_PUBLIC_PWA_URL 后显示) */}
        <PwaPromo />

        {/* Affiliate Disclosure —— FTC / 欧盟强制,显眼位置 */}
        <div className="mt-8 rounded-lg border border-border bg-muted/30 p-4">
          <p className="text-xs font-semibold text-foreground">{t('affiliateDisclosure')}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{t('affiliateText')}</p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{t('aiNotice')}</p>
        </div>

        <div className="mt-6 flex flex-col items-center justify-between gap-2 text-xs text-muted-foreground md:flex-row">
          <p>© {year} AggreAPI. {t('rights')}.</p>
          <p>{/* 主域名 .com;hreflang="zh-CN" 指向未来中国镜像已在 <head> 预留 */}</p>
        </div>
      </div>
    </footer>
  );
}
