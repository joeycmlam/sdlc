"use client";

import Link from "next/link";
import { Github, MessageSquare, ListTree, Bug, Settings } from "lucide-react";
import useSWR from "swr";

import { checkHealth } from "@/lib/api";
import { cn } from "@/lib/utils";
import { StatusIndicator } from "./status-indicator";
import type { ConnectionStatus } from "@/lib/types";

type Tab = "chat" | "sessions" | "issues" | "settings";

const NAV: { id: Tab; href: string; label: string; icon: typeof Github }[] = [
  { id: "chat", href: "/", label: "Chat", icon: MessageSquare },
  { id: "sessions", href: "/sessions", label: "Sessions", icon: ListTree },
  { id: "issues", href: "/issues/new", label: "Issues", icon: Bug },
  { id: "settings", href: "/settings", label: "Settings", icon: Settings },
];

interface AppShellProps {
  active: Tab;
  children: React.ReactNode;
  /** Optional right-side controls (e.g. model selector on the chat page) */
  rightSlot?: React.ReactNode;
}

export function AppShell({ active, children, rightSlot }: AppShellProps) {
  const { data: healthData, error: healthError } = useSWR(
    "health",
    checkHealth,
    { refreshInterval: 30_000, revalidateOnFocus: true },
  );

  const status: ConnectionStatus =
    healthError ? "disconnected" : healthData ? "connected" : "connecting";

  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary text-primary-foreground">
              <Github className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-semibold tracking-tight leading-tight">Copilot Agent</h1>
              <p className="text-xs text-muted-foreground leading-tight">
                GitHub Copilot SDK
              </p>
            </div>
          </Link>

          <nav className="hidden sm:flex items-center gap-1">
            {NAV.map((item) => {
              const Icon = item.icon;
              const isActive = item.id === active;
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:block">
            <StatusIndicator status={status} />
          </div>
          {rightSlot}
        </div>
      </header>

      <main className="flex-1 flex flex-col">{children}</main>
    </div>
  );
}
