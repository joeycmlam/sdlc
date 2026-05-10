import { AppShell } from "@/components/app-shell";
import { SessionDetail } from "@/components/session-detail";

export const metadata = {
  title: "Session | Copilot Agent",
};

export default async function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell active="sessions">
      <SessionDetail id={id} />
    </AppShell>
  );
}
