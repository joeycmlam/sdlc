"use client";

import { Cpu, ChevronDown, Loader2, AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";

import { fetchAvailableModels } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AvailableModel } from "@/lib/types";

interface ModelSelectorProps {
  selectedModel: string;
  onSelect: (model: string) => void;
  disabled?: boolean;
}

export function ModelSelector({
  selectedModel,
  onSelect,
  disabled,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { data, error, isLoading } = useSWR(
    "models",
    fetchAvailableModels,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );

  const models: AvailableModel[] = data?.models ?? [];
  const usingFallback = data?.source === "fallback";

  // If the parent's selected model isn't in the live list, switch to the
  // first available one. Runs whenever the model list arrives or changes.
  useEffect(() => {
    if (models.length === 0) return;
    if (!selectedModel || !models.some((m) => m.id === selectedModel)) {
      onSelect(models[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [models]);

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

  const selected = models.find((m) => m.id === selectedModel) ?? models[0];
  const buttonLabel = selected?.name ?? (isLoading ? "Loading models…" : "No models");

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => !disabled && models.length > 0 && setIsOpen(!isOpen)}
        disabled={disabled || models.length === 0}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card",
          "hover:bg-secondary transition-colors text-sm",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
        title={
          error
            ? "Failed to load models"
            : usingFallback
              ? "Using fallback model list — backend unreachable"
              : undefined
        }
      >
        {isLoading && !data ? (
          <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
        ) : usingFallback || error ? (
          <AlertTriangle className="w-4 h-4 text-amber-400" />
        ) : (
          <Cpu className="w-4 h-4 text-muted-foreground" />
        )}
        <span>{buttonLabel}</span>
        <ChevronDown
          className={cn(
            "w-4 h-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 z-50 w-64 rounded-lg border border-border bg-popover shadow-lg overflow-hidden max-h-96 overflow-y-auto">
          {models.map((model) => (
            <button
              key={model.id}
              onClick={() => {
                onSelect(model.id);
                setIsOpen(false);
              }}
              className={cn(
                "w-full flex flex-col items-start px-4 py-2.5 hover:bg-secondary transition-colors text-left",
                selectedModel === model.id && "bg-secondary"
              )}
            >
              <span className="font-medium text-sm">{model.name}</span>
              <span className="text-xs text-muted-foreground">
                {model.id}
                {typeof model.billing_multiplier === "number" && (
                  <> · {formatMultiplier(model.billing_multiplier)}</>
                )}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function formatMultiplier(mult: number): string {
  if (mult === 0) return "free";
  if (mult === 1) return "1× premium";
  return `${mult}× premium`;
}
