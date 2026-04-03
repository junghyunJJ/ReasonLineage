import { z } from "zod";

import { submitHumanReview } from "@/lib/orchestrator";

export const runtime = "nodejs";

const reviewSchema = z.object({
  decision: z.enum(["approve", "reject", "rerun"]),
  notes: z.string().optional()
});

export async function POST(
  request: Request,
  context: RouteContext<"/api/runs/[runId]/review">
) {
  const { runId } = await context.params;
  const review = reviewSchema.parse(await request.json());

  await submitHumanReview(runId, {
    ...review,
    createdAt: new Date().toISOString()
  });

  return Response.json({ ok: true });
}
