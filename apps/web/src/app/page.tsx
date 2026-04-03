import DashboardApp from "@/components/dashboard-app";
import { loadBootstrapData } from "@/lib/codex-runtime";

export default async function Home() {
  const bootstrap = await loadBootstrapData();

  return <DashboardApp bootstrap={bootstrap} />;
}
