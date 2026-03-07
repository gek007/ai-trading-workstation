"use client";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/contexts/AppContext";
import { fmt } from "@/lib/utils";

export default function ChatPanel() {
  const { chatMessages, chatLoading, sendMessage } = useApp();
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, chatLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const msg = input.trim();
    if (!msg || chatLoading) return;
    setInput("");
    await sendMessage(msg);
  };

  return (
    <div className={`panel flex flex-col transition-all ${open ? "h-72" : "h-10"}`}>
      {/* Header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="panel-header flex items-center justify-between w-full text-left"
      >
        <span className="flex items-center gap-2">
          <span className="text-accent-purple">◈</span> FinAlly AI
        </span>
        <span className="text-muted text-xs">{open ? "▼" : "▲"}</span>
      </button>

      {open && (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 text-sm">
            {chatMessages.length === 0 && (
              <p className="text-muted text-xs italic">
                Ask me about your portfolio, request trades, or add tickers to your watchlist.
              </p>
            )}

            {chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-accent-purple/20 text-primary border border-accent-purple/30"
                      : "bg-bg-tertiary text-primary border border-border"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {/* Executed actions */}
                  {msg.executed_actions && (
                    <div className="mt-2 pt-2 border-t border-border/50 space-y-1">
                      {msg.executed_actions.trades.map((t) => (
                        <div key={t.id} className={`text-xs font-mono ${t.side === "buy" ? "text-up" : "text-down"}`}>
                          {t.side === "buy" ? "▲ Bought" : "▼ Sold"} {fmt.qty(t.quantity)} {t.ticker} @{" "}
                          {fmt.price(t.price)}
                        </div>
                      ))}
                      {msg.executed_actions.watchlist_changes.map((c, i) => (
                        <div key={i} className="text-xs font-mono text-accent-blue">
                          {c.action === "added" ? "+ Added" : "− Removed"} {c.ticker} to watchlist
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-xs text-muted">
                  <span className="animate-pulse">FinAlly is thinking…</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} className="border-t border-border p-2 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask FinAlly anything…"
              className="input flex-1 text-sm"
              disabled={chatLoading}
            />
            <button
              type="submit"
              disabled={chatLoading || !input.trim()}
              className="btn-purple px-4 py-1.5 text-sm font-semibold disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </>
      )}
    </div>
  );
}
