import path from "node:path";

import { getDefaultBenchmarkCase } from "@reasonforge/core";
import { AppServerClient, loadCodexAuth, startLocalAppServer } from "@reasonforge/codex";

import type { BootstrapData } from "./types";

const APP_SERVER_URL = "ws://127.0.0.1:8791";

type RuntimeShape = {
  reasonforgeAppServerClient?: Promise<AppServerClient>;
};

const globalRuntime = globalThis as typeof globalThis & RuntimeShape;

export function getProjectRoot() {
  return (
    process.env.REASONFORGE_PROJECT_ROOT ??
    path.resolve(process.cwd(), "..", "..")
  );
}

async function getAppServerClient() {
  if (!globalRuntime.reasonforgeAppServerClient) {
    globalRuntime.reasonforgeAppServerClient = (async () => {
      try {
        const existing = new AppServerClient(APP_SERVER_URL);
        await existing.initialize();
        return existing;
      } catch {
        const handle = await startLocalAppServer(APP_SERVER_URL);
        return handle.client;
      }
    })();
  }

  return globalRuntime.reasonforgeAppServerClient;
}

export async function loadBootstrapData(): Promise<BootstrapData> {
  const benchmark = getDefaultBenchmarkCase();

  try {
    await loadCodexAuth();
    const client = await getAppServerClient();
    const models = await client.listModels();

    return {
      benchmark,
      prefillPrompt: benchmark.prompt,
      models: models.map((model) => ({
        id: model.id,
        displayName: model.displayName,
        isDefault: model.isDefault
      })),
      authReady: true,
      authMessage: null
    };
  } catch (error) {
    return {
      benchmark,
      prefillPrompt: benchmark.prompt,
      models: [],
      authReady: false,
      authMessage:
        error instanceof Error
          ? `${error.message}. Run codex login on this machine, then refresh.`
          : "Codex auth is unavailable. Run codex login on this machine, then refresh."
    };
  }
}
