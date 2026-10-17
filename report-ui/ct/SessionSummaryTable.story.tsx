/**
 * `SessionSummaryTable` mounted the way `SweepOverview` mounts it: with the Important Metrics its
 * cells imply (ADR 0071). A component test states sessions; `metricsFor` stands in for the
 * aggregates `emit/samples.py` would have written into `index.json` for them.
 */
import { SessionSummaryTable } from "../src/components/SessionSummaryTable";
import type { Cell } from "../src/lib/types";
import { metricsFor } from "./fixtures";

export function Summary({ cells }: { cells: Cell[] }) {
  return <SessionSummaryTable cells={cells} metrics={metricsFor(cells)} />;
}
