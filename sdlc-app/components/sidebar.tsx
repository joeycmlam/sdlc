"use client";

import { Bot, Info, ExternalLink, Zap, FileText } from "lucide-react";
import { useState } from "react";
import { AgentSelector } from "./agent-selector";
import { AgentContextPanel } from "./agent-context-panel";
import { getAgentDisplayName, getAgentDescription } from "@/lib/api";
import { cn } from "@/lib/utils";

interface SidebarProps {
  agents: string[];
  selectedAgent: string | null;
  onSelectAgent: (agent: string) => void;
  isLoading?: boolean;
  maxTurns: number;
  onMaxTurnsChange: (turns: number) => void;
}

export function Sidebar({
  agents,
  selectedAgent,
  onSelectAgent,
  isLoading,
  maxTurns,
  onMaxTurnsChange,
}: SidebarProps) {
  const [panelAgent, setPanelAgent] = useState<string | null>(null);

  return (
    <>
    <aside className="w-80 border-r border-border bg-card/30 flex flex-col">
      <div className="p-4 border-b border-border">
        <AgentSelector
          agents={agents}
          selectedAgent={selectedAgent}
          onSelect={onSelectAgent}
          disabled={isLoading}
        />
      </div>

      {selectedAgent && (
        <div className="p-4 border-b border-border">
          <div className="flex items-start gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 text-primary shrink-0">
              <Bot className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-medium truncate">
                {getAgentDisplayName(selectedAgent)}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                {getAgentDescription(selectedAgent)}
              </p>
            </div>
            <button
              onClick={() => setPanelAgent(selectedAgent)}
              title="View agent context"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors shrink-0"
            >
              <FileText className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="p-4 border-b border-border">
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Zap className="w-4 h-4 text-primary" />
          Configuration
        </h4>
        <div className="space-y-3">
          <div>
            <label className="text-sm text-muted-foreground block mb-1.5">
              Max Turns
            </label>
            <input
              type="range"
              min="5"
              max="50"
              value={maxTurns}
              onChange={(e) => onMaxTurnsChange(Number(e.target.value))}
              disabled={isLoading}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>5</span>
              <span className="font-medium text-foreground">{maxTurns}</span>
              <span>50</span>
            </div>
          </div>
        </div>
      </div>

      <div className="p-4 flex-1">
        <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Info className="w-4 h-4 text-muted-foreground" />
          Agent Capabilities
        </h4>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            Execute shell commands
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            Invoke sub-agents
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            Multi-step workflows
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            Jira integration
          </li>
        </ul>
      </div>

      <div className="p-4 border-t border-border">
        <a
          href="https://github.com/github/copilot-sdk"
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "flex items-center justify-center gap-2 px-4 py-2 rounded-lg",
            "border border-border bg-card hover:bg-secondary",
            "text-sm text-muted-foreground hover:text-foreground transition-colors"
          )}
        >
          <ExternalLink className="w-4 h-4" />
          Copilot SDK Docs
        </a>
      </div>
    </aside>

    <AgentContextPanel
      source={panelAgent ? { kind: "local", file: panelAgent } : null}
      onClose={() => setPanelAgent(null)}
    />
    </>
  );
}
