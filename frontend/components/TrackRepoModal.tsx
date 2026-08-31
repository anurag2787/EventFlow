"use client";

import { FiFolder, FiX } from "react-icons/fi";

interface TrackRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  trackRepoInput: string;
  setTrackRepoInput: (input: string) => void;
  trackLoading: boolean;
  trackMsg: string | null;
  onSubmit: (e: React.FormEvent) => void;
}

export default function TrackRepoModal({
  isOpen,
  onClose,
  trackRepoInput,
  setTrackRepoInput,
  trackLoading,
  trackMsg,
  onSubmit,
}: TrackRepoModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-[#151A20] border border-[#2A3038] rounded-md max-w-md w-full p-5 space-y-4 shadow-xl">

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#2A3038] pb-3">
          <div className="flex items-center gap-2">
            <FiFolder className="w-4 h-4 text-[#58A6FF]" />
            <h3 className="text-sm font-semibold text-[#E6EDF3]">
              Track Repository
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-[#8B949E] hover:text-[#E6EDF3] p-1 rounded hover:bg-[#1F242D]"
          >
            <FiX className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-[#C9D1D9] block mb-1.5">
              GitHub Repository URL or owner/repo
            </label>
            <input
              type="text"
              placeholder="e.g. https://github.com/facebook/react or facebook/react"
              value={trackRepoInput}
              onChange={(e) => setTrackRepoInput(e.target.value)}
              className="w-full bg-[#0B0E12] border border-[#2A3038] focus:border-[#58A6FF] focus:outline-none rounded px-3 py-1.5 text-xs text-[#E6EDF3] placeholder-[#8B949E] transition-colors"
              required
              autoFocus
            />
          </div>

          {trackMsg && (
            <div
              className={`text-xs p-2.5 rounded border ${
                trackMsg.startsWith("✓")
                  ? "text-[#3FB950] bg-[#13251A] border-[#3FB950]/30"
                  : "text-[#F85149] bg-[#271C1C] border-[#F85149]/30"
              }`}
            >
              {trackMsg}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1 rounded bg-[#1F242D] hover:bg-[#2A3038] border border-[#2A3038] text-xs font-medium text-[#C9D1D9] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={trackLoading}
              className="px-4 py-1 rounded bg-[#238636] hover:bg-[#2ea043] border border-[#2ea043]/50 text-xs font-semibold text-[#E6EDF3] transition-colors disabled:opacity-50"
            >
              {trackLoading ? "Tracking…" : "Track Repository"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
