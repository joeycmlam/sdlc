import { AppShell } from "@/components/app-shell";
import { IssueCreator } from "@/components/issue-creator";

export const metadata = {
  title: "New Issue | Copilot Agent",
};

export default function NewIssuePage() {
  return (
    <AppShell active="issues">
      <IssueCreator />
    </AppShell>
  );
}
