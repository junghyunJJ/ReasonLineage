import { z } from "zod";

import { startComparisonRun } from "@/lib/orchestrator";

export const runtime = "nodejs";

const createRunSchema = z.object({
  prompt: z.string().min(1),
  model: z.string().min(1)
});

export async function POST(request: Request) {
  const body = createRunSchema.parse(await request.json());
  const run = startComparisonRun(body.prompt, body.model);

  return Response.json({
    runId: run.id,
    status: run.status
  });
}
