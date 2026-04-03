import type { ScoredCandidate } from "@reasonforge/core";

/**
 * Simplified mirror of engine.ts:27-43 shouldTerminate.
 * Omits: useFitnessThreshold toggle (always true here),
 *        custom termination callback (not serializable over MCP).
 */
export function shouldTerminate(
  best: ScoredCandidate,
  threshold: number,
  hasBenchmark: boolean
): boolean {
  if (best.fitness < threshold) {
    return false;
  }
  if (hasBenchmark) {
    return best.benchmarkVerdict.passed;
  }
  return true;
}
