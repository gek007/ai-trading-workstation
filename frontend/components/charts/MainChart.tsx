"use client";
import { useEffect, useRef } from "react";
import { useApp } from "@/contexts/AppContext";
import type { IChartApi, ISeriesApi } from "lightweight-charts";

export default function MainChart() {
  const { selectedTicker, history, prices } = useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    let chart: IChartApi;

    // Dynamic import to avoid SSR issues — lightweight-charts v5 API
    import("lightweight-charts").then(({ createChart, ColorType, AreaSeries }) => {
      if (!containerRef.current) return;

      chart = createChart(containerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "#0d1117" },
          textColor: "#8b949e",
        },
        grid: {
          vertLines: { color: "#21262d" },
          horzLines: { color: "#21262d" },
        },
        crosshair: { mode: 1 },
        rightPriceScale: { borderColor: "#30363d" },
        timeScale: {
          borderColor: "#30363d",
          timeVisible: true,
          secondsVisible: false,
        },
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });

      // v5 uses addSeries(SeriesType, options) instead of addAreaSeries(options)
      const series = chart.addSeries(AreaSeries, {
        lineColor: "#209dd7",
        topColor: "rgba(32,157,215,0.25)",
        bottomColor: "rgba(32,157,215,0.02)",
        lineWidth: 2,
        priceLineVisible: true,
        crosshairMarkerVisible: true,
      });

      chartRef.current = chart;
      seriesRef.current = series;
    });

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Update data when selectedTicker or history changes
  useEffect(() => {
    if (!seriesRef.current || !selectedTicker) return;

    const pts = history.get(selectedTicker) ?? [];
    if (pts.length === 0) return;

    // Lightweight Charts requires strictly ascending integer time values
    const seen = new Set<number>();
    const deduped = pts
      .map((p) => ({ time: Math.floor(p.time) as unknown as import("lightweight-charts").Time, value: p.value }))
      .filter((p) => {
        const t = p.time as unknown as number;
        if (seen.has(t)) return false;
        seen.add(t);
        return true;
      })
      .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));

    seriesRef.current.setData(deduped);
    chartRef.current?.timeScale().fitContent();
  }, [selectedTicker, history]);

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header flex items-center gap-3">
        <span>{selectedTicker ?? "Select a ticker"}</span>
        {selectedTicker && prices.get(selectedTicker) && (
          <span className="font-mono text-accent-blue font-semibold">
            ${prices.get(selectedTicker)!.price.toFixed(2)}
          </span>
        )}
      </div>
      <div ref={containerRef} className="flex-1 min-h-0">
        {!selectedTicker && (
          <div className="h-full flex items-center justify-center text-muted text-sm">
            Click a ticker in the watchlist to view its chart
          </div>
        )}
      </div>
    </div>
  );
}
