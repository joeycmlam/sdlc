import { AppShell } from "@/components/app-shell";
import { SettingsView } from "@/components/settings-view";

export const metadata = {
  title: "Settings | Copilot Agent",
};

export default function SettingsPage() {
  return (
    <AppShell active="settings">
      <SettingsView />
    </AppShell>
  );
}
