import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ChartPanel, TurnMarks } from "@/components/charts/common";
import { axisProps, GRID } from "@/components/charts/chartStyle";
import { fmt, pct, windowLabel } from "@/lib/format";
import { type AxisMode, stepSeries } from "@/lib/series";
import type { RunResult } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

const CONFIG: ChartConfig = { pct: { label: "context % of window", color: "var(--xh-accent)" } };
const pct2 = (v: unknown): string => (typeof v === "number" ? `${v.toFixed(2)}%` : "–");

/** Context window consumption per turn, or as a step per session-log line (glossary: `ContextWindowChart`). */
export function ContextWindowChart({ result, lines, mode }: Props) {
  const window = result.context_window;
  const perLine = mode === "line" && window;
  const step = useMemo(() => (perLine ? stepSeries<number | null>(result, lines, (k) => k.context_pct, null) : null), [perLine, result, lines]);

  if (!window) {
    return (
      <ChartPanel
        id="ContextWindowChart"
        title="Context window consumption"
        note={
          <span id="ContextWindowNote" className="text-warn">
            The harness reported no context window for this model, so consumption cannot be expressed as a percentage; the per-turn prompt sizes are in the turn
            table.
          </span>
        }
      >
        <div className="h-[320px]" />
      </ChartPanel>
    );
  }

  const peakFinal = (
    <>
      Peak <b>{pct(result.context_window_pct)}</b>, final <b>{pct(result.final_context_pct)}</b>.
    </>
  );
  const yLabel = { value: `% of ${windowLabel(window)} window`, angle: -90, position: "insideLeft", fill: "var(--xh-muted)", fontSize: 11 } as const;

  if (step) {
    const data = step.x.map((line, i) => ({ line, pct: step.y[i] ?? null }));
    return (
      <ChartPanel
        id="ContextWindowChart"
        title="Context window consumption"
        note={
          <span id="ContextWindowNote">
            Per session-log line: the prompt size the provider reported for the latest turn measured at or before that line, as a percentage of the{" "}
            <b>{fmt(window)}</b>-token window. Tool results between turn starts are already counted in the next turn's measurement. {peakFinal}
          </span>
        }
      >
        <ChartContainer config={CONFIG} className="aspect-auto h-[320px] w-full">
          <LineChart data={data} margin={{ top: 20, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="line"
              type="number"
              domain={[1, "dataMax"]}
              allowDecimals={false}
              label={{ value: "session-log line", position: "insideBottom", offset: -4, fill: "var(--xh-muted)", fontSize: 11 }}
              {...axisProps}
            />
            <YAxis domain={[0, "auto"]} width={56} label={yLabel} {...axisProps} />
            <ChartTooltip content={<ChartTooltipContent labelFormatter={(v) => `L${v}`} formatter={(value) => [pct2(value), "context % of window"]} />} />
            <TurnMarks starts={step.starts} />
            <Line dataKey="pct" type="stepAfter" stroke="var(--color-pct)" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ChartContainer>
      </ChartPanel>
    );
  }

  const data = [
    ...result.calls.map((k) => ({ label: `t${k.n}`, pct: k.context_pct, tokens: k.context_tokens })),
    { label: "final", pct: result.final_context_pct, tokens: result.final_context_tokens },
  ];
  return (
    <ChartPanel
      id="ContextWindowChart"
      title="Context window consumption"
      note={
        <span id="ContextWindowNote">
          Each point is the prompt that turn processed as reported by the provider (input + cache read + cache write), as a percentage of the{" "}
          <b>{fmt(window)}</b>-token window; the last point adds the final turn's output. These are measured figures: whatever the server kept or dropped of
          earlier thinking is already inside them. {peakFinal}
        </span>
      }
    >
      <ChartContainer config={CONFIG} className="aspect-auto h-[320px] w-full">
        <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="label" {...axisProps} />
          <YAxis domain={[0, "auto"]} width={56} label={yLabel} {...axisProps} />
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value, _name, item) => [`${pct2(value)} · ${fmt((item?.payload as { tokens?: number })?.tokens)} tokens`, "context % of window"]}
              />
            }
          />
          <Line dataKey="pct" type="linear" stroke="var(--color-pct)" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} isAnimationActive={false} />
        </LineChart>
      </ChartContainer>
    </ChartPanel>
  );
}
