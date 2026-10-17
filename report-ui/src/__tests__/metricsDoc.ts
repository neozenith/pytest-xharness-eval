/**
 * The Important Metrics document a test mounts the summary with (ADR 0071). The declaration is
 * `important-metrics.json`, written from `model/metrics.py` and held to it by
 * `tests/model/test_metrics.py`, so these tests render the columns the plugin actually declares.
 * The aggregates are stated by hand per test: the page does no arithmetic, so neither do they.
 */
import declared from "./important-metrics.json";
import type { Aggregates, Cell, CellSamples, ImportantMetric, ImportantMetricsDoc } from "@/lib/types";

export const IMPORTANT_METRICS = declared as ImportantMetric[];

/** One aggregated cell with `c`'s identity: the twin `emit/samples.py` writes for its sessions. */
export const aggregated = (c: Cell, metrics: Record<string, Aggregates>, samples = 1): CellSamples => ({
  skill: c.skill,
  case: c.case,
  harness: c.harness,
  model: c.model,
  effort: c.effort,
  treatment: c.treatment,
  samples,
  metrics,
});

export const doc = (...cells: CellSamples[]): ImportantMetricsDoc => ({ metrics: IMPORTANT_METRICS, cells });
