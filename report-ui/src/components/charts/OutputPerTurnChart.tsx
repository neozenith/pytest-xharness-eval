import { PerTurnBars } from "@/components/charts/perTurnBars";
import { useChartTheme } from "@/components/charts/plotly";
import { type AxisMode, visibleOutput } from "@/lib/series";
import type { Call, RunResult } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

const valueOf = (k: Call, key: string): number => (key === "thinking" ? k.usage.reasoning_tokens : visibleOutput(k));

/** Thinking and visible output stacked, per turn or at each turn's measuring line (glossary: `OutputPerTurnChart`). */
export function OutputPerTurnChart({ result, lines, mode }: Props) {
  const theme = useChartTheme();
  const series = [
    { key: "thinking", label: "thinking", color: theme.waterfall.thinking ?? theme.accent },
    { key: "output", label: "visible output", color: theme.waterfall.output ?? theme.accent },
  ];
  return (
    <PerTurnBars
      id="OutputPerTurnChart"
      title="Output and thinking"
      yLabel="output_tokens"
      series={series}
      valueOf={valueOf}
      result={result}
      lines={lines}
      mode={mode}
    />
  );
}
