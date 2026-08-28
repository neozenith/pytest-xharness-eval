import { PerTurnBars } from "@/components/charts/perTurnBars";
import { seriesColor, useChartTheme } from "@/components/charts/plotly";
import type { AxisMode } from "@/lib/series";
import type { Call, RunResult, Usage } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

const valueOf = (k: Call, key: string): number => k.usage[key as keyof Usage] ?? 0;

/** The four billing tiers stacked, per turn or at each turn's measuring line (glossary: `TurnTiersChart`). */
export function TurnTiersChart({ result, lines, mode }: Props) {
  const theme = useChartTheme();
  // The legacy tier order, coloured by the fixed series order of the design tokens.
  const series = [
    { key: "cache_read_tokens", label: "cache read", color: seriesColor(theme, 0) },
    { key: "cache_write_tokens", label: "cache write", color: seriesColor(theme, 1) },
    { key: "input_tokens", label: "input (uncached)", color: seriesColor(theme, 2) },
    { key: "output_tokens", label: "output", color: seriesColor(theme, 3) },
  ];
  return <PerTurnBars id="TurnTiersChart" title="Billing tiers" yLabel="tokens" series={series} valueOf={valueOf} result={result} lines={lines} mode={mode} />;
}
