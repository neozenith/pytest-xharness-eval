import type { ChartConfig } from "@/components/ui/chart";
import { PerTurnBars } from "@/components/charts/perTurnBars";
import { type AxisMode, visibleOutput } from "@/lib/series";
import type { Call, RunResult } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

const CONFIG: ChartConfig = {
  thinking: { label: "thinking", color: "var(--xh-waterfall-thinking)" },
  output: { label: "visible output", color: "var(--xh-waterfall-output)" },
};
const valueOf = (k: Call, key: string): number => (key === "thinking" ? k.usage.reasoning_tokens : visibleOutput(k));

/** Thinking and visible output stacked, per turn or at each turn's measuring line (glossary: `OutputPerTurnChart`). */
export function OutputPerTurnChart({ result, lines, mode }: Props) {
  return (
    <PerTurnBars
      id="OutputPerTurnChart"
      title="Output and thinking"
      yLabel="output_tokens"
      config={CONFIG}
      valueOf={valueOf}
      result={result}
      lines={lines}
      mode={mode}
    />
  );
}
