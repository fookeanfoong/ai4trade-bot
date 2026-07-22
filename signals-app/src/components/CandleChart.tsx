/**
 * Interactive candlestick illustration using lightweight-charts.
 * Used by the Learn guides for K-line / support-resistance / pattern diagrams.
 */
import { useEffect, useRef } from 'react';
import { createChart, ColorType, type IChartApi } from 'lightweight-charts';
import type { CandleSeries } from '@/lib/types';

export default function CandleChart({ series }: { series: CandleSeries }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#0f1826' },
        textColor: '#9ca3af',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      rightPriceScale: { borderColor: '#1f2937' },
      timeScale: { borderColor: '#1f2937', fixLeftEdge: true, fixRightEdge: true },
      width: el.clientWidth,
      height: 240,
      handleScale: { mouseWheel: false },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });
    candleSeries.setData(series.candles);

    // Optional support/resistance reference lines.
    for (const level of series.levels ?? []) {
      candleSeries.createPriceLine({
        price: level.price,
        color: '#3b82f6',
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: level.label,
      });
    }

    chart.timeScale().fitContent();

    const onResize = () => chart.applyOptions({ width: el.clientWidth });
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [series]);

  return (
    <figure className="my-3">
      <div ref={containerRef} className="overflow-hidden rounded-card border border-border" />
      <figcaption className="mt-1 text-center text-[11px] text-muted">{series.caption}</figcaption>
    </figure>
  );
}
