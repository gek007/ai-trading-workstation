"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import * as api from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import type {
  ChatMessage,
  ConnectionStatus,
  ExecutedActions,
  PortfolioResponse,
  PricePoint,
  PriceUpdate,
  TradeRequest,
  WatchlistItem,
} from "@/lib/types";

interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  content: string;
  executed_actions?: ExecutedActions | null;
  created_at: string;
}

interface AppContextType {
  // Market
  prices: Map<string, PriceUpdate>;
  history: Map<string, PricePoint[]>;
  connectionStatus: ConnectionStatus;
  // Watchlist
  watchlist: WatchlistItem[];
  addTicker: (ticker: string) => Promise<void>;
  removeTicker: (ticker: string) => Promise<void>;
  // Portfolio
  portfolio: PortfolioResponse | null;
  refreshPortfolio: () => Promise<void>;
  executeTrade: (req: TradeRequest) => Promise<void>;
  // UI
  selectedTicker: string | null;
  setSelectedTicker: (t: string | null) => void;
  // Chat
  chatMessages: ChatEntry[];
  chatLoading: boolean;
  sendMessage: (msg: string) => Promise<void>;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { prices, history, connectionStatus } = useSSE();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const refreshPortfolio = useCallback(async () => {
    try {
      const p = await api.getPortfolio();
      setPortfolio(p);
    } catch (e) {
      console.error("portfolio fetch failed", e);
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      const w = await api.getWatchlist();
      setWatchlist(w.tickers);
    } catch (e) {
      console.error("watchlist fetch failed", e);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refreshPortfolio();
    refreshWatchlist();
  }, [refreshPortfolio, refreshWatchlist]);

  // Keep portfolio prices fresh from SSE
  useEffect(() => {
    if (!portfolio || prices.size === 0) return;
    setPortfolio((prev) => {
      if (!prev) return prev;
      const updatedPositions = prev.positions.map((pos) => {
        const p = prices.get(pos.ticker);
        if (!p) return pos;
        const market_value = pos.quantity * p.price;
        const unrealized_pl = market_value - pos.cost_basis;
        const unrealized_pl_percent =
          pos.cost_basis > 0 ? (unrealized_pl / pos.cost_basis) * 100 : 0;
        return {
          ...pos,
          current_price: p.price,
          market_value: Math.round(market_value * 100) / 100,
          unrealized_pl: Math.round(unrealized_pl * 100) / 100,
          unrealized_pl_percent: Math.round(unrealized_pl_percent * 100) / 100,
        };
      });
      const total_mv = updatedPositions.reduce((s, p) => s + p.market_value, 0);
      const total_unrealized_pl = updatedPositions.reduce((s, p) => s + p.unrealized_pl, 0);
      const total_cost = updatedPositions.reduce((s, p) => s + p.cost_basis, 0);
      return {
        ...prev,
        positions: updatedPositions,
        total_value: Math.round((prev.cash_balance + total_mv) * 100) / 100,
        total_unrealized_pl: Math.round(total_unrealized_pl * 100) / 100,
        total_unrealized_pl_percent:
          total_cost > 0
            ? Math.round((total_unrealized_pl / total_cost) * 10000) / 100
            : 0,
      };
    });
  }, [prices]); // eslint-disable-line react-hooks/exhaustive-deps

  const addTicker = useCallback(async (ticker: string) => {
    const res = await api.addTicker(ticker.toUpperCase());
    setWatchlist(res.watchlist.tickers);
  }, []);

  const removeTicker = useCallback(async (ticker: string) => {
    const res = await api.removeTicker(ticker);
    setWatchlist(res.watchlist.tickers);
  }, []);

  const executeTrade = useCallback(async (req: TradeRequest) => {
    const res = await api.executeTrade(req);
    setPortfolio(res.portfolio);
  }, []);

  const sendMessage = useCallback(async (msg: string) => {
    const userEntry: ChatEntry = {
      id: Date.now().toString(),
      role: "user",
      content: msg,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, userEntry]);
    setChatLoading(true);
    try {
      const res = await api.sendChatMessage(msg);
      setChatMessages((prev) => [
        ...prev,
        {
          id: res.message.id,
          role: "assistant",
          content: res.message.content,
          executed_actions: res.executed_actions,
          created_at: res.message.created_at,
        },
      ]);
      // Refresh portfolio + watchlist if the LLM executed actions
      if (res.executed_actions) {
        await Promise.all([refreshPortfolio(), refreshWatchlist()]);
      }
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail ?? "Failed to send message";
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: `Error: ${detail}`,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }, [refreshPortfolio, refreshWatchlist]);

  return (
    <AppContext.Provider
      value={{
        prices,
        history,
        connectionStatus,
        watchlist,
        addTicker,
        removeTicker,
        portfolio,
        refreshPortfolio,
        executeTrade,
        selectedTicker,
        setSelectedTicker,
        chatMessages,
        chatLoading,
        sendMessage,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppContextType {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside <AppProvider>");
  return ctx;
}
