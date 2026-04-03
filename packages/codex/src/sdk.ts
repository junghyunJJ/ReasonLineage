import {
  Codex,
  type RunResult,
  type ThreadEvent,
  type TurnOptions
} from "@openai/codex-sdk";

import { loadCodexAuth } from "./auth.js";

export type CodexPromptOptions = {
  model: string;
  prompt: string;
  workingDirectory?: string;
  outputSchema?: unknown;
};

export async function createLocalCodex() {
  const auth = await loadCodexAuth();
  const codexPathOverride = process.env.REASONFORGE_CODEX_BIN ?? "codex";

  return auth.apiKey
    ? new Codex({
        apiKey: auth.apiKey,
        codexPathOverride
      })
    : new Codex({ codexPathOverride });
}

function createThreadOptions(model: string, workingDirectory?: string) {
  return {
    approvalPolicy: "never" as const,
    model,
    networkAccessEnabled: false,
    sandboxMode: "read-only" as const,
    skipGitRepoCheck: true,
    workingDirectory
  };
}

export async function runCodexPrompt({
  model,
  prompt,
  workingDirectory,
  outputSchema
}: CodexPromptOptions) {
  const codex = await createLocalCodex();
  const thread = codex.startThread(createThreadOptions(model, workingDirectory));
  const turnOptions: TurnOptions | undefined = outputSchema
    ? { outputSchema }
    : undefined;
  const result = await thread.run(prompt, turnOptions);

  return result;
}

export async function streamCodexPrompt({
  model,
  prompt,
  workingDirectory,
  outputSchema
}: CodexPromptOptions): Promise<AsyncGenerator<ThreadEvent>> {
  const codex = await createLocalCodex();
  const thread = codex.startThread(createThreadOptions(model, workingDirectory));
  const streamed = await thread.runStreamed(prompt, outputSchema ? { outputSchema } : undefined);

  return streamed.events;
}

export function getFinalResponse(turn: RunResult) {
  return turn.finalResponse;
}
