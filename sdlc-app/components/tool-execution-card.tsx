"use client";

import { useState } from "react";
import { Terminal, Loader2, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
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
  const [isExpanded, setIsExpanded] = useState(false);

  const displayName = toolName
    .replace(/_/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  // Executing: always show full card with spinner
  if (isExecuting) {
    return (
      <div className="flex items-start gap-3 px-4 py-3 rounded-lg border mx-4 my-2 border-primary/50 bg-primary/5 pulse-glow">
        <div className="flex items-center justify-center w-8 h-8 rounded-md shrink-0 mt-0.5 bg-primary/20 text-primary">
          <Loader2 className="w-4 h-4 animate-spin" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-tool-cyan shrink-0" />
            <span className="text-sm font-medium">{displayName}</span>
          </div>
          {detail ? (
            <p className="text-xs font-mono text-muted-foreground mt-1 break-all whitespace-pre-wrap">
              {detail}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground mt-0.5">Executing...</p>
          )}
        </div>
      </div>
    );
  }

  // Completed + Collapsed: compact single-line pill
  if (!isExpanded) {
    return (
      <div
        role="button"
        tabIndex={0}
        onClick={() => setIsExpanded(true)}
        onKeyDown={(e) => e.key === "Enter" && setIsExpanded(true)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border bg-muted/30 mx-4 my-0.5 cursor-pointer hover:bg-muted/60 transition-colors"
      >
        <CheckCircle2 className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
        <Terminal className="w-3.5 h-3.5 text-tool-cyan shrink-0" />
        <span className="text-sm font-medium flex-1 min-w-0 truncate">{displayName}</span>
        {detail && (
          <span className="text-xs font-mono text-muted-foreground/60 truncate max-w-[160px] hidden sm:block">
            {detail}
          </span>
        )}
        <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0 ml-1" />
      </div>
    );
  }

  // Completed + Expanded: full card without truncation
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-lg border border-border bg-muted/30 mx-4 my-2">
      <div className="flex items-center justify-center w-8 h-8 rounded-md shrink-0 mt-0.5 bg-muted text-muted-foreground">
        <CheckCircle2 className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-tool-cyan shrink-0" />
          <span className="text-sm font-medium flex-1">{displayName}</span>
          <button
            onClick={() => setIsExpanded(false)}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Collapse"
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
        </div>
        {detail ? (
          <p className="text-xs font-mono text-muted-foreground mt-1 break-all whitespace-pre-wrap">
            {detail}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground/50 mt-1 italic">
            Tool ran without input arguments
          </p>
        )}
        {result ? (
          <pre className="text-xs text-muted-foreground mt-2 whitespace-pre-wrap font-mono bg-black/20 rounded p-2 max-h-64 overflow-y-auto">
            {result}
          </pre>
        ) : (
          <p className="text-xs text-muted-foreground/50 mt-1 italic">
            Result not yet received — the tool may still be running or returned no textual output.
          </p>
        )}
      </div>
    </div>
  );
}
