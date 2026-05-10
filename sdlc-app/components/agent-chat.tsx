"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { ArrowRight, Bot, Loader2 } from "lucide-react";

import { AppShell } from "./app-shell";
import { Sidebar } from "./sidebar";
import { MobileSidebar } from "./mobile-sidebar";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { SessionStatusBadge } from "./session-status-badge";
import {
  createSession,
  fetchAgents,
  getAgentDisplayName,
  listSessions,
  startSession,
} from "@/lib/api";
import { formatSessionDuration } from "@/lib/utils";
import type { SessionState } from "@/lib/types";

const TERMINAL_STATES = new Set<SessionState>(["completed", "failed", "rejected"]);

export function AgentChat() {
  const router = useRouter();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [maxTurns, setMaxTurns] = useState(20);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: agentsData } = useSWR("agents", fetchAgents, {
    revalidateOnFocus: false,
  });
  const agents = agentsData?.files || [];

  const { data: sessionsData } = useSWR(
    "sessions:recent",
    () => listSessions(8),
    { refreshInterval: 5000 },
  );
  const recentSessions = sessionsData?.sessions ?? [];

  const handleSend = useCallback(
    async (content: string) => {
      if (!selectedAgent || !selectedModel || submitting) return;
      setSubmitting(true);
      setSubmitError(null);
      try {
        const session = await createSession({
          agent_file: `agents/${selectedAgent}`,
          instruction: content,
          model: selectedModel,
          max_turns: maxTurns,
        });
        await startSession(session.id);
        router.push(`/sessions/${session.id}`);
      } catch (err) {
        setSubmitError((err as Error).message || "Failed to create request.");
        setSubmitting(false);
      }
    },
    [selectedAgent, selectedModel, maxTurns, submitting, router],
  );

  const chatControls = (
    <ModelSelector
      selectedModel={selectedModel}
      onSelect={setSelectedModel}
      disabled={submitting}
    />
  );

  const inputDisabled = !selectedAgent || !selectedModel || submitting;

  return (
    <AppShell active="chat" rightSlot={chatControls}>
      <div className="flex-1 flex min-h-0">
        <div className="hidden lg:block">
          <Sidebar
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            isLoading={submitting}
            maxTurns={maxTurns}
            onMaxTurnsChange={setMaxTurns}
          />
        </div>
        <main className="flex-1 flex flex-col min-w-0">
          <div className="lg:hidden flex items-center gap-2 px-4 py-2 border-b border-border">
            <MobileSidebar
              agents={agents}
              selectedAgent={selectedAgent}
              onSelectAgent={setSelectedAgent}
              isLoading={submitting}
              maxTurns={maxTurns}
              onMaxTurnsChange={setMaxTurns}
            />
            <span className="text-sm text-muted-foreground">
              {selectedAgent ? `Agent: ${selectedAgent.replace(/\.md$/, "")}` : "Select an agent"}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
              <header>
                <h1 className="text-xl font-semibold tracking-tight">New request</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Each send creates a durable session you can revisit on the{" "}
                  <Link href="/sessions" className="text-primary underline">
                    Sessions
                  </Link>{" "}
                  tab.
                </p>
              </header>

              {!selectedAgent && (
                <div className="rounded-lg border border-dashed border-border bg-card/30 p-6 text-center">
                  <Bot className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Pick an agent in the sidebar to start.
                  </p>
                </div>
              )}

              <section>
                <div className="flex items-baseline justify-between mb-2">
                  <h2 className="text-sm font-medium">Recent requests</h2>
                  <Link
                    href="/sessions"
                    className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                  >
                    View all <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
                {recentSessions.length === 0 ? (
                  <div className="rounded-lg border border-border bg-card/30 px-4 py-6 text-center text-sm text-muted-foreground">
                    No requests yet — send one below.
                  </div>
                ) : (
                  <ul className="rounded-lg border border-border bg-card/30 divide-y divide-border">
                    {recentSessions.map((s) => (
                      <li key={s.id}>
                        <Link
                          href={`/sessions/${s.id}`}
                          className="flex items-center gap-3 px-4 py-2.5 hover:bg-secondary/50 transition-colors"
                        >
                          <SessionStatusBadge state={s.state} />
                          <span className="text-xs font-mono text-muted-foreground shrink-0">
                            {getAgentDisplayName(s.agent_file)}
                          </span>
                          <span className="flex-1 text-sm truncate" title={s.instruction}>
                            {s.instruction}
                          </span>
                          <span className="text-xs text-muted-foreground tabular-nums shrink-0">
                            {formatSessionDuration(
                              s.created_at,
                              TERMINAL_STATES.has(s.state) ? s.updated_at : null,
                            )}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {submitError && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
                  {submitError}
                </div>
              )}
            </div>
          </div>

          <div className="p-4 border-t border-border bg-background">
            <div className="max-w-3xl mx-auto">
              <ChatInput
                onSend={handleSend}
                isLoading={submitting}
                disabled={inputDisabled}
                placeholder={
                  !selectedAgent
                    ? "Select an agent to start..."
                    : !selectedModel
                      ? "Loading models..."
                      : "Describe your request — Enter to submit"
                }
              />
              {submitting && (
                <p className="mt-2 text-xs text-muted-foreground flex items-center justify-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Creating session…
                </p>
              )}
            </div>
          </div>
        </main>
      </div>
    </AppShell>
  );
}

