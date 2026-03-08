"use client";
import { useState } from "react";
import { useApp } from "@/contexts/AppContext";
import { fmt } from "@/lib/utils";

export default function TradeBar() {
  const { prices, selectedTicker, executeTrade } = useApp();
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const effectiveTicker = ticker.trim().toUpperCase() || selectedTicker?.toUpperCase() || "";
  const livePrice = prices.get(effectiveTicker)?.price;

  const trade = async (side: "buy" | "sell") => {
    const t = effectiveTicker;
    const q = parseFloat(qty);
    if (!t || !/^[A-Z]{1,5}$/.test(t)) {
      setMessage({ text: "Enter a valid ticker (1-5 letters)", ok: false });
      return;
    }
    if (!q || q <= 0) {
      setMessage({ text: "Enter a valid quantity", ok: false });
      return;
    }

    setLoading(true);
    setMessage(null);
    try {
      const res = await executeTrade({ ticker: t, quantity: q, side });
      const { trade: executed } = res;
      setMessage({
        text: `${executed.side === "buy" ? "Bought" : "Sold"} ${fmt.qty(executed.quantity)} ${executed.ticker} @ ${fmt.price(executed.price)}`,
        ok: true,
      });
      setQty("");
    } catch (err: unknown) {
      const detail =
        (err as { error?: { message?: string } })?.error?.message ??
        (err as { detail?: string })?.detail ??
        "Trade failed";
      setMessage({ text: detail, ok: false });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted text-xs font-medium uppercase tracking-wider mr-1">Trade</span>

        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder={selectedTicker ?? "TICKER"}
          maxLength={5}
          className="input w-24 uppercase font-semibold text-accent-yellow text-sm"
          disabled={loading}
          aria-label="Ticker symbol"
        />

        <input
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder="Qty"
          type="number"
          min="0.0001"
          step="1"
          className="input w-24 text-sm"
          disabled={loading}
          aria-label="Quantity"
        />

        {livePrice && (
          <span className="text-muted text-xs font-mono">
            ≈ {qty ? fmt.price(parseFloat(qty) * livePrice) : fmt.price(livePrice)}
          </span>
        )}

        <button
          onClick={() => trade("buy")}
          disabled={loading}
          className="btn-buy px-5 py-1.5 text-sm font-semibold"
        >
          Buy
        </button>
        <button
          onClick={() => trade("sell")}
          disabled={loading}
          className="btn-sell px-5 py-1.5 text-sm font-semibold"
        >
          Sell
        </button>

        {message && (
          <span className={`text-xs font-mono ml-2 ${message.ok ? "text-up" : "text-down"}`}>
            {message.text}
          </span>
        )}
      </div>
    </div>
  );
}
