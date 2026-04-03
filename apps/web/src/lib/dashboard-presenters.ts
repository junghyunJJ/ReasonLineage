import type { CandidateCard, PublicRunEvent } from "./types";

const SUMMARY_PRIORITY = [
  "mode",
  "finalAnswer",
  "finalFitness",
  "candidateId",
  "generation",
  "runId",
  "status",
  "decision",
  "message",
  "type"
] as const;

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((entry) => formatValue(entry)).join(", ");
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }

  return "null";
}

function labelFor(key: string): string {
  switch (key) {
    case "finalAnswer":
      return "answer";
    case "finalFitness":
      return "fitness";
    default:
      return key;
  }
}

export function getSortedEvents(events: PublicRunEvent[]): PublicRunEvent[] {
  return events.slice().sort((left, right) => left.sequence - right.sequence);
}

export function getLatestEventSequence(events: PublicRunEvent[]): number | null {
  const latest = getSortedEvents(events).at(-1);

  return latest?.sequence ?? null;
}

export function getLatestScoredGeneration(
  candidates: Record<string, CandidateCard>
): number | null {
  const generations = Object.values(candidates).map((candidate) => candidate.generation);

  if (!generations.length) {
    return null;
  }

  return Math.max(...generations);
}

export function getGenerationPanelNote(
  events: PublicRunEvent[],
  candidates: Record<string, CandidateCard>
): string {
  const latestScoredGeneration = getLatestScoredGeneration(candidates);

  if (latestScoredGeneration === null) {
    return "Candidates will appear here once ReasonForge starts scoring.";
  }

  const sortedEvents = getSortedEvents(events);
  const latestThresholdEvent = [...sortedEvents]
    .reverse()
    .find((event) => event.type === "reasonforge.thresholdReached");
  const latestSelectionEvent = [...sortedEvents]
    .reverse()
    .find((event) => event.type === "reasonforge.selection");

  const thresholdGeneration = latestThresholdEvent?.payload.generation;
  if (
    typeof thresholdGeneration === "number" &&
    thresholdGeneration > latestScoredGeneration
  ) {
    return `Threshold reached at Gen ${thresholdGeneration} before Gen ${thresholdGeneration} candidates were scored, so this panel currently stops at Gen ${latestScoredGeneration}.`;
  }

  const selectionGeneration = latestSelectionEvent?.payload.generation;
  if (
    typeof selectionGeneration === "number" &&
    selectionGeneration > latestScoredGeneration
  ) {
    return `Selection advanced to Gen ${selectionGeneration}, but only candidates through Gen ${latestScoredGeneration} have been scored so far.`;
  }

  return `Showing scored candidates through Gen ${latestScoredGeneration}.`;
}

export function summarizeEventPayload(payload: Record<string, unknown>): string {
  const orderedKeys = [
    ...SUMMARY_PRIORITY.filter((key) => key in payload),
    ...Object.keys(payload).filter(
      (key) => !SUMMARY_PRIORITY.includes(key as (typeof SUMMARY_PRIORITY)[number])
    )
  ];

  if (!orderedKeys.length) {
    return "No payload";
  }

  return orderedKeys
    .map((key) => `${labelFor(key)}=${formatValue(payload[key])}`)
    .join(" | ");
}

/**
 * Converts camelCase dimension keys to human-readable format.
 * e.g., "logicalConsistency" → "Logical Consistency"
 */
export function formatDimensionName(key: string): string {
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (char) => char.toUpperCase())
    .trim();
}
