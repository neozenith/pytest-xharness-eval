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
  a == null || b == null ? "" : a === b ? <span className="good">=</span> : <Notice>Δ {fmt(b - a)}</Notice>;

/** The ledger built from the session log against the harness's own aggregate, row by row, with the difference. */
export function ReconciliationPanel({ result }: { result: RunResult }) {
  // The harness aggregate covers only the primary thread (docs/token-accounting.md §5),
  // so the tier rows compare the primary share of `usage` (the whole bill minus the
  // subagents' folded tiers); the subagents' bill is its own row.
  const subs = result.subagents ?? [];
  const subTier = (
    key: "input_tokens" | "output_tokens" | "cache_read_tokens" | "cache_write_tokens" | "cache_write_1h_tokens" | "cache_write_5m_tokens" | "reasoning_tokens",
  ) => subs.reduce((sum, s) => sum + s.usage[key], 0);
  const u = {
    input_tokens: result.usage.input_tokens - subTier("input_tokens"),
    output_tokens: result.usage.output_tokens - subTier("output_tokens"),
    cache_read_tokens: result.usage.cache_read_tokens - subTier("cache_read_tokens"),
    cache_write_tokens: result.usage.cache_write_tokens - subTier("cache_write_tokens"),
    cache_write_1h_tokens: result.usage.cache_write_1h_tokens - subTier("cache_write_1h_tokens"),
    cache_write_5m_tokens: result.usage.cache_write_5m_tokens - subTier("cache_write_5m_tokens"),
    reasoning_tokens: result.usage.reasoning_tokens - subTier("reasoning_tokens"),
  };
  const subBilled = subs.reduce(
    (sum, s) =>
      sum + (s.usage.accumulative_billed_tokens ?? s.usage.input_tokens + s.usage.output_tokens + s.usage.cache_read_tokens + s.usage.cache_write_tokens),
    0,
  );
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
    ...(subs.length
      ? ([
          [
            `subagents (${subs.length} spawned thread${subs.length === 1 ? "" : "s"})`,
            fmt(subBilled),
            <span key="s" className="muted">
              not in the harness figure
            </span>,
            "",
          ],
        ] as KvRow[])
      : []),
    ["accumulative_billed_tokens", fmt(result.usage.accumulative_billed_tokens), fmt(ru.total_tokens), ""],
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
          The ledger built from the session log against the harness's own aggregate. The harness figure covers only the primary thread, so spawned subagents
          appear as their own row inside `accumulative_billed_tokens`. On Claude the harness cost includes a ~$0.001 session-title side call that the ledger
          does not price.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <KvTable id="ReconciliationPanel" rows={rows} />
      </CardContent>
    </Card>
  );
}
