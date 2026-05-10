"use client";

import { Terminal, Loader2, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolExecutionCardProps {
  toolName: string;
  isExecuting?: boolean;
}

export function ToolExecutionCard({
  toolName,
  isExecuting = true,
}: ToolExecutionCardProps) {
  const displayName = toolName
    .replace(/_/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg border mx-4 my-2",
        isExecuting
          ? "border-primary/50 bg-primary/5 pulse-glow"
          : "border-border bg-muted/30"
      )}
    >
      <div
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-md",
          isExecuting
            ? "bg-primary/20 text-primary"
            : "bg-muted text-muted-foreground"
        )}
      >
        {isExecuting ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <CheckCircle2 className="w-4 h-4" />
        )}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-tool-cyan" />
          <span className="text-sm font-medium">{displayName}</span>
        </div>
        {isExecuting && (
          <p className="text-xs text-muted-foreground mt-0.5">Executing...</p>
        )}
      </div>
    </div>
  );
}
