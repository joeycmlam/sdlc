"use client";

import { User, Bot, Terminal, Clock } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";

interface ChatMessageProps {
  message: Message;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  if (isTool) {
    return (
      <div className="flex items-start gap-3 px-4 py-3 bg-muted/50 rounded-lg border border-border mx-4 my-2">
        <div className="flex items-center justify-center w-8 h-8 rounded-md bg-tool-cyan/10 text-tool-cyan shrink-0">
          <Terminal className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-tool-cyan">
              {message.toolName || "Tool Execution"}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatTime(message.timestamp)}
            </span>
          </div>
          <pre className="text-sm text-muted-foreground font-mono whitespace-pre-wrap break-all overflow-x-auto">
            {message.content}
          </pre>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex gap-4 px-4 py-6",
        isUser ? "bg-transparent" : "bg-card/50"
      )}
    >
      <div
        className={cn(
          "flex items-center justify-center w-9 h-9 rounded-lg shrink-0",
          isUser
            ? "bg-secondary text-secondary-foreground"
            : "bg-primary/10 text-primary"
        )}
      >
        {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="font-medium">{isUser ? "You" : "Agent"}</span>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="w-3 h-3" />
            {formatTime(message.timestamp)}
          </div>
        </div>
        <div
          className={cn(
            "prose-agent text-foreground",
            message.isStreaming && "cursor-blink"
          )}
        >
          {message.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          ) : (
            <span className="text-muted-foreground italic">Thinking...</span>
          )}
        </div>
      </div>
    </div>
  );
}
