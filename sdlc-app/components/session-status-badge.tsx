"use client";

import { cn } from "@/lib/utils";
import type { SessionState } from "@/lib/types";

const STYLES: Record<SessionState, string> = {
  pending: "bg-secondary text-muted-foreground border-border",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  awaiting_approval: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  approved: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  rejected: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  completed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  failed: "bg-rose-500/10 text-rose-400 border-rose-500/30",
};

export function SessionStatusBadge({ state }: { state: SessionState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border",
        STYLES[state],
      )}
    >
      {state.replace(/_/g, " ")}
    </span>
  );
}
