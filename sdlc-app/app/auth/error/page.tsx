"use client";

import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { AlertTriangle, Bot } from "lucide-react";
import { Suspense } from "react";

const ERROR_MESSAGES: Record<string, string> = {
  AccessDenied: "Your account is not authorised to access this application.",
  Configuration: "There is a problem with the server configuration.",
  Verification: "The sign-in link is no longer valid.",
  Default: "An error occurred during sign-in. Please try again.",
};

function ErrorContent() {
  const params = useSearchParams();
  const error = params.get("error") ?? "Default";
  const message = ERROR_MESSAGES[error] ?? ERROR_MESSAGES.Default;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 px-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-destructive/10 text-destructive">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Sign-in failed</h1>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>

        <button
          onClick={() => signIn("google", { callbackUrl: "/" })}
          className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-lg border border-border bg-card hover:bg-secondary transition-colors text-sm font-medium"
        >
          <Bot className="w-4 h-4" />
          Try again
        </button>
      </div>
    </div>
  );
}

export default function AuthErrorPage() {
  return (
    <Suspense>
      <ErrorContent />
    </Suspense>
  );
}
