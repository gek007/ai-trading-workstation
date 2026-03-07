"use client";
import { useEffect, useRef, useState } from "react";
import type { ConnectionStatus, PricePoint, PriceUpdate, PriceUpdateEvent } from "@/lib/types";

export interface SSEState {
  prices: Map<string, PriceUpdate>;
  history: Map<string, PricePoint[]>; // per-ticker price history for charts
  connectionStatus: ConnectionStatus;
}

const MAX_HISTORY = 300; // keep last 300 data points per ticker

export function useSSE(): SSEState {
  const [prices, setPrices] = useState<Map<string, PriceUpdate>>(new Map());
  const [history, setHistory] = useState<Map<string, PricePoint[]>>(new Map());
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (esRef.current) esRef.current.close();

      const es = new EventSource("/api/stream/prices");
      esRef.current = es;

      es.onopen = () => setConnectionStatus("connected");

      es.onerror = () => {
        setConnectionStatus("reconnecting");
        es.close();
        retryTimer = setTimeout(connect, 3000);
      };

      es.addEventListener("price_update", (e: MessageEvent) => {
        const event: PriceUpdateEvent = JSON.parse(e.data);

        setPrices((prev) => {
          const next = new Map(prev);
          for (const u of event.tickers) next.set(u.ticker, u);
          return next;
        });

        setHistory((prev) => {
          const next = new Map(prev);
          for (const u of event.tickers) {
            const pts = next.get(u.ticker) ?? [];
            const updated = [...pts, { time: u.timestamp, value: u.price }];
            next.set(u.ticker, updated.length > MAX_HISTORY ? updated.slice(-MAX_HISTORY) : updated);
          }
          return next;
        });
      });
    };

    connect();

    return () => {
      clearTimeout(retryTimer);
      esRef.current?.close();
    };
  }, []);

  return { prices, history, connectionStatus };
}
