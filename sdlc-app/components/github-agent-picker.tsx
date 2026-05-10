"use client";

import useSWR from "swr";
import {
  Bot,
  Building2,
  Eye,
  GitBranch,
  Loader2,
  RefreshCw,
} from "lucide-react";

import { listGitHubAgents } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { GitHubCustomAgent } from "@/lib/types";

interface GitHubAgentPickerProps {
  owner: string;
  repo: string;
  /** Selected agent id, e.g. "backend-agent". null when none selected. */
  value: string | null;
  onChange: (agent: GitHubCustomAgent | null) => void;
  onViewContext?: (agent: GitHubCustomAgent) => void;
  disabled?: boolean;
}

/**
 * GitHubAgentPicker — discovers `.agent.md` files from:
 *   - the target repo's `.github/agents/` directory  (scope: "repo")
 *   - the org's `.github-private` repo's `agents/` directory  (scope: "org")
 * and lets the user pick one.  Loads only after `owner` + `repo` are filled.
 */
export function GitHubAgentPicker({
  owner,
  repo,
  value,
  onChange,
  onViewContext,
  disabled,
}: GitHubAgentPickerProps) {
  const ready = Boolean(owner.trim() && repo.trim());
  const { data, error, isLoading, mutate } = useSWR(
    ready ? ["github-agents", owner, repo] : null,
    () => listGitHubAgents(owner.trim(), repo.trim()),
    { revalidateOnFocus: false },
  );

  const agents = data?.agents ?? [];
  const selected = agents.find((a) => a.id === value) ?? null;

  if (!ready) {
    return (
      <div className="rounded-md border border-dashed border-border bg-card/30 px-3 py-3 text-xs text-muted-foreground">
        Fill in <strong>Owner</strong> and <strong>Repository</strong> above to
        discover custom agents.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Bot className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <select
            value={value ?? ""}
            onChange={(e) => {
              const next = agents.find((a) => a.id === e.target.value) ?? null;
              onChange(next);
            }}
            disabled={disabled || isLoading || !!error}
            className={cn(
              "w-full pl-9 pr-3 py-2 rounded-md border border-border bg-background",
              "text-sm appearance-none disabled:opacity-50",
            )}
          >
            <option value="">— Select a custom agent —</option>
            {agents.map((a) => (
              <option key={`${a.scope}:${a.id}`} value={a.id}>
                {a.name} ({a.scope})
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => selected && onViewContext?.(selected)}
          disabled={disabled || !selected}
          title={selected ? "View agent context" : "Select an agent first"}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
            "border border-border bg-card hover:bg-secondary",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <Eye className="w-4 h-4" />
          View
        </button>
        <button
          type="button"
          onClick={() => mutate()}
          disabled={disabled || isLoading}
          title="Re-discover agents from GitHub"
          className={cn(
            "flex items-center justify-center w-9 h-9 rounded-md",
            "border border-border bg-card hover:bg-secondary",
            "disabled:opacity-50",
          )}
        >
          <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
        </button>
      </div>

      {isLoading && !data && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin" />
          Loading agents from GitHub…
        </div>
      )}

      {error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          Failed to load agents: {(error as Error).message}
        </div>
      )}

      {data && agents.length === 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          No custom agents found at <code>.github/agents/</code> in{" "}
          <code className="font-mono">
            {data.owner}/{data.repo}
          </code>{" "}
          or in <code className="font-mono">{data.owner}/.github-private/agents/</code>.
          Submit with the default Copilot agent instead, or add an{" "}
          <code>.agent.md</code> file at one of those paths.
        </div>
      )}

      {selected && (
        <div className="rounded-md border border-border bg-card/30 px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{selected.name}</span>
            <ScopePill scope={selected.scope} />
          </div>
          {selected.description && (
            <p className="text-xs text-muted-foreground line-clamp-3 mt-0.5">
              {selected.description}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground/70 mt-1 font-mono">
            {selected.source_repo}/{selected.path}
          </p>
        </div>
      )}
    </div>
  );
}

function ScopePill({ scope }: { scope: "repo" | "org" }) {
  const Icon = scope === "repo" ? GitBranch : Building2;
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide border border-border bg-secondary text-muted-foreground">
      <Icon className="w-3 h-3" />
      {scope}
    </span>
  );
}
