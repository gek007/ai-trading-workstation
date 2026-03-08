"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ConnectionStatus,
  PricePoint,
  PriceUpdate,
  PriceUpdateEvent,
} from "@/lib/types";

export interface PriceBufferConfig {
  sparklineSize: number;
  mainChartSize: number;
  flashCooldown: number;
}

export interface UseSSEPricesOptions {
  bufferConfig?: Partial<PriceBufferConfig>;
  onPriceUpdate?: (ticker: string, update: PriceUpdate) => void;
  onConnectionChange?: (status: ConnectionStatus) => void;
}

export interface SSEPricesState {
  prices: Map<string, PriceUpdate>;
  sparklineHistory: Map<string, PricePoint[]>;
  chartHistory: Map<string, PricePoint[]>;
  connectionStatus: ConnectionStatus;
  flashMap: Map<string, "up" | "down">;
  triggerFlash: (ticker: string, direction: "up" | "down") => void;
  clearFlashes: () => void;
}

const DEFAULT_CONFIG: PriceBufferConfig = {
  sparklineSize: 100,
  mainChartSize: 500,
  flashCooldown: 300,
};

const RETRY_BASE_MS = 1000;
const RETRY_MAX_MS = 30000;

export function useSSEPrices(options: UseSSEPricesOptions = {}): SSEPricesState {
  const { bufferConfig: partialConfig, onPriceUpdate, onConnectionChange } = options;

  const config: PriceBufferConfig = { ...DEFAULT_CONFIG, ...partialConfig };

  const [prices, setPrices] = useState<Map<string, PriceUpdate>>(new Map());
  const [sparklineHistory, setSparklineHistory] = useState<Map<string, PricePoint[]>>(new Map());
  const [chartHistory, setChartHistory] = useState<Map<string, PricePoint[]>>(new Map());
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");
  const [flashMap, setFlashMap] = useState<Map<string, "up" | "down">>(new Map());

  const flashCooldowns = useRef<Map<string, number>>(new Map());
  const prevPrices = useRef<Map<string, number>>(new Map());
  const esRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);
  const flashTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const updateConnectionStatus = useCallback(
    (status: ConnectionStatus) => {
      setConnectionStatus(status);
      onConnectionChange?.(status);
    },
    [onConnectionChange]
  );

  const triggerFlash = useCallback(
    (ticker: string, direction: "up" | "down") => {
      const now = Date.now();
      const lastFlash = flashCooldowns.current.get(ticker) ?? 0;
      if (now - lastFlash < config.flashCooldown) return;

      flashCooldowns.current.set(ticker, now);
      setFlashMap((prev) => new Map(prev).set(ticker, direction));

      const existingTimer = flashTimersRef.current.get(ticker);
      if (existingTimer) clearTimeout(existingTimer);

      const timer = setTimeout(() => {
        setFlashMap((prev) => {
          const next = new Map(prev);
          next.delete(ticker);
          return next;
        });
        flashTimersRef.current.delete(ticker);
      }, 500);

      flashTimersRef.current.set(ticker, timer);
    },
    [config.flashCooldown]
  );

  const clearFlashes = useCallback(() => {
    flashTimersRef.current.forEach((timer) => clearTimeout(timer));
    flashTimersRef.current.clear();
    setFlashMap(new Map());
  }, []);

  const processPriceUpdates = useCallback(
    (updates: PriceUpdate[]) => {
      setPrices((prev) => {
        const next = new Map(prev);
        for (const update of updates) {
          next.set(update.ticker, update);
          const prevPrice = prevPrices.current.get(update.ticker);
          if (prevPrice !== undefined && prevPrice !== update.price) {
            triggerFlash(update.ticker, update.price > prevPrice ? "up" : "down");
          }
          prevPrices.current.set(update.ticker, update.price);
          onPriceUpdate?.(update.ticker, update);
        }
        return next;
      });

      setSparklineHistory((prev) => {
        const next = new Map(prev);
        for (const update of updates) {
          const existing = next.get(update.ticker) ?? [];
          const point: PricePoint = {
            time: Math.floor(new Date(update.timestamp).getTime() / 1000),
            value: update.price,
          };
          const updated = [...existing, point];
          next.set(
            update.ticker,
            updated.length > config.sparklineSize ? updated.slice(-config.sparklineSize) : updated
          );
        }
        return next;
      });

      setChartHistory((prev) => {
        const next = new Map(prev);
        for (const update of updates) {
          const existing = next.get(update.ticker) ?? [];
          const point: PricePoint = {
            time: Math.floor(new Date(update.timestamp).getTime() / 1000),
            value: update.price,
          };
          const updated = [...existing, point];
          next.set(
            update.ticker,
            updated.length > config.mainChartSize ? updated.slice(-config.mainChartSize) : updated
          );
        }
        return next;
      });
    },
    [config.sparklineSize, config.mainChartSize, triggerFlash, onPriceUpdate]
  );

  useEffect(() => {
    let mounted = true;

    const connect = () => {
      if (!mounted) return;
      if (esRef.current) esRef.current.close();

      try {
        const es = new EventSource("/api/stream/prices");
        esRef.current = es;

        es.onopen = () => {
          if (!mounted) return;
          retryCountRef.current = 0;
          updateConnectionStatus("connected");
        };

        es.onerror = () => {
          if (!mounted) return;
          updateConnectionStatus("reconnecting");
          es.close();

          if (retryTimerRef.current) clearTimeout(retryTimerRef.current);

          // Exponential backoff: 1s, 2s, 4s, 8s, ... capped at 30s
          const delay = Math.min(RETRY_BASE_MS * 2 ** retryCountRef.current, RETRY_MAX_MS);
          retryCountRef.current += 1;
          retryTimerRef.current = setTimeout(connect, delay);
        };

        es.addEventListener("price_update", (e: MessageEvent) => {
          if (!mounted) return;
          try {
            const event: PriceUpdateEvent = JSON.parse(e.data);
            processPriceUpdates(event.tickers);
          } catch (error) {
            console.error("Failed to parse SSE price update:", error);
          }
        });
      } catch (error) {
        console.error("Failed to create EventSource:", error);
        updateConnectionStatus("disconnected");

        if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
        const delay = Math.min(RETRY_BASE_MS * 2 ** retryCountRef.current, RETRY_MAX_MS);
        retryCountRef.current += 1;
        retryTimerRef.current = setTimeout(connect, delay);
      }
    };

    connect();

    return () => {
      mounted = false;
      esRef.current?.close();
      esRef.current = null;
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      flashTimersRef.current.forEach((timer) => clearTimeout(timer));
      flashTimersRef.current.clear();
    };
  }, [processPriceUpdates, updateConnectionStatus]);

  return {
    prices,
    sparklineHistory,
    chartHistory,
    connectionStatus,
    flashMap,
    triggerFlash,
    clearFlashes,
  };
}
