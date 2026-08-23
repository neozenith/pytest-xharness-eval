import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { El } from "@/components/El";
import { fmt, usd } from "@/lib/format";
import type { RunResult } from "@/lib/types";
import { KvTable, type KvRow, Notice } from "./shared";

/** The harness's own aggregate, in its own field names (Claude envelope `usage` or Codex `total_token_usage`). */
interface ReportedUsage {
  input_tokens?: number;
  output_tokens?: number;
  cache_read_input_tokens?: number;
  cached_input_tokens?: number;
  cache_creation_input_tokens?: number;
  reasoning_output_tokens?: number;
  total_tokens?: number;
}

const cmp = (a: number | null | undefined, b: number | null | undefined) =>
  a == null || b == null ? "" : a === b ? <span className="text-good">=</span> : <Notice>Δ {fmt(b - a)}</Notice>;

/** The ledger built from the session log against the harness's own aggregate, row by row, with the difference. */
export function ReconciliationPanel({ result }: { result: RunResult }) {
  const u = result.usage;
  const ru = (result.reported_usage ?? {}) as ReportedUsage;
  const rRead = ru.cache_read_input_tokens ?? ru.cached_input_tokens;
  // Codex's input_tokens includes the cached tokens; Claude's does not (docs/token-accounting.md).
  const rInput = ru.input_tokens == null ? null : "cached_input_tokens" in ru ? ru.input_tokens - (ru.cached_input_tokens ?? 0) : ru.input_tokens;
  const costDelta =
    result.harness_reported_cost_usd != null && result.estimated_cost_usd != null ? (
      <Notice>Δ {usd(result.harness_reported_cost_usd - result.estimated_cost_usd)}</Notice>
    ) : (
      ""
    );
  const rows: KvRow[] = [
    ["", <b key="l">ledger</b>, <b key="h">harness aggregate</b>, ""],
    ["turns (model calls)", fmt(result.turns), fmt(result.reported_turns), cmp(result.turns, result.reported_turns)],
    ["input (uncached)", fmt(u.input_tokens), fmt(rInput), cmp(u.input_tokens, rInput)],
    ["output", fmt(u.output_tokens), fmt(ru.output_tokens), cmp(u.output_tokens, ru.output_tokens)],
    ["cache read", fmt(u.cache_read_tokens), fmt(rRead), cmp(u.cache_read_tokens, rRead)],
    ["cache write", fmt(u.cache_write_tokens), fmt(ru.cache_creation_input_tokens), cmp(u.cache_write_tokens, ru.cache_creation_input_tokens)],
    ["of which 1h / 5m", `${fmt(u.cache_write_1h_tokens)} / ${fmt(u.cache_write_5m_tokens)}`, "", ""],
    ["reasoning (inside output)", fmt(u.reasoning_tokens), fmt(ru.reasoning_output_tokens), ""],
    ["accumulative_billed_tokens", fmt(u.accumulative_billed_tokens), fmt(ru.total_tokens), ""],
    ["baseline_tokens", fmt(result.baseline_tokens), "", ""],
    ["estimated / harness reported cost", usd(result.estimated_cost_usd), usd(result.harness_reported_cost_usd), costDelta],
  ];
  return (
    <Card data-el="ReconciliationPanel">
      <CardHeader>
        <CardTitle>
          Reconciliation
          <El name="ReconciliationPanel" />
        </CardTitle>
        <CardDescription>
          The ledger built from the session log against the harness's own aggregate. On Claude the harness cost includes a ~$0.001 session-title side call that
          the ledger does not price.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <KvTable id="ReconciliationPanel" rows={rows} />
      </CardContent>
    </Card>
  );
}
