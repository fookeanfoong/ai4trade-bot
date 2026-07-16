'use client';

import { useEffect } from 'react';

// 分析:自托管(Plausible / Umami / 百度统计)+ GA4 + Microsoft Clarity。全部可选,靠环境变量开启。
// 规则:① 默认关闭(env 为空则不加载对应脚本);② 仅在用户同意「分析」类 Cookie 后加载(GDPR);
// ③ GA4 为 Google 服务、国内可能被墙——自托管与百度统计用于覆盖国内,GA4 覆盖海外。
const CONSENT_KEY = 'aggreapi.cookie.consent.v1';

function analyticsAllowed(): boolean {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    if (!raw) return false;
    return !!JSON.parse(raw).analytics;
  } catch {
    return false;
  }
}

function marketingAllowed(): boolean {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    if (!raw) return false;
    return !!JSON.parse(raw).marketing;
  } catch {
    return false;
  }
}

// Google AdSense 主脚本 —— 仅在用户同意「营销」类 Cookie 后加载(GDPR)。
// 广告位由 <AdSlot> 渲染;未配置 NEXT_PUBLIC_ADSENSE_CLIENT 时完全不加载。
function injectAds() {
  if (typeof document === 'undefined') return;
  if (document.getElementById('aggreapi-ads-loaded')) return;
  if (!marketingAllowed()) return;
  const client = process.env.NEXT_PUBLIC_ADSENSE_CLIENT; // ca-pub-XXXXXXXXXXXXXXXX
  if (!client) return;

  const marker = document.createElement('meta');
  marker.id = 'aggreapi-ads-loaded';
  document.head.appendChild(marker);

  const s = document.createElement('script');
  s.async = true;
  s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${client}`;
  s.crossOrigin = 'anonymous';
  document.head.appendChild(s);
}

function inject() {
  if (typeof document === 'undefined') return;
  if (document.getElementById('aggreapi-analytics-loaded')) return;
  if (!analyticsAllowed()) return;

  const marker = document.createElement('meta');
  marker.id = 'aggreapi-analytics-loaded';
  document.head.appendChild(marker);

  const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
  const plausibleSrc = process.env.NEXT_PUBLIC_PLAUSIBLE_SRC; // 自托管脚本地址
  const umamiUrl = process.env.NEXT_PUBLIC_UMAMI_URL;
  const umamiId = process.env.NEXT_PUBLIC_UMAMI_ID;
  const baiduId = process.env.NEXT_PUBLIC_BAIDU_TONGJI_ID;
  const gaId = process.env.NEXT_PUBLIC_GA_ID; // GA4 Measurement ID(G-XXXXXXXXXX)
  const clarityId = process.env.NEXT_PUBLIC_CLARITY_ID; // Microsoft Clarity 项目 ID

  if (plausibleDomain && plausibleSrc) {
    const s = document.createElement('script');
    s.defer = true;
    s.setAttribute('data-domain', plausibleDomain);
    s.src = plausibleSrc;
    document.head.appendChild(s);
  }

  if (umamiUrl && umamiId) {
    const s = document.createElement('script');
    s.defer = true;
    s.src = umamiUrl;
    s.setAttribute('data-website-id', umamiId);
    document.head.appendChild(s);
  }

  // 百度统计(国内合规,非被墙资源)
  if (baiduId) {
    const s = document.createElement('script');
    s.text = `var _hmt=_hmt||[];(function(){var hm=document.createElement("script");hm.src="https://hm.baidu.com/hm.js?${baiduId}";var s=document.getElementsByTagName("script")[0];s.parentNode.insertBefore(hm,s);})();`;
    document.head.appendChild(s);
  }

  // Google Analytics 4(覆盖海外流量;国内可能被墙,由自托管/百度覆盖)
  if (gaId) {
    const g = document.createElement('script');
    g.async = true;
    g.src = `https://www.googletagmanager.com/gtag/js?id=${gaId}`;
    document.head.appendChild(g);
    const g2 = document.createElement('script');
    g2.text = `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${gaId}');`;
    document.head.appendChild(g2);
  }

  // Microsoft Clarity(点击热图 / 会话回放)
  if (clarityId) {
    const c = document.createElement('script');
    c.text = `(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","${clarityId}");`;
    document.head.appendChild(c);
  }
}

export function Analytics() {
  useEffect(() => {
    inject();
    injectAds();
    // 用户在 Cookie 弹窗保存同意后再加载(分析→analytics,广告→marketing)
    const onConsent = () => {
      inject();
      injectAds();
    };
    window.addEventListener('aggreapi:consent', onConsent);
    return () => window.removeEventListener('aggreapi:consent', onConsent);
  }, []);
  return null;
}
