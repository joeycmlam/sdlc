"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { ArrowLeft, Check, Loader2, Play, Square, X } from "lucide-react";

import {
  approveSession,
  cancelSession,
  getAgentDisplayName,
  getSession,
  startSession,
  streamSessionEvents,
} from "@/lib/api";
import type { Session, SessionEvent, SessionState } from "@/lib/types";
import { cn, formatSessionDuration } from "@/lib/utils";
import { SessionStatusBadge } from "./session-status-badge";
import { ToolExecutionCard } from "./tool-execution-card";

const TERMINAL_STATES = new Set<SessionState>(["completed", "failed", "rejected"]);

export function SessionDetail({ id }: { id: string }) {
  const [transcript, setTranscript] = useState("");
  const [tools, setTools] = useState<string[]>([]);
  const [toolDetails, setToolDetails] = useState<Record<number, string>>({});
  const [toolResults, setToolResults] = useState<Record<number, string>>({});
  const [currentTurn, setCurrentTurn] = useState<{ n: number; max: number } | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // Ref mirror of tools so callbacks can read the latest count synchronously
  // without nested setState. Also a tool_call_id → index map so out-of-order
  // events (and sub-agent events that omit the id) still attach correctly.
  const toolsCountRef = useRef(0);
  const toolIndexByIdRef = useRef<Map<string, number>>(new Map());

  const { data: session, mutate, error } = useSWR<Session>(
    ["session", id],
    () => getSession(id),
    {
      refreshInterval: (s) =>
        s && TERMINAL_STATES.has(s.state) ? 0 : 3_000,
    },
  );

  // Subscribe to SSE once, on mount.
  useEffect(() => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setTranscript("");
    setTools([]);
    setToolDetails({});
    setToolResults({});
    setCurrentTurn(null);
    setStreamError(null);
    toolsCountRef.current = 0;
    toolIndexByIdRef.current = new Map();

    (async () => {
      try {
        for await (const ev of streamSessionEvents(id, ac.signal)) {
          handleEvent(ev);
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setStreamError((err as Error).message);
        }
      }
      // SSE ended — refresh state once so terminal status shows.
      mutate();
    })();

    function resolveToolIndex(toolCallId: string | undefined): number {
      // Prefer explicit tool_call_id correlation; fall back to "most recent"
      // for legacy events (bash_result, sub-agent leaks) that don't carry one.
      if (toolCallId) {
        const known = toolIndexByIdRef.current.get(toolCallId);
        if (known != null) return known;
      }
      return toolsCountRef.current - 1;
    }

    function handleEvent(ev: SessionEvent) {
      if (ev.type === "chunk" && ev.content) {
        setTranscript((t) => t + ev.content);
      } else if (ev.type === "tool" && ev.name) {
        const idx = toolsCountRef.current;
        toolsCountRef.current += 1;
        if (ev.tool_call_id) {
          toolIndexByIdRef.current.set(ev.tool_call_id, idx);
        }
        setTools((prev) => [...prev, ev.name as string]);
      } else if (ev.type === "bash_result" && ev.command != null) {
        const idx = resolveToolIndex(undefined);
        if (idx >= 0) {
          setToolDetails((d) => ({ ...d, [idx]: `$ ${ev.command}` }));
          if (ev.result) {
            setToolResults((r) => ({ ...r, [idx]: ev.result as string }));
          }
        }
      } else if (ev.type === "tool_args") {
        // Attach args to the right card via tool_call_id (or fall back to
        // most-recent). Don't clobber a bash_result $-prefixed command —
        // that has richer formatting.
        const idx = resolveToolIndex(ev.tool_call_id);
        if (idx >= 0) {
          const summary = summariseToolArgs(ev.name, ev.arguments);
          if (summary) {
            setToolDetails((d) => (d[idx] ? d : { ...d, [idx]: summary }));
          }
        }
      } else if (ev.type === "tool_result") {
        const idx = resolveToolIndex(ev.tool_call_id);
        if (idx >= 0 && ev.result) {
          setToolResults((r) => (r[idx] ? r : { ...r, [idx]: ev.result as string }));
        }
      } else if (ev.type === "turn" && ev.n != null) {
        setCurrentTurn({ n: ev.n, max: ev.max_turns ?? 0 });
      } else if (ev.type === "state" || ev.type === "done") {
        mutate();
      } else if (ev.type === "error" && ev.message) {
        setStreamError(ev.message);
      }
    }

    return () => ac.abort();
  }, [id, mutate]);

  async function handleStart() {
    if (!session) return;
    setStarting(true);
    try {
      await startSession(id);
      await mutate();
    } finally {
      setStarting(false);
    }
  }

  async function handleApprove(action: "approve" | "reject") {
    setApproving(true);
    try {
      await approveSession(id, action);
      await mutate();
    } finally {
      setApproving(false);
    }
  }

  async function handleCancel() {
    setCancelling(true);
    try {
      await cancelSession(id);
      await mutate();
    } finally {
      setCancelling(false);
    }
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-rose-400">Failed to load: {(error as Error).message}</p>
        <Link href="/sessions" className="text-primary underline mt-2 inline-block">
          Back to sessions
        </Link>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="p-12 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const canStart = session.state === "pending" || session.state === "approved";
  const needsApproval = session.state === "awaiting_approval";
  const isRunning = session.state === "running" || session.state === "awaiting_approval";

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="flex items-center gap-2">
          <Link
            href="/sessions"
            className="p-2 rounded-lg hover:bg-secondary text-muted-foreground"
            title="Back"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-xl font-semibold tracking-tight">
            {getAgentDisplayName(session.agent_file)}
          </h1>
          <SessionStatusBadge state={session.state} />
        </div>

        <div className="rounded-lg border border-border bg-card/50 p-4">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <Field label="ID" value={session.id} mono />
            <Field label="Model" value={session.model} mono />
            <Field label="Agent file" value={session.agent_file} mono />
            <Field label="Max turns" value={String(session.max_turns)} />
            <Field
              label="Timeout"
              value={session.timeout_seconds ? `${session.timeout_seconds}s` : "default"}
            />
            <Field label="Created" value={new Date(session.created_at).toLocaleString()} />
            <Field label="Updated" value={new Date(session.updated_at).toLocaleString()} />
            <Field
              label="Duration"
              value={formatSessionDuration(
                session.created_at,
                TERMINAL_STATES.has(session.state) ? session.updated_at : null,
              )}
            />
            {(session.github_owner || session.github_repo) && (
              <Field
                label="GitHub repo"
                value={[session.github_owner, session.github_repo].filter(Boolean).join("/")}
                mono
              />
            )}
            {session.custom_agent && (
              <Field label="Custom agent" value={session.custom_agent} mono />
            )}
          </div>
          <div className="mt-3 pt-3 border-t border-border">
            <div className="text-xs uppercase text-muted-foreground mb-1">Instruction</div>
            <p className="text-sm whitespace-pre-wrap">{session.instruction}</p>
          </div>
          {session.extra_context && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="text-xs uppercase text-muted-foreground mb-1">Extra context</div>
              <p className="text-sm whitespace-pre-wrap text-muted-foreground">{session.extra_context}</p>
            </div>
          )}
          {session.jira_url && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="text-xs uppercase text-muted-foreground mb-1">Jira</div>
              <a
                href={session.jira_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-primary underline"
              >
                {session.jira_url}
              </a>
            </div>
          )}
          {session.github_issue_url && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="text-xs uppercase text-muted-foreground mb-1">GitHub issue</div>
              <a
                href={session.github_issue_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-primary underline"
              >
                {session.github_issue_url}
              </a>
            </div>
          )}
          {session.confluence_pages.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="text-xs uppercase text-muted-foreground mb-1">Confluence pages</div>
              <ul className="space-y-1">
                {session.confluence_pages.map((url) => (
                  <li key={url}>
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-primary underline"
                    >
                      {url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {canStart && (
            <button
              onClick={handleStart}
              disabled={starting}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-sm",
                "bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50",
              )}
            >
              {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Enqueue run
            </button>
          )}
          {isRunning && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 disabled:opacity-50"
            >
              {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Square className="w-4 h-4" />}
              Stop
            </button>
          )}
          {needsApproval && (
            <>
              <button
                onClick={() => handleApprove("approve")}
                disabled={approving}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 disabled:opacity-50"
              >
                <Check className="w-4 h-4" /> Approve
              </button>
              <button
                onClick={() => handleApprove("reject")}
                disabled={approving}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 disabled:opacity-50"
              >
                <X className="w-4 h-4" /> Reject
              </button>
            </>
          )}
        </div>

        {(tools.length > 0 || currentTurn) && (
          <div className="rounded-lg border border-border bg-card/50 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase text-muted-foreground">Tool calls</div>
              {currentTurn && !TERMINAL_STATES.has(session.state) && (
                <div className="text-xs text-muted-foreground">
                  Turn {currentTurn.n}{currentTurn.max > 0 ? ` / ${currentTurn.max}` : ""}
                </div>
              )}
            </div>
            {tools.map((name, i) => (
              <ToolExecutionCard
                key={`${name}-${i}`}
                toolName={name}
                isExecuting={i === tools.length - 1 && !TERMINAL_STATES.has(session.state)}
                detail={toolDetails[i]}
                result={toolResults[i]}
              />
            ))}
          </div>
        )}

        <div className="rounded-lg border border-border bg-card/50 p-4">
          <div className="text-xs uppercase text-muted-foreground mb-2">Transcript</div>
          {transcript ? (
            <pre className="text-sm whitespace-pre-wrap font-mono leading-relaxed">
              {transcript}
            </pre>
          ) : session.result ? (
            <pre className="text-sm whitespace-pre-wrap font-mono leading-relaxed">
              {session.result}
            </pre>
          ) : TERMINAL_STATES.has(session.state) ? (
            <div className="text-sm text-muted-foreground italic space-y-1">
              <p>
                Session ended in state <span className="font-mono not-italic">{session.state}</span>
                {" "}without producing any textual output.
              </p>
              <p className="text-xs">
                {tools.length > 0
                  ? `The agent invoked ${tools.length} tool${tools.length === 1 ? "" : "s"} but never returned a final message. Open each tool card above to inspect what ran.`
                  : "No tool calls were captured either — the model likely refused or returned an empty response. Try re-running, switching models, or sharpening the instruction."}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              {session.state === "pending"
                ? "Click Enqueue run to start."
                : "Waiting for output…"}
            </p>
          )}
        </div>

        {session.error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4">
            <div className="text-xs uppercase text-rose-400 mb-1">Error</div>
            <p className="text-sm text-rose-200 whitespace-pre-wrap">{session.error}</p>
          </div>
        )}

        {streamError && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
            Stream interrupted: {streamError}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase text-muted-foreground mb-0.5">{label}</div>
      <div className={cn("text-sm break-all", mono && "font-mono text-xs")}>{value}</div>
    </div>
  );
}

// Pick the most informative one-line summary for a tool's arguments.
// Copilot forwards arguments as either a parsed dict or a raw JSON string —
// normalise both. Falls back to compact JSON if no single field stands out.
function summariseToolArgs(name: string | undefined, args: unknown): string | undefined {
  if (args == null) return undefined;

  // Raw JSON string? Try to parse so we can pull priority fields.
  if (typeof args === "string") {
    const trimmed = args.trim();
    if (!trimmed) return undefined;
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        return summariseToolArgs(name, JSON.parse(trimmed));
      } catch {
        // not valid JSON — show as-is below
      }
    }
    return trimmed.length > 400 ? trimmed.slice(0, 400) + "…" : trimmed;
  }
  if (typeof args !== "object") return String(args);

  const obj = args as Record<string, unknown>;
  // Prefer common high-signal fields when present.
  const priorityKeys = [
    "command",
    "path",
    "file_path",
    "url",
    "agent_file",
    "instruction",
    "query",
    "summary",
    "title",
    "subject",
    "intent",
  ];
  for (const k of priorityKeys) {
    const v = obj[k];
    if (typeof v === "string" && v.trim()) {
      const value = v.length > 300 ? v.slice(0, 300) + "…" : v;
      return name === "bash_exec" && k === "command" ? `$ ${value}` : `${k}: ${value}`;
    }
  }

  try {
    const json = JSON.stringify(obj);
    if (json === "{}") return undefined;
    return json.length > 400 ? json.slice(0, 400) + "…" : json;
  } catch {
    return undefined;
  }
}
