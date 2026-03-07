"use client";
import { useMemo } from "react";
import { useApp } from "@/contexts/AppContext";
import { fmt } from "@/lib/utils";

interface Rect {
  ticker: string;
  x: number;
  y: number;
  w: number;
  h: number;
  pl_pct: number;
  market_value: number;
}

function treemap(items: { value: number; ticker: string; pl_pct: number }[], w: number, h: number): Rect[] {
  if (!items.length) return [];
  const total = items.reduce((s, i) => s + i.value, 0);
  if (total === 0) return [];

  const rects: Rect[] = [];
  const remaining = [...items].sort((a, b) => b.value - a.value);

  function squarify(items: typeof remaining, x: number, y: number, w: number, h: number) {
    if (!items.length) return;
    if (items.length === 1) {
      rects.push({ ticker: items[0].ticker, x, y, w, h, pl_pct: items[0].pl_pct, market_value: items[0].value });
      return;
    }

    const totalVal = items.reduce((s, i) => s + i.value, 0);
    let best = Infinity;
    let splitIdx = 1;

    for (let i = 1; i <= items.length; i++) {
      const rowVal = items.slice(0, i).reduce((s, it) => s + it.value, 0);
      const ratio = w >= h ? (h * h * totalVal) / (rowVal * rowVal) : (w * w * totalVal) / (rowVal * rowVal);
      const aspect = Math.max(ratio, 1 / ratio);
      if (aspect > best) break;
      best = aspect;
      splitIdx = i;
    }

    const row = items.slice(0, splitIdx);
    const rest = items.slice(splitIdx);
    const rowVal = row.reduce((s, i) => s + i.value, 0);
    const rowFrac = rowVal / totalVal;

    if (w >= h) {
      const rowW = w * rowFrac;
      let cy = y;
      for (const item of row) {
        const ih = h * (item.value / rowVal);
        rects.push({ ticker: item.ticker, x, y: cy, w: rowW, h: ih, pl_pct: item.pl_pct, market_value: item.value });
        cy += ih;
      }
      squarify(rest, x + rowW, y, w - rowW, h);
    } else {
      const rowH = h * rowFrac;
      let cx = x;
      for (const item of row) {
        const iw = w * (item.value / rowVal);
        rects.push({ ticker: item.ticker, x: cx, y, w: iw, h: rowH, pl_pct: item.pl_pct, market_value: item.value });
        cx += iw;
      }
      squarify(rest, x, y + rowH, w, h - rowH);
    }
  }

  squarify(remaining, 0, 0, w, h);
  return rects;
}

function plColor(pct: number): string {
  if (pct > 5) return "rgba(0,200,83,0.75)";
  if (pct > 2) return "rgba(0,200,83,0.5)";
  if (pct > 0) return "rgba(0,200,83,0.3)";
  if (pct < -5) return "rgba(255,82,82,0.75)";
  if (pct < -2) return "rgba(255,82,82,0.5)";
  if (pct < 0) return "rgba(255,82,82,0.3)";
  return "rgba(139,148,158,0.2)";
}

const W = 400;
const H = 180;

export default function PortfolioHeatmap() {
  const { portfolio } = useApp();
  const positions = portfolio?.positions ?? [];

  const rects = useMemo(() => {
    const items = positions.map((p) => ({
      ticker: p.ticker,
      value: p.market_value,
      pl_pct: p.unrealized_pl_percent,
    }));
    return treemap(items, W, H);
  }, [positions]);

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">Portfolio Heatmap</div>
      <div className="flex-1 flex items-center justify-center p-2 min-h-0">
        {rects.length === 0 ? (
          <span className="text-muted text-sm">No positions yet</span>
        ) : (
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{ maxHeight: 180 }}>
            {rects.map((r) => (
              <g key={r.ticker}>
                <rect
                  x={r.x + 1}
                  y={r.y + 1}
                  width={Math.max(0, r.w - 2)}
                  height={Math.max(0, r.h - 2)}
                  fill={plColor(r.pl_pct)}
                  rx={3}
                />
                {r.w > 40 && r.h > 24 && (
                  <>
                    <text x={r.x + r.w / 2} y={r.y + r.h / 2 - 5} textAnchor="middle" fill="#e6edf3"
                      fontSize={Math.min(14, r.w / 4)} fontWeight="bold">
                      {r.ticker}
                    </text>
                    <text x={r.x + r.w / 2} y={r.y + r.h / 2 + 10} textAnchor="middle"
                      fill={r.pl_pct >= 0 ? "#00c853" : "#ff5252"} fontSize={Math.min(11, r.w / 5)}>
                      {fmt.pct(r.pl_pct)}
                    </text>
                  </>
                )}
              </g>
            ))}
          </svg>
        )}
      </div>
    </div>
  );
}
