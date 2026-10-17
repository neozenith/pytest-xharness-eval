/**
 * Reading the Important Metrics `index.json` carries (ADR 0071). Pure, like `lib/summary.ts`.
 *
 * The page does none of the arithmetic: `emit/samples.py` reduces every cell's samples by each
 * metric's declared aggregates, and this module only says how one of those numbers is printed.
 * The declaration's `aggregates` list leads with the headline, so a cell that shows one number
 * shows `aggregates[0]` and its title spells out the rest.
 */
import { compact, dec, NONE, pct, secs, usd3 } from "./format";
import type { Aggregates, ImportantMetric } from "./types";

/** Aggregates that are a share of the samples, whatever the metric measures. */
const SHARE_AGGREGATES = new Set(["share", "pass_rate", "ci_low", "ci_high"]);

/** What each aggregate is called in a title: the operation spelled out, never inferred (ADR 0021). */
const AGGREGATE_NAMES: Record<string, string> = {
  median: "median",
  p25: "p25",
  p75: "p75",
  mean: "mean",
  min: "min",
  max: "max",
  share: "share of samples with any",
  pass_rate: "pass rate",
  ci_low: "95% CI low",
  ci_high: "95% CI high",
  n: "n",
};

export const aggregateName = (aggregate: string): string => AGGREGATE_NAMES[aggregate] ?? aggregate;

/** The aggregate a one-number cell shows: the declaration's first. */
export const headline = (metric: ImportantMetric): string => metric.aggregates[0] ?? "n";

/** The headline's value for one cell, or null when the cell has no samples carrying the metric. */
export const headlineValue = (metric: ImportantMetric, aggregates: Aggregates | undefined): number | null => aggregates?.[headline(metric)] ?? null;

/** One aggregate of one metric, printed in the metric's unit; a missing value is the shared muted glyph. */
export function formatAggregate(metric: ImportantMetric, aggregate: string, value: number | null | undefined): string {
  if (value == null) return NONE;
  if (aggregate === "n") return String(value);
  if (SHARE_AGGREGATES.has(aggregate)) return pct(100 * value);
  switch (metric.unit) {
    case "usd":
      return usd3(value);
    case "tokens":
      return compact(Math.round(value));
    case "percent":
      return pct(value);
    case "share":
      return pct(100 * value);
    case "ms":
      return secs(value);
    case "tokens_per_sec":
      return dec(value, 1);
    case "count":
      return Number.isInteger(value) ? String(value) : dec(value, 1);
  }
}

/** The name a column answers to: the headline's operation and the record field it reduces (ADR 0021). */
export const metricName = (metric: ImportantMetric): string => `${aggregateName(headline(metric))} ${metric.field}${metric.per ? ` / ${metric.per}` : ""}`;

/** Every aggregate of one cell, spelled out: what a cell's title says beside its one printed number. */
export const aggregatesTitle = (metric: ImportantMetric, aggregates: Aggregates | undefined): string =>
  metric.aggregates.map((a) => `${aggregateName(a)} ${formatAggregate(metric, a, aggregates?.[a])}`).join(" · ");
