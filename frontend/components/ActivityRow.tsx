import { useState } from "react";
import { ActivityItem } from "./types";
import {
  FiActivity,
  FiGitPullRequest,
  FiGitCommit,
  FiAlertCircle,
  FiTag,
  FiCalendar,
  FiExternalLink,
} from "react-icons/fi";

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Safely parses metadata if returned as a JSON string from backend API. */
function parseMetadata(meta: any): Record<string, any> {
  if (!meta) return {};
  if (typeof meta === "object") return meta;
  if (typeof meta === "string") {
    try {
      return JSON.parse(meta);
    } catch {
      return {};
    }
  }
  return {};
}

/** Maps an activity_type string to a display label, pill CSS class, and icon. */
export function getActivityMeta(type: string) {
  switch (type) {
    case "PR_MERGED":
      return {
        label: "Merged PR",
        pillClass: "bg-[#13251A] text-[#3FB950] border-[#3FB950]/30",
        Icon: FiGitPullRequest,
      };
    case "PR_OPENED":
      return {
        label: "Open PR",
        pillClass: "bg-[#121D2F] text-[#58A6FF] border-[#58A6FF]/30",
        Icon: FiGitPullRequest,
      };
    case "PR_CLOSED":
      return {
        label: "Closed PR",
        pillClass: "bg-[#271C1C] text-[#F85149] border-[#F85149]/30",
        Icon: FiGitPullRequest,
      };
    case "ISSUE_OPENED":
    case "ISSUE_CREATED":
      return {
        label: "Issue",
        pillClass: "bg-[#2B2013] text-[#D29922] border-[#D29922]/30",
        Icon: FiAlertCircle,
      };
    case "ISSUE_CLOSED":
      return {
        label: "Closed Issue",
        pillClass: "bg-[#271C1C] text-[#F85149] border-[#F85149]/30",
        Icon: FiAlertCircle,
      };
    case "COMMIT_PUSHED":
      return {
        label: "Commit",
        pillClass: "bg-[#13251A] text-[#3FB950] border-[#3FB950]/30",
        Icon: FiGitCommit,
      };
    case "RELEASE_PUBLISHED":
      return {
        label: "Release",
        pillClass: "bg-[#241B2F] text-[#A371F7] border-[#A371F7]/30",
        Icon: FiTag,
      };
    default:
      return {
        label: type.replace(/_/g, " "),
        pillClass: "bg-[#151A20] text-[#8B949E] border-[#2A3038]",
        Icon: FiActivity,
      };
  }
}

/** Extracts the actual GitHub actor / username from act.actor, metadata, or GitHub event payload. */
export function getActorUsername(act: ActivityItem): string {
  if (act.actor?.username) return act.actor.username;

  const metadata = parseMetadata(act.metadata);

  if (metadata.actor) return String(metadata.actor);
  if (metadata.sender?.login) return String(metadata.sender.login);
  if (metadata.author?.login) return String(metadata.author.login);
  if (metadata.author?.name) return String(metadata.author.name);

  // Traverse nested payloads (metadata.payload.payload...)
  const p1 = metadata.payload;
  const p2 = p1 && typeof p1 === "object" ? (p1.payload || p1) : null;

  for (const p of [p2, p1]) {
    if (p && typeof p === "object") {
      if (p.actor?.login) return String(p.actor.login);
      if (p.actor?.display_login) return String(p.actor.display_login);
      if (p.sender?.login) return String(p.sender.login);
      if (p.pusher?.name) return String(p.pusher.name);
      if (p.head_commit?.author?.username) return String(p.head_commit.author.username);
      if (p.head_commit?.author?.name) return String(p.head_commit.author.name);
    }
  }

  return "anonymous";
}

/** Determines if an event actor is a bot. */
export function isBotActor(act: ActivityItem, username: string): boolean {
  const metadata = parseMetadata(act.metadata);
  if (metadata.sender?.type === "Bot") return true;
  const u = username.toLowerCase();
  if (u.includes("[bot]") || u.endsWith("-bot") || u.endsWith("_bot") || u === "dependabot" || u === "stale") return true;
  if (act.actor?.username?.toLowerCase().includes("bot")) return true;
  return false;
}

