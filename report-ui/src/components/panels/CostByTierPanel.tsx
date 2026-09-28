import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { El } from "@/components/El";
import { NONE, fmt, usd } from "@/lib/format";
import { effectiveInterval, isLegacyRates, ratesPerMtok } from "@/lib/rates";
import type { RatesApplied as RatesAppliedRecord, RunResult } from "@/lib/types";
import { KvTable, type KvRow } from "./shared";
import { rate } from "./helpers";

interface ModelUsage {
  costUSD?: number;
  inputTokens?: number;
  outputTokens?: number;
  cacheReadInputTokens?: number;
  cacheCreationInputTokens?: number;
}

/** RatesApplied: the per-tier rates the estimate used, the interval they held, and where they came from (ADR 0021, ADR 0050). */
export function RatesApplied({ rates }: { rates: RatesAppliedRecord | null | undefined }) {
  const ra = rates ?? {};
  const mtok = ratesPerMtok(ra);
  const rows: KvRow[] = Object.keys(ra).length
    ? [
        ["price row", <code key="m">{ra.model}</code>],
        ["harness", ra.harness],
        ["source file", <code key="s">{ra.source}</code>],
        ["in effect", effectiveInterval(ra) ?? NONE],
        ["unit", isLegacyRates(ra) ? "usd_per_token (before ADR 0050; shown per MTok)" : ra.unit],
        ["applied at", ra.applied_at],
        ["input", rate(mtok.input)],
        ["output", rate(mtok.output)],
        ["cache_read", rate(mtok.cache_read)],
        ["cache_write (5m)", rate(mtok.cache_write)],
        ["cache_write_1h", rate(mtok.cache_write_1h)],
      ]
    : [["no rates_applied", "this result predates ADR 0021; replay the captured directory"]];
  return (
    <div data-el="RatesApplied">
      <h3 className="muted" style={{ margin: "1rem 0 0.25rem", fontSize: "0.8rem", fontWeight: 500 }}>
        rates applied (USD per million tokens)
        <El name="RatesApplied" />
      </h3>
      <KvTable id="RatesApplied" rows={rows} label="rates applied" />
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
        <span className="muted">
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
        <KvTable id="CostByTierPanel" rows={rows} label="cost by tier" />
        <RatesApplied rates={result.rates_applied} />
      </CardContent>
    </Card>
  );
}
