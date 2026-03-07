"use client";
import dynamic from "next/dynamic";
import Header from "@/components/Header";
import WatchlistPanel from "@/components/watchlist/WatchlistPanel";
import PortfolioHeatmap from "@/components/portfolio/PortfolioHeatmap";
import PositionsTable from "@/components/portfolio/PositionsTable";
import TradeBar from "@/components/trading/TradeBar";
import ChatPanel from "@/components/chat/ChatPanel";

// Lightweight Charts uses browser APIs — must be client-only
const MainChart = dynamic(() => import("@/components/charts/MainChart"), { ssr: false });

export default function Page() {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg-primary">
      <Header />

      {/* Main content grid */}
      <div className="flex flex-1 min-h-0 gap-2 p-2">
        {/* Left column — Watchlist */}
        <div className="w-64 shrink-0 flex flex-col">
          <WatchlistPanel />
        </div>

        {/* Center + right columns */}
        <div className="flex flex-col flex-1 min-w-0 gap-2">
          {/* Top row: chart + heatmap */}
          <div className="flex gap-2" style={{ height: "55%" }}>
            <div className="flex-1 min-w-0">
              <MainChart />
            </div>
            <div className="w-80 shrink-0 flex flex-col gap-2">
              <div className="flex-1 min-h-0">
                <PortfolioHeatmap />
              </div>
            </div>
          </div>

          {/* Bottom row: positions table */}
          <div className="flex-1 min-h-0">
            <PositionsTable />
          </div>

          {/* Trade bar */}
          <TradeBar />

          {/* AI Chat */}
          <ChatPanel />
        </div>
      </div>
    </div>
  );
}
