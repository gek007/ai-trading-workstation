"use client";
import { useApp } from "@/contexts/AppContext";
import { fmt } from "@/lib/utils";

export default function Header() {
  const { portfolio, connectionStatus } = useApp();

  const statusDot = {
    connected: "bg-up",
    reconnecting: "bg-accent-yellow",
    disconnected: "bg-down",
  }[connectionStatus];

  const statusLabel = {
    connected: "Live",
    reconnecting: "Reconnecting…",
    disconnected: "Disconnected",
  }[connectionStatus];

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-bg-secondary border-b border-border h-12 shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <span className="text-accent-yellow font-bold text-lg tracking-tight">FinAlly</span>
        <span className="text-muted text-xs hidden sm:block">AI Trading Workstation</span>
      </div>

      {/* Portfolio summary */}
      <div className="flex items-center gap-6">
        {portfolio ? (
          <>
            <Stat
              label="Total Value"
              value={fmt.price(portfolio.total_value)}
              sub={`${portfolio.total_unrealized_pl >= 0 ? "+" : ""}${fmt.price(portfolio.total_unrealized_pl)} (${fmt.pct(portfolio.total_unrealized_pl_percent)})`}
              subClass={fmt.plClass(portfolio.total_unrealized_pl)}
            />
            <Stat label="Cash" value={fmt.price(portfolio.cash_balance)} />
            <Stat label="Positions" value={String(portfolio.positions.length)} />
          </>
        ) : (
          <span className="text-muted text-xs">Loading…</span>
        )}
      </div>

      {/* Connection status */}
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${statusDot}`} />
        <span className="text-xs text-muted">{statusLabel}</span>
      </div>
    </header>
  );
}

function Stat({ label, value, sub, subClass }: { label: string; value: string; sub?: string; subClass?: string }) {
  return (
    <div className="flex flex-col items-end">
      <span className="text-xs text-muted leading-none">{label}</span>
      <span className="font-mono text-sm font-semibold text-primary leading-tight">{value}</span>
      {sub && <span className={`font-mono text-xs leading-none ${subClass ?? "text-muted"}`}>{sub}</span>}
    </div>
  );
}
