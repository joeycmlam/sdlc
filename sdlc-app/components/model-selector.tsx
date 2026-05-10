"use client";

import { Cpu, ChevronDown } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";

interface ModelSelectorProps {
  selectedModel: string;
  onSelect: (model: string) => void;
  disabled?: boolean;
}

const MODELS = [
  { id: "gpt-4o", name: "GPT-4o", description: "Most capable model" },
  { id: "gpt-4o-mini", name: "GPT-4o Mini", description: "Fast and efficient" },
  { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", description: "Balanced performance" },
  { id: "meta-llama-3.1-70b-instruct", name: "Llama 3.1 70B", description: "Open source large model" },
];

export function ModelSelector({
  selectedModel,
  onSelect,
  disabled,
}: ModelSelectorProps) {
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

  const selected = MODELS.find((m) => m.id === selectedModel) || MODELS[0];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card",
          "hover:bg-secondary transition-colors text-sm",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
      >
        <Cpu className="w-4 h-4 text-muted-foreground" />
        <span>{selected.name}</span>
        <ChevronDown
          className={cn(
            "w-4 h-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 z-50 w-56 rounded-lg border border-border bg-popover shadow-lg overflow-hidden">
          {MODELS.map((model) => (
            <button
              key={model.id}
              onClick={() => {
                onSelect(model.id);
                setIsOpen(false);
              }}
              className={cn(
                "w-full flex flex-col items-start px-4 py-3 hover:bg-secondary transition-colors text-left",
                selectedModel === model.id && "bg-secondary"
              )}
            >
              <span className="font-medium text-sm">{model.name}</span>
              <span className="text-xs text-muted-foreground">
                {model.description}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
