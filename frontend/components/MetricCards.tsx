"use client";

import { ActivityStats } from "./types";
import {
  FiTrendingUp,
  FiGitPullRequest,
  FiCode,
  FiFolder,
} from "react-icons/fi";

interface MetricCardsProps {
  stats: ActivityStats | null;
}

export default function MetricCards({ stats }: MetricCardsProps) {
  const cards = [
    {
      label: "Total Activities",
      value: stats?.total_activities?.toLocaleString() ?? "0",
      sub: "Normalized stream",
      Icon: FiTrendingUp,
      iconColor: "text-[#3FB950]",
    },
    {
      label: "Merged PRs",
      value: stats?.by_type?.PR_MERGED?.toLocaleString() ?? "0",
      sub: "Successfully merged",
      Icon: FiGitPullRequest,
      iconColor: "text-[#3FB950]",
    },
    {
      label: "Commits Pushed",
      value: stats?.by_type?.COMMIT_PUSHED?.toLocaleString() ?? "0",
      sub: "Across repositories",
      Icon: FiCode,
      iconColor: "text-[#58A6FF]",
    },
    {
      label: "Active Repos",
      value: stats?.by_repository
        ? String(Object.keys(stats.by_repository).length)
        : "0",
      sub: "Currently syncing",
      Icon: FiFolder,
      iconColor: "text-[#D29922]",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      {cards.map(({ label, value, sub, Icon, iconColor }) => (
        <div
          key={label}
          className="bg-[#151A20] border border-[#2A3038] rounded-md px-4 py-3"
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-[#8B949E]">{label}</span>
            <Icon className={`w-4 h-4 ${iconColor}`} />
          </div>
          <p className="text-xl font-bold tracking-tight text-[#E6EDF3] tabular-nums">
            {value}
          </p>
          <p className="text-[11px] text-[#8B949E] mt-0.5">{sub}</p>
        </div>
      ))}
    </div>
  );
}
