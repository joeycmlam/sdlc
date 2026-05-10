"use client";

import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Sidebar } from "./sidebar";
import { cn } from "@/lib/utils";

interface MobileSidebarProps {
  agents: string[];
  selectedAgent: string | null;
  onSelectAgent: (agent: string) => void;
  isLoading?: boolean;
  maxTurns: number;
  onMaxTurnsChange: (turns: number) => void;
}

export function MobileSidebar({
  agents,
  selectedAgent,
  onSelectAgent,
  isLoading,
  maxTurns,
  onMaxTurnsChange,
}: MobileSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="lg:hidden flex items-center justify-center w-9 h-9 rounded-lg border border-border bg-card hover:bg-secondary transition-colors"
      >
        <Menu className="w-4 h-4" />
      </button>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 lg:hidden transition-transform duration-300",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="relative h-full">
          <button
            onClick={() => setIsOpen(false)}
            className="absolute top-4 right-4 flex items-center justify-center w-8 h-8 rounded-lg bg-secondary hover:bg-muted transition-colors z-10"
          >
            <X className="w-4 h-4" />
          </button>
          <Sidebar
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={(agent) => {
              onSelectAgent(agent);
              setIsOpen(false);
            }}
            isLoading={isLoading}
            maxTurns={maxTurns}
            onMaxTurnsChange={onMaxTurnsChange}
          />
        </div>
      </div>
    </>
  );
}
