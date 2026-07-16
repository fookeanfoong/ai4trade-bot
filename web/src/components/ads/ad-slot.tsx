'use client';

import { useEffect, useRef } from 'react';

// 单个 AdSense 广告位。
// - 未配置 NEXT_PUBLIC_ADSENSE_CLIENT 或未传 slot 时,渲染 null(部落格外观零变化)。
// - 主脚本由 analytics.tsx 在用户同意「营销」Cookie 后才加载;未同意时此 <ins> 保持空白、不显示广告。
// - 按你的计画,仅用于部落格文章(文章内 + 侧栏),不放首页/比价/计算机/详情页。

interface Props {
  slot?: string;
  className?: string;
  format?: string; // 默认 auto(自适应)
  layout?: string; // 例如 'in-article'
}

const CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT;

export function AdSlot({ slot, className, format = 'auto', layout }: Props) {
  const ref = useRef<HTMLModElement>(null);

  useEffect(() => {
    if (!CLIENT || !slot) return;
    try {
      // 若主脚本尚未加载(未同意营销),push 会安全排队,不会报错也不显示广告。
      ((window as unknown as { adsbygoogle?: unknown[] }).adsbygoogle =
        (window as unknown as { adsbygoogle?: unknown[] }).adsbygoogle || []).push({});
    } catch {
      /* 广告加载失败不影响页面 */
    }
  }, [slot]);

  if (!CLIENT || !slot) return null;

  return (
    <ins
      ref={ref}
      className={`adsbygoogle block${className ? ` ${className}` : ''}`}
      style={{ display: 'block' }}
      data-ad-client={CLIENT}
      data-ad-slot={slot}
      data-ad-format={format}
      data-ad-layout={layout}
      data-full-width-responsive="true"
    />
  );
}

// 是否已配置 AdSense(供页面决定要不要留出广告版位/侧栏,避免空框)。
export const adsEnabled = !!CLIENT;
