import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useSSEPrices } from "@/hooks/useSSEPrices";
import type { PriceUpdate } from "@/lib/types";

// ── Helpers ──────────────────────────────────────────────────────────────────

function makePriceUpdate(overrides: Partial<PriceUpdate> = {}): PriceUpdate {
  return {
    ticker: "AAPL",
    price: 190.5,
    previous_price: 190.25,
    change: 0.25,
    change_percent: 0.13,
    direction: "up",
    timestamp: "2025-01-15T10:30:45.123Z",
    ...overrides,
  };
}

function dispatchPriceUpdate(
  instance: { addEventListener: ReturnType<typeof vi.fn> },
  updates: PriceUpdate[]
) {
  const handler = instance.addEventListener.mock.calls.find(
    (call: unknown[]) => call[0] === "price_update"
  )?.[1] as ((e: MessageEvent) => void) | undefined;
  handler?.({ data: JSON.stringify({ tickers: updates }) } as MessageEvent);
}

// ── Mock EventSource ──────────────────────────────────────────────────────────

let mockInstance: {
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  onopen: ((e: Event) => void) | null;
  onerror: ((e: Event) => void) | null;
  onmessage: ((e: MessageEvent) => void) | null;
  readyState: number;
  url: string;
  withCredentials: boolean;
};

