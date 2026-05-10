"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Loader2, RefreshCw, Trash2, ExternalLink } from "lucide-react";

import { listSessions, deleteSession, getAgentDisplayName } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SessionStatusBadge } from "./session-status-badge";

export function SessionsList() {
  const [busyId, setBusyId] = useState<string | null>(null);
  const { data, error, isLoading, mutate } = useSWR(
    "sessions",
    () => listSessions(100),
    { refreshInterval: 5000, revalidateOnFocus: true },
  );

  async function handleDelete(id: string) {
    setBusyId(id);
    try {
      await deleteSession(id);
      await mutate();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Sessions</h1>
            <p className="text-sm text-muted-foreground">
              Worker-pool runs (Redis-backed). Polled every 5s.
            </p>
          </div>
          <button
            onClick={() => mutate()}
            disabled={isLoading}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg",
              "border border-border bg-card hover:bg-secondary",
              "text-sm transition-colors disabled:opacity-50",
            )}
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400 text-sm mb-4">
            Failed to load sessions: {(error as Error).message}
          </div>
        )}

        {!data && isLoading && (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {data && data.sessions.length === 0 && (
          <div className="p-12 rounded-lg border border-border bg-card/50 text-center">
            <p className="text-muted-foreground mb-2">No sessions yet.</p>
            <p className="text-sm text-muted-foreground">
              Start a chat in <Link href="/" className="text-primary underline">Chat</Link>{" "}
              and use &ldquo;Session mode&rdquo; to enqueue a worker run.
            </p>
          </div>
        )}

        {data && data.sessions.length > 0 && (
          <div className="rounded-lg border border-border bg-card/50 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="text-left p-3 font-medium">State</th>
                  <th className="text-left p-3 font-medium">Agent</th>
                  <th className="text-left p-3 font-medium">Instruction</th>
                  <th className="text-left p-3 font-medium">Updated</th>
                  <th className="text-right p-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {data.sessions.map((s) => (
                  <tr
                    key={s.id}
                    className="border-t border-border hover:bg-secondary/30 transition-colors"
                  >
                    <td className="p-3"><SessionStatusBadge state={s.state} /></td>
                    <td className="p-3 font-mono text-xs">
                      {getAgentDisplayName(s.agent_file)}
                    </td>
                    <td className="p-3 max-w-md truncate" title={s.instruction}>
                      {s.instruction}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground whitespace-nowrap">
                      {new Date(s.updated_at).toLocaleTimeString()}
                    </td>
                    <td className="p-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          href={`/sessions/${s.id}`}
                          className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
                          title="View session"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                        <button
                          onClick={() => handleDelete(s.id)}
                          disabled={busyId === s.id}
                          className="p-1.5 rounded hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 disabled:opacity-50"
                          title="Delete session"
                        >
                          {busyId === s.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
