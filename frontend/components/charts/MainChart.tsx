"use client";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/contexts/AppContext";
import type { IChartApi, ISeriesApi } from "lightweight-charts";

export default function MainChart() {
  const { selectedTicker, history, prices, connectionStatus } = useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    let chart: IChartApi | null = null;
    let series: ISeriesApi<"Area"> | null = null;

    const initChart = async () => {
      try {
        setIsInitializing(true);
        setChartError(null);

        // Dynamic import to avoid SSR issues — lightweight-charts v5 API
        const { createChart, ColorType, AreaSeries } = await import("lightweight-charts");
        
        if (!containerRef.current) {
          throw new Error("Chart container not available");
        }

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
        series = chart.addSeries(AreaSeries, {
          lineColor: "#209dd7",
          topColor: "rgba(32,157,215,0.25)",
          bottomColor: "rgba(32,157,215,0.02)",
          lineWidth: 2,
          priceLineVisible: true,
          crosshairMarkerVisible: true,
        });

        chartRef.current = chart;
        seriesRef.current = series;
        setIsInitializing(false);
      } catch (error) {
        console.error("Failed to initialize chart:", error);
        setChartError(error instanceof Error ? error.message : "Failed to load chart");
        setIsInitializing(false);
        
        // Cleanup on error
        if (chart) {
          chart.remove();
          chartRef.current = null;
          seriesRef.current = null;
        }
      }
    };

    initChart();

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        try {
          chartRef.current.applyOptions({
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
          });
        } catch (error) {
          console.error("Failed to resize chart:", error);
        }
      }
    });
    
    if (containerRef.current) {
      ro.observe(containerRef.current);
    }

    return () => {
      ro.disconnect();
      if (chart) {
        try {
          chart.remove();
        } catch (error) {
          console.error("Failed to cleanup chart:", error);
        }
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, []);

  // Update data when selectedTicker or history changes
  useEffect(() => {
    if (!seriesRef.current || !selectedTicker || chartError) return;

    try {
      const pts = history.get(selectedTicker) ?? [];
      if (pts.length === 0) return;

      // Lightweight Charts requires strictly ascending integer time values
      const seen = new Set<number>();
      const deduped = pts
        .map((p) => ({ 
          time: Math.floor(p.time) as unknown as import("lightweight-charts").Time, 
          value: p.value 
        }))
        .filter((p) => {
          const t = p.time as unknown as number;
          if (seen.has(t)) return false;
          seen.add(t);
          return true;
        })
        .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));

      seriesRef.current.setData(deduped);
      chartRef.current?.timeScale().fitContent();
    } catch (error) {
      console.error("Failed to update chart data:", error);
      setChartError(error instanceof Error ? error.message : "Failed to update chart");
    }
  }, [selectedTicker, history, chartError]);

  const connectionStatusColor: Record<string, string> = {
    connected: "bg-up",
    reconnecting: "bg-accent-yellow",
    disconnected: "bg-down",
  };

  const currentPrice = selectedTicker && prices.get(selectedTicker)
    ? prices.get(selectedTicker)!.price
    : null;

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Connection status indicator */}
          <div
            className={`w-2 h-2 rounded-full ${connectionStatusColor[connectionStatus] ?? "bg-muted"}`}
            title={`Connection: ${connectionStatus}`}
            aria-label={`Connection status: ${connectionStatus}`}
          />
          
          {/* Ticker symbol */}
          <span className="font-semibold">
            {selectedTicker ?? "Select a ticker"}
          </span>
          
          {/* Current price */}
          {selectedTicker && currentPrice !== null && (
            <span className="font-mono text-accent-blue font-semibold">
              ${currentPrice.toFixed(2)}
            </span>
          )}
        </div>

        {/* Data status */}
        {selectedTicker && connectionStatus === "connected" && (
          <span className="text-xs text-muted">
            Live
          </span>
        )}
      </div>

      {/* Chart container */}
      <div ref={containerRef} className="flex-1 min-h-0 relative">
        {/* Loading state */}
        {isInitializing && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-primary/80 z-10">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" 
                   aria-label="Loading chart"
                   role="status" />
              <span className="text-sm text-muted">Loading chart...</span>
            </div>
          </div>
        )}

        {/* Error state */}
        {chartError && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-primary z-10">
            <div className="text-center p-4">
              <p className="text-down mb-2">Failed to load chart</p>
              <p className="text-xs text-muted">{chartError}</p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isInitializing && !chartError && !selectedTicker && (
          <div className="h-full flex items-center justify-center text-muted text-sm">
            Click a ticker in the watchlist to view its chart
          </div>
        )}

        {/* No data state */}
        {!isInitializing && !chartError && selectedTicker && !(history.get(selectedTicker)?.length) && (
          <div className="h-full flex items-center justify-center text-muted text-sm">
            Waiting for price data…
          </div>
        )}
      </div>
    </div>
  );
}
