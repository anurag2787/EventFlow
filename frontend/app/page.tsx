"use client";

import { useEffect, useState, useCallback } from "react";
import Navbar from "@/components/Navbar";
import MetricCards from "@/components/MetricCards";
import FilterToolbar from "@/components/FilterToolbar";
import TrackRepoModal from "@/components/TrackRepoModal";
import ActivityRow, {
  getEventDescription,
  getActorUsername,
  isBotActor,
} from "@/components/ActivityRow";
import { ActivityItem, ActivityStats } from "@/components/types";
import {
  FiRefreshCw,
  FiChevronRight,
  FiChevronLeft,
  FiTrendingUp,
} from "react-icons/fi";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function extractOwnerRepo(input: string): string {
  let cleaned = input.trim();
  if (!cleaned) return "";

  // Remove trailing slashes and .git
  cleaned = cleaned.replace(/\/+$/, "").replace(/\.git$/i, "");

  // Match full GitHub URL e.g. https://github.com/facebook/react or https://github.com/facebook/react/issues
  const githubMatch = cleaned.match(
    /(?:https?:\/\/)?(?:www\.)?github\.com\/([^\/]+)\/([^\/\?#]+)/i
  );
  if (githubMatch && githubMatch[1] && githubMatch[2]) {
    return `${githubMatch[1]}/${githubMatch[2]}`;
  }

  // Match owner/repo format e.g. facebook/react
  const parts = cleaned.split("/");
  if (parts.length === 2 && parts[0] && parts[1]) {
    return `${parts[0]}/${parts[1]}`;
  }

  return cleaned;
}

export default function EventFlowDashboard() {
  // ── State ──
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [stats, setStats] = useState<ActivityStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [cacheHeader, setCacheHeader] = useState<string>("MISS");
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  // Pagination
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [prevCursor, setPrevCursor] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [includeBots, setIncludeBots] = useState<boolean>(true);

  // Auth User State
  const [currentUser, setCurrentUser] = useState<{ username: string } | null>(
    null
  );

  // Track Repo Modal
  const [showTrackModal, setShowTrackModal] = useState<boolean>(false);
  const [trackRepoInput, setTrackRepoInput] = useState<string>("");
  const [trackLoading, setTrackLoading] = useState<boolean>(false);
  const [trackMsg, setTrackMsg] = useState<string | null>(null);

  // ── Effects ──

  useEffect(() => {
    // Load bot filter preference from localStorage
    const savedBotPref = localStorage.getItem("eventflow_include_bots");
    if (savedBotPref !== null) {
      setIncludeBots(savedBotPref === "true");
    }

    // Process OAuth Callback params (?login=success&username=...)
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      const loginStatus = urlParams.get("login");
      const usernameParam = urlParams.get("username");

      if (loginStatus === "success" && usernameParam) {
        const u = { username: usernameParam };
        setCurrentUser(u);
        localStorage.setItem("eventflow_user", JSON.stringify(u));
        window.history.replaceState({}, document.title, window.location.pathname);
      } else {
        const savedUser = localStorage.getItem("eventflow_user");
        if (savedUser) {
          try {
            setCurrentUser(JSON.parse(savedUser));
          } catch {
            // ignore
          }
        }
      }
    }

    // Verify session with backend API
    fetch(`${API_BASE}/api/auth/me/`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.authenticated && data?.user?.username) {
          const u = { username: data.user.username };
          setCurrentUser(u);
          localStorage.setItem("eventflow_user", JSON.stringify(u));
        }
      })
      .catch(() => {});
  }, []);

  // ── Data Fetching ──

  const fetchActivities = useCallback(
    async (customUrl?: string) => {
      setLoading(true);
      try {
        let targetUrl = customUrl;
        if (!targetUrl) {
          const params = new URLSearchParams();
          if (selectedType) params.append("activity_type", selectedType);
          if (selectedRepo) params.append("repository", selectedRepo);
          if (startDate) params.append("start_date", startDate);
          if (endDate) params.append("end_date", endDate);
          const qStr = params.toString();
          targetUrl = `${API_BASE}/api/activities/${qStr ? `?${qStr}` : ""}`;
        }
        const res = await fetch(targetUrl);
        if (res.ok) {
          const rawHeader = res.headers.get("X-Cache") || res.headers.get("x-cache") || "MISS";
          setCacheHeader(rawHeader.toUpperCase());
          const data = await res.json();
          setActivities(data.results || []);
          setNextCursor(data.next || null);
          setPrevCursor(data.previous || null);
        }
      } catch (err) {
        console.error("Failed to fetch activities:", err);
      } finally {
        setLoading(false);
      }
    },
    [selectedType, selectedRepo, startDate, endDate]
  );

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/activities/stats/`);
      if (res.ok) setStats(await res.json());
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  }, []);

  useEffect(() => {
    fetchActivities();
    fetchStats();
  }, [fetchActivities, fetchStats]);

  // ── Actions ──

  const triggerSyncAll = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/github/repositories/sync-all/`,
        {
          method: "POST",
        }
      );
      if (res.ok) {
        const data = await res.json();
        const created = data?.totals?.created_activities ?? 0;
        setSyncMessage(`✓ Sync complete — ${created} new activities ingested`);
        fetchActivities();
        fetchStats();
      } else {
        const err = await res.json();
        setSyncMessage(
          `Sync status: ${err.detail || "Completed with warnings"}`
        );
      }
    } catch (err: any) {
      setSyncMessage(`Network error: ${err.message}`);
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMessage(null), 6000);
    }
  };

  const handleToggleIncludeBots = (checked: boolean) => {
    setIncludeBots(checked);
    localStorage.setItem("eventflow_include_bots", String(checked));
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout/`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // ignore
    }
    setCurrentUser(null);
    localStorage.removeItem("eventflow_user");
  };

  const handleTrackRepoSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const repoCoordinates = extractOwnerRepo(trackRepoInput);
    if (!repoCoordinates) return;

    setTrackLoading(true);
    setTrackMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/me/repositories/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ repository: repoCoordinates }),
      });
      if (res.ok) {
        setTrackMsg(
          `✓ Successfully tracking ${repoCoordinates}! Syncing now...`
        );
        setTrackRepoInput("");
        fetchStats();
        fetchActivities();
        setTimeout(() => setShowTrackModal(false), 2000);
      } else {
        const data = await res.json();
        setTrackMsg(`Error: ${data.detail || "Unable to track repository."}`);
      }
    } catch (err: any) {
      setTrackMsg(`Connection error: ${err.message}`);
    } finally {
      setTrackLoading(false);
    }
  };

  // ── Derived State ──

  const filteredActivities = activities.filter((act) => {
    const actorName = getActorUsername(act);
    const isBot = isBotActor(act, actorName);
    if (!includeBots && isBot) return false;

    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const desc = getEventDescription(act).toLowerCase();
    return (
      desc.includes(q) ||
      actorName.toLowerCase().includes(q) ||
      act.repository?.external_id?.toLowerCase().includes(q) ||
      act.activity_type?.toLowerCase().includes(q) ||
      act.target_id?.toLowerCase().includes(q)
    );
  });

  // ── Render ──
  return (
    <div className="min-h-screen bg-[#0B0E12] text-[#E6EDF3] antialiased">
      {/* ── Navigation Header ── */}
      <Navbar
        apiBase={API_BASE}
        cacheHeader={cacheHeader}
        syncing={syncing}
        currentUser={currentUser}
        onOpenTrackModal={() => setShowTrackModal(true)}
        onTriggerSyncAll={triggerSyncAll}
        onLogout={handleLogout}
      />

      {/* ── Sync Banner ── */}
      {syncMessage && (
        <div className="bg-[#121D2F] border-b border-[#58A6FF]/30 px-6 py-2 text-center text-xs text-[#58A6FF] font-medium">
          {syncMessage}
        </div>
      )}

      {/* ── Main Dashboard Content ── */}
      <main className="max-w-7xl mx-auto px-6 py-5 space-y-4">
        {/* Metric Cards Section */}
        <MetricCards stats={stats} />

        {/* Filter Toolbar Section */}
        <FilterToolbar
          selectedType={selectedType}
          setSelectedType={setSelectedType}
          selectedRepo={selectedRepo}
          setSelectedRepo={setSelectedRepo}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          startDate={startDate}
          setStartDate={setStartDate}
          endDate={endDate}
          setEndDate={setEndDate}
          stats={stats}
        />

        {/* Activity Stream Feed Table */}
        <div className="bg-[#151A20] border border-[#2A3038] rounded-md overflow-hidden shadow-sm">
          {/* Feed Table Header */}
          <div className="px-5 py-3 bg-[#0B0E12] border-b border-[#2A3038] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[#E6EDF3]">
                Activity
              </span>
              <span className="text-xs text-[#8B949E]">·</span>
              <span className="text-xs text-[#8B949E] font-medium">
                {filteredActivities.length} events
              </span>
            </div>

            {/* Bot Events Toggle */}
            <label className="flex items-center gap-2 text-sm text-[#8B949E] cursor-pointer hover:text-[#E6EDF3] select-none transition-colors">
              <input
                type="checkbox"
                checked={includeBots}
                onChange={(e) => handleToggleIncludeBots(e.target.checked)}
                className="w-4 h-4 rounded bg-[#0B0E12] border-[#2A3038] text-[#3FB950] focus:ring-0 cursor-pointer accent-[#3FB950]"
              />
              <span className="font-medium text-[#C9D1D9]">
                Include bot events
              </span>
            </label>
          </div>

          {/* Feed Loading State */}
          {loading && (
            <div className="p-12 text-center space-y-2">
              <FiRefreshCw className="w-5 h-5 animate-spin mx-auto text-[#8B949E]" />
              <p className="text-xs text-[#8B949E]">Loading activity feed…</p>
            </div>
          )}

          {/* Feed Empty State */}
          {!loading && filteredActivities.length === 0 && (
            <div className="p-12 text-center space-y-1.5">
              <FiTrendingUp className="w-6 h-6 mx-auto text-[#8B949E]" />
              <p className="text-sm font-medium text-[#E6EDF3]">
                No matching activity events
              </p>
              <p className="text-xs text-[#8B949E]">
                Try adjusting your search query, date range, or bot filter
              </p>
            </div>
          )}

          {/* Feed Rows */}
          {!loading && filteredActivities.length > 0 && (
            <div>
              {filteredActivities.map((act) => (
                <ActivityRow key={act.id} act={act} />
              ))}
            </div>
          )}

          {/* Feed Pagination Footer */}
          <div className="px-5 py-3 bg-[#0B0E12] border-t border-[#2A3038] flex items-center justify-between text-xs">
            <span className="text-[#8B949E]">
              Showing{" "}
              <span className="text-[#E6EDF3] font-medium">
                {filteredActivities.length}
              </span>{" "}
              events
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => prevCursor && fetchActivities(prevCursor)}
                disabled={!prevCursor || loading}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-[#1F242D] hover:bg-[#2A3038] border border-[#2A3038] text-[#C9D1D9] disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-xs font-medium"
              >
                <FiChevronLeft className="w-3.5 h-3.5" />
                Previous
              </button>
              <button
                onClick={() => nextCursor && fetchActivities(nextCursor)}
                disabled={!nextCursor || loading}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-[#1F242D] hover:bg-[#2A3038] border border-[#2A3038] text-[#C9D1D9] disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-xs font-medium"
              >
                Next
                <FiChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Track Repository Modal */}
      <TrackRepoModal
        isOpen={showTrackModal}
        onClose={() => setShowTrackModal(false)}
        trackRepoInput={trackRepoInput}
        setTrackRepoInput={setTrackRepoInput}
        trackLoading={trackLoading}
        trackMsg={trackMsg}
        onSubmit={handleTrackRepoSubmit}
      />
    </div>
  );
}
