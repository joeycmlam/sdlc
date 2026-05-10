"use client";

import { Bot, ChevronDown, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { getAgentDisplayName, getAgentDescription } from "@/lib/api";

interface AgentSelectorProps {
  agents: string[];
  selectedAgent: string | null;
  onSelect: (agent: string) => void;
  disabled?: boolean;
}

export function AgentSelector({
  agents,
  selectedAgent,
  onSelect,
  disabled,
}: AgentSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-card",
          "hover:bg-secondary transition-colors w-full text-left",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
      >
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 text-primary">
          <Bot className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-muted-foreground">Active Agent</div>
          <div className="font-medium truncate">
            {selectedAgent
              ? getAgentDisplayName(selectedAgent)
              : "Select an agent"}
          </div>
        </div>
        <ChevronDown
          className={cn(
            "w-5 h-5 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 z-50 rounded-lg border border-border bg-popover shadow-lg overflow-hidden">
          <div className="max-h-80 overflow-y-auto">
            {agents.map((agent) => (
              <button
                key={agent}
                onClick={() => {
                  onSelect(agent);
                  setIsOpen(false);
                }}
                className={cn(
                  "w-full flex items-start gap-3 px-4 py-3 hover:bg-secondary transition-colors text-left",
                  selectedAgent === agent && "bg-secondary"
                )}
              >
                <div
                  className={cn(
                    "flex items-center justify-center w-8 h-8 rounded-md mt-0.5",
                    selectedAgent === agent
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <Bot className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium flex items-center gap-2">
                    {getAgentDisplayName(agent)}
                    {selectedAgent === agent && (
                      <Check className="w-4 h-4 text-primary" />
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground line-clamp-1">
                    {getAgentDescription(agent)}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
