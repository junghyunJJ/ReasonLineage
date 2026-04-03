import { loadBootstrapData } from "@/lib/codex-runtime";

export const runtime = "nodejs";

export async function GET() {
  const data = await loadBootstrapData();
  return Response.json(data);
}
