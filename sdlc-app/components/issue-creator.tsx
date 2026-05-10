"use client";

import { useState } from "react";
import {
  Bot,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Send,
  UserX,
} from "lucide-react";

import { createGitHubIssue } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  CreateGitHubIssueResponse,
  GitHubCustomAgent,
} from "@/lib/types";
import {
  AgentContextPanel,
  type AgentContextSource,
} from "./agent-context-panel";
import { GitHubAgentPicker } from "./github-agent-picker";

type AssignmentMode = "none" | "copilot" | "copilot-with-agent";

interface FormState {
  owner: string;
  repo: string;
  title: string;
  body: string;
  assignment: AssignmentMode;
  customAgent: GitHubCustomAgent | null;
  additionalAssignees: string;
  labels: string;
}

const INITIAL: FormState = {
  owner: "",
  repo: "",
  title: "",
  body: "",
  assignment: "copilot",
  customAgent: null,
  additionalAssignees: "",
  labels: "",
};

const ASSIGNMENT_OPTIONS: {
  id: AssignmentMode;
  label: string;
  hint: string;
  icon: typeof Bot;
}[] = [
  {
    id: "none",
    label: "No Copilot assignment",
    hint: "Just create the issue. Useful when a human will triage first.",
    icon: UserX,
  },
  {
    id: "copilot",
    label: "Default Copilot agent",
    hint: "Assign to the Copilot coding agent — no custom .agent.md profile.",
    icon: Bot,
  },
  {
    id: "copilot-with-agent",
    label: "Copilot + custom agent",
    hint: "Assign to Copilot and pin a .agent.md profile (from .github/agents or org .github-private).",
    icon: Bot,
  },
];

function splitCsv(s: string): string[] {
  return s
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
}

