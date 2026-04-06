import { randomUUID } from "node:crypto";
import { existsSync, readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type {
  BenchmarkCase,
  Candidate,
  JudgeWeights,
  ScoredCandidate
} from "@reasonforge/core";

export type SessionConfig = {
  threshold: number;
  populationLimit: number;
  generationLimit: number;
  weights: JudgeWeights;
  benchmark?: BenchmarkCase;
};

export type SessionState = {
  id: string;
  config: SessionConfig;
  generation: number;
  population: ScoredCandidate[];
  pendingCandidates: Candidate[];
  status: "scoring" | "ready_to_select" | "mutating" | "completed" | "failed";
  createdAt: number;
};

function sessionPath(sessionId: string): string {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sessionId)) {
    throw new Error(`Invalid session ID format: ${sessionId}`);
  }
  return join(tmpdir(), `reasonforge-${sessionId}.json`);
}

export function createSessionFile(
  config: SessionConfig,
  seedCandidates: Candidate[]
): SessionState {
  const id = randomUUID();
  const session: SessionState = {
    id,
    config,
    generation: 0,
    population: [],
    pendingCandidates: [...seedCandidates],
    status: "scoring",
    createdAt: Date.now()
  };
  writeFileSync(sessionPath(id), JSON.stringify(session), "utf-8");
  return session;
}

export function readSessionFile(sessionId: string): SessionState | null {
  const path = sessionPath(sessionId);
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf-8")) as SessionState;
}

export function writeSessionFile(sessionId: string, state: SessionState): void {
  writeFileSync(sessionPath(sessionId), JSON.stringify(state), "utf-8");
}

export function deleteSessionFile(sessionId: string): boolean {
  const path = sessionPath(sessionId);
  if (!existsSync(path)) return false;
  unlinkSync(path);
  return true;
}
