import { getRunDetails } from "@/lib/orchestrator";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: RouteContext<"/api/runs/[runId]">
) {
  const { runId } = await context.params;
  const details = getRunDetails(runId);

  if (!details) {
    return Response.json({ message: "Run not found" }, { status: 404 });
  }

  return Response.json(details);
}
