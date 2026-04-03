import { randomUUID } from "node:crypto";
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
  lastAccessedAt: number;
};

const SESSION_TTL_MS = 30 * 60 * 1000; // 30 minutes
const GC_INTERVAL_MS = 60 * 1000; // 60 seconds
const MAX_SESSIONS = 100;

const sessions = new Map<string, SessionState>();

export function createSession(
  config: SessionConfig,
  seedCandidates: Candidate[]
): SessionState {
  if (sessions.size >= MAX_SESSIONS) {
    throw new Error(`Maximum concurrent sessions (${MAX_SESSIONS}) reached. Delete idle sessions first.`);
  }
  const id = randomUUID();
  const now = Date.now();
  const session: SessionState = {
    id,
    config,
    generation: 0,
    population: [],
    pendingCandidates: [...seedCandidates],
    status: "scoring",
    createdAt: now,
    lastAccessedAt: now
  };
  sessions.set(id, session);
  return session;
}

export function getSession(sessionId: string): SessionState | null {
  const session = sessions.get(sessionId) ?? null;
  if (session) {
    session.lastAccessedAt = Date.now();
  }
  return session;
}

export function updateSession(
  sessionId: string,
  updater: (session: SessionState) => SessionState
): SessionState | null {
  const session = sessions.get(sessionId);
  if (!session) return null;
  const updated = updater(session);
  updated.lastAccessedAt = Date.now();
  sessions.set(sessionId, updated);
  return updated;
}

export function deleteSession(sessionId: string): boolean {
  return sessions.delete(sessionId);
}

export function getSessionCount(): number {
  return sessions.size;
}

// Garbage collector for idle sessions
let gcInterval: ReturnType<typeof setInterval> | null = null;

export function startSessionGC(): void {
  if (gcInterval) return;
  gcInterval = setInterval(() => {
    const now = Date.now();
    for (const [id, session] of sessions) {
      if (now - session.lastAccessedAt > SESSION_TTL_MS) {
        sessions.delete(id);
      }
    }
  }, GC_INTERVAL_MS);
  // Don't prevent process exit
  if (gcInterval.unref) {
    gcInterval.unref();
  }
}

export function stopSessionGC(): void {
  if (gcInterval) {
    clearInterval(gcInterval);
    gcInterval = null;
  }
}

// For testing: clear all sessions
export function clearAllSessions(): void {
  sessions.clear();
}
