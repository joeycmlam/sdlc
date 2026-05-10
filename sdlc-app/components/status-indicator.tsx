"use client";

import { cn } from "@/lib/utils";
import type { ConnectionStatus } from "@/lib/types";

interface StatusIndicatorProps {
  status: ConnectionStatus;
}

export function StatusIndicator({ status }: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "w-2 h-2 rounded-full",
          status === "connected" && "bg-primary",
          status === "disconnected" && "bg-destructive",
          status === "connecting" && "bg-amber-500 animate-pulse"
        )}
      />
      <span className="text-sm text-muted-foreground capitalize">{status}</span>
    </div>
  );
}