export function IssueCreator() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CreateGitHubIssueResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contextSource, setContextSource] = useState<AgentContextSource | null>(
    null,
  );

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (form.assignment === "copilot-with-agent" && !form.customAgent) {
      setError("Pick a custom agent or switch to 'Default Copilot agent'.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await createGitHubIssue({
        owner: form.owner.trim(),
        repo: form.repo.trim(),
        title: form.title.trim(),
        body: form.body,
        assign_to_copilot: form.assignment !== "none",
        additional_assignees: splitCsv(form.additionalAssignees),
        labels: splitCsv(form.labels),
        custom_agent:
          form.assignment === "copilot-with-agent" && form.customAgent
            ? form.customAgent.id
            : undefined,
      });
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setForm(INITIAL);
    setResult(null);
    setError(null);
  }

  const required = form.owner && form.repo && form.title && form.body;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">New GitHub Issue</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create an issue in any repo and (optionally) assign it to GitHub&apos;s
            Copilot coding agent — with or without a custom{" "}
            <code className="bg-secondary px-1 rounded">.agent.md</code> profile
            discovered from your GitHub org/repo.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <fieldset className="rounded-lg border border-border bg-card/50 p-4 space-y-3">
            <legend className="text-sm font-medium px-1">Target repository</legend>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Owner" required>
                <input
                  type="text"
                  value={form.owner}
                  onChange={(e) => update("owner", e.target.value)}
                  placeholder="my-org"
                  className="input"
                  required
                />
              </Field>
              <Field label="Repository" required>
                <input
                  type="text"
                  value={form.repo}
                  onChange={(e) => update("repo", e.target.value)}
                  placeholder="my-repo"
                  className="input"
                  required
                />
              </Field>
            </div>
            <p className="text-xs text-muted-foreground">
              Custom agents are discovered from{" "}
              <code className="bg-secondary px-1 rounded">{"{owner}"}/{"{repo}"}/.github/agents/</code>{" "}
              and{" "}
              <code className="bg-secondary px-1 rounded">{"{owner}"}/.github-private/agents/</code>.
            </p>
          </fieldset>

          <Field label="Title" required>
            <input
              type="text"
              value={form.title}
              onChange={(e) => update("title", e.target.value)}
              placeholder="Implement the new pricing endpoint"
              className="input"
              required
            />
          </Field>

          <Field
            label="Body"
            required
            hint="Markdown supported. The Copilot coding agent reads this as the spec."
          >
            <textarea
              value={form.body}
              onChange={(e) => update("body", e.target.value)}
              rows={8}
              placeholder="## Goal&#10;Brief problem statement&#10;&#10;## Acceptance criteria&#10;- [ ] …"
              className="input font-mono text-xs leading-relaxed"
              required
            />
          </Field>

          <fieldset className="rounded-lg border border-border bg-card/50 p-4 space-y-3">
            <legend className="text-sm font-medium px-1">Assignment</legend>
            <div className="space-y-2">
              {ASSIGNMENT_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const checked = form.assignment === opt.id;
                return (
                  <label
                    key={opt.id}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-md border cursor-pointer transition-colors",
                      checked
                        ? "border-primary bg-primary/5"
                        : "border-border bg-card/30 hover:bg-secondary/50",
                    )}
                  >
                    <input
                      type="radio"
                      name="assignment"
                      value={opt.id}
                      checked={checked}
                      onChange={() => update("assignment", opt.id)}
                      className="mt-1 accent-primary"
                    />
                    <Icon className="w-4 h-4 mt-1 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">{opt.label}</div>
                      <p className="text-xs text-muted-foreground mt-0.5">{opt.hint}</p>
                    </div>
                  </label>
                );
              })}
            </div>

            {form.assignment === "copilot-with-agent" && (
              <div className="pt-2 border-t border-border space-y-2">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Custom agent (from GitHub)
                </div>
                <GitHubAgentPicker
                  owner={form.owner}
                  repo={form.repo}
                  value={form.customAgent?.id ?? null}
                  onChange={(a) => update("customAgent", a)}
                  onViewContext={(a) =>
                    setContextSource({
                      kind: "github",
                      sourceRepo: a.source_repo,
                      path: a.path,
                      scope: a.scope,
                      displayName: a.name,
                    })
                  }
                  disabled={submitting}
                />
                <p className="text-xs text-muted-foreground">
                  Selected agent&apos;s id is appended to the issue body so the cloud Copilot
                  picks the right profile.
                </p>
              </div>
            )}

            {form.assignment !== "none" && (
              <p className="text-xs text-muted-foreground pt-2 border-t border-border">
                Requires Copilot to be enabled on the target repo. If GitHub rejects the
                <code className="bg-secondary px-1 rounded mx-1">Copilot</code> assignee,
                the issue is still created — you&apos;ll see{" "}
                <code className="bg-secondary px-1 rounded">copilot_assigned: false</code>
                {" "}in the response.
              </p>
            )}
          </fieldset>

          <details className="rounded-lg border border-border bg-card/50 p-4">
            <summary className="text-sm font-medium cursor-pointer">
              Advanced options
            </summary>
            <div className="mt-3 space-y-3">
              <Field label="Additional assignees" hint="Comma-separated GitHub usernames">
                <input
                  type="text"
                  value={form.additionalAssignees}
                  onChange={(e) => update("additionalAssignees", e.target.value)}
                  placeholder="alice, bob"
                  className="input"
                />
              </Field>
              <Field label="Labels" hint="Comma-separated">
                <input
                  type="text"
                  value={form.labels}
                  onChange={(e) => update("labels", e.target.value)}
                  placeholder="bug, priority/p1"
                  className="input"
                />
              </Field>
            </div>
          </details>

          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!required || submitting}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
                "bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50",
              )}
            >
              {submitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Create issue
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={submitting}
              className="px-4 py-2 rounded-lg text-sm border border-border bg-card hover:bg-secondary disabled:opacity-50"
            >
              Reset
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300 whitespace-pre-wrap">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-2">
            <div className="flex items-center gap-2 text-emerald-300 font-medium">
              <CheckCircle2 className="w-5 h-5" />
              Issue #{result.number} created
            </div>
            <a
              href={result.html_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary underline break-all"
            >
              {result.html_url}
              <ExternalLink className="w-3 h-3" />
            </a>
            <div className="text-xs text-muted-foreground">
              State: <code className="bg-secondary px-1 rounded">{result.state}</code>
              {" · "}Assignees:{" "}
              {result.assignees.length > 0 ? (
                result.assignees.map((a) => (
                  <code key={a} className="bg-secondary px-1 rounded mx-0.5">
                    {a}
                  </code>
                ))
              ) : (
                <span className="italic">none</span>
              )}
            </div>
            {result.copilot_assigned && (
              <div className="text-xs text-emerald-300">
                ✓ Copilot coding agent assigned. It will start work shortly.
              </div>
            )}
            {form.assignment !== "none" && !result.copilot_assigned && (
              <CopilotAssignmentExplainer
                reason={result.copilot_reason}
                message={result.copilot_message}
                actorCandidates={result.actor_candidates}
                owner={form.owner}
                repo={form.repo}
              />
            )}
          </div>
        )}
      </div>

      <AgentContextPanel
        source={contextSource}
        onClose={() => setContextSource(null)}
      />

      <style jsx>{`
        .input {
          width: 100%;
          padding: 0.5rem 0.75rem;
          border-radius: 0.375rem;
          border: 1px solid hsl(var(--border));
          background: hsl(var(--background));
          font-size: 0.875rem;
        }
        .input:focus {
          outline: 2px solid hsl(var(--primary));
          outline-offset: -1px;
        }
      `}</style>
    </div>
  );
}

