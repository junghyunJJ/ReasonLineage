import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { loadCodexAuth } from "../src/index";

const cleanupPaths: string[] = [];

describe("loadCodexAuth", () => {
  afterEach(async () => {
    for (const target of cleanupPaths.splice(0)) {
      await import("node:fs/promises").then(({ rm }) =>
        rm(target, { recursive: true, force: true })
      );
    }
  });

  it("reads the local Codex auth file and returns the API key", async () => {
    const sandbox = await mkdtemp(path.join(tmpdir(), "reasonforge-auth-"));
    cleanupPaths.push(sandbox);
    const authFile = path.join(sandbox, "auth.json");

    await writeFile(
      authFile,
      JSON.stringify({
        auth_mode: "chatgpt",
        OPENAI_API_KEY: "sk-test-codex",
        tokens: { access_token: "token" }
      })
    );

    const auth = await loadCodexAuth(authFile);

    expect(auth.authMode).toBe("chatgpt");
    expect(auth.apiKey).toBe("sk-test-codex");
    expect(auth.hasTokens).toBe(true);
  });

  it("accepts token-backed ChatGPT auth even when no API key is embedded", async () => {
    const sandbox = await mkdtemp(path.join(tmpdir(), "reasonforge-auth-"));
    cleanupPaths.push(sandbox);
    const authFile = path.join(sandbox, "auth.json");

    await writeFile(
      authFile,
      JSON.stringify({
        auth_mode: "chatgpt",
        OPENAI_API_KEY: null,
        tokens: { access_token: "token" }
      })
    );

    const auth = await loadCodexAuth(authFile);

    expect(auth.authMode).toBe("chatgpt");
    expect(auth.apiKey).toBeNull();
    expect(auth.hasTokens).toBe(true);
  });
});
