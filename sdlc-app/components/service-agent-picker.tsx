"use client";

import useSWR from "swr";
import {
  Bot,
  Eye,
  HardDrive,
  Loader2,
  RefreshCw,
  Upload,
  X,
  CheckCircle2,
} from "lucide-react";
import { useState, useRef } from "react";

import { fetchAgents, getAgentDisplayName, uploadAgent } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { RegisteredAgent } from "@/lib/types";

export interface ServiceAgentChoice {
  /** Filename, e.g. "ba.agent.md". This is what /api/agents/content takes. */
  file: string;
  /** Display name (registered name if available, else humanised basename). */
  name: string;
  /** Registered description, if the agent has YAML frontmatter. */
  description: string | null;
}

interface ServiceAgentPickerProps {
  value: string | null;
  onChange: (agent: ServiceAgentChoice | null) => void;
  onViewContext?: (agent: ServiceAgentChoice) => void;
  disabled?: boolean;
  /** When true, shows the upload-new-agent button. Defaults to true. */
  showUpload?: boolean;
}

/**
 * ServiceAgentPicker — lists `.agent.md` / `.md` profiles bundled with the
 * copilot-agent service (`services/copilot-agent/agents/`) so a user can pick
 * one and have its instructions inlined into the issue body.
 */
export function ServiceAgentPicker({
  value,
  onChange,
  onViewContext,
  disabled,
  showUpload = true,
}: ServiceAgentPickerProps) {
  const { data, error, isLoading, mutate } = useSWR(
    "agents",
    fetchAgents,
    { revalidateOnFocus: false },
  );

  const choices = buildChoices(data?.files ?? [], data?.agents ?? []);
  const selected = choices.find((a) => a.file === value) ?? null;

  const [showUploadForm, setShowUploadForm] = useState(false);
  const [uploadFilename, setUploadFilename] = useState("");
  const [uploadContent, setUploadContent] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFilename.trim() || !uploadContent.trim()) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const res = await uploadAgent({ filename: uploadFilename.trim(), content: uploadContent });
      setUploadSuccess(res.file);
      setUploadFilename("");
      setUploadContent("");
      setShowUploadForm(false);
      await mutate();
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function handleFileRead(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!uploadFilename) setUploadFilename(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => setUploadContent(ev.target?.result as string ?? "");
    reader.readAsText(file);
    e.target.value = "";
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Bot className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <select
            value={value ?? ""}
            onChange={(e) => {
              const next = choices.find((a) => a.file === e.target.value) ?? null;
              onChange(next);
            }}
            disabled={disabled || isLoading || !!error}
            className={cn(
              "w-full pl-9 pr-3 py-2 rounded-md border border-border bg-background",
              "text-sm appearance-none disabled:opacity-50",
            )}
          >
            <option value="">— Select a service agent —</option>
            {choices.map((a) => (
              <option key={a.file} value={a.file}>
                {a.name} ({a.file})
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => selected && onViewContext?.(selected)}
          disabled={disabled || !selected}
          title={selected ? "View agent context" : "Select an agent first"}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
            "border border-border bg-card hover:bg-secondary",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <Eye className="w-4 h-4" />
          View
        </button>
        <button
          type="button"
          onClick={() => mutate()}
          disabled={disabled || isLoading}
          title="Re-discover agents from the service"
          className={cn(
            "flex items-center justify-center w-9 h-9 rounded-md",
            "border border-border bg-card hover:bg-secondary",
            "disabled:opacity-50",
          )}
        >
          <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
        </button>
        {showUpload && (
          <button
            type="button"
            onClick={() => { setShowUploadForm((v) => !v); setUploadError(null); setUploadSuccess(null); }}
            disabled={disabled}
            title="Upload a new agent"
            className={cn(
              "flex items-center justify-center w-9 h-9 rounded-md",
              "border border-border bg-card hover:bg-secondary",
              "disabled:opacity-50",
              showUploadForm && "border-primary text-primary",
            )}
          >
            {showUploadForm ? <X className="w-4 h-4" /> : <Upload className="w-4 h-4" />}
          </button>
        )}
      </div>

      {showUploadForm && (
        <form onSubmit={handleUpload} className="rounded-md border border-border bg-card/50 p-3 space-y-2">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Upload new agent</div>
          <div className="flex gap-2">
            <input
              type="text"
              value={uploadFilename}
              onChange={(e) => setUploadFilename(e.target.value)}
              placeholder="my-agent.agent.md"
              required
              className={cn(
                "flex-1 px-2 py-1.5 rounded-md border border-border bg-background text-sm font-mono",
                "focus:outline-none focus:ring-1 focus:ring-primary",
              )}
            />
            <label
              title="Load content from a local file"
              className={cn(
                "flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs cursor-pointer",
                "border border-border bg-card hover:bg-secondary text-muted-foreground",
              )}
            >
              <Upload className="w-3.5 h-3.5" />
              File
              <input ref={fileInputRef} type="file" accept=".md" className="hidden" onChange={handleFileRead} />
            </label>
          </div>
          <textarea
            value={uploadContent}
            onChange={(e) => setUploadContent(e.target.value)}
            placeholder={"---\nid: my-agent\nname: My Agent\ndescription: What this agent does\n---\n\nSystem prompt here..."}
            rows={6}
            required
            className={cn(
              "w-full px-2 py-1.5 rounded-md border border-border bg-background text-xs font-mono resize-y",
              "focus:outline-none focus:ring-1 focus:ring-primary",
            )}
          />
          {uploadError && (
            <div className="text-xs text-rose-300">{uploadError}</div>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={uploading || !uploadFilename.trim() || !uploadContent.trim()}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs",
                "bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50",
              )}
            >
              {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
              Upload
            </button>
            <button
              type="button"
              onClick={() => setShowUploadForm(false)}
              disabled={uploading}
              className="px-3 py-1.5 rounded-md text-xs border border-border bg-card hover:bg-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {uploadSuccess && !showUploadForm && (
        <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          Agent <code className="font-mono">{uploadSuccess}</code> uploaded successfully.
        </div>
      )}

      {isLoading && !data && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin" />
          Loading service agents…
        </div>
      )}

      {error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          Failed to load service agents: {(error as Error).message}
        </div>
      )}

      {data && choices.length === 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          No agents found in <code>services/copilot-agent/agents/</code>.
        </div>
      )}

      {selected && (
        <div className="rounded-md border border-border bg-card/30 px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{selected.name}</span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide border border-border bg-secondary text-muted-foreground">
              <HardDrive className="w-3 h-3" />
              service
            </span>
          </div>
          {selected.description && (
            <p className="text-xs text-muted-foreground line-clamp-3 mt-0.5">
              {selected.description}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground/70 mt-1 font-mono">
            services/copilot-agent/agents/{selected.file}
          </p>
        </div>
      )}
    </div>
  );
}

function buildChoices(
  files: string[],
  agents: RegisteredAgent[],
): ServiceAgentChoice[] {
  const byId = new Map(agents.map((a) => [a.id, a]));
  return files
    .slice()
    .sort((a, b) => a.localeCompare(b))
    .map((file) => {
      const id = file.replace(/\.agent\.md$|\.md$/, "");
      const reg = byId.get(id);
      return {
        file,
        name: reg?.name || getAgentDisplayName(file),
        description: reg?.description || null,
      };
    });
}
