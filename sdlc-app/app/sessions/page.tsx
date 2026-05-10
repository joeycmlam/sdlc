import { AppShell } from "@/components/app-shell";
import { SessionsList } from "@/components/sessions-list";

export const metadata = {
  title: "Sessions | Copilot Agent",
};

export default function SessionsPage() {
  return (
    <AppShell active="sessions">
      <SessionsList />
    </AppShell>
  );
}
