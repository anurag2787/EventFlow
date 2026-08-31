"use client";

import { ActivityStats } from "./types";
import { FiCalendar, FiSearch } from "react-icons/fi";

export const FILTER_TABS = [
  { id: "", label: "All Events" },
  { id: "PR_MERGED", label: "Merged PRs" },
  { id: "PR_OPENED", label: "Open PRs" },
  { id: "COMMIT_PUSHED", label: "Commits" },
  { id: "ISSUE_OPENED", label: "Issues" },
  { id: "RELEASE_PUBLISHED", label: "Releases" },
];

interface FilterToolbarProps {
  selectedType: string;
  setSelectedType: (type: string) => void;
  selectedRepo: string;
  setSelectedRepo: (repo: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  startDate: string;
  setStartDate: (date: string) => void;
  endDate: string;
  setEndDate: (date: string) => void;
  stats: ActivityStats | null;
}

export default function FilterToolbar({
  selectedType,
  setSelectedType,
  selectedRepo,
  setSelectedRepo,
  searchQuery,
  setSearchQuery,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  stats,
}: FilterToolbarProps) {
  return (
    <div className="space-y-3">
      {/* ── Filter Bar ── */}
      <div className="bg-[#151A20] border border-[#2A3038] rounded-md">
        <div className="px-4 py-1.5 flex flex-wrap items-center justify-between gap-3 text-sm">

          {/* Underline tabs */}
          <div className="flex items-center gap-1 overflow-x-auto">
            {FILTER_TABS.map((tab) => {
              const isActive = selectedType === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setSelectedType(tab.id)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                    isActive
                      ? "border-[#3FB950] text-[#E6EDF3] font-semibold"
                      : "border-transparent text-[#8B949E] hover:text-[#E6EDF3]"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Date pickers + Search */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Date pickers */}
            <div className="flex items-center gap-1.5 text-xs text-[#8B949E]">
              <FiCalendar className="w-3.5 h-3.5" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-[#0B0E12] border border-[#2A3038] text-[#E6EDF3] text-xs rounded px-2.5 py-1 focus:outline-none focus:border-[#58A6FF] transition-colors"
              />
              <span>→</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-[#0B0E12] border border-[#2A3038] text-[#E6EDF3] text-xs rounded px-2.5 py-1 focus:outline-none focus:border-[#58A6FF] transition-colors"
              />
              {(startDate || endDate) && (
                <button
                  onClick={() => {
                    setStartDate("");
                    setEndDate("");
                  }}
                  className="text-[#58A6FF] hover:underline text-xs ml-0.5"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Search input */}
            <div className="relative min-w-[200px]">
              <FiSearch className="w-3.5 h-3.5 text-[#8B949E] absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search events, repo, SHA…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#0B0E12] border border-[#2A3038] focus:border-[#58A6FF] focus:outline-none rounded pl-8 pr-2.5 py-1 text-xs text-[#E6EDF3] placeholder-[#8B949E] transition-colors"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Repository Filter Pills ── */}
      {stats?.by_repository && Object.keys(stats.by_repository).length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-xs text-[#8B949E] font-medium mr-1">
            Repository:
          </span>
          <button
            onClick={() => setSelectedRepo("")}
            className={`h-[32px] px-3 text-[13px] font-medium border rounded-md transition-colors inline-flex items-center gap-1 ${
              selectedRepo === ""
                ? "bg-[#13251A] text-[#3FB950] border-[#3FB950]"
                : "bg-[#151A20] text-[#8B949E] border-[#2A3038] hover:text-[#E6EDF3] hover:border-[#8B949E]"
            }`}
          >
            All
          </button>
          {Object.entries(stats.by_repository).map(([repoName, count]) => {
            const isSelected = selectedRepo === repoName;
            return (
              <button
                key={repoName}
                onClick={() => setSelectedRepo(isSelected ? "" : repoName)}
                className={`h-[32px] px-3 text-[13px] font-medium border rounded-md transition-colors inline-flex items-center gap-1.5 ${
                  isSelected
                    ? "bg-[#13251A] text-[#3FB950] border-[#3FB950]"
                    : "bg-[#151A20] text-[#8B949E] border-[#2A3038] hover:text-[#E6EDF3] hover:border-[#8B949E]"
                }`}
              >
                <span>{repoName}</span>
                <span
                  className={
                    isSelected ? "text-[#3FB950]/80" : "text-[#8B949E]/70"
                  }
                >
                  ({count.toLocaleString()})
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
