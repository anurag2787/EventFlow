"use client";

import {
  FiPlus,
  FiRefreshCw,
  FiGithub,
  FiLogOut,
  FiDatabase,
} from "react-icons/fi";

interface NavbarProps {
  apiBase: string;
  cacheHeader: string;
  syncing: boolean;
  currentUser: { username: string } | null;
  onOpenTrackModal: () => void;
  onTriggerSyncAll: () => void;
  onLogout: () => void;
}

export default function Navbar({
  apiBase,
  cacheHeader,
  syncing,
  currentUser,
  onOpenTrackModal,
  onTriggerSyncAll,
  onLogout,
}: NavbarProps) {
  const cleanUsername = currentUser?.username
    ? currentUser.username.replace(/^@/, "").trim()
    : "";

  return (
    <header className="sticky top-0 z-40 bg-[#0B0E12]/85 backdrop-blur-md border-b border-[#2A3038]/80 transition-colors">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between gap-4">

        {/* Brand */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-[#E6EDF3] tracking-tight">
            EventFlow
          </span>
          <span className="text-xs text-[#8B949E] font-mono">Stream</span>
        </div>

        {/* Nav Actions */}
        <div className="flex items-center gap-2.5">
          {/* Redis Cache Status Pill */}
          <div
            className={`hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border transition-colors cursor-help ${
              cacheHeader === "HIT"
                ? "bg-[#13251A] text-[#3FB950] border-[#3FB950]/30"
                : "bg-[#2B2013] text-[#D29922] border-[#D29922]/30"
            }`}
            title="Redis Cache status for Activity Stream (5-min TTL)"
          >
            <FiDatabase className="w-3.5 h-3.5 shrink-0 opacity-80" />
            <span className="font-mono text-[11px] font-medium">
              Cache: {cacheHeader}
            </span>
          </div>

          {/* Track Repo Button */}
          <button
            onClick={onOpenTrackModal}
            className="flex items-center gap-1.5 bg-[#151A20] hover:bg-[#1F242D] border border-[#2A3038] hover:border-[#58A6FF]/40 text-[#C9D1D9] hover:text-[#58A6FF] px-3 py-1.5 rounded-md text-xs font-medium transition-all shadow-sm active:scale-95"
          >
            <FiPlus className="w-3.5 h-3.5 text-[#58A6FF]" />
            <span>Track Repo</span>
          </button>

          {/* Sync All Button */}
          <button
            onClick={onTriggerSyncAll}
            disabled={syncing}
            className="flex items-center gap-1.5 bg-[#151A20] hover:bg-[#1F242D] border border-[#2A3038] hover:border-[#3FB950]/40 text-[#C9D1D9] hover:text-[#3FB950] px-3 py-1.5 rounded-md text-xs font-medium transition-all shadow-sm active:scale-95 disabled:opacity-50"
          >
            <FiRefreshCw
              className={`w-3.5 h-3.5 ${
                syncing ? "animate-spin text-[#3FB950]" : "text-[#3FB950]"
              }`}
            />
            <span>{syncing ? "Syncing…" : "Sync All"}</span>
          </button>

          {/* GitHub Login OR Logged-in User Profile Badge */}
          {currentUser ? (
            <div className="flex items-center gap-2.5 bg-[#151A20] border border-[#2A3038] hover:border-[#8B949E]/50 rounded-md px-2.5 py-1 transition-all">
              <div className="relative w-5 h-5 rounded-full overflow-hidden border border-[#30363D] shrink-0">
                <img
                  src={`https://github.com/${cleanUsername}.png`}
                  alt={cleanUsername}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = "none";
                  }}
                />
              </div>
              <span className="font-semibold text-xs text-[#E6EDF3] max-w-[110px] truncate">
                {cleanUsername}
              </span>
              <div className="h-3 w-[1px] bg-[#2A3038]" />
              <button
                onClick={onLogout}
                className="text-[#8B949E] hover:text-[#F85149] p-0.5 rounded transition-colors"
                title="Log out of session"
              >
                <FiLogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <a
              href={`${apiBase}/api/auth/github/login/`}
              className="flex items-center gap-1.5 bg-[#238636] hover:bg-[#2ea043] border border-[#2ea043]/60 text-[#E6EDF3] px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all shadow-sm active:scale-95"
            >
              <FiGithub className="w-3.5 h-3.5" />
              <span>Login with GitHub</span>
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
