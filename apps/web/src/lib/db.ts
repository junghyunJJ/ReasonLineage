import { randomUUID } from "node:crypto";
import path from "node:path";

import Database from "better-sqlite3";

import type { BenchmarkCase } from "@reasonforge/core";

import {
  createInitialRunRecord,
  type HumanReviewDecision,
  type PublicRunEvent,
  type RunRecord
} from "./types";

type DbShape = {
  db?: Database.Database;
};

const globalDb = globalThis as typeof globalThis & DbShape;

function resolveDbPath() {
  return (
    process.env.REASONFORGE_DB_PATH ??
    path.join(process.cwd(), "reasonforge.db")
  );
}

function now() {
  return new Date().toISOString();
}

function getDatabase() {
  if (!globalDb.db) {
    globalDb.db = new Database(resolveDbPath());
    globalDb.db.pragma("journal_mode = WAL");
    globalDb.db.exec(`
      CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        data_json TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
    `);
  }

  return globalDb.db;
}

export function createRun(prompt: string, model: string, benchmark: BenchmarkCase, demoMode?: boolean) {
  const database = getDatabase();
  const createdAt = now();
  const run = createInitialRunRecord({
    id: randomUUID(),
    prompt,
    benchmark,
    model,
    createdAt,
    demoMode
  });

  database
    .prepare("INSERT INTO runs (id, data_json) VALUES (?, ?)")
    .run(run.id, JSON.stringify(run));

  return run;
}

export function saveRun(run: RunRecord) {
  getDatabase()
    .prepare("UPDATE runs SET data_json = ? WHERE id = ?")
    .run(JSON.stringify(run), run.id);

  return run;
}

export function getRun(runId: string) {
  const row = getDatabase()
    .prepare("SELECT data_json FROM runs WHERE id = ?")
    .get(runId) as { data_json: string } | undefined;

  if (!row) {
    return null;
  }

  return JSON.parse(row.data_json) as RunRecord;
}

export function updateRun(
  runId: string,
  updater: (run: RunRecord) => RunRecord
) {
  const current = getRun(runId);
  if (!current) {
    throw new Error(`Run ${runId} was not found`);
  }

  const updated = updater({
    ...current,
    updatedAt: now()
  });

  saveRun(updated);
  return updated;
}

export function listRunEvents(runId: string) {
  const rows = getDatabase()
    .prepare(
      "SELECT sequence, type, payload_json, created_at FROM events WHERE run_id = ? ORDER BY sequence ASC"
    )
    .all(runId) as Array<{
    sequence: number;
    type: string;
    payload_json: string;
    created_at: string;
  }>;

  return rows.map(
    (row) =>
      ({
        sequence: row.sequence,
        type: row.type,
        payload: JSON.parse(row.payload_json) as Record<string, unknown>,
        createdAt: row.created_at
      }) satisfies PublicRunEvent
  );
}

export function appendRunEvent(
  runId: string,
  type: string,
  payload: Record<string, unknown>
) {
  const database = getDatabase();
  const row = database
    .prepare("SELECT COALESCE(MAX(sequence), 0) AS sequence FROM events WHERE run_id = ?")
    .get(runId) as { sequence: number };
  const event = {
    sequence: row.sequence + 1,
    type,
    payload,
    createdAt: now()
  } satisfies PublicRunEvent;

  database
    .prepare(
      "INSERT INTO events (run_id, sequence, type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)"
    )
    .run(runId, event.sequence, event.type, JSON.stringify(payload), event.createdAt);

  return event;
}

export function recordHumanReview(runId: string, review: HumanReviewDecision) {
  return updateRun(runId, (run) => ({
    ...run,
    humanReview: review,
    status: review.decision === "rerun" ? "queued" : "completed"
  }));
}
