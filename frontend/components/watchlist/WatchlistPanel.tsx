"use client";
import { useState } from "react";
import { useApp } from "@/contexts/AppContext";
import { fmt } from "@/lib/utils";
import Sparkline from "./Sparkline";

export default function WatchlistPanel() {
  const {
    watchlist,
    prices,
    sparklineHistory,
    flashMap,
    selectedTicker,
    setSelectedTicker,
    addTicker,
    removeTicker,
  } = useApp();
  const [newTicker, setNewTicker] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = newTicker.trim().toUpperCase();
    if (!t || !/^[A-Z]{1,5}$/.test(t)) {
      setError("1–5 uppercase letters only");
      return;
    }
    setAdding(true);
    setError("");
    try {
      await addTicker(t);
      setNewTicker("");
    } catch (err: unknown) {
      const detail =
        (err as { error?: { message?: string } })?.error?.message ??
        (err as { detail?: string })?.detail ??
        "Failed to add";
      setError(detail);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">Watchlist</div>

      <div className="flex-1 overflow-y-auto">
        {watchlist.map((item) => {
          const live = prices.get(item.ticker);
          const price = live?.price ?? item.price;
          const changePct = live?.change_percent ?? item.change_percent;
          const dir = live?.direction ?? (item.change_percent >= 0 ? "up" : "down");
          const sparkData = (sparklineHistory.get(item.ticker) ?? []).map((p) => p.value);
          const flash = flashMap.get(item.ticker);

          return (
            <div
              key={item.ticker}
              onClick={() => setSelectedTicker(item.ticker)}
              className={`watchlist-row group ${selectedTicker === item.ticker ? "selected" : ""} ${
                flash === "up" ? "flash-up" : flash === "down" ? "flash-down" : ""
              }`}
            >
              <div className="flex flex-col justify-center min-w-0 w-16">
                <span className="font-semibold text-sm text-accent-yellow leading-none">
                  {item.ticker}
                </span>
              </div>

              <div className="flex-1 flex items-center justify-center px-1">
                <Sparkline data={sparkData} width={72} height={24} />
              </div>

              <div className="flex flex-col items-end justify-center w-28">
                <span className={`font-mono text-sm font-medium ${fmt.dirClass(dir)}`}>
                  {price > 0 ? fmt.price(price) : "—"}
                </span>
                <span className={`font-mono text-xs ${fmt.dirClass(dir)}`}>
                  {price > 0 ? fmt.pct(changePct) : ""}
                </span>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeTicker(item.ticker);
                }}
                className="ml-1 opacity-0 group-hover:opacity-100 text-muted hover:text-down text-xs px-1 transition-opacity"
                title={`Remove ${item.ticker}`}
                aria-label={`Remove ${item.ticker} from watchlist`}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>

      <form onSubmit={handleAdd} className="border-t border-border px-3 py-2 flex gap-2">
        <input
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          placeholder="TICKER"
          maxLength={5}
          className="input flex-1 uppercase text-sm"
          disabled={adding}
          aria-label="Add ticker symbol"
        />
        <button type="submit" className="btn-accent text-xs px-3 py-1" disabled={adding}>
          {adding ? "…" : "Add"}
        </button>
      </form>
      {error && <p className="text-down text-xs px-3 pb-1">{error}</p>}
    </div>
  );
}
