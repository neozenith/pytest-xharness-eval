/**
 * The two stacked per-turn bar charts share one frame: x is the turn label, or each turn's
 * measuring log line with turn starts marked when the axis is per line.
 */
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ChartPanel, TurnMarks } from "@/components/charts/common";
import { axisProps, compact, GRID, numberFormatter, SURFACE } from "@/components/charts/chartStyle";
import { type AxisMode, callStarts } from "@/lib/series";
import type { Call, RunResult } from "@/lib/types";

interface Props {
  id: string;
  title: string;
  yLabel: string;
  config: ChartConfig;
  valueOf: (call: Call, key: string) => number;
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

export function PerTurnBars({ id, title, yLabel, config, valueOf, result, lines, mode }: Props) {
  const starts = useMemo(() => (mode === "line" ? callStarts(result, lines) : []), [mode, result, lines]);
  const data = useMemo(
    () =>
      result.calls.map((k, i) => {
        const row: Record<string, number | string> = { turn: `t${k.n}`, x: mode === "line" ? (starts[i] ?? i + 1) : k.n };
        for (const key of Object.keys(config)) row[key] = valueOf(k, key);
        return row;
      }),
    [result, mode, starts, config, valueOf],
  );
  const perLine = mode === "line";
  return (
    <ChartPanel id={id} title={title}>
      <ChartContainer config={config} className="aspect-auto h-[300px] w-full">
        <BarChart data={data} margin={{ top: perLine ? 20 : 12, right: 16, bottom: 8, left: 8 }} barCategoryGap="25%">
          <CartesianGrid stroke={GRID} vertical={false} />
          {perLine ? (
            <XAxis
              dataKey="x"
              type="number"
              domain={[1, "dataMax"]}
              allowDecimals={false}
              label={{ value: "session-log line", position: "insideBottom", offset: -4, fill: "var(--xh-muted)", fontSize: 11 }}
              {...axisProps}
            />
          ) : (
            <XAxis dataKey="turn" label={{ value: "turn", position: "insideBottom", offset: -4, fill: "var(--xh-muted)", fontSize: 11 }} {...axisProps} />
          )}
          <YAxis
            tickFormatter={compact}
            width={56}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "var(--xh-muted)", fontSize: 11 }}
            {...axisProps}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(_v, payload) => String((payload?.[0]?.payload as { turn?: string })?.turn ?? "")}
                formatter={(value, name) => [numberFormatter(value), config[String(name)]?.label ?? name]}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          {perLine ? <TurnMarks starts={starts} /> : null}
          {Object.keys(config).map((key) => (
            <Bar key={key} dataKey={key} stackId="s" fill={`var(--color-${key})`} stroke={SURFACE} strokeWidth={2} isAnimationActive={false} />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartPanel>
  );
}
