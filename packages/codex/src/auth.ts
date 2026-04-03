import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";

export type CodexLocalAuth = {
  authMode: string;
  apiKey: string | null;
  hasTokens: boolean;
  authFile: string;
};

type RawAuthShape = {
  OPENAI_API_KEY?: string;
  auth_mode?: string;
  tokens?: unknown;
};

export function getDefaultAuthFile() {
  return path.join(homedir(), ".codex", "auth.json");
}

export async function loadCodexAuth(authFile = getDefaultAuthFile()): Promise<CodexLocalAuth> {
  const raw = JSON.parse(await readFile(authFile, "utf8")) as RawAuthShape;

  if (!raw.OPENAI_API_KEY && !raw.tokens) {
    throw new Error(`No reusable Codex auth found in ${authFile}`);
  }

  return {
    authMode: raw.auth_mode ?? "unknown",
    apiKey: raw.OPENAI_API_KEY ?? null,
    hasTokens: Boolean(raw.tokens),
    authFile
  };
}
