"use client";

import { Github, Settings, RotateCcw } from "lucide-react";
import { StatusIndicator } from "./status-indicator";
import { ModelSelector } from "./model-selector";
import type { ConnectionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface HeaderProps {
  status: ConnectionStatus;
  selectedModel: string;
  onModelChange: (model: string) => void;
  onReset: () => void;
  isLoading?: boolean;
}

export function Header({
  status,
  selectedModel,
  onModelChange,
  onReset,
  isLoading,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary text-primary-foreground">
            <Github className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold tracking-tight">Copilot Agent</h1>
            <p className="text-xs text-muted-foreground">
              Powered by GitHub Copilot SDK
            </p>
          </div>
        </div>
        <div className="hidden sm:block h-6 w-px bg-border" />
        <div className="hidden sm:block">
          <StatusIndicator status={status} />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <ModelSelector
          selectedModel={selectedModel}
          onSelect={onModelChange}
          disabled={isLoading}
        />
        <button
          onClick={onReset}
          disabled={isLoading}
          className={cn(
            "flex items-center justify-center w-9 h-9 rounded-lg",
            "border border-border bg-card hover:bg-secondary",
            "transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          )}
          title="Reset conversation"
        >
          <RotateCcw className="w-4 h-4 text-muted-foreground" />
        </button>
        <button
          className={cn(
            "flex items-center justify-center w-9 h-9 rounded-lg",
            "border border-border bg-card hover:bg-secondary",
            "transition-colors"
          )}
          title="Settings"
        >
          <Settings className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
    </header>
  );
}
