"use client";

import { X, Bot, Wrench, BookOpen, Zap, ChevronRight, Loader2, GitBranch, Building2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import {
  fetchAgentContent,
  fetchGitHubAgentContent,
  getAgentDisplayName,
} from "@/lib/api";
import type { AgentMetadata } from "@/lib/types";

/**
 * Source descriptor for the panel.
 *
 *   { kind: "local",  file: "ba.agent.md" }
 *     → fetched from /api/agents/content (services/copilot-agent/agents/)
 *
 *   { kind: "github", sourceRepo, path, scope?, displayName? }
 *     → fetched from /api/github/agents/content (repo or org .agent.md)
 */
export type AgentContextSource =
  | { kind: "local"; file: string }
  | {
      kind: "github";
      sourceRepo: string;
      path: string;
      scope?: "repo" | "org";
      displayName?: string;
    };

interface AgentContextPanelProps {
  source: AgentContextSource | null;
  onClose: () => void;
}

interface LoadedDetail {
  title: string;
  subtitle: string;
  scope?: "repo" | "org" | "local";
  metadata: AgentMetadata;
  body: string;
}

export function AgentContextPanel({ source, onClose }: AgentContextPanelProps) {
  const [detail, setDetail] = useState<LoadedDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!source) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        if (source.kind === "local") {
          const data = await fetchAgentContent(source.file);
          if (cancelled) return;
          setDetail({
            title: getAgentDisplayName(source.file),
            subtitle: source.file,
            scope: "local",
            metadata: data.metadata,
            body: data.content,
          });
        } else {
          const data = await fetchGitHubAgentContent(source.sourceRepo, source.path);
          if (cancelled) return;
          setDetail({
            title:
              source.displayName ||
              (data.metadata.name as string | undefined) ||
              source.path.split("/").pop()?.replace(/\.agent\.md$|\.md$/, "") ||
              "Agent",
            subtitle: `${source.sourceRepo} · ${source.path}`,
            scope: source.scope ?? "repo",
            metadata: data.metadata as AgentMetadata,
            body: stripFrontmatter(data.content),
          });
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message || "Failed to load.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source]);

  const isOpen = source !== null;

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-200",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        )}
        onClick={onClose}
      />
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-full max-w-2xl bg-card border-l border-border shadow-2xl",
          "flex flex-col transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center gap-3 px-6 py-4 border-b border-border shrink-0">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10 text-primary">
            <Bot className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-lg truncate">
              {detail?.title || "Agent Context"}
            </h2>
            <p className="text-xs text-muted-foreground truncate">
              {detail?.subtitle || ""}
            </p>
          </div>
          {detail?.scope && detail.scope !== "local" && (
            <ScopeBadge scope={detail.scope} />
          )}
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
            aria-label="Close panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center h-40 gap-2 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Loading agent context…</span>
            </div>
          )}

          {error && (
            <div className="m-6 p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}

          {detail && !loading && (
            <div className="divide-y divide-border">
              <MetadataSection metadata={detail.metadata} />
              <div className="px-6 py-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  System Prompt
                </h3>
                <div className="prose-agent text-sm text-foreground leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {detail.body}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function ScopeBadge({ scope }: { scope: "repo" | "org" }) {
  const Icon = scope === "repo" ? GitBranch : Building2;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border border-border bg-secondary text-muted-foreground">
      <Icon className="w-3 h-3" />
      {scope}
    </span>
  );
}

function MetadataSection({ metadata }: { metadata: AgentMetadata }) {
  const hasAny =
    metadata.description ||
    (metadata.skills?.length ?? 0) > 0 ||
    (metadata.tools?.length ?? 0) > 0 ||
    (metadata.agents?.length ?? 0) > 0 ||
    (metadata.triggers?.length ?? 0) > 0;
  if (!hasAny) return null;

  return (
    <div className="px-6 py-5 space-y-4">
      {metadata.description && (
        <Section title="Description">
          <p className="text-sm text-foreground leading-relaxed">{metadata.description}</p>
        </Section>
      )}
      {metadata.skills && metadata.skills.length > 0 && (
        <Section title="Skills" icon={BookOpen}>
          <Chips items={metadata.skills} color="blue" />
        </Section>
      )}
      {metadata.tools && metadata.tools.length > 0 && (
        <Section title="Tools" icon={Wrench}>
          <Chips items={metadata.tools} color="emerald" />
        </Section>
      )}
      {metadata.agents && metadata.agents.length > 0 && (
        <Section title="Sub-Agents" icon={Bot}>
          <Chips items={metadata.agents} color="purple" />
        </Section>
      )}
      {metadata.triggers && metadata.triggers.length > 0 && (
        <Section title="Triggers" icon={Zap}>
          <div className="space-y-1">
            {metadata.triggers.map((t) => (
              <div key={t} className="flex items-center gap-2 text-xs text-muted-foreground">
                <ChevronRight className="w-3.5 h-3.5 shrink-0" />
                <code className="font-mono">{t}</code>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5" />}
        {title}
      </h3>
      {children}
    </div>
  );
}

const COLOR_CLASSES: Record<string, string> = {
  blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
};

function Chips({ items, color }: { items: string[]; color: keyof typeof COLOR_CLASSES }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className={cn(
            "px-2.5 py-0.5 rounded-full text-xs font-medium border",
            COLOR_CLASSES[color],
          )}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

/** Strip a YAML `--- ... ---` frontmatter block at the top of a Markdown doc. */
function stripFrontmatter(raw: string): string {
  if (!raw.startsWith("---")) return raw;
  const end = raw.indexOf("\n---", 3);
  if (end < 0) return raw;
  return raw.slice(end + 4).replace(/^\n+/, "");
}
