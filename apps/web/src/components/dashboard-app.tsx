"use client";

import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import clsx from "clsx";

import type {
  BootstrapData,
  CandidateCard,
  ModeSnapshot,
  PublicRunEvent,
  RunMode,
  RunRecord
} from "@/lib/types";
import {
  formatDimensionName,
  getGenerationPanelNote,
  getLatestEventSequence,
  getLatestScoredGeneration,
  getSortedEvents,
  summarizeEventPayload
} from "@/lib/dashboard-presenters";

type LiveRun = RunRecord & {
  events: PublicRunEvent[];
};

function withEvents(run: RunRecord, events: PublicRunEvent[]): LiveRun {
  return {
    ...run,
    events
  };
}

function applyEvent(run: LiveRun, event: PublicRunEvent): LiveRun {
  if (run.events.some((existing) => existing.sequence === event.sequence)) {
    return run;
  }

  const next = {
    ...run,
    events: [...run.events, event]
  };

  switch (event.type) {
    case "comparison.started":
      return { ...next, status: "running" };
    case "mode.started": {
      const mode = event.payload.mode as RunMode;
      return {
        ...next,
        results: {
          ...next.results,
          [mode]: {
            ...next.results[mode],
            status: "running"
          }
        }
      };
    }
    case "mode.completed": {
      const mode = event.payload.mode as RunMode;
      return {
        ...next,
        results: {
          ...next.results,
          [mode]: {
            ...next.results[mode],
            status: "completed",
            finalAnswer: String(event.payload.finalAnswer ?? ""),
            finalFitness:
              typeof event.payload.finalFitness === "number"
                ? event.payload.finalFitness
                : next.results[mode].finalFitness,
            steps: Array.isArray(event.payload.steps)
              ? (event.payload.steps as string[])
              : next.results[mode].steps,
            trace: Array.isArray(event.payload.trace)
              ? (event.payload.trace as Array<{ label: string; text: string }>)
              : next.results[mode].trace
          }
        }
      };
    }
    case "reasonforge.candidateScored": {
      const payload = event.payload as CandidateCard & {
        generation: number;
        bestFitness: number;
        averageFitness: number;
      };
      const updatedTrend = [
        ...next.trend.filter((point) => point.generation !== payload.generation),
        {
          generation: payload.generation,
          bestFitness: payload.bestFitness,
          averageFitness: payload.averageFitness
        }
      ].sort((left, right) => left.generation - right.generation);

      return {
        ...next,
        candidates: {
          ...next.candidates,
          [payload.id]: {
            ...payload
          }
        },
        trend: updatedTrend
      };
    }
    case "reasonforge.selection": {
      const survivors = new Set((event.payload.survivorIds as string[]) ?? []);
      const candidates = Object.fromEntries(
        Object.entries(next.candidates).map(([id, candidate]) => [
          id,
          {
            ...candidate,
            selected: survivors.has(id)
          }
        ])
      );
      return {
        ...next,
        candidates
      };
    }
    case "human.review.required":
      return {
        ...next,
        status: "human_review_required",
        results: {
          ...next.results,
          reasonforge: {
            ...next.results.reasonforge,
            status: "completed",
            finalAnswer: String(event.payload.finalAnswer ?? ""),
            finalFitness:
              typeof event.payload.finalFitness === "number"
                ? event.payload.finalFitness
                : next.results.reasonforge.finalFitness
          }
        }
      };
    case "human.review.recorded":
      return {
        ...next,
        humanReview: {
          decision: event.payload.decision as "approve" | "reject" | "rerun",
          notes: typeof event.payload.notes === "string" ? event.payload.notes : undefined,
          createdAt: event.createdAt
        }
      };
    case "comparison.completed":
      return {
        ...next,
        status:
          (event.payload.status as LiveRun["status"] | undefined) ?? "completed"
      };
    case "comparison.failed":
      return {
        ...next,
        status: "failed",
        results: {
          ...next.results,
          reasonforge: {
            ...next.results.reasonforge,
            status: "failed",
            error: String(event.payload.message ?? "Unknown failure")
          }
        }
      };
    default:
      return next;
  }
}

function formatFitness(value?: number) {
  if (typeof value !== "number") {
    return "Pending";
  }

  return value.toFixed(2);
}

