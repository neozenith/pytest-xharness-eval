import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { El } from "@/components/El";
import { fmt, usd } from "@/lib/format";
import type { RunResult } from "@/lib/types";
import { KvTable, type KvRow } from "./shared";
import { rate } from "./helpers";

interface ModelUsage {
  costUSD?: number;
  inputTokens?: number;
  outputTokens?: number;
  cacheReadInputTokens?: number;
  cacheCreationInputTokens?: number;
}

interface Rates {
  model?: string;
  source?: string;
  applied_at?: string;
  input?: number;
  output?: number;
  cache_read?: number;
  cache_write?: number;
  cache_write_1h?: number;
}

/** RatesApplied: the per-tier USD-per-token rates the estimate used, and where they came from (ADR 0021). */
export function RatesApplied({ rates }: { rates: Rates | null | undefined }) {
  const ra = rates ?? {};
  const rows: KvRow[] = Object.keys(ra).length
    ? [
        ["price row", <code key="m">{ra.model}</code>],
        ["source file", <code key="s">{ra.source}</code>],
        ["applied at", ra.applied_at],
        ["input", rate(ra.input)],
        ["output", rate(ra.output)],
        ["cache_read", rate(ra.cache_read)],
        ["cache_write (5m)", rate(ra.cache_write)],
        ["cache_write_1h", rate(ra.cache_write_1h)],
      ]
    : [["no rates_applied", "this result predates ADR 0021; replay the captured directory"]];
  return (
    <div data-el="RatesApplied">
      <h3 className="text-muted-foreground mt-4 mb-1 text-[0.8rem]">
        rates applied (USD per token)
        <El name="RatesApplied" />
      </h3>
      <KvTable id="RatesApplied" rows={rows} />
    </div>
  );
}

/** Cost by tier: `cost_by_tier` rows summing to `estimated_cost_usd`, the harness's own per-model estimate, and the rates applied. */
export function CostByTierPanel({ result }: { result: RunResult }) {
  const tiers = (result.cost_by_tier ?? {}) as Record<string, number>;
  const rows: KvRow[] = Object.keys(tiers).length
    ? [...Object.entries(tiers).map(([k, v]): KvRow => [k, usd(v)]), ["estimated_cost_usd", <b key="e">{usd(result.estimated_cost_usd)}</b>]]
    : [["no cost_by_tier", "this result predates ADR 0019; replay the captured directory"]];
  for (const [model, m] of Object.entries((result.reported_model_usage ?? {}) as Record<string, ModelUsage>)) {
    rows.push([
      `harness estimate · ${model}`,
      <span key={model}>
        {usd(m.costUSD)}{" "}
        <span className="text-muted-foreground">
          ({fmt(m.inputTokens)} in · {fmt(m.outputTokens)} out · {fmt(m.cacheReadInputTokens)} read · {fmt(m.cacheCreationInputTokens)} write)
        </span>
      </span>,
    ]);
  }
  if (result.harness_reported_cost_usd != null) rows.push(["harness_reported_cost_usd", <b key="h">{usd(result.harness_reported_cost_usd)}</b>]);
  return (
    <Card data-el="CostByTierPanel">
      <CardHeader>
        <CardTitle>
          Cost by tier and rates applied
          <El name="CostByTierPanel" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <KvTable id="CostByTierPanel" rows={rows} />
        <RatesApplied rates={result.rates_applied as Rates} />
      </CardContent>
    </Card>
  );
}