/** Extracts or generates official GitHub profile avatar URL. */
export function getActorAvatarUrl(act: ActivityItem, username: string): string {
  const metadata = parseMetadata(act.metadata);
  if (metadata.avatar_url) return String(metadata.avatar_url);
  if (metadata.sender?.avatar_url) return String(metadata.sender.avatar_url);

  const p1 = metadata.payload;
  const p2 = p1 && typeof p1 === "object" ? (p1.payload || p1) : null;

  for (const p of [p2, p1]) {
    if (p && typeof p === "object") {
      if (p.actor?.avatar_url) return String(p.actor.avatar_url);
      if (p.sender?.avatar_url) return String(p.sender.avatar_url);
    }
  }

  if (username && username !== "anonymous") {
    const cleanUsername = username.replace("[bot]", "");
    return `https://github.com/${cleanUsername}.png?size=64`;
  }

  return "";
}

/** Extracts a rich human-readable title from the activity's metadata. */
export function getEventDescription(act: ActivityItem): string {
  let title = "";
  const metadata = parseMetadata(act.metadata);

  // 1. Direct metadata fields
  if (metadata.title) title = String(metadata.title);
  else if (metadata.head_commit?.message)
    title = String(metadata.head_commit.message).split("\n")[0];
  else if (metadata.commit_message)
    title = String(metadata.commit_message).split("\n")[0];
  else if (metadata.release_name) title = String(metadata.release_name);
  else if (metadata.message) title = String(metadata.message);

  // 2. Inspect double-nested payload: metadata.payload = GitHub event wrapper,
  //    metadata.payload.payload = actual event-specific data (PR, Issue, commits...)
  const p1 = metadata.payload;
  const p2 = p1 && typeof p1 === "object" ? (p1.payload || p1) : null;

  for (const p of [p2, p1]) {
    if (!title && p && typeof p === "object") {
      if (p.pull_request?.title) title = String(p.pull_request.title);
      else if (p.issue?.title) title = String(p.issue.title);
      else if (p.release?.name) title = String(p.release.name);
      else if (p.release?.tag_name) title = String(p.release.tag_name);
      else if (p.head_commit?.message)
        title = String(p.head_commit.message).split("\n")[0];
      else if (Array.isArray(p.commits) && p.commits.length > 0 && p.commits[0]?.message)
        title = String(p.commits[0].message).split("\n")[0];
    }
  }

  // 3. Best-effort fallback using fields that ARE present in GitHub Events API
  if (!title) {
    const target = formatTargetId(act.target_id);

    if (act.activity_type.startsWith("PR_")) {
      const headRef: string | undefined = p2?.pull_request?.head?.ref ?? p1?.pull_request?.head?.ref;
      if (headRef) {
        const readable = headRef
          .replace(/^(feat|fix|chore|refactor|docs|perf|test|style)\//i, (_: string, prefix: string) => `${prefix}: `)
          .replace(/[-_]/g, " ")
          .trim();
        title = `${readable}${target ? ` (${target})` : ""}`;
      } else {
        title = `PR ${target || ""}`.trim();
      }
    } else if (act.activity_type === "COMMIT_PUSHED") {
      const sha = act.target_id?.length > 7 ? act.target_id.slice(0, 7) : act.target_id;
      const ref: string | undefined = p2?.ref ?? p1?.ref;
      const branch = ref ? ref.replace("refs/heads/", "") : null;
      title = branch ? `Push to ${branch} (${sha})` : `Commit ${sha}`;
    } else if (act.activity_type.startsWith("ISSUE_")) {
      title = `Issue ${target || ""}`.trim();
    } else if (act.activity_type === "RELEASE_PUBLISHED") {
      title = `Release ${target || ""}`.trim();
    } else {
      const meta = getActivityMeta(act.activity_type);
      title = `${meta.label}${target ? ` ${target}` : ""}`;
    }
  }

  return title;
}

/** Formats a target_id into a short display string (#123 or short SHA). */
export function formatTargetId(targetId: string): string | null {
  if (!targetId) return null;
  if (/^\d+$/.test(targetId)) return `#${targetId}`;
  return targetId.length > 7 ? targetId.slice(0, 7) : targetId;
}

/** Formats an ISO timestamp to a consistent "Sep 1 · 12:48 AM" format. */
export function formatTime(isoString: string): string {
  if (!isoString) return "—";
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "—";

  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const month = months[date.getMonth()];
  const day = date.getDate();
  const year = date.getFullYear();
  const now = new Date();
  const showYear = year !== now.getFullYear();

  let hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;

  const datePart = showYear ? `${month} ${day}, ${year}` : `${month} ${day}`;
  return `${datePart} · ${hours}:${minutes} ${ampm}`;
}

// ─── ActivityRow Component ────────────────────────────────────────────────────

interface ActivityRowProps {
  act: ActivityItem;
}

/**
 * A single activity feed row.
 */
export default function ActivityRow({ act }: ActivityRowProps) {
  const [imgError, setImgError] = useState(false);
  const meta = getActivityMeta(act.activity_type);
  const IconComponent = meta.Icon;
  const formattedTarget = formatTargetId(act.target_id);
  const description = getEventDescription(act);
  const timeStr = formatTime(act.created_at);
  const username = getActorUsername(act);
  const avatarUrl = getActorAvatarUrl(act, username);
  const isBot = isBotActor(act, username);

  return (
    <div className="flex items-center gap-4 px-5 py-3.5 hover:bg-[#1F242D] transition-colors group border-b border-[#2A3038]/40 last:border-b-0">

      {/* Zone 1: Status Pill (fixed 118px) */}
      <div className="shrink-0 w-[118px]">
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border whitespace-nowrap ${meta.pillClass}`}
        >
          <IconComponent className="w-3.5 h-3.5" />
          {meta.label}
        </span>
      </div>

      {/* Zone 2: Title + subtitle (flex-1, fills middle space) */}
      <div className="flex-1 min-w-0 pr-4">
        {/* Line 1: Event title */}
        <h4
          className="text-[14px] font-semibold text-[#E6EDF3] leading-snug hover:text-[#58A6FF] transition-colors cursor-pointer truncate"
          title={description}
        >
          {description}
        </h4>

        {/* Line 2: #ID · repo · event type */}
        <div className="flex items-center gap-1.5 mt-[3px] text-[12px] text-[#8B949E]">
          {formattedTarget && (
            <span className="font-mono">{formattedTarget}</span>
          )}
          {formattedTarget && <span className="text-[#3D444D]">·</span>}
          <span>
            {act.repository?.external_id || act.repository?.name || "—"}
          </span>
          <span className="text-[#3D444D]">·</span>
          <span>{meta.label}</span>
        </div>
      </div>

      {/* Zone 3: Timestamp (Locked at fixed 150px width for 100% straight vertical alignment) */}
      <div className="shrink-0 hidden md:flex items-center gap-1.5 text-[12px] text-[#8B949E] w-[150px]">
        <FiCalendar className="w-3.5 h-3.5 shrink-0 text-[#8B949E]" />
        <span className="whitespace-nowrap">{timeStr}</span>
      </div>

      {/* Zone 4: Avatar + username + @handle stacked (Locked at fixed 160px width so Date never shifts) */}
      <div className="shrink-0 hidden sm:flex items-center gap-2 w-[160px] min-w-0">
        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-[#21262D] border border-[#30363D] flex items-center justify-center shrink-0 overflow-hidden">
          {avatarUrl && !imgError ? (
            <img
              src={avatarUrl}
              alt={username}
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <span className="text-[12px] font-bold text-[#C9D1D9] uppercase leading-none select-none">
              {username && username !== "anonymous" ? username[0] : "?"}
            </span>
          )}
        </div>

        {/* Name + @handle stacked with clean truncation */}
        <div className="flex flex-col leading-tight min-w-0 flex-1">
          <div className="flex items-center gap-1 min-w-0">
            {username !== "anonymous" ? (
              <a
                href={`https://github.com/${username.replace("[bot]", "")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[12px] font-semibold text-[#C9D1D9] hover:text-[#58A6FF] transition-colors truncate block"
                title={username}
              >
                {username}
              </a>
            ) : (
              <span className="text-[12px] font-semibold text-[#8B949E] truncate block">
                {username}
              </span>
            )}
            {isBot && (
              <span className="bg-[#21262D] text-[#8B949E] border border-[#30363D] text-[9px] px-1 rounded font-mono uppercase font-medium leading-tight shrink-0">
                bot
              </span>
            )}
          </div>
          <span className="text-[11px] text-[#8B949E] truncate block" title={`@${username}`}>
            @{username}
          </span>
        </div>
      </div>

      {/* Zone 5: External GitHub link (fixed 20px) */}
      <div className="shrink-0 w-5 flex justify-center">
        {act.source_url ? (
          <a
            href={act.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#8B949E] hover:text-[#58A6FF] transition-colors inline-flex items-center"
            title="View on GitHub"
          >
            <FiExternalLink className="w-4 h-4" />
          </a>
        ) : (
          <span className="w-4 h-4 block" />
        )}
      </div>
    </div>
  );
}
