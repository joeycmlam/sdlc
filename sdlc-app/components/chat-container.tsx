"use client";

import { useEffect, useRef } from "react";
import { Bot, MessageSquare } from "lucide-react";
import { ChatMessage } from "./chat-message";
import { ToolExecutionCard } from "./tool-execution-card";
import { ChatInput } from "./chat-input";
import type { Message } from "@/lib/types";

interface ChatContainerProps {
  messages: Message[];
  onSend: (message: string) => void;
  onStop?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  currentTool?: string | null;
  agentSelected?: boolean;
}

export function ChatContainer({
  messages,
  onSend,
  onStop,
  isLoading,
  disabled,
  currentTool,
  agentSelected,
}: ChatContainerProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentTool]);

  if (!agentSelected) {
    return (
      <div className="flex-1 flex flex-col">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <div className="flex items-center justify-center w-16 h-16 mx-auto rounded-2xl bg-primary/10 text-primary mb-4">
              <Bot className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Select an Agent</h2>
            <p className="text-muted-foreground">
              Choose an agent from the sidebar to start a conversation. Each
              agent is specialized for different tasks and workflows.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full p-8">
            <div className="text-center max-w-md">
              <div className="flex items-center justify-center w-16 h-16 mx-auto rounded-2xl bg-secondary text-muted-foreground mb-4">
                <MessageSquare className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Start a Conversation</h2>
              <p className="text-muted-foreground">
                Send a message to the agent. It can execute commands, analyze
                data, and complete complex multi-step workflows.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                  "Analyze Jira SCRUM-12",
                  "Explain recursion",
                  "Run tests",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => onSend(suggestion)}
                    disabled={disabled || isLoading}
                    className="px-3 py-1.5 text-sm rounded-full border border-border bg-card hover:bg-secondary transition-colors disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {currentTool && <ToolExecutionCard toolName={currentTool} />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="p-4 border-t border-border bg-background">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSend={onSend}
            onStop={onStop}
            isLoading={isLoading}
            disabled={disabled}
            placeholder={
              disabled
                ? "Select an agent to start..."
                : "Send a message to the agent..."
            }
          />
        </div>
      </div>
    </div>
  );
}
