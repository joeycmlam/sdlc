"use client";

import { useState, useCallback, useRef } from "react";
import useSWR from "swr";
import { RotateCcw } from "lucide-react";

import { AppShell } from "./app-shell";
import { Sidebar } from "./sidebar";
import { MobileSidebar } from "./mobile-sidebar";
import { ChatContainer } from "./chat-container";
import { ModelSelector } from "./model-selector";
import { fetchAgents, streamAgent } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";

function generateId(): string {
  return Math.random().toString(36).substring(2, 15);
}

export function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("gpt-4o");
  const [maxTurns, setMaxTurns] = useState(20);
  const [isLoading, setIsLoading] = useState(false);
  const [currentTool, setCurrentTool] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { data: agentsData } = useSWR("agents", fetchAgents, {
    revalidateOnFocus: false,
  });

  // Use the file list (string[]) so the existing Sidebar/AgentSelector
  // string-based API keeps working. (The Issues page sources its custom
  // agents from GitHub instead of the local agents/ directory.)
  const agents = agentsData?.files || [];

  const handleSend = useCallback(
    async (content: string) => {
      if (!selectedAgent || isLoading) return;

      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setCurrentTool(null);

      const assistantMessageId = generateId();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      try {
        abortControllerRef.current = new AbortController();

        const stream = streamAgent(
          {
            agent_file: `agents/${selectedAgent}`,
            instruction: content,
            model: selectedModel,
            max_turns: maxTurns,
          },
          abortControllerRef.current.signal
        );

        for await (const event of stream) {
          switch (event.type) {
            case "chunk":
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: msg.content + (event.content || "") }
                    : msg
                )
              );
              break;

            case "tool":
              setCurrentTool(event.name || null);
              if (event.name) {
                const toolMessage: Message = {
                  id: generateId(),
                  role: "tool",
                  content: `Executing ${event.name}...`,
                  timestamp: new Date(),
                  toolName: event.name,
                };
                setMessages((prev) => [...prev, toolMessage]);
              }
              break;

            case "done":
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: event.content || msg.content,
                        isStreaming: false,
                      }
                    : msg
                )
              );
              setCurrentTool(null);
              break;

            case "error":
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: `Error: ${event.message}`,
                        isStreaming: false,
                      }
                    : msg
                )
              );
              break;
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
        } else {
          console.error("Stream error:", error);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content:
                      msg.content ||
                      "An error occurred while communicating with the agent.",
                    isStreaming: false,
                  }
                : msg
            )
          );
        }
      } finally {
        setIsLoading(false);
        setCurrentTool(null);
        abortControllerRef.current = null;
      }
    },
    [selectedAgent, selectedModel, maxTurns, isLoading]
  );

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsLoading(false);
    setCurrentTool(null);
  }, []);

  const handleReset = useCallback(() => {
    setMessages([]);
    setCurrentTool(null);
  }, []);

  const chatControls = (
    <>
      <ModelSelector
        selectedModel={selectedModel}
        onSelect={setSelectedModel}
        disabled={isLoading}
      />
      <button
        onClick={handleReset}
        disabled={isLoading}
        className={cn(
          "flex items-center justify-center w-9 h-9 rounded-lg",
          "border border-border bg-card hover:bg-secondary",
          "transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        )}
        title="Reset conversation"
      >
        <RotateCcw className="w-4 h-4 text-muted-foreground" />
      </button>
    </>
  );

  return (
    <AppShell active="chat" rightSlot={chatControls}>
      <div className="flex-1 flex min-h-0">
        <div className="hidden lg:block">
          <Sidebar
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            isLoading={isLoading}
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
              isLoading={isLoading}
              maxTurns={maxTurns}
              onMaxTurnsChange={setMaxTurns}
            />
            <span className="text-sm text-muted-foreground">
              {selectedAgent ? `Agent: ${selectedAgent.replace(/\.md$/, "")}` : "Select an agent"}
            </span>
          </div>
          <ChatContainer
            messages={messages}
            onSend={handleSend}
            onStop={handleStop}
            isLoading={isLoading}
            disabled={!selectedAgent}
            currentTool={currentTool}
            agentSelected={!!selectedAgent}
          />
        </main>
      </div>
    </AppShell>
  );
}