function ModeCard({
  title,
  status,
  finalAnswer,
  finalFitness,
  steps,
  trace,
  error
}: ModeSnapshot) {
  const hasDetails = steps.length > 0 || trace.length > 0;

  return (
    <section className="mode-card">
      <div className="mode-card__header">
        <div>
          <p className="eyebrow">{title}</p>
          <h2>{status === "pending" ? "Ready" : status.replace(/-/g, " ")}</h2>
        </div>
        <span className={clsx("status-pill", `status-pill--${status}`)}>{status}</span>
      </div>
      <div className="mode-card__hero">
        <p className={clsx("mode-card__answer", !finalAnswer && "mode-card__answer--empty")}>
          {finalAnswer ?? "No answer yet."}
        </p>
        <div className="mode-card__meta">
          <p className="mode-card__fitness">
            Fitness <strong>{formatFitness(finalFitness)}</strong>
          </p>
          {error ? <p className="mode-card__error">{error}</p> : null}
        </div>
      </div>
      {hasDetails ? (
        <details className="mode-card__details">
          <summary>Trace and steps</summary>
          {steps.length > 0 ? (
            <ol className="step-list">
              {steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          ) : null}
          <div className="trace-list trace-list--compact">
            {trace.length ? (
              trace.map((entry) => (
                <article key={`${entry.label}-${entry.text}`} className="trace-item">
                  <p className="trace-item__label">{entry.label}</p>
                  <p>{entry.text}</p>
                </article>
              ))
            ) : (
              <p className="empty-state">The mode trace will appear here after execution.</p>
            )}
          </div>
        </details>
      ) : null}
    </section>
  );
}

export default function DashboardApp({ bootstrap }: { bootstrap: BootstrapData }) {
  const [prompt, setPrompt] = useState(bootstrap.prefillPrompt);
  const [selectedModel, setSelectedModel] = useState(
    bootstrap.models.find((model) => model.isDefault)?.id ?? bootstrap.models[0]?.id ?? ""
  );
  const [activeRun, setActiveRun] = useState<LiveRun | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(bootstrap.authMessage);
  const eventSourceRef = useRef<EventSource | null>(null);
  const eventLogRef = useRef<HTMLDivElement | null>(null);
  const eventLogStickToBottomRef = useRef(true);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const groupedCandidates = useMemo(() => {
    const groups = new Map<number, CandidateCard[]>();

    Object.values(activeRun?.candidates ?? {})
      .sort((left, right) => left.generation - right.generation || right.fitness - left.fitness)
      .forEach((candidate) => {
        const current = groups.get(candidate.generation) ?? [];
        groups.set(candidate.generation, [...current, candidate]);
      });

    return Array.from(groups.entries()).sort((left, right) => left[0] - right[0]);
  }, [activeRun]);

  const sortedEvents = useMemo(
    () => getSortedEvents(activeRun?.events ?? []),
    [activeRun?.events]
  );

  const latestScoredGeneration = useMemo(
    () => getLatestScoredGeneration(activeRun?.candidates ?? {}),
    [activeRun?.candidates]
  );

  const generationPanelNote = useMemo(
    () => getGenerationPanelNote(activeRun?.events ?? [], activeRun?.candidates ?? {}),
    [activeRun?.events, activeRun?.candidates]
  );

  const latestEventSequence = useMemo(
    () => getLatestEventSequence(activeRun?.events ?? []),
    [activeRun?.events]
  );

  useEffect(() => {
    eventLogStickToBottomRef.current = true;
  }, [activeRun?.id]);

  useEffect(() => {
    const node = eventLogRef.current;

    if (!node || !sortedEvents.length || !eventLogStickToBottomRef.current) {
      return;
    }

    node.scrollTop = node.scrollHeight;
  }, [sortedEvents]);

  function handleEventLogScroll() {
    const node = eventLogRef.current;

    if (!node) {
      return;
    }

    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    eventLogStickToBottomRef.current = distanceFromBottom < 48;
  }

  async function hydrateRun(runId: string) {
    const response = await fetch(`/api/runs/${runId}`);
    const details = (await response.json()) as {
      run: RunRecord;
      events: PublicRunEvent[];
    };
    setActiveRun(withEvents(details.run, details.events));

    eventSourceRef.current?.close();
    const source = new EventSource(`/api/runs/${runId}/stream`);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as PublicRunEvent;
      startTransition(() => {
        setActiveRun((current) => (current ? applyEvent(current, event) : current));
      });

      if (
        event.type === "comparison.failed" ||
        (event.type === "comparison.completed" && event.payload.status === "completed")
      ) {
        source.close();
      }
    };
    source.onerror = () => {
      source.close();
    };
    eventSourceRef.current = source;
  }

  async function handleRun() {
    if (!bootstrap.authReady) {
      setError(bootstrap.authMessage);
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          prompt,
          model: selectedModel
        })
      });
      const payload = (await response.json()) as { runId: string };
      await hydrateRun(payload.runId);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Run failed to start");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReview(decision: "approve" | "reject" | "rerun") {
    if (!activeRun) {
      return;
    }

    await fetch(`/api/runs/${activeRun.id}/review`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ decision })
    });
  }

  return (
    <div className="dashboard-shell">
      <div className="top-grid">
        <header className="hero">
          <div className="hero__copy">
            <p className="eyebrow">ReasonForge</p>
            <h1>Live benchmark dashboard for evolutionary reasoning.</h1>
            <p className="hero__lede">
              Compare single-pass, sequential, and ReasonForge runs while the event stream updates in
              place.
            </p>
          </div>
          <div className="hero__badge">
            <span>Localhost only</span>
            <strong>Codex auth reuse</strong>
          </div>
        </header>

        <section className="control-panel">
          <div className="panel__header control-panel__header">
            <div>
              <p className="eyebrow">Run setup</p>
              <h2>Launch a comparison</h2>
            </div>
            <span className="metric-chip">{bootstrap.authReady ? "Ready" : "Auth required"}</span>
          </div>
          <div className="field">
            <label htmlFor="prompt">Benchmark prompt</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={3}
            />
          </div>
          <div className="control-panel__row">
            <div className="field field--compact">
              <label htmlFor="model">Model</label>
              <select
                id="model"
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value)}
                disabled={!bootstrap.models.length}
              >
                {bootstrap.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.displayName}
                  </option>
                ))}
              </select>
            </div>
            <button type="button" className="run-button" onClick={handleRun} disabled={submitting || !selectedModel}>
              {submitting ? "Launching..." : "Run Comparison"}
            </button>
          </div>
          {error ? <p className="error-banner">{error}</p> : null}
        </section>
      </div>

      <section className="mode-grid">
        <ModeCard {...(activeRun?.results["simple-pass"] ?? {
          title: "Simple Pass",
          mode: "simple-pass",
          status: "pending",
          finalAnswer: undefined,
          finalFitness: undefined,
          steps: [],
          trace: []
        })} />
        <ModeCard {...(activeRun?.results["sequential-thinking"] ?? {
          title: "Sequential Thinking",
          mode: "sequential-thinking",
          status: "pending",
          finalAnswer: undefined,
          finalFitness: undefined,
          steps: [],
          trace: []
        })} />
        <ModeCard {...(activeRun?.results.reasonforge ?? {
          title: "ReasonForge",
          mode: "reasonforge",
          status: "pending",
          finalAnswer: undefined,
          finalFitness: undefined,
          steps: [],
          trace: []
        })} />
      </section>

      <section className="analysis-grid">
        <section className="panel panel--lineage">
          <div className="panel__header">
            <div>
              <p className="eyebrow">ReasonForge lineage</p>
              <h2>Scored candidates by generation</h2>
            </div>
            <span className="metric-chip">
              {latestScoredGeneration === null ? "Waiting" : `Scored Gen ${latestScoredGeneration}`}
            </span>
          </div>
          <p className="panel-note">{generationPanelNote}</p>
          {groupedCandidates.length ? (
            <div className="generation-grid">
              {groupedCandidates.map(([generation, candidates]) => (
                <div key={generation} className="generation-column">
                  <p className="generation-column__label">Gen {generation}</p>
                  {candidates.map((candidate) => (
                    <article
                      key={candidate.id}
                      className={clsx("candidate-card", candidate.selected && "candidate-card--selected")}
                    >
                      <div className="candidate-card__meta">
                        <span>{candidate.source}</span>
                        <strong>{candidate.fitness.toFixed(2)}</strong>
                      </div>
                      {candidate.scores && Object.keys(candidate.scores).length > 0 && (
                        <div className="candidate-card__scores">
                          {Object.entries(candidate.scores).map(([key, value]) => (
                            <span key={key} className="candidate-card__score-item">
                              {formatDimensionName(key)}: {(value as number).toFixed(2)}
                            </span>
                          ))}
                        </div>
                      )}
                      <p>{candidate.answer}</p>
                      {candidate.parents.length ? (
                        <p className="candidate-card__parents">
                          {candidate.parents.join(" + ")}
                        </p>
                      ) : (
                        <p className="candidate-card__parents">seed</p>
                      )}
                    </article>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-state">
              Lineage cards will populate here as ReasonForge scores, mutates, and selects candidates.
            </p>
          )}
        </section>

        <section className="panel panel--log panel--log-expanded">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Run console</p>
              <h2>Live event log</h2>
            </div>
            <span className="metric-chip">
              {latestEventSequence ? `Latest #${latestEventSequence}` : "Idle"}
            </span>
          </div>
          {sortedEvents.length ? (
            <div className="event-log">
              <div
                ref={eventLogRef}
                className="event-log__scroll event-log__scroll--expanded"
                onScroll={handleEventLogScroll}
              >
                <table className="event-log__table">
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Event</th>
                      <th scope="col">Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedEvents.map((event) => {
                      const payloadJson = JSON.stringify(event.payload);
                      const summary = summarizeEventPayload(event.payload);

                      return (
                        <tr key={`${event.sequence}-${event.type}`}>
                          <td className="event-log__seq">#{event.sequence}</td>
                          <td className="event-log__type" title={event.type}>
                            <code>{event.type}</code>
                          </td>
                          <td title={payloadJson}>
                            <code className="event-log__summary">{summary}</code>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="empty-state event-log__empty">
              The live stream will be mirrored here once a run begins.
            </p>
          )}
        </section>
      </section>

      {activeRun?.status === "human_review_required" ? (
        <section className="review-panel">
          <div>
            <p className="eyebrow">Human review required</p>
            <h2>Threshold not met within five generations.</h2>
          </div>
          <div className="review-panel__actions">
            <button type="button" onClick={() => handleReview("approve")}>
              Approve best chain
            </button>
            <button type="button" onClick={() => handleReview("reject")}>
              Reject run
            </button>
            <button type="button" onClick={() => handleReview("rerun")}>
              Rerun evolution
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
