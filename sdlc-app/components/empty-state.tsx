"use client";

import { Bot, Zap, Terminal, GitBranch } from "lucide-react";

interface EmptyStateProps {
  onSelectExample?: (example: string) => void;
}

const FEATURES = [
  {
    icon: Terminal,
    title: "Shell Execution",
    description: "Run bash commands directly",
  },
  {
    icon: GitBranch,
    title: "Sub-Agents",
    description: "Delegate to specialized agents",
  },
  {
    icon: Zap,
    title: "Multi-Step Workflows",
    description: "Complete complex tasks autonomously",
  },
];

const EXAMPLES = [
  "Analyze Jira issue SCRUM-12 and create test cases",
  "Explain recursion with code examples",
  "Run the test suite and summarize results",
  "Read the README and explain the project structure",
];

export function EmptyState({ onSelectExample }: EmptyStateProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center w-20 h-20 mx-auto rounded-2xl bg-primary/10 text-primary mb-6">
            <Bot className="w-10 h-10" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight mb-3">
            Copilot Agent
          </h1>
          <p className="text-lg text-muted-foreground max-w-md mx-auto text-balance">
            An autonomous AI agent powered by GitHub Copilot SDK for executing
            complex workflows.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-12">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="p-4 rounded-xl border border-border bg-card/50 text-center"
            >
              <div className="flex items-center justify-center w-10 h-10 mx-auto rounded-lg bg-secondary text-muted-foreground mb-3">
                <feature.icon className="w-5 h-5" />
              </div>
              <h3 className="font-medium text-sm mb-1">{feature.title}</h3>
              <p className="text-xs text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>

        {onSelectExample && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-3 text-center">
              Try an example
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  onClick={() => onSelectExample(example)}
                  className="p-3 text-left text-sm rounded-lg border border-border bg-card hover:bg-secondary transition-colors line-clamp-2"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
