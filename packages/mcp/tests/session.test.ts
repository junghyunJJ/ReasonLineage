import { describe, it, expect, beforeEach } from "vitest";
import {
  createSession,
  getSession,
  updateSession,
  deleteSession,
  clearAllSessions,
  getSessionCount,
  touchSession
} from "../src/session.js";
import type { SessionConfig } from "../src/session.js";
import { createCandidate, defaultJudgeWeights } from "@reasonforge/core";

const defaultConfig: SessionConfig = {
  threshold: 0.85,
  populationLimit: 5,
  generationLimit: 5,
  weights: defaultJudgeWeights
};

describe("Session management", () => {
  beforeEach(() => {
    clearAllSessions();
  });

  it("creates a session with seed candidates", () => {
    const candidates = [
      createCandidate("a", "Answer A"),
      createCandidate("b", "Answer B")
    ];
    const session = createSession(defaultConfig, candidates);
    expect(session.id).toBeTruthy();
    expect(session.pendingCandidates).toHaveLength(2);
    expect(session.population).toHaveLength(0);
    expect(session.generation).toBe(0);
    expect(session.status).toBe("scoring");
  });

  it("returns null for unknown session", () => {
    expect(getSession("nonexistent")).toBeNull();
  });

  it("updates session atomically", () => {
    const session = createSession(defaultConfig, [createCandidate("a", "A")]);
    const updated = updateSession(session.id, (s) => ({
      ...s,
      generation: 1
    }));
    expect(updated?.generation).toBe(1);
    expect(getSession(session.id)?.generation).toBe(1);
  });

  it("deletes a session", () => {
    const session = createSession(defaultConfig, [createCandidate("a", "A")]);
    expect(deleteSession(session.id)).toBe(true);
    expect(getSession(session.id)).toBeNull();
  });

  it("manages concurrent sessions independently", () => {
    const s1 = createSession(defaultConfig, [createCandidate("a1", "A1")]);
    const s2 = createSession(defaultConfig, [createCandidate("b1", "B1")]);
    expect(getSessionCount()).toBe(2);

    updateSession(s1.id, (s) => ({ ...s, generation: 5 }));
    expect(getSession(s1.id)?.generation).toBe(5);
    expect(getSession(s2.id)?.generation).toBe(0);
  });

  it("getSession does not mutate lastAccessedAt", () => {
    const session = createSession(defaultConfig, [createCandidate("a", "A")]);
    const initialAccess = session.lastAccessedAt;

    // Wait a tiny bit to ensure time difference
    const before = Date.now();
    while (Date.now() === before) {} // spin until time advances

    getSession(session.id);
    const afterGet = getSession(session.id);
    expect(afterGet?.lastAccessedAt).toBe(initialAccess);
  });

  it("touchSession updates lastAccessedAt", () => {
    const session = createSession(defaultConfig, [createCandidate("a", "A")]);
    const initialAccess = session.lastAccessedAt;

    const before = Date.now();
    while (Date.now() === before) {}

    touchSession(session.id);
    const updated = getSession(session.id);
    expect(updated?.lastAccessedAt).toBeGreaterThan(initialAccess);
  });
});