let MockEventSource: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();

  mockInstance = {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    close: vi.fn(),
    onopen: null,
    onerror: null,
    onmessage: null,
    readyState: 1,
    url: "",
    withCredentials: false,
  };

  // Regular function (not arrow) so vitest's spy can handle `new MockEventSource()`
  MockEventSource = vi.fn().mockImplementation(function () { return mockInstance; });
  Object.defineProperty(MockEventSource, "CONNECTING", { value: 0, configurable: true });
  Object.defineProperty(MockEventSource, "OPEN", { value: 1, configurable: true });
  Object.defineProperty(MockEventSource, "CLOSED", { value: 2, configurable: true });

  global.EventSource = MockEventSource as unknown as typeof EventSource;
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe("useSSEPrices", () => {
  describe("initialization", () => {
    it("initializes with empty state and disconnected status", () => {
      const { result } = renderHook(() => useSSEPrices());
      expect(result.current.prices.size).toBe(0);
      expect(result.current.sparklineHistory.size).toBe(0);
      expect(result.current.chartHistory.size).toBe(0);
      expect(result.current.connectionStatus).toBe("disconnected");
      expect(result.current.flashMap.size).toBe(0);
    });

    it("connects to /api/stream/prices on mount", () => {
      renderHook(() => useSSEPrices());
      expect(MockEventSource).toHaveBeenCalledWith("/api/stream/prices");
    });

    it("transitions to connected when EventSource opens", () => {
      const { result } = renderHook(() => useSSEPrices());
      act(() => {
        mockInstance.onopen?.(new Event("open"));
      });
      expect(result.current.connectionStatus).toBe("connected");
    });
  });

  describe("price updates", () => {
    it("stores incoming price updates in prices map", () => {
      const { result } = renderHook(() => useSSEPrices());
      const update = makePriceUpdate();

      act(() => {
        dispatchPriceUpdate(mockInstance, [update]);
      });

      expect(result.current.prices.get("AAPL")).toEqual(update);
    });

    it("accumulates sparkline history per ticker", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 100, timestamp: "2025-01-15T10:00:00.000Z" })]);
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 101, timestamp: "2025-01-15T10:00:01.000Z" })]);
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 102, timestamp: "2025-01-15T10:00:02.000Z" })]);
      });

      const history = result.current.sparklineHistory.get("AAPL");
      expect(history).toHaveLength(3);
      expect(history?.[0].value).toBe(100);
      expect(history?.[2].value).toBe(102);
    });

    it("accumulates chart history per ticker", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 200, timestamp: "2025-01-15T10:00:00.000Z" })]);
      });

      const history = result.current.chartHistory.get("AAPL");
      expect(history).toHaveLength(1);
      expect(history?.[0].value).toBe(200);
    });

    it("converts ISO timestamp to Unix seconds for PricePoints", () => {
      const { result } = renderHook(() => useSSEPrices());
      const isoTimestamp = "2025-01-15T10:00:00.000Z";
      const expectedUnix = Math.floor(new Date(isoTimestamp).getTime() / 1000);

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ timestamp: isoTimestamp })]);
      });

      const history = result.current.sparklineHistory.get("AAPL");
      expect(history?.[0].time).toBe(expectedUnix);
    });

    it("tracks multiple tickers independently", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [
          makePriceUpdate({ ticker: "AAPL", price: 190 }),
          makePriceUpdate({ ticker: "GOOGL", price: 175 }),
        ]);
      });

      expect(result.current.prices.get("AAPL")?.price).toBe(190);
      expect(result.current.prices.get("GOOGL")?.price).toBe(175);
    });

    it("caps sparkline history at configured size", () => {
      const { result } = renderHook(() =>
        useSSEPrices({ bufferConfig: { sparklineSize: 3 } })
      );

      act(() => {
        for (let i = 0; i < 5; i++) {
          dispatchPriceUpdate(mockInstance, [
            makePriceUpdate({
              price: 100 + i,
              timestamp: `2025-01-15T10:00:0${i}.000Z`,
            }),
          ]);
        }
      });

      expect(result.current.sparklineHistory.get("AAPL")).toHaveLength(3);
    });

    it("caps chart history at configured size", () => {
      const { result } = renderHook(() =>
        useSSEPrices({ bufferConfig: { mainChartSize: 2 } })
      );

      act(() => {
        for (let i = 0; i < 4; i++) {
          dispatchPriceUpdate(mockInstance, [
            makePriceUpdate({
              price: 100 + i,
              timestamp: `2025-01-15T10:00:0${i}.000Z`,
            }),
          ]);
        }
      });

      expect(result.current.chartHistory.get("AAPL")).toHaveLength(2);
    });
  });

  describe("price flash on change", () => {
    it("triggers flash-up when price increases", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 190 })]);
      });
      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 191 })]);
      });

      expect(result.current.flashMap.get("AAPL")).toBe("up");
    });

    it("triggers flash-down when price decreases", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 191 })]);
      });
      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 190 })]);
      });

      expect(result.current.flashMap.get("AAPL")).toBe("down");
    });

    it("does not flash on first price (no previous value)", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 190 })]);
      });

      expect(result.current.flashMap.get("AAPL")).toBeUndefined();
    });

    it("does not flash when price is unchanged", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 190 })]);
      });
      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 190 })]);
      });

      expect(result.current.flashMap.get("AAPL")).toBeUndefined();
    });

    it("clears flash after 500ms", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 190 })]);
      });
      act(() => {
        dispatchPriceUpdate(mockInstance, [makePriceUpdate({ price: 191 })]);
      });
      expect(result.current.flashMap.get("AAPL")).toBe("up");

      act(() => {
        vi.advanceTimersByTime(500);
      });

      expect(result.current.flashMap.get("AAPL")).toBeUndefined();
    });

    it("respects flash cooldown — suppresses rapid-fire flashes", () => {
      const { result } = renderHook(() =>
        useSSEPrices({ bufferConfig: { flashCooldown: 500 } })
      );

      act(() => {
        result.current.triggerFlash("AAPL", "up");
      });
      expect(result.current.flashMap.get("AAPL")).toBe("up");

      act(() => {
        result.current.triggerFlash("AAPL", "down");
      });
      // still "up" because cooldown hasn't elapsed
      expect(result.current.flashMap.get("AAPL")).toBe("up");
    });
  });

  describe("triggerFlash / clearFlashes", () => {
    it("triggerFlash sets flash direction for ticker", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        result.current.triggerFlash("AAPL", "up");
      });

      expect(result.current.flashMap.get("AAPL")).toBe("up");
    });

    it("clearFlashes removes all active flashes", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        result.current.triggerFlash("AAPL", "up");
        result.current.triggerFlash("GOOGL", "down");
      });
      expect(result.current.flashMap.size).toBe(2);

      act(() => {
        result.current.clearFlashes();
      });

      expect(result.current.flashMap.size).toBe(0);
    });
  });

  describe("reconnect logic", () => {
    it("transitions to reconnecting on SSE error", () => {
      const { result } = renderHook(() => useSSEPrices());

      act(() => {
        mockInstance.onerror?.(new Event("error"));
      });

      expect(result.current.connectionStatus).toBe("reconnecting");
    });

    it("closes EventSource on SSE error before retrying", () => {
      renderHook(() => useSSEPrices());

      act(() => {
        mockInstance.onerror?.(new Event("error"));
      });

      expect(mockInstance.close).toHaveBeenCalled();
    });

    it("schedules reconnect after error with exponential backoff", () => {
      renderHook(() => useSSEPrices());
      const callCountBefore = MockEventSource.mock.calls.length;

      act(() => {
        mockInstance.onerror?.(new Event("error"));
      });

      // First retry: 1000ms (1 * 2^0)
      act(() => {
        vi.advanceTimersByTime(1000);
      });

      expect(MockEventSource.mock.calls.length).toBeGreaterThan(callCountBefore);
    });

    it("resets retry count to 0 on successful reconnect", () => {
      const { result } = renderHook(() => useSSEPrices());

      // Simulate error then open
      act(() => {
        mockInstance.onerror?.(new Event("error"));
      });
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      act(() => {
        mockInstance.onopen?.(new Event("open"));
      });

      expect(result.current.connectionStatus).toBe("connected");
    });
  });

  describe("cleanup", () => {
    it("closes EventSource on unmount", () => {
      const { unmount } = renderHook(() => useSSEPrices());
      unmount();
      expect(mockInstance.close).toHaveBeenCalled();
    });

    it("does not crash on unmount", () => {
      const { unmount } = renderHook(() => useSSEPrices());
      expect(() => unmount()).not.toThrow();
    });

    it("cancels pending retry timer on unmount", () => {
      const { unmount } = renderHook(() => useSSEPrices());

      act(() => {
        mockInstance.onerror?.(new Event("error"));
      });

      unmount();

      // Advancing timers after unmount should not create a new EventSource
      const callCountAfterUnmount = MockEventSource.mock.calls.length;
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      expect(MockEventSource.mock.calls.length).toBe(callCountAfterUnmount);
    });
  });

  describe("callbacks", () => {
    it("calls onPriceUpdate when a price arrives", () => {
      const onPriceUpdate = vi.fn();
      renderHook(() => useSSEPrices({ onPriceUpdate }));
      const update = makePriceUpdate();

      act(() => {
        dispatchPriceUpdate(mockInstance, [update]);
      });

      expect(onPriceUpdate).toHaveBeenCalledWith("AAPL", update);
    });

    it("calls onConnectionChange when status changes", () => {
      const onConnectionChange = vi.fn();
      renderHook(() => useSSEPrices({ onConnectionChange }));

      act(() => {
        mockInstance.onopen?.(new Event("open"));
      });

      expect(onConnectionChange).toHaveBeenCalledWith("connected");
    });
  });
});