function CopilotAssignmentExplainer({
  reason,
  message,
  actorCandidates,
  owner,
  repo,
}: {
  reason: string | null;
  message: string | null;
  actorCandidates: string[];
  owner: string;
  repo: string;
}) {
  if (reason === "not_enabled") {
    return (
      <div className="text-xs text-amber-300 space-y-1">
        <div>⚠ Copilot coding agent is not enabled on this repository.</div>
        <div>
          Enable it at{" "}
          <a
            href={`https://github.com/${owner}/${repo}/settings/copilot`}
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            {owner}/{repo} → Settings → Copilot → Coding agent
          </a>
          , then retry.
        </div>
        {message && (
          <div className="text-amber-300/70 mt-1">{message}</div>
        )}
        {actorCandidates.length > 0 && (
          <details className="mt-1">
            <summary className="cursor-pointer text-amber-300/80">
              GitHub returned {actorCandidates.length} suggestable actor(s) — show
            </summary>
            <ul className="mt-1 ml-4 space-y-0.5 font-mono text-amber-300/70">
              {actorCandidates.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    );
  }
  if (reason === "graphql_error") {
    return (
      <div className="text-xs text-rose-300 space-y-1">
        <div>⚠ Copilot assignment failed via GraphQL.</div>
        {message && (
          <div className="text-rose-300/70 whitespace-pre-wrap">{message}</div>
        )}
      </div>
    );
  }
  if (reason === "unknown" || reason === null) {
    return (
      <div className="text-xs text-amber-300 space-y-1">
        <div>⚠ Reason missing — your API server is likely running outdated code.</div>
        <div className="text-amber-300/70">
          Restart <code className="bg-secondary px-1 rounded">agent-api</code> so the
          new GraphQL-based assignment flow takes effect, then retry.
        </div>
      </div>
    );
  }
  return (
    <div className="text-xs text-amber-300">
      ⚠ Copilot was requested but not applied. Reason:{" "}
      <code className="bg-secondary px-1 rounded">{reason}</code>
      {message && <div className="text-amber-300/70 mt-1">{message}</div>}
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="text-sm font-medium mb-1">
        {label}
        {required && <span className="text-rose-400 ml-1">*</span>}
      </div>
      {children}
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </label>
  );
}
