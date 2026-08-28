/**
 * The two stacked per-turn bar charts share one frame: x is the turn label, or each turn's
 * measuring log line with turn starts marked when the axis is per line.
 */
import { useMemo } from "react";
import type { Data } from "plotly.js";
import { ChartPanel } from "@/components/charts/common";
import { PlotWithLegend, useHiddenSeries, type LegendItem } from "@/components/charts/Plot";
import { axis, baseLayout, turnMarks, useChartTheme } from "@/components/charts/plotly";
import { type AxisMode, callStarts } from "@/lib/series";
import type { Call, RunResult } from "@/lib/types";

interface Props {
  id: string;
  title: string;
  yLabel: string;
  /** Stacking order; colours are resolved design tokens. */
  series: { key: string; label: string; color: string }[];
  valueOf: (call: Call, key: string) => number;
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

export function PerTurnBars({ id, title, yLabel, series, valueOf, result, lines, mode }: Props) {
  const theme = useChartTheme();
  const { hidden, toggle } = useHiddenSeries();
  const perLine = mode === "line";
  const starts = useMemo(() => (perLine ? callStarts(result, lines) : []), [perLine, result, lines]);

  const { traces, layout, legend } = useMemo(() => {
    const legend: LegendItem[] = series.map((s) => ({ key: s.key, label: s.label, color: s.color }));
    const x = perLine ? result.calls.map((_k, i) => starts[i] ?? i + 1) : result.calls.map((k) => `t${k.n}`);
    const turnLabels = result.calls.map((k) => `t${k.n}`);
    const traces: Data[] = series.map((s) => ({
      type: "bar",
      name: s.label,
      x,
      y: result.calls.map((k) => valueOf(k, s.key) || null),
      customdata: turnLabels,
      marker: { color: s.color, line: { color: theme.plot, width: 1 } },
      visible: hidden.has(s.key) ? "legendonly" : true,
      hovertemplate: `%{y:,} · ${s.label} (%{customdata})<extra></extra>`,
    }));
    const layout = baseLayout(theme, {
      barmode: "stack",
      bargap: 0.25,
      xaxis: perLine
        ? { ...axis(theme, { title: "session-log line" }), range: [0, Math.max(...starts, 1) + 1], tickformat: ",d" }
        : axis(theme, { title: "turn" }),
      yaxis: axis(theme, { title: yLabel, compact: true }),
      ...(perLine ? { ...turnMarks(theme, starts), margin: { t: 28, r: 16, b: 44, l: 64 } } : {}),
    });
    return { traces, layout, legend };
  }, [series, perLine, result, starts, theme, hidden, valueOf, yLabel]);

  return (
    <ChartPanel id={id} title={title}>
      <PlotWithLegend data={traces} layout={layout} height={300} ariaLabel={title} items={legend} hidden={hidden} onToggle={toggle} />
    </ChartPanel>
  );
}
