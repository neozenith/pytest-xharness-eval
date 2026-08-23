import type { ChartConfig } from "@/components/ui/chart";
import { PerTurnBars } from "@/components/charts/perTurnBars";
import type { AxisMode } from "@/lib/series";
import type { Call, RunResult, Usage } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

/** The four billing tiers in the legacy order, coloured by the fixed series order of the design tokens. */
const CONFIG: ChartConfig = {
  cache_read_tokens: { label: "cache read", color: "var(--xh-series-1)" },
  cache_write_tokens: { label: "cache write", color: "var(--xh-series-2)" },
  input_tokens: { label: "input (uncached)", color: "var(--xh-series-3)" },
  output_tokens: { label: "output", color: "var(--xh-series-4)" },
};
const valueOf = (k: Call, key: string): number => k.usage[key as keyof Usage] ?? 0;

/** The four billing tiers stacked, per turn or at each turn's measuring line (glossary: `TurnTiersChart`). */
export function TurnTiersChart({ result, lines, mode }: Props) {
  return <PerTurnBars id="TurnTiersChart" title="Billing tiers" yLabel="tokens" config={CONFIG} valueOf={valueOf} result={result} lines={lines} mode={mode} />;
}
