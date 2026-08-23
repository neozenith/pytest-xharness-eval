import { useMemo } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ChartPanel, TurnMarks } from "@/components/charts/common";
import { axisProps, compact, GRID, numberFormatter, SURFACE } from "@/components/charts/chartStyle";
import { type AxisMode, waterfallByLine, waterfallColumns } from "@/lib/series";
import type { RunResult } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

/** The five visible categories of the waterfall, in stacking order, coloured by the `waterfall` design tokens. */
const CATEGORIES: ChartConfig = {
  baseline: { label: "baseline_tokens (harness)", color: "var(--xh-waterfall-baseline)" },
  read: { label: "cache read (re-read context)", color: "var(--xh-waterfall-read)" },
  context: { label: "new context (input + cache write)", color: "var(--xh-waterfall-context)" },
  thinking: { label: "thinking", color: "var(--xh-waterfall-thinking)" },
  output: { label: "visible output", color: "var(--xh-waterfall-output)" },
};
const TURN_CONFIG: ChartConfig = { ...CATEGORIES, total: { label: "accumulative_billed_tokens", color: "var(--xh-waterfall-total)" } };

const NOTE =
  "Starts at baseline_tokens (the harness's own prompt on turn 1); each turn adds the cache it re-read, the new context it ingested, its thinking, and its visible output. The last bar is accumulative_billed_tokens.";

/**
 * Per turn: a waterfall of stacked bars from `baseline_tokens` to `accumulative_billed_tokens`; per
 * session-log line: the same categories as a stacked step area of cumulative tokens, turn starts
 * marked (glossary: `TokenWaterfallChart`).
 */
export function TokenWaterfallChart({ result, lines, mode }: Props) {
  const columns = useMemo(() => waterfallColumns(result), [result]);
  const byLine = useMemo(() => waterfallByLine(result, lines), [result, lines]);

  if (mode === "line") {
    return (
      <ChartPanel id="TokenWaterfallChart" title="Token waterfall" note={NOTE}>
        <ChartContainer config={CATEGORIES} className="aspect-auto h-[440px] w-full">
          <AreaChart data={byLine.rows} margin={{ top: 20, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="line"
              type="number"
              domain={[1, "dataMax"]}
              allowDecimals={false}
              label={{ value: "session-log line", position: "insideBottom", offset: -4, fill: "var(--xh-muted)", fontSize: 11 }}
              {...axisProps}
            />
            <YAxis
              tickFormatter={compact}
              width={56}
              label={{ value: "accumulative_billed_tokens so far", angle: -90, position: "insideLeft", fill: "var(--xh-muted)", fontSize: 11 }}
              {...axisProps}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(v) => `L${v}`}
                  formatter={(value, name) => [numberFormatter(value), CATEGORIES[String(name)]?.label ?? name]}
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            <TurnMarks starts={byLine.starts} />
            {Object.keys(CATEGORIES).map((key) => (
              <Area
                key={key}
                dataKey={key}
                stackId="tokens"
                type="stepAfter"
                stroke={SURFACE}
                strokeWidth={1}
                fill={`var(--color-${key})`}
                fillOpacity={0.9}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ChartContainer>
      </ChartPanel>
    );
  }

  return (
    <ChartPanel id="TokenWaterfallChart" title="Token waterfall" note={NOTE}>
      <ChartContainer config={TURN_CONFIG} className="aspect-auto h-[440px] w-full">
        <BarChart data={columns} margin={{ top: 12, right: 16, bottom: 8, left: 8 }} barCategoryGap="25%">
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="label" {...axisProps} />
          <YAxis
            tickFormatter={compact}
            width={56}
            label={{ value: "tokens", angle: -90, position: "insideLeft", fill: "var(--xh-muted)", fontSize: 11 }}
            {...axisProps}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value, name, item) =>
                  String(name) === "base" || item?.value === 0 ? null : [numberFormatter(value), TURN_CONFIG[String(name)]?.label ?? name]
                }
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          {/* the invisible riser each turn's segments sit on; not in the legend, not in the tooltip */}
          <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} legendType="none" />
          {Object.keys(TURN_CONFIG).map((key) => (
            <Bar key={key} dataKey={key} stackId="w" fill={`var(--color-${key})`} stroke={SURFACE} strokeWidth={2} isAnimationActive={false} />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartPanel>
  );
}
