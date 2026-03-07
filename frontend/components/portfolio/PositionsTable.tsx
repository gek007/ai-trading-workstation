"use client";
import { useApp } from "@/contexts/AppContext";
import { fmt } from "@/lib/utils";

export default function PositionsTable() {
  const { portfolio } = useApp();
  const positions = portfolio?.positions ?? [];

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">Positions</div>
      <div className="flex-1 overflow-y-auto min-h-0">
        {positions.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted text-sm">
            No open positions
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-secondary">
              <tr className="text-muted border-b border-border">
                {["Ticker", "Qty", "Avg Cost", "Price", "Mkt Value", "P&L", "%"].map((h) => (
                  <th key={h} className="px-3 py-2 text-right first:text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={pos.ticker} className="border-b border-border/40 hover:bg-bg-tertiary transition-colors">
                  <td className="px-3 py-2 font-semibold text-accent-yellow">{pos.ticker}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt.qty(pos.quantity)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt.price(pos.avg_cost)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt.price(pos.current_price)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt.price(pos.market_value)}</td>
                  <td className={`px-3 py-2 text-right font-mono ${fmt.plClass(pos.unrealized_pl)}`}>
                    {pos.unrealized_pl >= 0 ? "+" : ""}{fmt.price(pos.unrealized_pl)}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${fmt.plClass(pos.unrealized_pl_percent)}`}>
                    {fmt.pct(pos.unrealized_pl_percent)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
