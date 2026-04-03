import { listRunEvents } from "@/lib/db";
import { subscribeToRun } from "@/lib/run-broker";

export const runtime = "nodejs";

function formatEvent(payload: unknown) {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

export async function GET(
  request: Request,
  context: RouteContext<"/api/runs/[runId]/stream">
) {
  const { runId } = await context.params;
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      listRunEvents(runId).forEach((event) => {
        controller.enqueue(encoder.encode(formatEvent(event)));
      });

      const unsubscribe = subscribeToRun(runId, (event) => {
        controller.enqueue(encoder.encode(formatEvent(event)));
      });

      const close = () => {
        unsubscribe();
        controller.close();
      };

      request.signal.addEventListener("abort", close, { once: true });
    }
  });

  return new Response(stream, {
    headers: {
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "Content-Type": "text/event-stream"
    }
  });
}
