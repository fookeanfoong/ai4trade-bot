'use client';

import { useEffect } from 'react';

// 自托管分析:Plausible / Umami / 百度统计。全部为可选,靠环境变量开启。
// 规则:① 默认关闭(env 为空则不加载任何脚本);② 仅在用户同意「分析」类 Cookie 后加载;
// ③ 不使用 Google Analytics / GTM 等被墙服务。
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
}

export function Analytics() {
  useEffect(() => {
    inject();
    // 用户在 Cookie 弹窗保存「分析」同意后再加载
    const onConsent = () => inject();
    window.addEventListener('aggreapi:consent', onConsent);
    return () => window.removeEventListener('aggreapi:consent', onConsent);
  }, []);
  return null;
}
