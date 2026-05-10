"use client";

import useSWR from "swr";
import {
  Bot,
  Eye,
  HardDrive,
  Loader2,
  RefreshCw,
} from "lucide-react";

import { fetchAgents, getAgentDisplayName } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { RegisteredAgent } from "@/lib/types";

export interface ServiceAgentChoice {
  /** Filename, e.g. "ba.agent.md". This is what /api/agents/content takes. */
  file: string;
  /** Display name (registered name if available, else humanised basename). */
  name: string;
  /** Registered description, if the agent has YAML frontmatter. */
  description: string | null;
}

interface ServiceAgentPickerProps {
  value: string | null;
  onChange: (agent: ServiceAgentChoice | null) => void;
  onViewContext?: (agent: ServiceAgentChoice) => void;
  disabled?: boolean;
}

/**
 * ServiceAgentPicker — lists `.agent.md` / `.md` profiles bundled with the
 * copilot-agent service (`services/copilot-agent/agents/`) so a user can pick
 * one and have its instructions inlined into the issue body.
 */
export function ServiceAgentPicker({
  value,
  onChange,
  onViewContext,
  disabled,
}: ServiceAgentPickerProps) {
  const { data, error, isLoading, mutate } = useSWR(
    "service-agents",
    fetchAgents,
    { revalidateOnFocus: false },
  );

  const choices = buildChoices(data?.files ?? [], data?.agents ?? []);
  const selected = choices.find((a) => a.file === value) ?? null;

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Bot className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <select
            value={value ?? ""}
            onChange={(e) => {
              const next = choices.find((a) => a.file === e.target.value) ?? null;
              onChange(next);
            }}
            disabled={disabled || isLoading || !!error}
            className={cn(
              "w-full pl-9 pr-3 py-2 rounded-md border border-border bg-background",
              "text-sm appearance-none disabled:opacity-50",
            )}
          >
            <option value="">— Select a service agent —</option>
            {choices.map((a) => (
              <option key={a.file} value={a.file}>
                {a.name} ({a.file})
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
          title="Re-discover agents from the service"
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
          Loading service agents…
        </div>
      )}

      {error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          Failed to load service agents: {(error as Error).message}
        </div>
      )}

      {data && choices.length === 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          No agents found in <code>services/copilot-agent/agents/</code>.
        </div>
      )}

      {selected && (
        <div className="rounded-md border border-border bg-card/30 px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{selected.name}</span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide border border-border bg-secondary text-muted-foreground">
              <HardDrive className="w-3 h-3" />
              service
            </span>
          </div>
          {selected.description && (
            <p className="text-xs text-muted-foreground line-clamp-3 mt-0.5">
              {selected.description}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground/70 mt-1 font-mono">
            services/copilot-agent/agents/{selected.file}
          </p>
        </div>
      )}
    </div>
  );
}

function buildChoices(
  files: string[],
  agents: RegisteredAgent[],
): ServiceAgentChoice[] {
  const byId = new Map(agents.map((a) => [a.id, a]));
  return files
    .slice()
    .sort((a, b) => a.localeCompare(b))
    .map((file) => {
      const id = file.replace(/\.agent\.md$|\.md$/, "");
      const reg = byId.get(id);
      return {
        file,
        name: reg?.name || getAgentDisplayName(file),
        description: reg?.description || null,
      };
    });
}
