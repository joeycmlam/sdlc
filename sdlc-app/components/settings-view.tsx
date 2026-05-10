"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Save, RotateCcw, CheckCircle2, AlertCircle } from "lucide-react";

import { checkHealth, listSessions } from "@/lib/api";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "copilot-agent.backend-url";
const DEFAULT_URL = "http://localhost:8000";

export function SettingsView() {
  const [stored, setStored] = useState<string>(DEFAULT_URL);
  const [draft, setDraft] = useState<string>(DEFAULT_URL);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Load on mount.
  useEffect(() => {
    if (typeof window !== "undefined") {
      const v = window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_URL;
      setStored(v);
      setDraft(v);
    }
  }, []);

  function handleSave() {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, draft.trim() || DEFAULT_URL);
    setStored(draft.trim() || DEFAULT_URL);
    setSavedAt(Date.now());
  }

  function handleReset() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(STORAGE_KEY);
    setStored(DEFAULT_URL);
    setDraft(DEFAULT_URL);
    setSavedAt(Date.now());
  }

  const { data: health } = useSWR("settings-health", checkHealth, {
    refreshInterval: 10_000,
  });
  const { data: sessions } = useSWR("settings-sessions", () => listSessions(1), {
    refreshInterval: 30_000,
  });

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground">
            UI-side configuration. Server-side config (Redis URL, models, agent files) lives in
            <code className="px-1 mx-1 bg-secondary rounded text-xs">.env</code>
            on the API server.
          </p>
        </div>

        <section className="rounded-lg border border-border bg-card/50 p-5 space-y-4">
          <div>
            <h2 className="font-medium mb-1">Backend URL</h2>
            <p className="text-xs text-muted-foreground">
              The Copilot Agent FastAPI service. The Next.js API routes proxy to this URL via
              the <code className="px-1 bg-secondary rounded">NEXT_PUBLIC_API_URL</code> env var
              at runtime; this UI-side setting is informational for now.
            </p>
          </div>
          <div className="flex gap-2">
            <input
              type="url"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={DEFAULT_URL}
              className="flex-1 px-3 py-2 rounded-md border border-border bg-background text-sm font-mono"
            />
            <button
              onClick={handleSave}
              disabled={draft.trim() === stored.trim()}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
                "bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50",
              )}
            >
              <Save className="w-4 h-4" /> Save
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-sm border border-border bg-card hover:bg-secondary"
            >
              <RotateCcw className="w-4 h-4" /> Reset
            </button>
          </div>
          {savedAt && (
            <p className="text-xs text-emerald-400">
              Saved at {new Date(savedAt).toLocaleTimeString()}
            </p>
          )}
        </section>

        <section className="rounded-lg border border-border bg-card/50 p-5 space-y-3">
          <h2 className="font-medium">Backend status</h2>
          <Row
            ok={health?.status === "ok"}
            label="API server"
            value={health ? `${health.status}` : "unknown"}
          />
          <Row
            ok={health?.redis === true}
            label="Redis (sessions + streams)"
            value={
              health?.redis === undefined
                ? "unknown — check /health"
                : health.redis
                  ? "connected"
                  : "down"
            }
          />
          <Row
            ok={Array.isArray(sessions?.sessions)}
            label="Sessions endpoint"
            value={
              sessions ? `reachable — ${sessions.sessions.length} live session(s)` : "checking…"
            }
          />
        </section>
      </div>
    </div>
  );
}

function Row({ ok, label, value }: { ok: boolean | undefined; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("flex items-center gap-2", ok ? "text-emerald-400" : "text-amber-400")}>
        {ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
        {value}
      </span>
    </div>
  );
}
