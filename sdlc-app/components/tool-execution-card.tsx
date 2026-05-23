"use client";

import { Terminal, Loader2, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolExecutionCardProps {
  toolName: string;
  isExecuting?: boolean;
  /** Optional detail shown while executing, e.g. the bash command */
  detail?: string;
  /** Optional result preview shown after execution */
  result?: string;
}

export function ToolExecutionCard({
  toolName,
  isExecuting = true,
  detail,
  result,
}: ToolExecutionCardProps) {
  const displayName = toolName
    .replace(/_/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return (
    <div
      className={cn(
        "flex items-start gap-3 px-4 py-3 rounded-lg border mx-4 my-2",
        isExecuting
          ? "border-primary/50 bg-primary/5 pulse-glow"
          : "border-border bg-muted/30"
      )}
    >
      <div
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-md shrink-0 mt-0.5",
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
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-tool-cyan shrink-0" />
          <span className="text-sm font-medium">{displayName}</span>
        </div>
        {detail && (
          <p className="text-xs font-mono text-muted-foreground mt-1 truncate" title={detail}>
            $ {detail}
          </p>
        )}
        {isExecuting && !detail && (
          <p className="text-xs text-muted-foreground mt-0.5">Executing...</p>
        )}
        {!isExecuting && result && (
          <pre className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap line-clamp-3 font-mono">
            {result}
          </pre>
        )}
      </div>
    </div>
  );
}
